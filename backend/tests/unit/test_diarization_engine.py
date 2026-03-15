"""
DiarizationEngine 단위 테스트 (RED phase)
REQ-DIA-007~012: pyannote.audio Pipeline 싱글톤 엔진
"""

import sys
from pathlib import Path
from threading import Thread
from unittest.mock import MagicMock, patch

import pytest

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

    mock_diarization = MagicMock()
    mock_diarization.itertracks.return_value = [
        (mock_turn1, None, "SPEAKER_00"),
        (mock_turn2, None, "SPEAKER_01"),
    ]

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

        with ctx:
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

        with ctx:
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

        with ctx:
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
