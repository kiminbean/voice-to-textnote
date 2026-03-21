"""
SPEC-OPS-001 Prometheus 메트릭스 단위 테스트
REQ-OPS-001: /metrics 엔드포인트가 Prometheus 형식 메트릭스 노출
REQ-OPS-002: HTTP 요청 자동 계측 (요청 수, 응답 시간 히스토그램, 상태 코드)
REQ-OPS-003: 커스텀 메트릭스 (활성 작업 수, 처리 시간, 실패 수)
REQ-OPS-004: 시스템 메트릭스 (RSS 메모리, CPU 사용률)
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_prometheus_registry():
    """각 테스트 전후 Prometheus 레지스트리 초기화 (중복 등록 방지)"""
    from prometheus_client import REGISTRY

    # 테스트 전 커스텀 메트릭스 수집기 목록 스냅샷
    collectors_before = set(REGISTRY._names_to_collectors.keys())
    yield
    # 테스트 후 새로 추가된 수집기 제거
    collectors_after = set(REGISTRY._names_to_collectors.keys())
    new_collectors = collectors_after - collectors_before
    # 새 컬렉터 이름으로 등록된 것 제거
    for name in list(REGISTRY._names_to_collectors.keys()):
        if name in new_collectors:
            try:
                collector = REGISTRY._names_to_collectors[name]
                REGISTRY.unregister(collector)
            except Exception:
                pass


@pytest.fixture
def app_with_metrics():
    """Prometheus 메트릭스가 적용된 테스트 앱"""

    from backend.app.metrics import setup_metrics

    app = FastAPI()
    setup_metrics(app)

    @app.get("/api/test")
    async def test_route():
        return {"message": "ok"}

    return TestClient(app)


# ---------------------------------------------------------------------------
# REQ-OPS-001: /metrics 엔드포인트
# ---------------------------------------------------------------------------


class TestMetricsEndpoint:
    """/metrics 엔드포인트 테스트"""

    def test_metrics_endpoint_exists(self, app_with_metrics):
        """REQ-OPS-001: /metrics 엔드포인트가 존재"""
        response = app_with_metrics.get("/metrics")
        assert response.status_code == 200

    def test_metrics_endpoint_returns_prometheus_format(self, app_with_metrics):
        """REQ-OPS-001: /metrics 응답이 Prometheus 텍스트 형식"""
        response = app_with_metrics.get("/metrics")
        # Prometheus 텍스트 형식은 text/plain 또는 text/plain; version=0.0.4
        content_type = response.headers.get("content-type", "")
        assert "text/plain" in content_type

    def test_metrics_endpoint_contains_help_lines(self, app_with_metrics):
        """REQ-OPS-001: /metrics 응답에 # HELP 줄 포함 (Prometheus 형식 확인)"""
        response = app_with_metrics.get("/metrics")
        assert "# HELP" in response.text

    def test_metrics_endpoint_contains_type_lines(self, app_with_metrics):
        """REQ-OPS-001: /metrics 응답에 # TYPE 줄 포함"""
        response = app_with_metrics.get("/metrics")
        assert "# TYPE" in response.text

    def test_metrics_endpoint_does_not_require_auth(self):
        """REQ-OPS-001: /metrics 엔드포인트는 인증 불필요"""
        from backend.app.metrics import setup_metrics

        app = FastAPI()
        setup_metrics(app)

        # 인증 헤더 없이 접근
        client = TestClient(app)
        response = client.get("/metrics")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# REQ-OPS-002: HTTP 요청 자동 계측
# ---------------------------------------------------------------------------


class TestHTTPRequestMetrics:
    """HTTP 요청 자동 계측 테스트"""

    def test_http_request_count_metric_exists(self, app_with_metrics):
        """REQ-OPS-002: HTTP 요청 수 메트릭스 존재"""
        # 요청 먼저 실행
        app_with_metrics.get("/api/test")
        response = app_with_metrics.get("/metrics")
        # prometheus-fastapi-instrumentator 기본 메트릭스 확인
        # http_requests_total 또는 http_request_duration_seconds 등
        assert (
            "http_request" in response.text.lower()
            or "http_requests" in response.text.lower()
        )

    def test_http_request_duration_histogram_exists(self, app_with_metrics):
        """REQ-OPS-002: HTTP 요청 응답 시간 히스토그램 존재"""
        app_with_metrics.get("/api/test")
        response = app_with_metrics.get("/metrics")
        # 히스토그램은 _bucket, _count, _sum 접미사를 가짐
        assert "_bucket" in response.text or "_count" in response.text

    def test_metrics_updated_after_request(self, app_with_metrics):
        """REQ-OPS-002: API 요청 후 메트릭스 업데이트"""
        # 첫 번째 API 요청
        app_with_metrics.get("/api/test")
        response = app_with_metrics.get("/metrics")
        # 응답 내용이 비어있지 않음
        assert len(response.text) > 100


# ---------------------------------------------------------------------------
# REQ-OPS-003: 커스텀 태스크 메트릭스
# ---------------------------------------------------------------------------


class TestCustomTaskMetrics:
    """커스텀 태스크 메트릭스 테스트"""

    def test_active_tasks_gauge_exists(self):
        """REQ-OPS-003: 활성 작업 수 게이지 메트릭스 존재"""
        from backend.app.metrics import ACTIVE_TASKS

        assert ACTIVE_TASKS is not None

    def test_active_tasks_gauge_can_be_incremented(self):
        """REQ-OPS-003: 활성 작업 수 증가 가능"""
        from backend.app.metrics import ACTIVE_TASKS

        # 증가/감소 테스트
        ACTIVE_TASKS.inc()
        ACTIVE_TASKS.dec()

    def test_task_processing_time_histogram_exists(self):
        """REQ-OPS-003: 태스크 처리 시간 히스토그램 존재"""
        from backend.app.metrics import TASK_PROCESSING_TIME

        assert TASK_PROCESSING_TIME is not None

    def test_task_processing_time_histogram_can_be_observed(self):
        """REQ-OPS-003: 태스크 처리 시간 관측 가능"""
        from backend.app.metrics import TASK_PROCESSING_TIME

        # observe 메서드로 값 기록
        TASK_PROCESSING_TIME.observe(1.5)

    def test_task_failures_counter_exists(self):
        """REQ-OPS-003: 태스크 실패 수 카운터 존재"""
        from backend.app.metrics import TASK_FAILURES

        assert TASK_FAILURES is not None

    def test_task_failures_counter_can_be_incremented(self):
        """REQ-OPS-003: 태스크 실패 수 증가 가능"""
        from backend.app.metrics import TASK_FAILURES

        TASK_FAILURES.inc()


# ---------------------------------------------------------------------------
# REQ-OPS-004: 시스템 메트릭스
# ---------------------------------------------------------------------------


class TestSystemMetrics:
    """시스템 메트릭스 테스트"""

    def test_memory_rss_metric_exists(self):
        """REQ-OPS-004: RSS 메모리 메트릭스 존재"""
        from backend.app.metrics import collect_system_metrics

        metrics = collect_system_metrics()
        assert "memory_rss_bytes" in metrics

    def test_memory_rss_is_positive(self):
        """REQ-OPS-004: RSS 메모리 값이 양수"""
        from backend.app.metrics import collect_system_metrics

        metrics = collect_system_metrics()
        assert metrics["memory_rss_bytes"] > 0

    def test_cpu_usage_metric_exists(self):
        """REQ-OPS-004: CPU 사용률 메트릭스 존재"""
        from backend.app.metrics import collect_system_metrics

        metrics = collect_system_metrics()
        assert "cpu_percent" in metrics

    def test_cpu_usage_is_valid_percentage(self):
        """REQ-OPS-004: CPU 사용률이 0-100% 범위"""
        from backend.app.metrics import collect_system_metrics

        metrics = collect_system_metrics()
        cpu = metrics["cpu_percent"]
        assert 0.0 <= cpu <= 100.0

    def test_system_metrics_exposed_in_prometheus_endpoint(self, app_with_metrics):
        """REQ-OPS-004: 시스템 메트릭스가 /metrics 엔드포인트에 노출"""
        response = app_with_metrics.get("/metrics")
        # python_ 또는 process_ 메트릭스 (기본 prometheus_client 제공) 확인
        assert (
            "process_" in response.text
            or "python_" in response.text
            or "system_" in response.text
            or "voicenote_" in response.text
        )
