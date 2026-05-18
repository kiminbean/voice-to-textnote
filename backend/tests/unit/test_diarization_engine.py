"""
DiarizationEngine 단위 테스트 (RED phase)
REQ-DIA-007~012: pyannote.audio Pipeline 싱글톤 엔진
"""

import sys
from pathlib import Path
from threading import Thread
from unittest.mock import MagicMock, patch

import pytest
import torch

# ---------------------------------------------------------------------------
# 테스트 헬퍼 - pyannote Pipeline mock 생성
# ---------------------------------------------------------------------------


def _make_mock_pipeline():
    """pyannote.audio Pipeline mock 생성"""
    mock_pipeline = MagicMock()

    # diarization 결과 mock - itertracks() 형태
    mock_turn1 = MagicMock()
    mock_turn1.start = 0.0
    mock_turn1.end = 5.0
    mock_turn2 = MagicMock()
    mock_turn2.start = 6.0
    mock_turn2.end = 10.0

    mock_diarization = MagicMock(spec=[])
    mock_diarization.itertracks = MagicMock(return_value=[
        (mock_turn1, None, "SPEAKER_00"),
        (mock_turn2, None, "SPEAKER_01"),
    ])

    # pyannote 4.x: DiarizeOutput.speaker_diarization → Annotation
    # spec=[]로 생성하여 speaker_diarization이 없으면 getattr fallback 동작
    mock_pipeline.return_value = mock_diarization
    return mock_pipeline


def _reset_engine():
    """DiarizationEngine 싱글톤 리셋"""
    from backend.ml.diarization_engine import DiarizationEngine

    DiarizationEngine._instance = None
    DiarizationEngine._model_loaded = False
    DiarizationEngine._load_time_seconds = None
    DiarizationEngine._pipeline = None


# ---------------------------------------------------------------------------
# 싱글톤 패턴 테스트
# ---------------------------------------------------------------------------


class TestDiarizationEngineSingleton:
    """싱글톤 패턴 테스트 (REQ-DIA-007: 프로세스당 1개)"""

    def setup_method(self):
        """각 테스트 전 싱글톤 리셋"""
        _reset_engine()

    def test_get_instance_returns_same_object(self):
        """get_instance()는 동일한 인스턴스 반환"""
        from backend.ml.diarization_engine import DiarizationEngine

        instance1 = DiarizationEngine.get_instance()
        instance2 = DiarizationEngine.get_instance()
        assert instance1 is instance2

    def test_get_instance_called_multiple_times_same(self):
        """여러 번 호출해도 동일 인스턴스"""
        from backend.ml.diarization_engine import DiarizationEngine

        instances = [DiarizationEngine.get_instance() for _ in range(5)]
        assert all(i is instances[0] for i in instances)

    def test_is_loaded_false_initially(self):
        """초기 상태에서 is_loaded == False"""
        from backend.ml.diarization_engine import DiarizationEngine

        engine = DiarizationEngine.get_instance()
        assert engine.is_loaded is False

    def test_thread_safety(self):
        """멀티스레드에서 동일 인스턴스 반환 (thread safety)"""
        from backend.ml.diarization_engine import DiarizationEngine

        instances = []

        def get_inst():
            instances.append(DiarizationEngine.get_instance())

        threads = [Thread(target=get_inst) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(i is instances[0] for i in instances)


# ---------------------------------------------------------------------------
# load() 메서드 테스트
# ---------------------------------------------------------------------------


class TestDiarizationEngineLoad:
    """모델 로딩 테스트 (REQ-DIA-008: 지연 로딩)"""

    def setup_method(self):
        _reset_engine()

    def _patch_pyannote(self):
        """pyannote.audio를 sys.modules에 mock 주입 (함수 내부 import 대응)"""
        mock_pipeline_cls = MagicMock()
        mock_pyannote_audio = MagicMock()
        mock_pyannote_audio.Pipeline = mock_pipeline_cls

        return patch.dict(
            sys.modules,
            {
                "pyannote": MagicMock(),
                "pyannote.audio": mock_pyannote_audio,
            },
        ), mock_pipeline_cls

    def test_load_sets_model_loaded_true(self):
        """load() 후 is_loaded == True"""
        from backend.ml.diarization_engine import DiarizationEngine

        ctx, mock_pipeline_cls = self._patch_pyannote()
        with ctx:
            mock_pipeline_cls.from_pretrained.return_value = _make_mock_pipeline()
            engine = DiarizationEngine.get_instance()
            engine.load(hf_token="hf_testtoken")
            assert engine.is_loaded is True

    def test_load_records_load_time(self):
        """load() 후 load_time_seconds 기록"""
        from backend.ml.diarization_engine import DiarizationEngine

        ctx, mock_pipeline_cls = self._patch_pyannote()
        with ctx:
            mock_pipeline_cls.from_pretrained.return_value = _make_mock_pipeline()
            engine = DiarizationEngine.get_instance()
            engine.load(hf_token="hf_testtoken")
            assert engine.load_time_seconds is not None
            assert engine.load_time_seconds >= 0

    def test_load_called_twice_is_idempotent(self):
        """load() 두 번 호출해도 에러 없음 (재사용)"""
        from backend.ml.diarization_engine import DiarizationEngine

        ctx, mock_pipeline_cls = self._patch_pyannote()
        with ctx:
            mock_pipeline_cls.from_pretrained.return_value = _make_mock_pipeline()
            engine = DiarizationEngine.get_instance()
            engine.load(hf_token="hf_testtoken")
            assert engine.is_loaded is True
            # 두 번째 호출 시 from_pretrained 다시 호출 안 됨
            engine.load(hf_token="hf_testtoken")
            assert engine.is_loaded is True
            assert mock_pipeline_cls.from_pretrained.call_count == 1

    def test_load_without_token_raises_error(self):
        """HuggingFace 토큰 없이 load() 시 에러"""
        from backend.ml.diarization_engine import DiarizationEngine

        engine = DiarizationEngine.get_instance()
        with pytest.raises((ValueError, RuntimeError)):
            engine.load(hf_token="")

    def test_load_with_invalid_token_raises_error(self):
        """잘못된 토큰으로 load() 시 RuntimeError"""
        from backend.ml.diarization_engine import DiarizationEngine

        ctx, mock_pipeline_cls = self._patch_pyannote()
        with ctx:
            mock_pipeline_cls.from_pretrained.side_effect = Exception("401 Unauthorized")
            engine = DiarizationEngine.get_instance()
            with pytest.raises((RuntimeError, Exception)):
                engine.load(hf_token="invalid_token")

    def test_load_sends_token_to_pipeline(self):
        """load() 시 HuggingFace 토큰이 Pipeline.from_pretrained에 전달됨"""
        from backend.ml.diarization_engine import DiarizationEngine

        ctx, mock_pipeline_cls = self._patch_pyannote()
        with ctx:
            mock_pipeline_cls.from_pretrained.return_value = _make_mock_pipeline()
            engine = DiarizationEngine.get_instance()
            engine.load(hf_token="hf_mytoken123")

            call_kwargs = mock_pipeline_cls.from_pretrained.call_args
            assert call_kwargs is not None
            # 토큰이 전달되었는지 확인
            all_args = str(call_kwargs)
            assert "hf_mytoken123" in all_args


# ---------------------------------------------------------------------------
# diarize() 메서드 테스트
# ---------------------------------------------------------------------------


class TestDiarizationEngineDiarize:
    """화자 분리 기능 테스트 (REQ-DIA-009)"""

    def setup_method(self):
        _reset_engine()

    def _patch_pyannote(self, pipeline_instance=None):
        """pyannote.audio sys.modules mock 주입 헬퍼"""
        mock_pipeline_cls = MagicMock()
        mock_pyannote_audio = MagicMock()
        mock_pyannote_audio.Pipeline = mock_pipeline_cls
        if pipeline_instance is not None:
            mock_pipeline_cls.from_pretrained.return_value = pipeline_instance
        return patch.dict(
            sys.modules,
            {"pyannote": MagicMock(), "pyannote.audio": mock_pyannote_audio},
        ), mock_pipeline_cls

    def test_diarize_returns_speaker_segment_list(self, tmp_path: Path):
        """diarize() 결과가 SpeakerSegment 리스트"""
        from backend.ml.diarization_engine import DiarizationEngine
        from backend.pipeline.speaker_matcher import SpeakerSegment

        mock_pipeline_instance = _make_mock_pipeline()
        ctx, _ = self._patch_pyannote(mock_pipeline_instance)

        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"\x00" * 100)

        mock_waveform = torch.zeros(1, 16000)
        with ctx, patch("torchaudio.load", return_value=(mock_waveform, 16000)):
            engine = DiarizationEngine.get_instance()
            engine.load(hf_token="hf_testtoken")
            result = engine.diarize(wav_file)

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(seg, SpeakerSegment) for seg in result)

    def test_diarize_result_has_correct_speakers(self, tmp_path: Path):
        """diarize() 결과에 올바른 화자 ID 포함"""
        from backend.ml.diarization_engine import DiarizationEngine

        ctx, _ = self._patch_pyannote(_make_mock_pipeline())
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"\x00" * 100)

        mock_waveform = torch.zeros(1, 16000)
        with ctx, patch("torchaudio.load", return_value=(mock_waveform, 16000)):
            engine = DiarizationEngine.get_instance()
            engine.load(hf_token="hf_testtoken")
            result = engine.diarize(wav_file)

        speaker_ids = {seg.speaker_id for seg in result}
        assert "SPEAKER_00" in speaker_ids
        assert "SPEAKER_01" in speaker_ids

    def test_diarize_segments_have_valid_timestamps(self, tmp_path: Path):
        """diarize() 결과 세그먼트에 유효한 타임스탬프 (start < end)"""
        from backend.ml.diarization_engine import DiarizationEngine

        ctx, _ = self._patch_pyannote(_make_mock_pipeline())
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"\x00" * 100)

        mock_waveform = torch.zeros(1, 16000)
        with ctx, patch("torchaudio.load", return_value=(mock_waveform, 16000)):
            engine = DiarizationEngine.get_instance()
            engine.load(hf_token="hf_testtoken")
            result = engine.diarize(wav_file)

        for seg in result:
            assert seg.start < seg.end

    def test_diarize_auto_loads_if_not_loaded(self, tmp_path: Path):
        """미로드 상태에서 diarize() 호출 시 RuntimeError (HF 토큰 필요)"""
        from backend.ml.diarization_engine import DiarizationEngine

        engine = DiarizationEngine.get_instance()
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"\x00" * 100)

        # 미로드 상태에서 diarize 호출 → 에러 발생
        with pytest.raises((RuntimeError, ValueError)):
            engine.diarize(wav_file)

    def test_diarize_raises_on_pipeline_error(self, tmp_path: Path):
        """Pipeline 실행 오류 시 예외 전파"""
        from backend.ml.diarization_engine import DiarizationEngine

        mock_pipeline_instance = MagicMock()
        mock_pipeline_instance.side_effect = RuntimeError("Pipeline 오류")
        ctx, _ = self._patch_pyannote(mock_pipeline_instance)

        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"\x00" * 100)

        with ctx:
            engine = DiarizationEngine.get_instance()
            engine.load(hf_token="hf_testtoken")
            with pytest.raises(RuntimeError):
                engine.diarize(wav_file)


# ---------------------------------------------------------------------------
# unload() 메서드 테스트
# ---------------------------------------------------------------------------


class TestDiarizationEngineUnload:
    """모델 언로드 테스트"""

    def setup_method(self):
        _reset_engine()

    def _patch_pyannote(self):
        mock_pipeline_cls = MagicMock()
        mock_pyannote_audio = MagicMock()
        mock_pyannote_audio.Pipeline = mock_pipeline_cls
        mock_pipeline_cls.from_pretrained.return_value = _make_mock_pipeline()
        return patch.dict(
            sys.modules,
            {"pyannote": MagicMock(), "pyannote.audio": mock_pyannote_audio},
        )

    def test_unload_resets_model_loaded(self):
        """unload() 후 is_loaded == False"""
        from backend.ml.diarization_engine import DiarizationEngine

        with self._patch_pyannote():
            engine = DiarizationEngine.get_instance()
            engine.load(hf_token="hf_testtoken")
            assert engine.is_loaded is True
            engine.unload()
            assert engine.is_loaded is False

    def test_unload_clears_pipeline(self):
        """unload() 후 _pipeline == None"""
        from backend.ml.diarization_engine import DiarizationEngine

        with self._patch_pyannote():
            engine = DiarizationEngine.get_instance()
            engine.load(hf_token="hf_testtoken")
            engine.unload()
            assert engine._pipeline is None


# ---------------------------------------------------------------------------
# 모델 정보 프로퍼티 테스트
# ---------------------------------------------------------------------------


class TestDiarizationEngineProperties:
    """모델 정보 프로퍼티 테스트"""

    def setup_method(self):
        _reset_engine()

    def test_model_name_contains_diarization(self):
        """model_name에 'diarization' 포함"""
        from backend.ml.diarization_engine import DiarizationEngine

        engine = DiarizationEngine.get_instance()
        assert "diarization" in engine.model_name.lower()

    def test_load_time_none_before_load(self):
        """load() 전 load_time_seconds == None"""
        from backend.ml.diarization_engine import DiarizationEngine

        engine = DiarizationEngine.get_instance()
        assert engine.load_time_seconds is None

    def test_load_time_positive_after_load(self):
        """load() 후 load_time_seconds >= 0"""
        from backend.ml.diarization_engine import DiarizationEngine

        mock_pipeline_cls = MagicMock()
        mock_pyannote_audio = MagicMock()
        mock_pyannote_audio.Pipeline = mock_pipeline_cls
        mock_pipeline_cls.from_pretrained.return_value = _make_mock_pipeline()

        with patch.dict(
            sys.modules,
            {"pyannote": MagicMock(), "pyannote.audio": mock_pyannote_audio},
        ):
            engine = DiarizationEngine.get_instance()
            engine.load(hf_token="hf_testtoken")
            assert engine.load_time_seconds is not None
            assert engine.load_time_seconds >= 0.0


# ---------------------------------------------------------------------------
# Speaker hints + VAD + downsampling 테스트
# (REQ-DIA-PERF-001/002/003)
# ---------------------------------------------------------------------------


def _make_loaded_engine_with_mock_pipeline():
    """diarize() 테스트용 — 모델이 로드된 상태의 엔진 + pipeline 호출 추적 mock"""
    from backend.ml.diarization_engine import DiarizationEngine

    _reset_engine()
    mock_pipeline = _make_mock_pipeline()
    engine = DiarizationEngine.get_instance()
    engine._pipeline = mock_pipeline
    engine._model_loaded = True
    return engine, mock_pipeline


def _make_silero_vad_mock(timestamps=None):
    """silero_vad 모듈 mock 생성

    timestamps: get_speech_timestamps가 반환할 list[dict{start, end}]
    """
    if timestamps is None:
        timestamps = []
    mock_module = MagicMock()
    mock_module.load_silero_vad.return_value = MagicMock()
    mock_module.get_speech_timestamps.return_value = timestamps
    return mock_module


class TestDiarizeHints:
    """REQ-DIA-PERF-001: num_speakers/min_speakers/max_speakers hint 전달"""

    def setup_method(self):
        _reset_engine()

    def test_max_speakers_passed_to_pipeline(self, tmp_path):
        """max_speakers 인자가 pipeline 호출에 kwargs로 전달돼야 함"""

        engine, mock_pipeline = _make_loaded_engine_with_mock_pipeline()
        audio = tmp_path / "fake.wav"
        audio.write_bytes(b"")

        mock_torchaudio = MagicMock()
        mock_torchaudio.load.return_value = (torch.zeros((1, 16000)), 16000)

        with patch.dict(sys.modules, {"torchaudio": mock_torchaudio}):
            # vad_filter=False로 VAD 경로 제외하고 hint만 검증
            engine.diarize(audio, max_speakers=4, vad_filter=False)

        call_args = mock_pipeline.call_args
        kwargs = call_args.kwargs if hasattr(call_args, "kwargs") else {}
        assert kwargs.get("max_speakers") == 4

    def test_num_speakers_takes_priority_over_min_max(self, tmp_path):
        """num_speakers가 명시되면 min/max는 무시되고 num_speakers만 전달"""

        engine, mock_pipeline = _make_loaded_engine_with_mock_pipeline()
        audio = tmp_path / "fake.wav"
        audio.write_bytes(b"")

        mock_torchaudio = MagicMock()
        mock_torchaudio.load.return_value = (torch.zeros((1, 16000)), 16000)

        with patch.dict(sys.modules, {"torchaudio": mock_torchaudio}):
            engine.diarize(
                audio,
                num_speakers=2,
                min_speakers=1,
                max_speakers=10,
                vad_filter=False,
            )

        kwargs = mock_pipeline.call_args.kwargs
        assert kwargs.get("num_speakers") == 2
        # num_speakers 모드에서는 min/max 미전달
        assert "min_speakers" not in kwargs
        assert "max_speakers" not in kwargs

    def test_no_hints_means_no_kwargs(self, tmp_path):
        """인자 미제공 시 pipeline에 hint kwargs 전달 안 됨 (자동 추정)"""

        engine, mock_pipeline = _make_loaded_engine_with_mock_pipeline()
        audio = tmp_path / "fake.wav"
        audio.write_bytes(b"")

        mock_torchaudio = MagicMock()
        mock_torchaudio.load.return_value = (torch.zeros((1, 16000)), 16000)

        with patch.dict(sys.modules, {"torchaudio": mock_torchaudio}):
            engine.diarize(audio, vad_filter=False)

        kwargs = mock_pipeline.call_args.kwargs
        for key in ("num_speakers", "min_speakers", "max_speakers"):
            assert key not in kwargs


class TestDiarizeVAD:
    """REQ-DIA-PERF-002: Silero VAD 사전 필터 + 안전장치"""

    def setup_method(self):
        from backend.ml.diarization_engine import DiarizationEngine

        _reset_engine()
        DiarizationEngine._vad_model = None
        DiarizationEngine._vad_loaded = False

    def test_vad_skip_when_compression_gain_too_low(self, tmp_path):
        """speech_ratio > VAD_MIN_COMPRESSION_GAIN이면 VAD 미적용 (mapping=[])"""

        engine, _ = _make_loaded_engine_with_mock_pipeline()

        # 음성이 거의 전부 (16000 samples 중 15000 = 0.94 ratio)
        # threshold(0.85)보다 크므로 VAD skip되어 원본 사용
        vad_mock = _make_silero_vad_mock(
            timestamps=[{"start": 0, "end": 15000}]
        )

        waveform = torch.zeros((1, 16000))
        with patch.dict(sys.modules, {"silero_vad": vad_mock}):
            compressed, mapping = engine._compress_with_vad(waveform, 16000)

        # 효과 부족 → mapping 비어있어야 함
        assert mapping == []
        # 원본 waveform 그대로 반환
        assert compressed is waveform

    def test_vad_applies_when_silence_significant(self, tmp_path):
        """speech_ratio가 threshold 이하면 VAD 압축 적용"""

        engine, _ = _make_loaded_engine_with_mock_pipeline()

        # 16000 samples 중 음성 8000 (ratio 0.5, threshold 0.85보다 작음)
        vad_mock = _make_silero_vad_mock(
            timestamps=[
                {"start": 0, "end": 4000},
                {"start": 12000, "end": 16000},
            ]
        )

        waveform = torch.zeros((1, 16000))
        with patch.dict(sys.modules, {"silero_vad": vad_mock}):
            compressed, mapping = engine._compress_with_vad(waveform, 16000)

        # VAD 적용 → 2개 음성 segment에 대한 mapping이 생성됨
        assert len(mapping) == 2
        # 첫 mapping은 원본 start=0
        assert mapping[0]["original_start"] == 0
        assert mapping[1]["original_start"] == 12000
        # compressed는 원본보다 짧음 (8000 + silence padding)
        assert compressed.shape[-1] < waveform.shape[-1] + int(
            16000 * engine.VAD_SILENCE_PAD_SEC
        )

    def test_adjacent_segments_merged(self, tmp_path):
        """인접 짧은 음성 segment (간격 < VAD_MERGE_GAP_SEC)는 하나로 병합"""

        engine, _ = _make_loaded_engine_with_mock_pipeline()

        # 두 segment 간격 500 samples = 0.05s < merge_gap (0.3s) → 병합
        # 음성 1000 + 1000 = 2000 (ratio 0.125, threshold 통과)
        vad_mock = _make_silero_vad_mock(
            timestamps=[
                {"start": 0, "end": 1000},
                {"start": 1500, "end": 2500},
            ]
        )

        waveform = torch.zeros((1, 16000))
        with patch.dict(sys.modules, {"silero_vad": vad_mock}):
            _, mapping = engine._compress_with_vad(waveform, 16000)

        # 병합되어 mapping이 1개여야 함
        assert len(mapping) == 1
        assert mapping[0]["original_start"] == 0

    def test_map_segments_back_to_original_time(self):
        """compressed 시간의 segment를 원본 시간으로 역매핑"""
        from backend.pipeline.speaker_matcher import SpeakerSegment

        engine, _ = _make_loaded_engine_with_mock_pipeline()

        # mapping: 0~1초의 음성이 원본의 5~6초에 위치
        mapping = [
            {
                "compressed_start": 0,
                "compressed_end": 16000,
                "original_start": 80000,  # 5초 (16000Hz)
            }
        ]
        # compressed에서 0.5~0.7초 segment
        raw_segments = [
            SpeakerSegment(speaker_id="SPEAKER_00", start=0.5, end=0.7)
        ]

        mapped = engine._map_segments(raw_segments, mapping, 16000)

        assert len(mapped) == 1
        # 원본 5.5~5.7초로 매핑돼야 함
        assert abs(mapped[0].start - 5.5) < 0.01
        assert abs(mapped[0].end - 5.7) < 0.01


class TestDiarizeDownsampling:
    """REQ-DIA-PERF-003: target_sample_rate 다운샘플링 옵션 (실험적)"""

    def setup_method(self):
        _reset_engine()

    def test_no_downsample_when_target_is_none(self, tmp_path):
        """target_sample_rate=None이면 resample 호출되지 않음"""

        engine, _ = _make_loaded_engine_with_mock_pipeline()
        audio = tmp_path / "fake.wav"
        audio.write_bytes(b"")

        mock_torchaudio = MagicMock()
        mock_torchaudio.load.return_value = (torch.zeros((1, 16000)), 16000)
        mock_torchaudio.functional.resample = MagicMock()

        with patch.dict(sys.modules, {"torchaudio": mock_torchaudio}):
            engine.diarize(audio, target_sample_rate=None, vad_filter=False)

        mock_torchaudio.functional.resample.assert_not_called()

    def test_no_downsample_when_target_matches_source(self, tmp_path):
        """target_sample_rate == source면 resample 호출되지 않음"""

        engine, _ = _make_loaded_engine_with_mock_pipeline()
        audio = tmp_path / "fake.wav"
        audio.write_bytes(b"")

        mock_torchaudio = MagicMock()
        mock_torchaudio.load.return_value = (torch.zeros((1, 16000)), 16000)
        mock_torchaudio.functional.resample = MagicMock()

        with patch.dict(sys.modules, {"torchaudio": mock_torchaudio}):
            engine.diarize(audio, target_sample_rate=16000, vad_filter=False)

        mock_torchaudio.functional.resample.assert_not_called()

    def test_downsample_when_target_differs(self, tmp_path):
        """target_sample_rate > 0 && != source면 resample 호출"""

        engine, _ = _make_loaded_engine_with_mock_pipeline()
        audio = tmp_path / "fake.wav"
        audio.write_bytes(b"")

        mock_torchaudio = MagicMock()
        mock_torchaudio.load.return_value = (torch.zeros((1, 16000)), 16000)
        # resample 결과는 8kHz 길이의 절반 길이 waveform
        mock_torchaudio.functional.resample.return_value = torch.zeros((1, 8000))

        with patch.dict(sys.modules, {"torchaudio": mock_torchaudio}):
            engine.diarize(audio, target_sample_rate=8000, vad_filter=False)

        # resample 한 번 호출되고 args는 (waveform, 16000, 8000)
        assert mock_torchaudio.functional.resample.call_count == 1
        args = mock_torchaudio.functional.resample.call_args.args
        assert args[1] == 16000
        assert args[2] == 8000
