"""
SPEC-TONE-001: 발화 톤/운율 분석 엔진 래퍼 - 싱글톤 패턴
REQ-TONE-001: double-checked locking 싱글톤 (WhisperEngine/DiarizationEngine 패턴 복제)
REQ-TONE-002: tone_min_segment_duration_sec 미만 세그먼트 스킵
REQ-TONE-003: _check_memory_usage() 19.2GB 초과 시 예외 발생 (분석 중단)
REQ-TONE-014: opensmile(AGPL-3.0) 로컬 전용 처리 환경에서만 사용

아키텍처 결정 A2: 싱글톤 보일러플레이트는 WhisperEngine/DiarizationEngine과
중복되지만, 베이스 클래스를 추출하지 않는다. 각 엔진의 독립적인 수명주기와
명확한 의존성 격리가 중복 제거보다 우선한다.
"""

import time
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np
import psutil

from backend.app.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# @MX:ANCHOR: STT/DIA와 동일한 메모리 경고선 (24GB * 80% = 19.2GB)
# @MX:REASON: WhisperEngine._check_memory_usage()와 동일 값. 시스템 전역 임계값.
MEMORY_WARNING_THRESHOLD_BYTES = 19 * 1024 * 1024 * 1024

# 5-class tone 분류 체계. SentimentSegment.emotion(10 labels)과 독립적 차원 (REQ-TONE-009).
# @MX:NOTE: SPEC §3 기술 제약 — 초기 confidence 임계값 미달 시 "unknown" 라벨 반환
CONFIDENCE_THRESHOLD = 0.4

# pyin 기본 hop length (librosa 기본값, F0 프레임 간격)
_DEFAULT_HOP_LENGTH = 512


class ToneEngine:
    """
    opensmile(eGeMAPSv02) + librosa(F0/RMS/speaking rate) 기반 톤 분석 싱글톤 엔진.
    - 프로세스당 1개 인스턴스 (double-checked locking)
    - 스레드 안전 초기화
    - CPU only 처리 (opensmile/librosa는 MPS 미사용)

    WhisperEngine._check_memory_usage()는 경고 로그만 남기지만,
    ToneEngine은 SPEC REQ-TONE-003에 따라 예외를 발생시켜 분석을 중단한다.
    STT/DIA 파이프라인에 메모리 부족 영향을 주어서는 안 된다.
    """

    _instance: "ToneEngine | None" = None
    _lock: Lock = Lock()

    _initialized: bool = False
    _smile: Any = None
    _load_time_seconds: float | None = None

    def __init__(self) -> None:
        pass

    @classmethod
    def get_instance(cls) -> "ToneEngine":
        """싱글톤 인스턴스 반환 (스레드 안전, double-checked locking)"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _initialize(self) -> None:
        """opensmile Smile 객체 lazy load (eGeMAPSv02 88차원 feature set)"""
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            logger.info("ToneEngine 초기화 시작 (opensmile eGeMAPSv02)")
            start_time = time.time()

            try:
                import opensmile

                self._smile = opensmile.Smile(
                    feature_set=opensmile.FeatureSet.eGeMAPSv02,
                    feature_level=opensmile.FeatureLevel.Functionals,
                )
                self._load_time_seconds = time.time() - start_time
                self._initialized = True
                logger.info(
                    "ToneEngine 초기화 완료",
                    load_time_seconds=round(self._load_time_seconds, 2),
                )
            except ImportError as e:
                logger.error("opensmile 미설치", error=str(e))
                raise RuntimeError(
                    "opensmile 패키지가 설치되지 않았습니다. "
                    "'pip install opensmile>=2.6.0'으로 설치하세요."
                ) from e

    def analyze_segments(
        self,
        wav_path: str | Path,
        segments: list[dict],
    ) -> list[dict]:
        """
        세그먼트별 톤/운율 분석 실행 (REQ-TONE-001, REQ-TONE-002)

        Args:
            wav_path: 16kHz 모노 WAV 파일 경로 (DIA 전처리 산출물)
            segments: SpeakerSegment 리스트 [{start, end, speaker}, ...]

        Returns:
            분석 결과 리스트. 각 원소는:
            {start, end, speaker, tone, confidence, prosody_features}
            tone이 "skipped"인 세그먼트는 prosody_features가 빈 딕셔너리다.
        """
        if not segments:
            return []

        self._initialize()
        self._check_memory_usage()

        import librosa

        logger.info("톤 분석 시작", path=str(wav_path), segments=len(segments))
        start_time = time.time()

        # 전체 오디오 1회 로드 (16kHz 모노 강제 — DIA wav는 이미 16kHz 모노지만 안전망)
        y_full, sr = librosa.load(str(wav_path), sr=16000, mono=True)

        results: list[dict] = []
        for seg in segments:
            start = float(seg.get("start", 0.0))
            end = float(seg.get("end", 0.0))
            speaker = str(seg.get("speaker", "UNKNOWN"))

            duration = end - start

            # REQ-TONE-002: 0.5초 미만 세그먼트는 F0/RMS 추출 불안정으로 스킵
            if duration < settings.tone_min_segment_duration_sec:
                results.append(
                    {
                        "start": start,
                        "end": end,
                        "speaker": speaker,
                        "tone": "skipped",
                        "confidence": 0.0,
                        "prosody_features": {},
                    }
                )
                continue

            start_sample = int(start * sr)
            end_sample = int(end * sr)
            y_seg = y_full[start_sample:end_sample]

            prosody = self._extract_prosody(y_seg, int(sr))
            tone, confidence = self._classify_tone(prosody, duration)

            results.append(
                {
                    "start": start,
                    "end": end,
                    "speaker": speaker,
                    "tone": tone,
                    "confidence": confidence,
                    "prosody_features": prosody,
                }
            )

        elapsed = time.time() - start_time
        logger.info(
            "톤 분석 완료",
            path=str(wav_path),
            segments=len(results),
            elapsed_seconds=round(elapsed, 2),
        )

        return results

    def _extract_prosody(self, y: np.ndarray, sr: int) -> dict[str, float]:
        """단일 세그먼트에서 prosody 특징 추출 (opensmile + librosa)

        Returns:
            {f0_mean, f0_std, rms_energy, speaking_rate, ...opensmile subset}
        """
        import librosa

        # F0 추출 (pYIN: 입력 세그먼트에 대해 frame-level F0)
        f0, voiced_flag, _ = librosa.pyin(
            y,
            fmin=80,
            fmax=400,
            sr=sr,
            hop_length=_DEFAULT_HOP_LENGTH,
        )

        voiced_f0 = f0[~np.isnan(f0)] if f0 is not None else np.array([])
        f0_mean = float(np.mean(voiced_f0)) if len(voiced_f0) > 0 else 0.0
        f0_std = float(np.std(voiced_f0)) if len(voiced_f0) > 0 else 0.0

        # RMS energy
        rms = librosa.feature.rms(y=y, hop_length=_DEFAULT_HOP_LENGTH)
        rms_energy = float(np.mean(rms)) if rms.size > 0 else 0.0

        # speaking rate: voiced frames per second (음성 밀도 프록시)
        duration = len(y) / sr if sr > 0 else 0.0
        n_voiced = int(np.sum(voiced_flag)) if voiced_flag is not None else 0
        speaking_rate = n_voiced / duration if duration > 0 else 0.0

        # opensmile eGeMAPSv02 특징 (88차원) — prosody 보조 지표
        opensmile_features: dict[str, float] = {}
        if self._smile is not None:
            try:
                smile_result = self._smile.process_signal(y, sr)
                for col in smile_result.columns:
                    opensmile_features[col] = float(smile_result[col].iloc[0])
            except Exception as e:
                logger.warning("opensmile 특징 추출 실패, librosa 특징만 사용", error=str(e))

        return {
            "f0_mean": f0_mean,
            "f0_std": f0_std,
            "rms_energy": rms_energy,
            "speaking_rate": speaking_rate,
            **opensmile_features,
        }

    def _classify_tone(self, prosody: dict[str, float], duration: float) -> tuple[str, float]:
        """규칙 기반 톤 분류 (5-class + unknown)

        회의 맥락의 prosody 패턴을 기반으로 한 휴리스틱 분류.
        SPEC §3 기술 제약: 초기 confidence 임계값 미달 시 "unknown" 반환.

        분류 규칙 (WHY: 음성학적 근거):
        - monotone: F0 변화량 매우 낮음 (평탄한 피치 — 무감정 낭독)
        - excited: F0 변화량 높음 + 에너지 높음 (감정적 몰입)
        - authoritative: 에너지 높음 + 피치 안정 (자신감 있는 단언)
        - hesitant: 에너지 낮음 + 발화 밀도 낮음 (불확실, 조용한 발화)
        - calm: 전반적 중간 수준 (차분한 전달)
        - unknown: 어느 클래스에도 명확히 매칭되지 않음
        """
        f0_std = prosody.get("f0_std", 0.0)
        rms_energy = prosody.get("rms_energy", 0.0)
        speaking_rate = prosody.get("speaking_rate", 0.0)

        # 각 클래스별 매칭 강도 (0.0~1.0)
        scores: dict[str, float] = {}

        # monotone: f0_std 낮을수록 강함 (10Hz 이하 → 1.0, 30Hz 이상 → 0.0)
        scores["monotone"] = max(0.0, 1.0 - f0_std / 30.0)

        # excited: f0_std 높음 + rms 높음의 결합
        f0_dynamic = min(1.0, max(0.0, (f0_std - 20.0) / 40.0))
        rms_high = min(1.0, rms_energy / 0.15)
        scores["excited"] = (f0_dynamic + rms_high) / 2

        # authoritative: rms 높음 + f0_std 중간이하 (안정적)
        rms_authority = min(1.0, max(0.0, (rms_energy - 0.04) / 0.12))
        pitch_stability = max(0.0, 1.0 - f0_std / 35.0)
        scores["authoritative"] = (rms_authority + pitch_stability) / 2

        # hesitant: rms 낮음 + speaking_rate 낮음
        rms_quiet = max(0.0, 1.0 - rms_energy / 0.05)
        rate_slow = max(0.0, 1.0 - speaking_rate / 100.0)
        scores["hesitant"] = (rms_quiet + rate_slow) / 2

        # calm: 중간 대역 (극단이 아닌 균형)
        f0_mid = 1.0 - abs(f0_std - 15.0) / 30.0
        rms_mid = 1.0 - abs(rms_energy - 0.05) / 0.10
        scores["calm"] = max(0.0, (f0_mid + rms_mid) / 2)

        best_tone = max(scores, key=lambda k: scores[k])
        best_score = scores[best_tone]

        confidence = round(best_score, 4)

        if confidence < CONFIDENCE_THRESHOLD:
            return "unknown", confidence

        return best_tone, confidence

    def _check_memory_usage(self) -> None:
        """메모리 임계값 초과 시 예외 발생 (REQ-TONE-003)

        WhisperEngine._check_memory_usage()는 경고 로그만 남기지만,
        ToneEngine은 예외를 발생시켜 분석을 중단한다. tone 분석은 STT/DIA에 비해
        우선순위가 낮으므로, 메모리 부족 시 tone만 포기하고 핵심 파이프라인을 보호한다.
        """
        vm = psutil.virtual_memory()
        if vm.used > MEMORY_WARNING_THRESHOLD_BYTES:
            logger.error(
                "메모리 사용량 임계값 초과: 톤 분석 중단",
                used_gb=round(vm.used / (1024**3), 2),
                threshold_gb=round(MEMORY_WARNING_THRESHOLD_BYTES / (1024**3), 2),
                percent=vm.percent,
            )
            raise MemoryError(
                f"시스템 메모리 사용량({vm.used / (1024**3):.1f}GB)이 "
                f"경고선({MEMORY_WARNING_THRESHOLD_BYTES / (1024**3):.1f}GB)을 초과했습니다. "
                "톤 분석을 중단합니다."
            )

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def load_time_seconds(self) -> float | None:
        return self._load_time_seconds

    def get_memory_info(self) -> dict[str, float]:
        """현재 메모리 사용량 반환 (WhisperEngine 패턴 준수)"""
        vm = psutil.virtual_memory()
        return {
            "total_mb": vm.total / (1024 * 1024),
            "available_mb": vm.available / (1024 * 1024),
            "used_mb": vm.used / (1024 * 1024),
            "percent": vm.percent,
        }
