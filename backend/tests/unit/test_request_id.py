"""
SPEC-OPS-001 Request ID 미들웨어 단위 테스트
REQ-OPS-005: 모든 HTTP 요청에 UUID Request ID 부여, X-Request-ID 응답 헤더 포함
REQ-OPS-006: 모든 로그 항목에 Request ID 포함
REQ-OPS-007: 클라이언트가 X-Request-ID 헤더 제공 시 해당 ID 사용
"""

import re
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def app_with_request_id():
    """Request ID 미들웨어가 적용된 테스트 앱"""
    from backend.app.middleware.request_id import RequestIDMiddleware

    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/test")
    async def test_route():
        return {"message": "ok"}

    @app.post("/test")
    async def test_post_route():
        return {"message": "created"}

    return TestClient(app)


# ---------------------------------------------------------------------------
# REQ-OPS-005: UUID Request ID 자동 부여
# ---------------------------------------------------------------------------


class TestRequestIDAssignment:
    """모든 요청에 UUID Request ID 자동 부여 테스트"""

    def test_response_contains_x_request_id_header(self, app_with_request_id):
        """REQ-OPS-005: 응답에 X-Request-ID 헤더 포함"""
        response = app_with_request_id.get("/test")
        assert "x-request-id" in response.headers

    def test_request_id_is_valid_uuid(self, app_with_request_id):
        """REQ-OPS-005: 부여된 Request ID가 유효한 UUID 형식"""
        response = app_with_request_id.get("/test")
        request_id = response.headers["x-request-id"]
        # UUID 형식 검증 (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        assert uuid_pattern.match(request_id), f"유효하지 않은 UUID 형식: {request_id}"

    def test_each_request_gets_unique_id(self, app_with_request_id):
        """REQ-OPS-005: 요청마다 고유한 Request ID 부여"""
        response1 = app_with_request_id.get("/test")
        response2 = app_with_request_id.get("/test")
        id1 = response1.headers["x-request-id"]
        id2 = response2.headers["x-request-id"]
        assert id1 != id2, "각 요청은 다른 Request ID를 가져야 함"

    def test_request_id_present_on_post_requests(self, app_with_request_id):
        """REQ-OPS-005: POST 요청에도 X-Request-ID 헤더 포함"""
        response = app_with_request_id.post("/test")
        assert "x-request-id" in response.headers

    def test_request_id_present_on_404_response(self):
        """REQ-OPS-005: 404 응답에도 X-Request-ID 헤더 포함"""
        from backend.app.middleware.request_id import RequestIDMiddleware

        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)
        client = TestClient(app)

        response = client.get("/nonexistent", follow_redirects=False)
        assert "x-request-id" in response.headers


# ---------------------------------------------------------------------------
# REQ-OPS-007: 클라이언트 제공 X-Request-ID 사용
# ---------------------------------------------------------------------------


class TestClientProvidedRequestID:
    """클라이언트 제공 Request ID 사용 테스트"""

    def test_uses_client_provided_request_id(self, app_with_request_id):
        """REQ-OPS-007: 클라이언트가 X-Request-ID 제공 시 해당 ID 사용"""
        client_id = str(uuid.uuid4())
        response = app_with_request_id.get(
            "/test", headers={"X-Request-ID": client_id}
        )
        assert response.headers["x-request-id"] == client_id

    def test_generates_new_id_when_client_does_not_provide(self, app_with_request_id):
        """REQ-OPS-007: 클라이언트가 X-Request-ID 미제공 시 새 UUID 생성"""
        response = app_with_request_id.get("/test")
        request_id = response.headers["x-request-id"]
        # UUID 형식인지 확인 (자동 생성된 ID)
        assert len(request_id) > 0
        try:
            uuid.UUID(request_id)
        except ValueError:
            pytest.fail(f"유효하지 않은 UUID: {request_id}")

    def test_client_provided_non_uuid_id_is_used(self, app_with_request_id):
        """REQ-OPS-007: 클라이언트가 비-UUID 형식 ID 제공 시에도 해당 ID 사용"""
        custom_id = "custom-trace-id-12345"
        response = app_with_request_id.get(
            "/test", headers={"X-Request-ID": custom_id}
        )
        assert response.headers["x-request-id"] == custom_id


# ---------------------------------------------------------------------------
# REQ-OPS-006: 로그에 Request ID 포함
# ---------------------------------------------------------------------------


class TestRequestIDInLogs:
    """로그에 Request ID 포함 테스트"""

    def test_middleware_sets_request_id_in_context(self):
        """REQ-OPS-006: 미들웨어가 structlog context에 request_id 설정"""
        from structlog.contextvars import get_contextvars

        from backend.app.middleware.request_id import RequestIDMiddleware

        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        captured_context = {}

        @app.get("/context-test")
        async def context_test_route():
            # 요청 처리 중 contextvars에서 request_id 캡처
            ctx = get_contextvars()
            captured_context.update(ctx)
            return {"message": "ok"}

        client = TestClient(app)
        client.get("/context-test")

        assert "request_id" in captured_context, "structlog context에 request_id가 없음"

    def test_request_id_in_context_matches_response_header(self):
        """REQ-OPS-006: 로그 context의 request_id가 응답 헤더와 일치"""
        from structlog.contextvars import get_contextvars

        from backend.app.middleware.request_id import RequestIDMiddleware

        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        captured_context = {}

        @app.get("/context-match-test")
        async def context_match_test_route():
            ctx = get_contextvars()
            captured_context.update(ctx)
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/context-match-test")

        response_request_id = response.headers.get("x-request-id")
        context_request_id = captured_context.get("request_id")

        assert context_request_id == response_request_id
