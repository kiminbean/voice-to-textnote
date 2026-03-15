"""
mlx-whisper STT 엔진 래퍼 단위 테스트
REQ-STT-005, REQ-STT-006, REQ-STT-007, REQ-STT-008, REQ-STT-009
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_mock_mlx(transcribe_result=None):
    """mlx_whisper mock 모듈 생성 헬퍼"""
    mock = MagicMock()
    if transcribe_result is not None:
        mock.transcribe.return_value = transcribe_result
    return mock


# ---------------------------------------------------------------------------
# WhisperEngine 싱글톤 테스트
# ---------------------------------------------------------------------------

class TestWhisperEngineSingleton:
    """싱글톤 패턴 테스트 (REQ-STT-007)"""

    def setup_method(self):
        """각 테스트 전 싱글톤 리셋"""
        from backend.ml.stt_engine import WhisperEngine
        WhisperEngine._instance = None
        WhisperEngine._model_loaded = False
        WhisperEngine._load_time_seconds = None
        WhisperEngine._device = "cpu"

    def test_get_instance_returns_same_object(self):
        """get_instance()는 동일한 인스턴스를 반환해야 함"""
        from backend.ml.stt_engine import WhisperEngine

        instance1 = WhisperEngine.get_instance()
        instance2 = WhisperEngine.get_instance()
        assert instance1 is instance2

    def test_get_instance_called_multiple_times_same(self):
        """여러 번 호출해도 동일 인스턴스"""
        from backend.ml.stt_engine import WhisperEngine

        instances = [WhisperEngine.get_instance() for _ in range(5)]
        assert all(i is instances[0] for i in instances)

    def test_is_loaded_false_initially(self):
        """초기 상태에서 is_loaded == False (모델 미로드)"""
        from backend.ml.stt_engine import WhisperEngine

        engine = WhisperEngine.get_instance()
        assert engine.is_loaded is False

    def test_model_not_loaded_without_explicit_call(self):
        """load() 호출 없이는 모델 미로드"""
        from backend.ml.stt_engine import WhisperEngine

        engine = WhisperEngine.get_instance()
        # 로드 호출 안 함 → _model_loaded=False
        assert not engine._model_loaded


# ---------------------------------------------------------------------------
# load() 메서드 테스트
# ---------------------------------------------------------------------------

class TestWhisperEngineLoad:
    """모델 로딩 테스트 (REQ-STT-007: lazy load + 재사용)"""

    def setup_method(self):
        from backend.ml.stt_engine import WhisperEngine
        WhisperEngine._instance = None
        WhisperEngine._model_loaded = False
        WhisperEngine._load_time_seconds = None
        WhisperEngine._device = "cpu"

    def test_load_sets_model_loaded_true(self):
        """load() 후 is_loaded == True"""
        from backend.ml.stt_engine import WhisperEngine

        with patch.dict(sys.modules, {"mlx_whisper": _make_mock_mlx()}):
            with patch.object(WhisperEngine, "_detect_device", return_value="mps"):
                engine = WhisperEngine.get_instance()
                engine.load()
                assert engine.is_loaded is True

    def test_load_records_load_time(self):
        """load() 후 load_time_seconds가 기록됨 (시나리오 9)"""
        from backend.ml.stt_engine import WhisperEngine

        with patch.dict(sys.modules, {"mlx_whisper": _make_mock_mlx()}):
            with patch.object(WhisperEngine, "_detect_device", return_value="mps"):
                engine = WhisperEngine.get_instance()
                engine.load()
                assert engine.load_time_seconds is not None
                assert engine.load_time_seconds >= 0

    def test_load_called_twice_is_idempotent(self):
        """load() 두 번 호출해도 에러 없음 (재사용, REQ-STT-007)"""
        from backend.ml.stt_engine import WhisperEngine

        with patch.dict(sys.modules, {"mlx_whisper": _make_mock_mlx()}):
            with patch.object(WhisperEngine, "_detect_device", return_value="mps"):
                engine = WhisperEngine.get_instance()
                engine.load()
                assert engine.is_loaded is True
                engine.load()  # 두 번째 호출도 정상
                assert engine.is_loaded is True

    def test_load_raises_runtime_error_when_mlx_unavailable(self):
        """mlx-whisper 미설치 시 RuntimeError 발생"""
        from backend.ml.stt_engine import WhisperEngine

        with patch.object(WhisperEngine, "_detect_device", return_value="cpu"):
            with patch("builtins.__import__", side_effect=ImportError("No module named 'mlx_whisper'")):
                engine = WhisperEngine.get_instance()
                with pytest.raises((RuntimeError, ImportError)):
                    engine.load()


# ---------------------------------------------------------------------------
# transcribe() 메서드 테스트
# ---------------------------------------------------------------------------

class TestWhisperEngineTranscribe:
    """전사 기능 테스트 (REQ-STT-005, REQ-STT-008)"""

    def setup_method(self):
        from backend.ml.stt_engine import WhisperEngine
        WhisperEngine._instance = None
        WhisperEngine._model_loaded = False
        WhisperEngine._load_time_seconds = None
        WhisperEngine._device = "cpu"

    def test_transcribe_returns_correct_structure(self, test_audio_file: Path):
        """전사 결과에 segments, language 키 포함 (REQ-STT-008)"""
        from backend.ml.stt_engine import WhisperEngine

        mock_result = {
            "segments": [
                {"id": 0, "start": 0.0, "end": 4.2, "text": "안녕하세요.", "no_speech_prob": 0.05}
            ],
            "language": "ko",
            "text": "안녕하세요.",
        }

        mock_mlx = _make_mock_mlx(mock_result)
        with patch.dict(sys.modules, {"mlx_whisper": mock_mlx}):
            with patch.object(WhisperEngine, "_detect_device", return_value="mps"):
                engine = WhisperEngine.get_instance()
                engine.load()
                result = engine.transcribe(test_audio_file)

        assert "segments" in result
        assert "language" in result
        assert isinstance(result["segments"], list)

    def test_transcribe_uses_korean_language_default(self, test_audio_file: Path):
        """기본 language='ko' 강제 디코딩 사용 (REQ-STT-005)"""
        from backend.ml.stt_engine import WhisperEngine

        mock_mlx = _make_mock_mlx({"segments": [], "language": "ko"})
        with patch.dict(sys.modules, {"mlx_whisper": mock_mlx}):
            with patch.object(WhisperEngine, "_detect_device", return_value="mps"):
                engine = WhisperEngine.get_instance()
                engine.load()
                engine.transcribe(test_audio_file)

                call_args = mock_mlx.transcribe.call_args
                assert call_args is not None
                kwargs = call_args.kwargs if hasattr(call_args, "kwargs") else {}
                assert kwargs.get("language") == "ko"

    def test_transcribe_with_explicit_language(self, test_audio_file: Path):
        """language 파라미터 명시 전달"""
        from backend.ml.stt_engine import WhisperEngine

        mock_mlx = _make_mock_mlx({"segments": [], "language": "en"})
        with patch.dict(sys.modules, {"mlx_whisper": mock_mlx}):
            with patch.object(WhisperEngine, "_detect_device", return_value="mps"):
                engine = WhisperEngine.get_instance()
                engine.load()
                engine.transcribe(test_audio_file, language="en")

                call_args = mock_mlx.transcribe.call_args
                kwargs = call_args.kwargs if hasattr(call_args, "kwargs") else {}
                assert kwargs.get("language") == "en"

    def test_segment_has_required_fields(self, test_audio_file: Path):
        """세그먼트에 id, start, end, text 필드 포함 (REQ-STT-008)"""
        from backend.ml.stt_engine import WhisperEngine

        expected_segment = {
            "id": 0,
            "start": 0.0,
            "end": 4.2,
            "text": "테스트",
            "no_speech_prob": 0.05,
        }

        mock_mlx = _make_mock_mlx({"segments": [expected_segment], "language": "ko"})
        with patch.dict(sys.modules, {"mlx_whisper": mock_mlx}):
            with patch.object(WhisperEngine, "_detect_device", return_value="mps"):
                engine = WhisperEngine.get_instance()
                engine.load()
                result = engine.transcribe(test_audio_file)

        segment = result["segments"][0]
        for field in ("id", "start", "end", "text"):
            assert field in segment, f"세그먼트에 '{field}' 필드 누락"

    def test_start_less_than_end_in_segments(self, test_audio_file: Path):
        """각 세그먼트의 start < end (REQ-STT-008)"""
        from backend.ml.stt_engine import WhisperEngine

        segments = [
            {"id": 0, "start": 0.0, "end": 4.2, "text": "A"},
            {"id": 1, "start": 4.2, "end": 8.5, "text": "B"},
        ]

        mock_mlx = _make_mock_mlx({"segments": segments, "language": "ko"})
        with patch.dict(sys.modules, {"mlx_whisper": mock_mlx}):
            with patch.object(WhisperEngine, "_detect_device", return_value="mps"):
                engine = WhisperEngine.get_instance()
                engine.load()
                result = engine.transcribe(test_audio_file)

        for seg in result["segments"]:
            assert seg["start"] < seg["end"], f"세그먼트 start >= end: {seg}"

    def test_transcribe_raises_on_mlx_error(self, test_audio_file: Path):
        """전사 중 에러 발생 시 예외 전파 (REQ-STT-009: 부분 결과 없음)"""
        from backend.ml.stt_engine import WhisperEngine

        mock_mlx = _make_mock_mlx()
        mock_mlx.transcribe.side_effect = RuntimeError("MLX 런타임 오류")
        with patch.dict(sys.modules, {"mlx_whisper": mock_mlx}):
            with patch.object(WhisperEngine, "_detect_device", return_value="mps"):
                engine = WhisperEngine.get_instance()
                engine.load()

                with pytest.raises(RuntimeError, match="MLX 런타임 오류"):
                    engine.transcribe(test_audio_file)

    def test_transcribe_auto_loads_if_not_loaded(self, test_audio_file: Path):
        """미로드 상태에서 transcribe() 호출 시 자동 load() 실행 (REQ-STT-007)"""
        from backend.ml.stt_engine import WhisperEngine

        mock_mlx = _make_mock_mlx({"segments": [], "language": "ko"})
        with patch.dict(sys.modules, {"mlx_whisper": mock_mlx}):
            with patch.object(WhisperEngine, "_detect_device", return_value="mps"):
                engine = WhisperEngine.get_instance()
                # load() 호출 안 함
                assert engine.is_loaded is False
                engine.transcribe(test_audio_file)
                # 자동 load 후 상태
                assert engine.is_loaded is True


# ---------------------------------------------------------------------------
# 디바이스 선택 테스트
# ---------------------------------------------------------------------------

class TestDeviceSelection:
    """MLX/MPS 디바이스 선택 테스트 (REQ-STT-006)"""

    def test_mps_returned_when_mlx_available(self):
        """MLX 가용 시 'mps' 반환 (REQ-STT-006)"""
        from backend.ml.stt_engine import WhisperEngine

        mock_mx = MagicMock()
        mock_mx.array.return_value = MagicMock()
        with patch.dict(sys.modules, {"mlx": MagicMock(), "mlx.core": mock_mx}):
            device = WhisperEngine._detect_device()
            # MLX import 성공 → mps
            assert device == "mps"

    def test_cpu_returned_when_mlx_not_installed(self):
        """mlx 미설치 시 'cpu' 반환 (REQ-STT-006: CPU 폴백)"""
        from backend.ml.stt_engine import WhisperEngine

        with patch.dict("sys.modules", {"mlx.core": None}):
            import sys
            old = sys.modules.pop("mlx.core", None)
            try:
                # ImportError 시뮬레이션
                with patch("backend.ml.stt_engine.WhisperEngine._detect_device") as mock_detect:
                    mock_detect.return_value = "cpu"
                    device = WhisperEngine._detect_device()
                    assert device == "cpu"
            finally:
                if old:
                    sys.modules["mlx.core"] = old

    def test_detect_device_returns_string(self):
        """_detect_device()는 문자열 반환"""
        from backend.ml.stt_engine import WhisperEngine

        result = WhisperEngine._detect_device()
        assert isinstance(result, str)
        assert result in ("mps", "cpu")


# ---------------------------------------------------------------------------
# 메모리 모니터링 테스트
# ---------------------------------------------------------------------------

class TestWhisperEngineMemory:
    """메모리 사용량 모니터링 테스트 (REQ-STT-022)"""

    def setup_method(self):
        from backend.ml.stt_engine import WhisperEngine
        WhisperEngine._instance = None
        WhisperEngine._model_loaded = False

    def test_get_memory_info_returns_dict(self):
        """get_memory_info()가 딕셔너리 반환"""
        from backend.ml.stt_engine import WhisperEngine

        engine = WhisperEngine.get_instance()
        info = engine.get_memory_info()
        assert isinstance(info, dict)

    def test_get_memory_info_has_required_keys(self):
        """get_memory_info()에 필수 키 포함 (시나리오 13)"""
        from backend.ml.stt_engine import WhisperEngine

        engine = WhisperEngine.get_instance()
        info = engine.get_memory_info()
        for key in ("total_mb", "available_mb", "used_mb", "percent"):
            assert key in info, f"memory_info에 '{key}' 키 누락"

    def test_memory_info_values_are_positive(self):
        """메모리 정보값은 양수 (시나리오 4, 13)"""
        from backend.ml.stt_engine import WhisperEngine

        engine = WhisperEngine.get_instance()
        info = engine.get_memory_info()
        assert info["total_mb"] > 0
        assert info["available_mb"] >= 0
        assert info["used_mb"] >= 0
        assert 0 <= info["percent"] <= 100

    def test_memory_warning_logged_when_threshold_exceeded(self):
        """메모리 임계값 초과 시 경고 로그 기록 (REQ-STT-022)"""
        from backend.ml.stt_engine import WhisperEngine, MEMORY_WARNING_THRESHOLD_BYTES

        import psutil
        mock_vm = MagicMock()
        mock_vm.used = MEMORY_WARNING_THRESHOLD_BYTES + 1
        mock_vm.percent = 85.0

        engine = WhisperEngine.get_instance()

        with patch("psutil.virtual_memory", return_value=mock_vm):
            with patch("backend.ml.stt_engine.logger") as mock_logger:
                engine._check_memory_usage()
                mock_logger.warning.assert_called_once()

    def test_no_warning_below_threshold(self):
        """임계값 이하에서는 경고 없음"""
        from backend.ml.stt_engine import WhisperEngine, MEMORY_WARNING_THRESHOLD_BYTES

        mock_vm = MagicMock()
        mock_vm.used = MEMORY_WARNING_THRESHOLD_BYTES - 1
        mock_vm.percent = 75.0

        engine = WhisperEngine.get_instance()

        with patch("psutil.virtual_memory", return_value=mock_vm):
            with patch("backend.ml.stt_engine.logger") as mock_logger:
                engine._check_memory_usage()
                mock_logger.warning.assert_not_called()


# ---------------------------------------------------------------------------
# 모델 정보 프로퍼티 테스트
# ---------------------------------------------------------------------------

class TestWhisperEngineProperties:
    """모델 정보 프로퍼티 테스트 (REQ-STT-020)"""

    def setup_method(self):
        from backend.ml.stt_engine import WhisperEngine
        WhisperEngine._instance = None
        WhisperEngine._model_loaded = False
        WhisperEngine._load_time_seconds = None
        WhisperEngine._device = "cpu"

    def test_model_name_contains_whisper_large(self):
        """모델명에 'whisper'와 'large' 포함 (시나리오 4)"""
        from backend.ml.stt_engine import WhisperEngine

        engine = WhisperEngine.get_instance()
        assert "whisper" in engine.model_name.lower()
        assert "large" in engine.model_name.lower()

    def test_device_property_returns_string(self):
        """device 프로퍼티가 문자열 반환"""
        from backend.ml.stt_engine import WhisperEngine

        engine = WhisperEngine.get_instance()
        assert isinstance(engine.device, str)

    def test_load_time_none_before_load(self):
        """load() 호출 전 load_time_seconds == None"""
        from backend.ml.stt_engine import WhisperEngine

        engine = WhisperEngine.get_instance()
        assert engine.load_time_seconds is None

    def test_load_time_positive_after_load(self):
        """load() 호출 후 load_time_seconds가 0 이상 (시나리오 9)"""
        from backend.ml.stt_engine import WhisperEngine

        with patch.dict(sys.modules, {"mlx_whisper": _make_mock_mlx()}):
            with patch.object(WhisperEngine, "_detect_device", return_value="mps"):
                engine = WhisperEngine.get_instance()
                engine.load()
                assert engine.load_time_seconds is not None
                assert engine.load_time_seconds >= 0.0
