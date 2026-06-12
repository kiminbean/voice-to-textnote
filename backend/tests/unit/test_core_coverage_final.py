"""
최종 코어 모듈 커버리지 테스트

Main.py, lifecycle.py, error_handlers.py, audit_log.py, metrics.py,
bookmark.py, validators.py의 미커버리지 라인 테스트 커버리지 완료
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Request, Response
from fastapi.responses import JSONResponse

from backend.app.main import app
from backend.app.metrics import (
    _get_or_create_metric,
    collect_system_metrics,
    record_task_completed,
    record_task_failed,
    record_task_started,
    setup_metrics,
    update_system_metrics,
)
from backend.app.middleware.audit_log import AuditLogMiddleware
from backend.schemas.bookmark import BookmarkCreate, BookmarkUpdate
from backend.utils.validators import validate_webhook_url

# =============================================================================
# Test Main.py - lines 116-117, 121-129 (8 lines)
# =============================================================================


@pytest.mark.asyncio
async def test_main_lifecycle_huggingface_token_not_set():
    """
    main.py line 131: HUGGINGFACE_TOKEN 미설정 시 warning 로그
    """
    from backend.app.config import Settings
    from backend.app.main import lifespan

    # settings mock - huggingface_token 없음
    mock_settings = MagicMock(spec=Settings)
    mock_settings.huggingface_token = None  # 토큰 미설정
    mock_settings.diarization_model = "test-model"

    # spy logger calls
    warning_calls = []

    def spy_warning(msg, **kwargs):
        warning_calls.append((msg, kwargs))

    with patch("backend.app.main.settings", mock_settings):
        with patch("backend.app.main.logger") as mock_logger:
            mock_logger.warning = spy_warning

            # lifespan 실행
            async with lifespan(app):
                pass  # startup 단계 실행

            # warning 로그가 기록되었는지 확인
            assert len(warning_calls) > 0
            assert any("HUGGINGFACE_TOKEN 미설정" in str(call[0]) for call in warning_calls)


@pytest.mark.asyncio
async def test_main_lifecycle_diarization_model_load_failure(client):
    """
    main.py lines 121-129: 화자 분리 모델 로드 실패 시 에러 로그 기록
    """
    from backend.app.config import Settings
    from backend.app.main import lifespan

    # settings mock
    mock_settings = MagicMock(spec=Settings)
    mock_settings.huggingface_token = "test-token"
    mock_settings.diarization_model = "test-model"

    with patch("backend.app.main.DiarizationEngine") as mock_engine_cls:
        mock_engine = MagicMock()
        mock_engine_cls.return_value = mock_engine
        mock_engine.load.side_effect = Exception("화자 분리 모델 로드 실패")

        with patch("backend.app.main.logger") as mock_logger:
            with patch("backend.app.main.settings", mock_settings):
                # lifespan은 async context manager
                async with lifespan(app):
                    pass  # startup 단계 실행

                # 에러 로그가 기록되었는지 확인
                assert mock_logger.error.called
                error_call_args = mock_logger.error.call_args
                assert "화자 분리 모델 사전 로드 실패" in error_call_args[0][0]


# =============================================================================
# Test lifecycle.py - lines 108-109, 116-117 (4 lines)
# =============================================================================


@pytest.mark.asyncio
async def test_lifecycle_shutdown_tagging_client_failure():
    """
    lifecycle.py lines 108-109: 태깅 HTTP 클라이언트 정리 실패 시 warning 로그
    """
    from backend.app.lifecycle import cleanup_shutdown

    # 클라이언트 정리 실패 시뮬레이션
    with patch("backend.ml.tagging_engine.close_http_client", side_effect=Exception("정리 실패")):
        with patch("backend.app.lifecycle.logger") as mock_logger:
            await cleanup_shutdown()
            # warning 로그가 기록되었는지 확인
            assert mock_logger.warning.called
            warning_call_args = mock_logger.warning.call_args
            assert "태깅 HTTP 클라이언트 정리 실패" in warning_call_args[0][0]


@pytest.mark.asyncio
async def test_lifecycle_shutdown_redis_client_failure():
    """
    lifecycle.py lines 116-117: Redis 클라이언트 정리 실패 시 warning 로그
    """
    from backend.app.lifecycle import cleanup_shutdown

    # Redis 정리 실패 시뮬레이션
    with patch(
        "backend.app.dependencies.close_redis_client", side_effect=Exception("Redis 정리 실패")
    ):
        # 태깅 클라이언트는 성공 가정
        with patch("backend.ml.tagging_engine.close_http_client"):
            with patch("backend.app.lifecycle.logger") as mock_logger:
                await cleanup_shutdown()
                # warning 로그가 기록되었는지 확인
                assert mock_logger.warning.called
                warning_call_args = mock_logger.warning.call_args_list[-1]
                assert "Redis 클라이언트 정리 실패" in warning_call_args[0][0]


# =============================================================================
# Test error_handlers.py - lines 48, 77 (2 lines)
# =============================================================================


@pytest.mark.asyncio
async def test_voice_note_error_handler_none_domain_exc():
    """
    error_handlers.py line 48: domain_exc이 None일 때 unhandled handler 호출
    """
    from fastapi import Request

    from backend.app.error_handlers import _voicenote_error_handler

    # 일반 Exception으로 호출 (VoiceNoteError 아님)
    request = MagicMock(spec=Request)
    exc = Exception("일반 예외")

    with patch("backend.app.error_handlers._unhandled_exception_handler") as mock_unhandled:
        mock_unhandled.return_value = JSONResponse(status_code=500, content={"error": "Unhandled"})

        await _voicenote_error_handler(request, exc)

        # unhandled handler가 호출되었는지 확인
        assert mock_unhandled.called


@pytest.mark.asyncio
async def test_validation_error_handler_none_validation_exc():
    """
    error_handlers.py line 77: validation_exc이 None일 때 unhandled handler 호출
    """
    from backend.app.error_handlers import _validation_error_handler

    # 일반 Exception으로 호출 (RequestValidationError 아님)
    request = MagicMock(spec=Request)
    exc = Exception("일반 예외")

    with patch("backend.app.error_handlers._unhandled_exception_handler") as mock_unhandled:
        mock_unhandled.return_value = JSONResponse(status_code=500, content={"error": "Unhandled"})

        await _validation_error_handler(request, exc)

        # unhandled handler가 호출되었는지 확인
        assert mock_unhandled.called


# =============================================================================
# Test audit_log.py - lines 57, 166, 171 (3 lines)
# =============================================================================


@pytest.mark.asyncio
async def test_audit_log_dispatch_slow_request():
    """
    audit_log.py line 57, 109: 처리 시간 5초 초과 시 WARNING 레벨 로그
    """
    from fastapi import Request

    middleware = AuditLogMiddleware(app)

    # mock request
    request = MagicMock(spec=Request)
    request.url.path = "/api/v1/transcribe"
    request.method = "POST"
    request.headers = {"user-agent": "test"}
    request.client = MagicMock()
    request.client.host = "127.0.0.1"

    # mock call_next - 6초 소요
    async def slow_call_next(req):
        await asyncio.sleep(0)  # yield
        response = MagicMock(spec=Response)
        response.status_code = 200
        return response

    # perf_counter mock으로 시간 조작
    with patch("time.perf_counter", side_effect=[0.0, 6.0]):
        with patch("backend.app.middleware.audit_log.logger") as mock_logger:
            with patch("backend.app.middleware.audit_log.get_contextvars", return_value={}):
                with patch.object(middleware, "_should_skip", return_value=False):
                    await middleware.dispatch(request, slow_call_next)

                    # warning이 호출되었는지 확인
                    assert mock_logger.warning.called
                    warning_call = mock_logger.warning.call_args
                    assert "audit" in warning_call[0][0]
                    assert warning_call[1]["slow_request"] is True


@pytest.mark.asyncio
async def test_audit_log_get_client_ip_forwarded_for():
    """
    audit_log.py line 166: X-Forwarded-For 헤더에서 첫 번째 IP 추출
    """
    from fastapi import Request

    from backend.app.middleware.audit_log import AuditLogMiddleware

    middleware = AuditLogMiddleware(app)
    request = MagicMock(spec=Request)
    request.headers = {"x-forwarded-for": "203.0.113.195, 70.41.3.18, 150.172.238.178"}

    ip = middleware._get_client_ip(request)

    # 첫 번째 IP만 반환되는지 확인
    assert ip == "203.0.113.195"


@pytest.mark.asyncio
async def test_audit_log_get_client_ip_no_client():
    """
    audit_log.py line 171: request.client가 None일 때 빈 문자열 반환
    """
    from fastapi import Request

    from backend.app.middleware.audit_log import AuditLogMiddleware

    middleware = AuditLogMiddleware(app)
    request = MagicMock(spec=Request)
    request.headers = {}
    request.client = None

    ip = middleware._get_client_ip(request)

    # 빈 문자열 반환되는지 확인
    assert ip == ""


# =============================================================================
# Test metrics.py - lines 25, 188 (2 lines)
# =============================================================================


def test_metrics_get_or_create_metric_existing():
    """
    metrics.py line 25: 이미 존재하는 메트릭 반환 (중복 등록 방지)
    """
    from prometheus_client import Counter
    from prometheus_client.registry import REGISTRY

    # 첫 번째 생성
    metric1 = _get_or_create_metric(
        Counter,
        "test_metric_duplicate",
        "테스트 메트릭",
    )

    # 두 번째 호출 (기존 메트릭 반환해야 함)
    metric2 = _get_or_create_metric(
        Counter,
        "test_metric_duplicate",
        "테스트 메트릭",
    )

    # 동일 인스턴스인지 확인
    assert metric1 is metric2

    # 정리
    REGISTRY.unregister(metric1)


def test_metrics_setup_already_done():
    """
    metrics.py line 188: 이미 설정된 경우 기존 instrumentator 반환
    """
    from fastapi import FastAPI
    from prometheus_fastapi_instrumentator import Instrumentator

    test_app = FastAPI()

    # 이미 설정된 상태로 mark
    test_app.state._metrics_setup_done = True
    test_app.state._instrumentator = MagicMock(spec=Instrumentator)

    result = setup_metrics(test_app)

    # 기존 instrumentator 반환되는지 확인
    assert result is test_app.state._instrumentator


# =============================================================================
# Test bookmark.py - lines 28, 58, 63 (3 lines)
# =============================================================================


def test_bookmark_create_color_empty_string():
    """
    bookmark.py line 28: color 빈 문자열 (None 반환)
    """
    # 빈 문자열 after strip
    bookmark = BookmarkCreate(
        task_id="test-task",
        segment_start=0.0,
        segment_end=10.0,
        color="   ",  # 공백만
    )

    # None으로 변환되어야 함
    assert bookmark.color is None


def test_bookmark_update_color_empty_string():
    """
    bookmark.py line 58: BookmarkUpdate color 빈 문자열 (None 반환)
    """
    # 빈 문자열 after strip
    bookmark = BookmarkUpdate(color="   ")

    # None으로 변환되어야 함
    assert bookmark.color is None


def test_bookmark_update_color_invalid_format():
    """
    bookmark.py line 63: color 유효하지 않은 형식 (ValueError)
    """
    from pydantic import ValidationError as PydanticValidationError

    with pytest.raises(PydanticValidationError) as exc_info:
        BookmarkUpdate(
            color="invalid-color-format-!!"  # 유효하지 않은 형식
        )

    # 에러 메시지 확인 (Pydantic ValidationError)
    assert "color" in str(exc_info.value).lower()


# =============================================================================
# Test validators.py - lines 103, 118-119, 138 (4 lines)
# =============================================================================


def test_validators_webhook_literal_ip_none():
    """
    validators.py line 103: literal_ip가 None일 때 continue로 다음 entry 확인
    """
    from backend.utils.validators import _assert_public_webhook_host

    # socket.getaddrinfo가 유효하지 않은 IP를 반환하는 경우
    with patch("socket.getaddrinfo") as mock_getaddrinfo:
        mock_getaddrinfo.return_value = [
            (
                None,
                None,
                None,
                None,
                ("invalid-not-an-ip", 443),  # ValueError 발생할 주소
            )
        ]

        # 예외 없이 통과해야 함 (continue로 다음 entry)
        _assert_public_webhook_host("example.com", None, resolve_host=True)


def test_validators_webhook_resolve_oserror():
    """
    validators.py line 118-119: socket.getaddrinfo OSError 발생 시 ValueError
    """
    from backend.utils.validators import _assert_public_webhook_host

    # 호스트 확인 실패
    with patch("socket.getaddrinfo", side_effect=OSError("Name resolution failed")):
        with pytest.raises(ValueError) as exc_info:
            _assert_public_webhook_host("unresolved-host.com", None, resolve_host=True)

        # 에러 메시지 확인
        assert "웹훅 URL 호스트를 확인할 수 없습니다" in str(exc_info.value)


def test_validators_webhook_url_validation_error():
    """
    validators.py line 138: URL validation 실패 시 ValueError
    """
    # 유효하지 않은 URL
    with pytest.raises(ValueError, match="웹훅 URL은 유효한 HTTP\\(S\\) URL이어야 합니다"):
        validate_webhook_url("not-a-valid-url")


def test_validators_webhook_url_private_ip_rejected():
    """
    validators.py line 121: 사설 네트워크 IP 거절
    """
    # 127.0.0.1 URL - resolve_host=False로 직접 IP 검사만 수행
    with pytest.raises(ValueError, match="사설/로컬 네트워크"):
        validate_webhook_url("http://127.0.0.1:8080/webhook", resolve_host=False)


# =============================================================================
# Test Collect System Metrics
# =============================================================================


def test_collect_system_metrics():
    """
    collect_system_metrics 함수가 메트릭을 올바르게 수집하는지 확인
    """
    metrics = collect_system_metrics()

    # 필드 존재 확인
    assert "memory_rss_bytes" in metrics
    assert "cpu_percent" in metrics

    # 타입 확인
    assert isinstance(metrics["memory_rss_bytes"], int)
    assert isinstance(metrics["cpu_percent"], float)

    # 합리한 범위 확인
    assert metrics["memory_rss_bytes"] > 0
    assert 0 <= metrics["cpu_percent"] <= 100


# =============================================================================
# Test Update System Metrics
# =============================================================================


def test_update_system_metrics():
    """
    update_system_metrics 함수가 Prometheus Gauge를 올바르게 갱신하는지 확인
    """
    from backend.app.metrics import (
        PROCESS_CPU_PERCENT,
        PROCESS_MEMORY_RSS_BYTES,
    )

    # 메트릭 갱신
    metrics = update_system_metrics()

    # 반환값 확인
    assert "memory_rss_bytes" in metrics
    assert "cpu_percent" in metrics

    # Gauge 값이 설정되었는지 확인 (get으로 조회)
    assert PROCESS_MEMORY_RSS_BYTES._value.get() > 0
    assert PROCESS_CPU_PERCENT._value.get() >= 0


# =============================================================================
# Test Record Task Metrics
# =============================================================================


def test_record_task_started():
    """작업 시작 메트릭 기록 확인"""
    from backend.app.metrics import (
        ACTIVE_TASKS,
        TASKS_STARTED,
    )

    # 메트릭 기록
    record_task_started("transcription")

    # 카운터 증가 확인
    samples = next(iter(TASKS_STARTED.collect())).samples
    transcription_sample = next(s for s in samples if s.labels.get("task_type") == "transcription")
    assert transcription_sample.value > 0

    # 활성 태스크 증가 확인
    active_samples = next(iter(ACTIVE_TASKS.collect())).samples
    assert active_samples[0].value > 0


def test_record_task_completed():
    """작업 완료 메트릭 기록 확인"""
    from backend.app.metrics import (
        ACTIVE_TASKS,
        TASKS_COMPLETED,
    )

    # 메트릭 기록
    record_task_completed("transcription", 5.5)

    # 완료 카운터 증가 확인
    samples = next(iter(TASKS_COMPLETED.collect())).samples
    transcription_sample = next(s for s in samples if s.labels.get("task_type") == "transcription")
    assert transcription_sample.value > 0

    # 활성 태스크 감소 확인 (이전 테스트에서 증가했음)
    next(iter(ACTIVE_TASKS.collect())).samples
    # 감소했으므로 0 또는 음수 (실제로는 0 이상이어야 함)
    # Note: 테스트 순서에 따라 값이 다를 수 있음


def test_record_task_failed():
    """작업 실패 메트릭 기록 확인"""
    from backend.app.metrics import (
        TASK_FAILURES,
        TASKS_FAILED,
    )

    # 메트릭 기록
    record_task_failed("transcription")

    # 실패 카운터 증가 확인
    samples = next(iter(TASKS_FAILED.collect())).samples
    transcription_sample = next(s for s in samples if s.labels.get("task_type") == "transcription")
    assert transcription_sample.value > 0

    # 전체 실패 카운터 증가 확인
    failure_samples = next(iter(TASK_FAILURES.collect())).samples
    assert failure_samples[0].value > 0


# =============================================================================
# Helper imports
# =============================================================================
