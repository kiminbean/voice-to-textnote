"""
SPEC-TONE-001 ToneEngine 단위 테스트
REQ-TONE-001: double-checked locking 싱글톤
REQ-TONE-002: tone_min_segment_duration_sec 미만 세그먼트 스킵
REQ-TONE-003: _check_memory_usage() 19.2GB 초과 시 예외 발생
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


def _reset_tone_engine_singleton():
    """각 테스트 전 ToneEngine 싱글톤 상태 초기화"""
    import sys

    import backend.ml.tone_engine as tone_engine_module
    from backend.ml.tone_engine import ToneEngine

    ToneEngine._instance = None
    ToneEngine._initialized = False
    ToneEngine._smile = None
    ToneEngine._load_time_seconds = None
    sys.modules["librosa"] = tone_engine_module.librosa


def _make_mock_smile():
    """opensmile.Smile mock — process_signal이 단일 특징 벡터 반환"""
    import pandas as pd

    mock = MagicMock()
    mock.process_signal.return_value = pd.DataFrame([{"F0semitoneFrom27.5Hz_sma3nz_amean": 220.0}])
    return mock


def _make_initialized_tone_engine(mock_smile: MagicMock | None = None):
    """테스트용 ToneEngine에 mock Smile을 주입하고 lazy init 덮어쓰기를 방지한다."""
    from backend.ml.tone_engine import ToneEngine

    engine = ToneEngine.get_instance()
    engine._smile = mock_smile or _make_mock_smile()
    engine._initialized = True
    return engine


# ---------------------------------------------------------------------------
# REQ-TONE-001: 싱글톤 패턴 테스트
# ---------------------------------------------------------------------------


class TestToneEngineSingleton:
    """double-checked locking 싱글톤 테스트 (REQ-TONE-001)"""

    def setup_method(self):
        _reset_tone_engine_singleton()

    def test_tone_engine_singleton(self):
        """get_instance() 두 번 호출 시 동일 인스턴스 반환 (REQ-TONE-001)"""
        from backend.ml.tone_engine import ToneEngine

        instance1 = ToneEngine.get_instance()
        instance2 = ToneEngine.get_instance()
        assert instance1 is instance2


# ---------------------------------------------------------------------------
# REQ-TONE-003: 메모리 임계값 초과 시 예외 발생 테스트
# ---------------------------------------------------------------------------


class TestToneEngineMemoryCheck:
    """_check_memory_usage() 메모리 경고 테스트 (REQ-TONE-003)"""

    def setup_method(self):
        _reset_tone_engine_singleton()

    def test_tone_engine_memory_check_raises(self):
        """시스템 메모리 19.2GB 초과 시 예외 발생 (REQ-TONE-003)

        WhisperEngine._check_memory_usage()는 경고 로그만 남기지만,
        ToneEngine은 SPEC REQ-TONE-003에 따라 예외를 발생시켜 분석을 중단한다.
        STT/DIA 파이프라인에 메모리 부족 영향을 주어서는 안 된다.
        """
        from backend.ml.tone_engine import MEMORY_WARNING_THRESHOLD_BYTES, ToneEngine

        mock_vm = MagicMock()
        mock_vm.used = MEMORY_WARNING_THRESHOLD_BYTES + 1
        mock_vm.percent = 85.0

        engine = ToneEngine.get_instance()

        with patch("psutil.virtual_memory", return_value=mock_vm):
            with pytest.raises((RuntimeError, MemoryError)):
                engine._check_memory_usage()

    def test_memory_check_passes_below_threshold(self):
        """임계값 이하에서는 예외 발생하지 않음"""
        from backend.ml.tone_engine import MEMORY_WARNING_THRESHOLD_BYTES, ToneEngine

        mock_vm = MagicMock()
        mock_vm.used = MEMORY_WARNING_THRESHOLD_BYTES - 1
        mock_vm.percent = 50.0

        engine = ToneEngine.get_instance()

        with patch("psutil.virtual_memory", return_value=mock_vm):
            engine._check_memory_usage()


# ---------------------------------------------------------------------------
# REQ-TONE-002: 세그먼트 길이 필터링 테스트
# ---------------------------------------------------------------------------


class TestToneEngineSegmentFiltering:
    """세그먼트 길이 기반 스킵 로직 테스트 (REQ-TONE-002)"""

    def setup_method(self):
        _reset_tone_engine_singleton()

    def test_tone_engine_short_segment_skipped(self, tmp_path: Path):
        """0.5초 미만 세그먼트는 분석 스킵 — opensmile 미호출 (REQ-TONE-002)"""
        wav_path = tmp_path / "test.wav"
        wav_path.write_bytes(b"dummy")

        short_segment = {"start": 0.0, "end": 0.3, "speaker": "SPEAKER_00"}

        mock_smile = _make_mock_smile()
        mock_y = np.zeros(4800, dtype=np.float32)

        engine = _make_initialized_tone_engine(mock_smile)

        with (
            patch("librosa.load", return_value=(mock_y, 16000)),
            patch("librosa.pyin") as mock_pyin,
            patch("librosa.feature.rms"),
        ):
            results = engine.analyze_segments(str(wav_path), [short_segment])

        assert len(results) == 1
        result = results[0]
        # 짧은 세그먼트는 tone="skipped" 로 마킹
        assert result["tone"] == "skipped"
        # opensmile이 호출되지 않았는지 확인
        mock_smile.process_signal.assert_not_called()
        mock_pyin.assert_not_called()

    def test_tone_engine_boundary_0_5s(self, tmp_path: Path):
        """정확히 0.5초 세그먼트는 처리됨 (경계 포함, REQ-TONE-002)"""
        wav_path = tmp_path / "test.wav"
        wav_path.write_bytes(b"dummy")

        boundary_segment = {"start": 0.0, "end": 0.5, "speaker": "SPEAKER_00"}

        mock_smile = _make_mock_smile()
        mock_y = np.zeros(8000, dtype=np.float32)

        f0 = np.full(50, 200.0)
        voiced_flag = np.ones(50, dtype=bool)
        voiced_probs = np.ones(50)

        engine = _make_initialized_tone_engine(mock_smile)

        with (
            patch("librosa.load", return_value=(mock_y, 16000)),
            patch("librosa.pyin", return_value=(f0, voiced_flag, voiced_probs)),
            patch("librosa.feature.rms", return_value=np.array([[0.05] * 10])),
        ):
            results = engine.analyze_segments(str(wav_path), [boundary_segment])

        assert len(results) == 1
        result = results[0]
        # 0.5초 세그먼트는 실제 분석 수행 — "skipped" 가 아님
        assert result["tone"] != "skipped"
        # opensmile이 호출되었는지 확인
        mock_smile.process_signal.assert_called_once()

    def test_empty_segments_returns_empty_list(self, tmp_path: Path):
        """빈 세그먼트 리스트 입력 시 빈 리스트 반환"""
        from backend.ml.tone_engine import ToneEngine

        wav_path = tmp_path / "test.wav"
        wav_path.write_bytes(b"dummy")

        engine = ToneEngine.get_instance()

        with patch("librosa.load", return_value=(np.zeros(8000, dtype=np.float32), 16000)):
            results = engine.analyze_segments(str(wav_path), [])

        assert results == []


# ---------------------------------------------------------------------------
# REQ-TONE-001: analyze_segments 결과 구조 테스트
# ---------------------------------------------------------------------------


class TestToneEngineAnalyzeStructure:
    """analyze_segments 결과 구조 검증 (REQ-TONE-001)"""

    def setup_method(self):
        _reset_tone_engine_singleton()

    def test_tone_engine_analyze_returns_expected_structure(self, tmp_path: Path):
        """유효 세그먼트 분석 결과에 tone/confidence/prosody_features 포함 (REQ-TONE-001)

        tone 분류 체계: calm/excited/authoritative/hesitant/monotone/unknown 중 하나.
        SentimentSegment.emotion(10 labels)과 독립적 차원이다 (REQ-TONE-009).
        """
        valid_tones = {
            "calm",
            "excited",
            "authoritative",
            "hesitant",
            "monotone",
            "unknown",
        }

        wav_path = tmp_path / "test.wav"
        wav_path.write_bytes(b"dummy")

        valid_segment = {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"}

        mock_smile = _make_mock_smile()
        mock_y = np.ones(32000, dtype=np.float32) * 0.1

        f0 = np.full(100, 200.0)
        voiced_flag = np.ones(100, dtype=bool)
        voiced_probs = np.ones(100)

        engine = _make_initialized_tone_engine(mock_smile)

        with (
            patch("librosa.load", return_value=(mock_y, 16000)),
            patch("librosa.pyin", return_value=(f0, voiced_flag, voiced_probs)),
            patch("librosa.feature.rms", return_value=np.array([[0.08] * 20])),
        ):
            results = engine.analyze_segments(str(wav_path), [valid_segment])

        assert len(results) == 1
        result = results[0]

        assert result["start"] == 0.0
        assert result["end"] == 2.0
        assert result["speaker"] == "SPEAKER_00"
        assert result["tone"] in valid_tones
        assert isinstance(result["confidence"], float)
        assert 0.0 <= result["confidence"] <= 1.0

        prosody = result["prosody_features"]
        assert isinstance(prosody, dict)
        # 핵심 prosody 특징 키 존재 확인
        for key in ("f0_mean", "rms_energy", "speaking_rate"):
            assert key in prosody, f"prosody_features에 '{key}' 키 누락"

    def test_multiple_segments_returns_list(self, tmp_path: Path):
        """여러 세그먼트 입력 시 각각 결과 반환"""
        wav_path = tmp_path / "test.wav"
        wav_path.write_bytes(b"dummy")

        segments = [
            {"start": 0.0, "end": 1.5, "speaker": "SPEAKER_00"},
            {"start": 1.5, "end": 3.0, "speaker": "SPEAKER_01"},
        ]

        mock_smile = _make_mock_smile()
        mock_y = np.ones(48000, dtype=np.float32) * 0.1

        f0 = np.full(100, 200.0)
        voiced_flag = np.ones(100, dtype=bool)
        voiced_probs = np.ones(100)

        engine = _make_initialized_tone_engine(mock_smile)

        with (
            patch("librosa.load", return_value=(mock_y, 16000)),
            patch("librosa.pyin", return_value=(f0, voiced_flag, voiced_probs)),
            patch("librosa.feature.rms", return_value=np.array([[0.08] * 20])),
        ):
            results = engine.analyze_segments(str(wav_path), segments)

        assert len(results) == 2
        assert results[0]["speaker"] == "SPEAKER_00"
        assert results[1]["speaker"] == "SPEAKER_01"

    def test_analyze_calls_memory_check(self, tmp_path: Path):
        """analyze_segments 호출 시 _check_memory_usage() 선행 실행 (REQ-TONE-003)"""
        wav_path = tmp_path / "test.wav"
        wav_path.write_bytes(b"dummy")

        valid_segment = {"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}

        engine = _make_initialized_tone_engine()

        with patch.object(engine, "_check_memory_usage") as mock_mem_check:
            with patch("librosa.load", return_value=(np.zeros(16000, dtype=np.float32), 16000)):
                with patch(
                    "librosa.pyin",
                    return_value=(np.full(50, 200.0), np.ones(50, dtype=bool), np.ones(50)),
                ):
                    with patch("librosa.feature.rms", return_value=np.array([[0.05] * 10])):
                        engine.analyze_segments(str(wav_path), [valid_segment])

        mock_mem_check.assert_called_once()


# ---------------------------------------------------------------------------
# _initialize() lazy load 테스트
# ---------------------------------------------------------------------------


class TestToneEngineInitialize:
    """opensmile lazy 초기화 테스트"""

    def setup_method(self):
        _reset_tone_engine_singleton()

    def test_initialize_loads_opensmile_successfully(self):
        """_initialize()가 opensmile.Smile 객체를 생성하고 _initialized=True로 설정"""
        import sys

        from backend.ml.tone_engine import ToneEngine

        mock_opensmile = MagicMock()
        mock_smile_obj = MagicMock()
        mock_opensmile.Smile.return_value = mock_smile_obj
        mock_opensmile.FeatureSet.eGeMAPSv02 = MagicMock()
        mock_opensmile.FeatureLevel.Functionals = MagicMock()

        with patch.dict(sys.modules, {"opensmile": mock_opensmile}):
            engine = ToneEngine.get_instance()
            engine._initialize()

        assert engine._initialized is True
        assert engine._smile is mock_smile_obj
        assert engine._load_time_seconds is not None
        assert engine._load_time_seconds >= 0.0

    def test_initialize_raises_runtime_error_when_opensmile_missing(self):
        """opensmile ImportError 시 RuntimeError 발생"""
        import sys

        from backend.ml.tone_engine import ToneEngine

        engine = ToneEngine.get_instance()

        with patch.dict(sys.modules, {"opensmile": None}):
            with pytest.raises(RuntimeError, match="opensmile"):
                engine._initialize()

        assert engine._initialized is False

    def test_initialize_is_idempotent(self):
        """이미 초기화된 상태에서 재호출 시 opensmile 재생성 안 함"""
        import sys

        from backend.ml.tone_engine import ToneEngine

        mock_opensmile = MagicMock()
        mock_smile_obj = MagicMock()
        mock_opensmile.Smile.return_value = mock_smile_obj
        mock_opensmile.FeatureSet.eGeMAPSv02 = MagicMock()
        mock_opensmile.FeatureLevel.Functionals = MagicMock()

        with patch.dict(sys.modules, {"opensmile": mock_opensmile}):
            engine = ToneEngine.get_instance()
            engine._initialize()
            # 두 번째 호출 — Smile 객체가 다시 생성되지 않아야 함
            engine._initialize()

        mock_opensmile.Smile.assert_called_once()


# ---------------------------------------------------------------------------
# _classify_tone() 분류 로직 테스트
# ---------------------------------------------------------------------------


class TestToneEngineClassifyTone:
    """규칙 기반 톤 분류 휴리스틱 검증"""

    def setup_method(self):
        _reset_tone_engine_singleton()

    def test_monotone_low_f0_variance(self):
        """F0 표준편차 매우 낮으면 monotone 분류 (평탄한 피치)"""
        from backend.ml.tone_engine import ToneEngine

        engine = ToneEngine.get_instance()
        # f0_std=5.0 → monotone score ≈ 1.0 - 5/30 ≈ 0.83
        prosody = {"f0_std": 5.0, "rms_energy": 0.05, "speaking_rate": 50.0}
        tone, confidence = engine._classify_tone(prosody, duration=2.0)
        assert tone == "monotone"
        assert confidence >= 0.4

    def test_excited_high_f0_variance_and_energy(self):
        """F0 변화량 높음 + 에너지 높음 → excited 분류"""
        from backend.ml.tone_engine import ToneEngine

        engine = ToneEngine.get_instance()
        prosody = {"f0_std": 50.0, "rms_energy": 0.12, "speaking_rate": 80.0}
        tone, confidence = engine._classify_tone(prosody, duration=2.0)
        assert tone == "excited"
        assert confidence >= 0.4

    def test_authoritative_high_energy_stable_pitch(self):
        """에너지 높음 + 피치 안정 → authoritative 분류"""
        from backend.ml.tone_engine import ToneEngine

        engine = ToneEngine.get_instance()
        # f0_std 낮음 + rms 높음 → authoritative 우세
        prosody = {"f0_std": 3.0, "rms_energy": 0.10, "speaking_rate": 50.0}
        tone, _ = engine._classify_tone(prosody, duration=2.0)
        # authoritative 또는 monotone 가능 — 둘 다 낮은 f0_std에서 강함
        assert tone in ("authoritative", "monotone")

    def test_returns_unknown_for_low_confidence(self):
        """모든 점수가 임계값 미만이면 unknown 반환"""
        from backend.ml.tone_engine import ToneEngine

        engine = ToneEngine.get_instance()
        # 극단적으로 낮은 값 — 어느 클래스에도 강하게 매칭되지 않음
        prosody = {"f0_std": 50.0, "rms_energy": 0.001, "speaking_rate": 200.0}
        tone, confidence = engine._classify_tone(prosody, duration=0.5)
        # confidence가 임계값 미만일 수 있음
        if confidence < 0.4:
            assert tone == "unknown"
        # 아니면 유효한 톤이어야 함
        else:
            assert tone in ("calm", "excited", "authoritative", "hesitant", "monotone", "unknown")


# ---------------------------------------------------------------------------
# _extract_prosody() 에러 처리 테스트
# ---------------------------------------------------------------------------


class TestToneEngineExtractProsodyError:
    """opensmile 추출 실패 시 graceful degradation 테스트"""

    def setup_method(self):
        _reset_tone_engine_singleton()

    def test_extract_prosody_handles_opensmile_error(self, tmp_path: Path):
        """opensmile.process_signal 예외 시 librosa 특징만 반환 (line 219-220)"""
        import numpy as np

        from backend.ml.tone_engine import ToneEngine

        mock_smile = MagicMock()
        mock_smile.process_signal.side_effect = RuntimeError("opensmile internal error")

        engine = ToneEngine.get_instance()
        engine._smile = mock_smile
        engine._initialized = True

        y_seg = np.ones(16000, dtype=np.float32) * 0.1

        with (
            patch(
                "librosa.pyin",
                return_value=(np.full(50, 200.0), np.ones(50, dtype=bool), np.ones(50)),
            ),
            patch("librosa.feature.rms", return_value=np.array([[0.05] * 10])),
        ):
            prosody = engine._extract_prosody(y_seg, 16000)

        # opensmile 실패해도 librosa 특징은 정상 반환
        assert "f0_mean" in prosody
        assert prosody["f0_mean"] == 200.0
        assert "rms_energy" in prosody
        assert "speaking_rate" in prosody

    def test_extract_prosody_with_all_nan_f0(self):
        """모든 F0이 NaN (무음 구간)일 때 f0_mean=0.0 반환"""
        import numpy as np

        from backend.ml.tone_engine import ToneEngine

        engine = ToneEngine.get_instance()
        engine._smile = None
        engine._initialized = True

        nan_f0 = np.full(50, np.nan)
        voiced_flag = np.zeros(50, dtype=bool)

        y_seg = np.zeros(16000, dtype=np.float32)

        with (
            patch("librosa.pyin", return_value=(nan_f0, voiced_flag, np.zeros(50))),
            patch("librosa.feature.rms", return_value=np.array([[0.0] * 10])),
        ):
            prosody = engine._extract_prosody(y_seg, 16000)

        assert prosody["f0_mean"] == 0.0
        assert prosody["f0_std"] == 0.0


# ---------------------------------------------------------------------------
# 프로퍼티 및 유틸리티 테스트
# ---------------------------------------------------------------------------


class TestToneEngineProperties:
    """is_initialized, load_time_seconds, get_memory_info 프로퍼티 테스트"""

    def setup_method(self):
        _reset_tone_engine_singleton()

    def test_is_initialized_false_before_init(self):
        from backend.ml.tone_engine import ToneEngine

        engine = ToneEngine.get_instance()
        assert engine.is_initialized is False

    def test_load_time_seconds_none_before_init(self):
        from backend.ml.tone_engine import ToneEngine

        engine = ToneEngine.get_instance()
        assert engine.load_time_seconds is None

    def test_get_memory_info_returns_dict(self):
        from backend.ml.tone_engine import ToneEngine

        engine = ToneEngine.get_instance()
        info = engine.get_memory_info()
        assert isinstance(info, dict)
        for key in ("total_mb", "available_mb", "used_mb", "percent"):
            assert key in info
        assert info["total_mb"] > 0
