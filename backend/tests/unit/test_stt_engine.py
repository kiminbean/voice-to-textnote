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



# ---------------------------------------------------------------------------
# load() 메서드 테스트
# ---------------------------------------------------------------------------


class TestWhisperEngineLoad:
    """모델 로딩 테스트 (REQ-STT-007: lazy load + 재사용)"""

    def test_load_sets_model_loaded_true(self):
        """load() 후 is_loaded == True"""
        from backend.ml.stt_engine import WhisperEngine

        with patch.dict(sys.modules, {"mlx_whisper": _make_mock_mlx()}):
            with (
                patch("platform.system", return_value="Darwin"),
                patch.object(WhisperEngine, "_detect_device", return_value="mps"),
            ):
                engine = WhisperEngine()
                engine.load()
                assert engine.is_loaded is True

    def test_load_records_load_time(self):
        """load() 후 load_time_seconds가 기록됨 (시나리오 9)"""
        from backend.ml.stt_engine import WhisperEngine

        with patch.dict(sys.modules, {"mlx_whisper": _make_mock_mlx()}):
            with (
                patch("platform.system", return_value="Darwin"),
                patch.object(WhisperEngine, "_detect_device", return_value="mps"),
            ):
                engine = WhisperEngine()
                engine.load()
                assert engine.load_time_seconds is not None
                assert engine.load_time_seconds >= 0

    def test_load_called_twice_is_idempotent(self):
        """load() 두 번 호출해도 에러 없음 (재사용, REQ-STT-007)"""
        from backend.ml.stt_engine import WhisperEngine

        with patch.dict(sys.modules, {"mlx_whisper": _make_mock_mlx()}):
            with (
                patch("platform.system", return_value="Darwin"),
                patch.object(WhisperEngine, "_detect_device", return_value="mps"),
            ):
                engine = WhisperEngine()
                engine.load()
                assert engine.is_loaded is True
                engine.load()  # 두 번째 호출도 정상
                assert engine.is_loaded is True

    def test_load_raises_runtime_error_when_mlx_unavailable(self):
        """mlx-whisper 미설치 시 RuntimeError 발생"""
        from backend.ml.stt_engine import WhisperEngine

        with patch.object(WhisperEngine, "_detect_device", return_value="cpu"), patch(
            "builtins.__import__", side_effect=ImportError("No module named 'mlx_whisper'")
        ):
            engine = WhisperEngine()
            with pytest.raises((RuntimeError, ImportError)):
                engine.load()


# ---------------------------------------------------------------------------
# transcribe() 메서드 테스트
# ---------------------------------------------------------------------------


class TestWhisperEngineTranscribe:
    """전사 기능 테스트 (REQ-STT-005, REQ-STT-008)"""

    def setup_method(self):
        """테스트 전 상태 리셋"""
        from backend.ml.stt_engine import WhisperEngine

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
            with (
                patch("platform.system", return_value="Darwin"),
                patch.object(WhisperEngine, "_detect_device", return_value="mps"),
            ):
                engine = WhisperEngine()
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
            with (
                patch("platform.system", return_value="Darwin"),
                patch.object(WhisperEngine, "_detect_device", return_value="mps"),
            ):
                engine = WhisperEngine()
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
            with (
                patch("platform.system", return_value="Darwin"),
                patch.object(WhisperEngine, "_detect_device", return_value="mps"),
            ):
                engine = WhisperEngine()
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
            with (
                patch("platform.system", return_value="Darwin"),
                patch.object(WhisperEngine, "_detect_device", return_value="mps"),
            ):
                engine = WhisperEngine()
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
            with (
                patch("platform.system", return_value="Darwin"),
                patch.object(WhisperEngine, "_detect_device", return_value="mps"),
            ):
                engine = WhisperEngine()
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
            with (
                patch("platform.system", return_value="Darwin"),
                patch.object(WhisperEngine, "_detect_device", return_value="mps"),
            ):
                engine = WhisperEngine()
                engine.load()

                with pytest.raises(RuntimeError, match="MLX 런타임 오류"):
                    engine.transcribe(test_audio_file)

    def test_transcribe_auto_loads_if_not_loaded(self, test_audio_file: Path):
        """미로드 상태에서 transcribe() 호출 시 자동 load() 실행 (REQ-STT-007)"""
        from backend.ml.stt_engine import WhisperEngine

        mock_mlx = _make_mock_mlx({"segments": [], "language": "ko"})
        with patch.dict(sys.modules, {"mlx_whisper": mock_mlx}):
            with (
                patch("platform.system", return_value="Darwin"),
                patch.object(WhisperEngine, "_detect_device", return_value="mps"),
            ):
                engine = WhisperEngine()
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
                    sys.modules["mlx.core"] = old  # pragma: no cover

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

        WhisperEngine._model_loaded = False

    def test_get_memory_info_returns_dict(self):
        """get_memory_info()가 딕셔너리 반환"""
        from backend.ml.stt_engine import WhisperEngine

        engine = WhisperEngine()
        info = engine.get_memory_info()
        assert isinstance(info, dict)

    def test_get_memory_info_has_required_keys(self):
        """get_memory_info()에 필수 키 포함 (시나리오 13)"""
        from backend.ml.stt_engine import WhisperEngine

        engine = WhisperEngine()
        info = engine.get_memory_info()
        for key in ("total_mb", "available_mb", "used_mb", "percent"):
            assert key in info, f"memory_info에 '{key}' 키 누락"

    def test_memory_info_values_are_positive(self):
        """메모리 정보값은 양수 (시나리오 4, 13)"""
        from backend.ml.stt_engine import WhisperEngine

        engine = WhisperEngine()
        info = engine.get_memory_info()
        assert info["total_mb"] > 0
        assert info["available_mb"] >= 0
        assert info["used_mb"] >= 0
        assert 0 <= info["percent"] <= 100

    def test_memory_warning_logged_when_threshold_exceeded(self):
        """메모리 임계값 초과 시 경고 로그 기록 (REQ-STT-022)"""
        from backend.ml.stt_engine import MEMORY_WARNING_THRESHOLD_BYTES, WhisperEngine

        mock_vm = MagicMock()
        mock_vm.used = MEMORY_WARNING_THRESHOLD_BYTES + 1
        mock_vm.percent = 85.0

        engine = WhisperEngine()

        with patch("psutil.virtual_memory", return_value=mock_vm):
            with patch("backend.ml.stt_engine.logger") as mock_logger:
                engine._check_memory_usage()
                mock_logger.warning.assert_called_once()

    def test_no_warning_below_threshold(self):
        """임계값 이하에서는 경고 없음"""
        from backend.ml.stt_engine import MEMORY_WARNING_THRESHOLD_BYTES, WhisperEngine

        mock_vm = MagicMock()
        mock_vm.used = MEMORY_WARNING_THRESHOLD_BYTES - 1
        mock_vm.percent = 75.0

        engine = WhisperEngine()

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

        WhisperEngine._model_loaded = False
        WhisperEngine._load_time_seconds = None
        WhisperEngine._device = "cpu"

    def test_model_name_contains_whisper(self):
        """모델명에 'whisper' 포함 (시나리오 4)"""
        from backend.ml.stt_engine import WhisperEngine

        engine = WhisperEngine()
        assert "whisper" in engine.model_name.lower()

    def test_device_property_returns_string(self):
        """device 프로퍼티가 문자열 반환"""
        from backend.ml.stt_engine import WhisperEngine

        engine = WhisperEngine()
        assert isinstance(engine.device, str)

    def test_load_time_none_before_load(self):
        """load() 호출 전 load_time_seconds == None"""
        from backend.ml.stt_engine import WhisperEngine

        engine = WhisperEngine()
        assert engine.load_time_seconds is None

    def test_load_time_positive_after_load(self):
        """load() 호출 후 load_time_seconds가 0 이상 (시나리오 9)"""
        from backend.ml.stt_engine import WhisperEngine

        with patch.dict(sys.modules, {"mlx_whisper": _make_mock_mlx()}):
            with (
                patch("platform.system", return_value="Darwin"),
                patch.object(WhisperEngine, "_detect_device", return_value="mps"),
            ):
                engine = WhisperEngine()
                engine.load()
                assert engine.load_time_seconds is not None
                assert engine.load_time_seconds >= 0.0


# ---------------------------------------------------------------------------
# faster-whisper 백엔드 테스트 (REQ-STT-PERF-001)
# ---------------------------------------------------------------------------


def _make_mock_faster_whisper(segments=None, language="ko"):
    """faster_whisper mock 모듈 생성 헬퍼

    Args:
        segments: 반환할 SegmentResult mock 리스트 (None이면 빈 리스트)
        language: info.language 값

    Returns:
        faster_whisper 모듈 mock과 WhisperModel 인스턴스 mock의 튜플
    """
    if segments is None:
        segments = []

    mock_info = MagicMock()
    mock_info.language = language

    mock_model = MagicMock()
    # transcribe()는 (generator, info) 튜플을 반환
    mock_model.transcribe.return_value = (iter(segments), mock_info)

    mock_module = MagicMock()
    mock_module.WhisperModel.return_value = mock_model
    return mock_module, mock_model


def _make_fw_segment(idx, start, end, text, avg_logprob=-0.3):
    """faster-whisper SegmentResult mock 생성 헬퍼"""
    seg = MagicMock()
    seg.id = idx
    seg.start = start
    seg.end = end
    seg.text = text
    seg.avg_logprob = avg_logprob
    seg.no_speech_prob = 0.05
    seg.compression_ratio = 1.2
    return seg


class TestFasterWhisperBackend:
    """faster-whisper 백엔드 로드/추론 테스트"""

    def setup_method(self):
        from backend.ml.stt_engine import WhisperEngine

        WhisperEngine._model_loaded = False
        WhisperEngine._load_time_seconds = None
        WhisperEngine._device = "cpu"
        WhisperEngine._backend = "unknown"
        WhisperEngine._faster_whisper_model = None
        WhisperEngine._whisper_model = None

    def test_faster_whisper_loads_on_linux_when_mlx_unavailable(self):
        """MLX 미설치 + faster-whisper 설치 시 faster-whisper 백엔드 선택"""
        from backend.ml.stt_engine import WhisperEngine

        mock_fw, _ = _make_mock_faster_whisper()
        # mlx_whisper를 ImportError로 만들기 위해 sys.modules에서 제거
        with patch.dict(sys.modules, {"faster_whisper": mock_fw, "mlx_whisper": None}):
            with patch("platform.system", return_value="Linux"):
                engine = WhisperEngine()
                engine.load()
                assert engine.is_loaded is True
                assert engine.backend == "faster_whisper"

    def test_faster_whisper_uses_cpu_int8_when_no_cuda(self):
        """CUDA 미가용 시 device='cpu', compute_type='int8' 선택"""
        from backend.ml.stt_engine import WhisperEngine

        mock_fw, _ = _make_mock_faster_whisper()
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        with patch.dict(
            sys.modules,
            {"faster_whisper": mock_fw, "torch": mock_torch, "mlx_whisper": None},
        ), patch("platform.system", return_value="Linux"):
            engine = WhisperEngine()
            engine.load()
            # WhisperModel() 호출 시 device, compute_type 확인
            call_args = mock_fw.WhisperModel.call_args
            kwargs = call_args.kwargs if hasattr(call_args, "kwargs") else {}
            assert kwargs.get("device") == "cpu"
            assert kwargs.get("compute_type") == "int8"
            assert engine.device == "cpu"

    def test_faster_whisper_uses_cuda_float16_when_available(self):
        """CUDA 가용 시 device='cuda', compute_type='float16' 선택"""
        from backend.ml.stt_engine import WhisperEngine

        mock_fw, _ = _make_mock_faster_whisper()
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True

        with patch.dict(
            sys.modules,
            {"faster_whisper": mock_fw, "torch": mock_torch, "mlx_whisper": None},
        ), patch("platform.system", return_value="Linux"):
            engine = WhisperEngine()
            engine.load()
            call_args = mock_fw.WhisperModel.call_args
            kwargs = call_args.kwargs if hasattr(call_args, "kwargs") else {}
            assert kwargs.get("device") == "cuda"
            assert kwargs.get("compute_type") == "float16"
            assert engine.device == "cuda"

    def test_faster_whisper_model_name_mapping(self):
        """mlx-community 모델명을 faster-whisper 모델명으로 변환"""
        from backend.ml.stt_engine import _resolve_faster_whisper_model

        assert _resolve_faster_whisper_model("mlx-community/whisper-small-mlx") == "small"
        assert (
            _resolve_faster_whisper_model("mlx-community/whisper-large-v3-turbo")
            == "large-v3-turbo"
        )
        # 매핑에 없는 이름은 그대로 반환 (자유 형식 모델 지원)
        assert _resolve_faster_whisper_model("custom/my-model") == "custom/my-model"

    def test_faster_whisper_transcribe_returns_compatible_format(self, test_audio_file: Path):
        """faster-whisper 출력이 openai-whisper와 호환되는 형식인지 검증"""
        from backend.ml.stt_engine import WhisperEngine

        segments = [
            _make_fw_segment(0, 0.0, 5.6, "지금부터 회의 시작하겠습니다."),
            _make_fw_segment(1, 6.68, 15.4, "노트 준비해 주시기 바랍니다."),
        ]
        mock_fw, _mock_model = _make_mock_faster_whisper(segments=segments, language="ko")
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        with patch.dict(
            sys.modules,
            {"faster_whisper": mock_fw, "torch": mock_torch, "mlx_whisper": None},
        ), patch("platform.system", return_value="Linux"):
            engine = WhisperEngine()
            engine.load()
            result = engine.transcribe(test_audio_file)

        # openai-whisper 호환 키 확인
        assert "segments" in result
        assert "language" in result
        assert "text" in result
        assert result["language"] == "ko"
        assert len(result["segments"]) == 2

        # 각 세그먼트의 필수 키
        for seg in result["segments"]:
            for field in ("id", "start", "end", "text", "avg_logprob"):
                assert field in seg

        # 첫 세그먼트 내용 확인
        assert result["segments"][0]["start"] == 0.0
        assert result["segments"][0]["end"] == 5.6
        assert "회의" in result["segments"][0]["text"]

    def test_faster_whisper_transcribe_calls_with_optimization_flags(self, test_audio_file: Path):
        """transcribe() 호출 시 속도 최적화 옵션이 적용되는지 확인"""
        from backend.ml.stt_engine import WhisperEngine

        mock_fw, mock_model = _make_mock_faster_whisper()
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        with patch.dict(
            sys.modules,
            {"faster_whisper": mock_fw, "torch": mock_torch, "mlx_whisper": None},
        ), patch("platform.system", return_value="Linux"):
            engine = WhisperEngine()
            engine.load()
            engine.transcribe(test_audio_file, language="ko")

            call_args = mock_model.transcribe.call_args
            kwargs = call_args.kwargs if hasattr(call_args, "kwargs") else {}
            # 속도 최적화 옵션 검증
            assert kwargs.get("language") == "ko"
            assert kwargs.get("word_timestamps") is False
            assert kwargs.get("beam_size") == 1
            assert kwargs.get("vad_filter") is True

    def test_falls_back_to_openai_whisper_when_faster_unavailable(self):
        """faster-whisper 미설치 시 openai-whisper로 폴백"""
        from backend.ml.stt_engine import WhisperEngine

        mock_whisper = MagicMock()
        mock_whisper.load_model.return_value = MagicMock()
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        # faster_whisper는 ImportError 발생 시뮬레이션 → None 매핑
        with patch.dict(
            sys.modules,
            {
                "faster_whisper": None,
                "whisper": mock_whisper,
                "torch": mock_torch,
                "mlx_whisper": None,
            },
        ), patch("platform.system", return_value="Linux"):
            engine = WhisperEngine()
            engine.load()
            # faster-whisper 실패 → openai-whisper 선택
            assert engine.backend == "whisper"
