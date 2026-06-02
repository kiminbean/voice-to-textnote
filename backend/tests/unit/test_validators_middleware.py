"""
SPEC-VALIDATORS-001: 경로 파라미터 유효성 검증 미들웨어 테스트
"""

import pytest
from starlette.requests import Request
from starlette.responses import Response

from backend.app.middleware.validators import PathValidationMiddleware

# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def validation_middleware() -> PathValidationMiddleware:
    """PathValidationMiddleware 인스턴스"""
    from backend.app.main import app

    # 기존 앱에서 이미 등록된 미들웨어를 가져옴니다
    for middleware in app.user_middleware:
        if isinstance(middleware, PathValidationMiddleware):
            return middleware

    # 등록되지 않았으면 새 인스턴스 생성
    return PathValidationMiddleware(app)


@pytest.fixture
def mock_request():
    """모의 Request 생성 헬퍼"""
    def _create_request(path: str) -> Request:
        scope = {
            "type": "http",
            "method": "GET",
            "path": path,
            "query_string": b"",
            "headers": [],
            "server": ("testserver", 80),
            "scheme": "http",
        }
        return Request(scope)
    return _create_request


# ---------------------------------------------------------------------------
# PathValidationMiddleware 테스트
# ---------------------------------------------------------------------------


class TestPathValidationMiddleware:
    """경로 검증 미들웨어 테스트"""

    async def test_pass_through_non_api_paths(self, validation_middleware, mock_request) -> None:
        """API 엔드포인트가 아닌 경로는 통과 (라인 40-41)"""
        from starlette.responses import Response

        request = mock_request("/health")
        call_next_called = False

        async def call_next(req):
            nonlocal call_next_called
            call_next_called = True
            return Response(content=b"OK", status_code=200)

        response = await validation_middleware.dispatch(request, call_next)

        assert call_next_called  # call_next가 호출되어야 함
        assert response.status_code == 200

    async def test_pass_known_segments(self, validation_middleware, mock_request) -> None:
        """알려진 세그먼트는 통과 (라인 46-48)"""
        from starlette.responses import Response

        request = mock_request("/api/v1/transcriptions/task-123/segments")
        call_next_called = False

        async def call_next(req):
            nonlocal call_next_called
            call_next_called = True
            return Response(content=b"OK", status_code=200)

        response = await validation_middleware.dispatch(request, call_next)

        assert call_next_called  # call_next가 호출되어야 함
        assert response.status_code == 200

    async def test_block_path_traversal_double_dot(self, validation_middleware, mock_request) -> None:
        """경로 탐색 패턴 차단 (.. 포함) - 라인 51-56"""
        request = mock_request("/api/v1/tasks/../etc/passwd")
        call_next_called = False

        async def call_next(req):
            nonlocal call_next_called
            call_next_called = True
            return Response(content=b"OK", status_code=200)

        response = await validation_middleware.dispatch(request, call_next)

        assert not call_next_called  # call_next가 호출되지 않아야 함
        assert response.status_code == 400
        assert "유효하지 않은 경로 파라미터입니다" in response.body.decode()

    async def test_block_path_traversal_slash(self, validation_middleware, mock_request) -> None:
        """경로 탐색 패턴 차단 (/ 포함) - 라인 51-56"""
        request = mock_request("/api/v1/tasks/secret/..config")
        call_next_called = False

        async def call_next(req):
            nonlocal call_next_called
            call_next_called = True
            return Response(content=b"OK", status_code=200)

        response = await validation_middleware.dispatch(request, call_next)

        assert not call_next_called
        assert response.status_code == 400

    async def test_block_path_traversal_backslash(self, validation_middleware, mock_request) -> None:
        """경로 탐색 패턴 차단 (\\ 포함) - 라인 51-56"""
        request = mock_request("/api/v1/tasks\\admin\\secret")
        call_next_called = False

        async def call_next(req):
            nonlocal call_next_called
            call_next_called = True
            return Response(content=b"OK", status_code=200)

        response = await validation_middleware.dispatch(request, call_next)

        assert not call_next_called
        assert response.status_code == 400

    async def test_block_segment_too_long(self, validation_middleware, mock_request) -> None:
        """세그먼트 길이 초과 차단 (128자 초과) - 라인 59-64"""
        long_segment = "a" * 129
        request = mock_request(f"/api/v1/tasks/{long_segment}")
        call_next_called = False

        async def call_next(req):
            nonlocal call_next_called
            call_next_called = True
            return Response(content=b"OK", status_code=200)

        response = await validation_middleware.dispatch(request, call_next)

        assert not call_next_called
        assert response.status_code == 400

    async def test_block_invalid_characters(self, validation_middleware, mock_request) -> None:
        """비정상 문자 포함 차단 - 라인 59-64"""
        request = mock_request("/api/v1/tasks/task@123#hash")
        call_next_called = False

        async def call_next(req):
            nonlocal call_next_called
            call_next_called = True
            return Response(content=b"OK", status_code=200)

        response = await validation_middleware.dispatch(request, call_next)

        assert not call_next_called
        assert response.status_code == 400

    async def test_pass_valid_task_id(self, validation_middleware, mock_request) -> None:
        """유효한 task_id 통과 - 라인 66"""
        request = mock_request("/api/v1/transcriptions/task-123")
        call_next_called = False

        async def call_next(req):
            nonlocal call_next_called
            call_next_called = True
            return Response(content=b"OK", status_code=200)

        response = await validation_middleware.dispatch(request, call_next)

        assert call_next_called
        assert response.status_code == 200

    async def test_pass_task_id_with_hyphen(self, validation_middleware, mock_request) -> None:
        """하이픈 포함 task_id 통과"""
        request = mock_request("/api/v1/transcriptions/task-123-456")
        call_next_called = False

        async def call_next(req):
            nonlocal call_next_called
            call_next_called = True
            return Response(content=b"OK", status_code=200)

        response = await validation_middleware.dispatch(request, call_next)

        assert call_next_called
        assert response.status_code == 200

    async def test_pass_task_id_with_underscore(self, validation_middleware, mock_request) -> None:
        """언더스코어 포함 task_id 통과"""
        request = mock_request("/api/v1/transcriptions/task_123_456")
        call_next_called = False

        async def call_next(req):
            nonlocal call_next_called
            call_next_called = True
            return Response(content=b"OK", status_code=200)

        response = await validation_middleware.dispatch(request, call_next)

        assert call_next_called
        assert response.status_code == 200

    async def test_pass_max_length_segment(self, validation_middleware, mock_request) -> None:
        """최대 길이(128자) 세그먼트 통과"""
        max_segment = "a" * 128
        request = mock_request(f"/api/v1/tasks/{max_segment}")
        call_next_called = False

        async def call_next(req):
            nonlocal call_next_called
            call_next_called = True
            return Response(content=b"OK", status_code=200)

        response = await validation_middleware.dispatch(request, call_next)

        assert call_next_called
        assert response.status_code == 200
