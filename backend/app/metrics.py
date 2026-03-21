"""
Prometheus 메트릭스 설정
REQ-OPS-001: /metrics 엔드포인트 노출
REQ-OPS-002: HTTP 요청 자동 계측 (prometheus-fastapi-instrumentator)
REQ-OPS-003: 커스텀 태스크 메트릭스 (활성 작업 수, 처리 시간, 실패 수)
REQ-OPS-004: 시스템 메트릭스 (RSS 메모리, CPU 사용률)
"""

import psutil
from fastapi import FastAPI
from prometheus_client import Counter, Gauge, Histogram
from prometheus_client import registry as prom_registry
from prometheus_fastapi_instrumentator import Instrumentator


def _get_or_create_metric(metric_class, name: str, documentation: str, **kwargs):
    """
    이미 등록된 메트릭스를 반환하거나 새로 생성

    Prometheus 레지스트리 중복 등록 방지
    (테스트 환경에서 여러 앱 인스턴스 생성 시 발생할 수 있는 문제 해결)
    """
    existing = prom_registry.REGISTRY._names_to_collectors.get(name)
    if existing is not None:
        return existing
    return metric_class(name, documentation, **kwargs)


# ---------------------------------------------------------------------------
# REQ-OPS-003: 커스텀 태스크 메트릭스
# ---------------------------------------------------------------------------

# 현재 처리 중인 활성 태스크 수
ACTIVE_TASKS: Gauge = _get_or_create_metric(
    Gauge,
    "voicenote_active_tasks_total",
    "현재 처리 중인 활성 태스크 수",
)

# 태스크 처리 시간 히스토그램 (초 단위)
TASK_PROCESSING_TIME: Histogram = _get_or_create_metric(
    Histogram,
    "voicenote_task_processing_seconds",
    "태스크 처리 소요 시간 (초)",
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)

# 태스크 실패 카운터
TASK_FAILURES: Counter = _get_or_create_metric(
    Counter,
    "voicenote_task_failures_total",
    "태스크 처리 실패 총 횟수",
)


# ---------------------------------------------------------------------------
# REQ-OPS-004: 시스템 메트릭스 수집 함수
# ---------------------------------------------------------------------------


def collect_system_metrics() -> dict:
    """
    현재 프로세스의 시스템 메트릭스 수집

    Returns:
        dict: memory_rss_bytes, cpu_percent 포함하는 딕셔너리
    """
    process = psutil.Process()

    # RSS 메모리 사용량 (바이트)
    memory_info = process.memory_info()
    memory_rss_bytes = memory_info.rss

    # CPU 사용률 (%, interval=None이면 비차단 방식으로 즉시 반환)
    cpu_percent = process.cpu_percent(interval=None)

    return {
        "memory_rss_bytes": memory_rss_bytes,
        "cpu_percent": cpu_percent,
    }


# ---------------------------------------------------------------------------
# REQ-OPS-001/002: Prometheus 계측기 설정
# ---------------------------------------------------------------------------


def setup_metrics(app: FastAPI) -> Instrumentator:
    """
    FastAPI 앱에 Prometheus 메트릭스 설정

    REQ-OPS-001: /metrics 엔드포인트 노출 (인증 불필요)
    REQ-OPS-002: HTTP 요청 자동 계측

    중복 등록 방지: http_requests_inprogress 메트릭스가 이미 등록된 경우
    기존 계측기를 재사용하지 않고 inprogress 계측을 비활성화

    Args:
        app: FastAPI 애플리케이션 인스턴스

    Returns:
        Instrumentator: 설정된 계측기 인스턴스
    """
    # 이미 동일한 앱에 계측기가 적용됐는지 확인 (FastAPI state 활용)
    if getattr(app.state, "_metrics_setup_done", False):
        return getattr(app.state, "_instrumentator", None)

    # http_requests_inprogress 이미 등록된 경우 inprogress 비활성화
    inprogress_registered = "http_requests_inprogress" in prom_registry.REGISTRY._names_to_collectors

    instrumentator = Instrumentator(
        # 모든 엔드포인트 계측 (필터 없음)
        should_group_status_codes=False,
        should_ignore_untemplated=False,
        should_respect_env_var=False,
        # 중복 등록 방지: 이미 등록된 경우 inprogress 비활성화
        should_instrument_requests_inprogress=not inprogress_registered,
        excluded_handlers=[],
        inprogress_name="http_requests_inprogress",
        inprogress_labels=True,
    )

    # 앱에 계측기 적용
    instrumentator.instrument(app)

    # REQ-OPS-001: /metrics 엔드포인트 노출 (인증 없이 접근 가능)
    instrumentator.expose(app, endpoint="/metrics", include_in_schema=False)

    # 중복 호출 방지를 위한 상태 기록
    app.state._metrics_setup_done = True
    app.state._instrumentator = instrumentator

    return instrumentator
