"""
SPEC-EXPORT-001: Export API 단위 테스트 (TDD RED 단계)

테스트 대상: GET /api/v1/export/pdf/{minutes_task_id}
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.error_handlers import register_exception_handlers
from backend.app.middleware.auth import verify_api_key

# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_minutes_data() -> dict:
    """유효한 회의록 Redis 데이터"""
    return {
        "task_id": "minutes-task-001",
        "segments": [
            {
                "speaker_name": "김팀장",
                "text": "안녕하세요, 오늘 회의를 시작하겠습니다.",
                "start": 0.0,
                "end": 5.0,
            },
            {
                "speaker_name": "이개발",
                "text": "네, 준비됐습니다.",
                "start": 5.5,
                "end": 8.0,
            },
        ],
        "speakers": [
            {
                "speaker_name": "김팀장",
                "total_speaking_time": 120.0,
                "segment_count": 15,
                "speaking_ratio": 60.0,
            }
        ],
        "total_duration": 200.0,
        "total_speakers": 1,
        "markdown": "# 회의록",
        "created_at": "2026-03-22T14:00:00",
        "completed_at": "2026-03-22T14:05:00",
    }


@pytest.fixture
def valid_summary_data() -> dict:
    """유효한 요약 Redis 데이터"""
    return {
        "task_id": "summary-task-001",
        "summary_text": "회의 요약 텍스트입니다.",
        "action_items": [
            {
                "assignee": "김팀장",
                "task": "보고서 작성",
                "deadline": "2026-03-25",
                "priority": "high",
            }
        ],
        "key_decisions": ["결정 사항 1"],
        "next_steps": ["다음 단계 1"],
    }


@pytest.fixture
def incomplete_minutes_data() -> dict:
    """segments가 빈 회의록 데이터 (422 케이스)"""
    return {
        "task_id": "minutes-task-incomplete",
        "segments": [],  # 빈 segments
        "speakers": [],
        "total_duration": 0.0,
        "total_speakers": 0,
        "markdown": "",
        "created_at": "2026-03-22T14:00:00",
        "completed_at": "2026-03-22T14:00:00",
    }


def _make_export_app(mock_redis: AsyncMock) -> FastAPI:
    """
    테스트용 FastAPI 앱 생성

    인증 미들웨어를 우회하고 Redis를 mock으로 교체합니다.
    """
    from backend.app.api.v1 import export
    from backend.app.dependencies import get_db_session, get_redis_client

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(export.router, prefix="/api/v1")

    # Redis mock 주입
    async def override_redis():
        return mock_redis

    # DB 세션 mock 주입
    async def override_db():
        db_mock = AsyncMock()
        # DB 폴백에서 None 반환 (Redis 히트 시나리오)
        from unittest.mock import MagicMock
        result_mock = MagicMock()
        result_mock.scalars.return_value.first.return_value = None
        db_mock.execute.return_value = result_mock
        yield db_mock

    # 인증 우회
    async def override_auth():
        return "test-bypass"

    app.dependency_overrides[get_redis_client] = override_redis
    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[verify_api_key] = override_auth

    return app


# ---------------------------------------------------------------------------
# Export API 테스트
# ---------------------------------------------------------------------------


class TestExportPdfApi:
    """Export PDF API 테스트 스위트"""

    def test_export_pdf_success(self, valid_minutes_data: dict) -> None:
        """
        REQ-EXPORT-010: Redis에 유효한 회의록 데이터가 있으면 200 + application/pdf 반환
        """
        mock_redis = AsyncMock()
        # Redis에서 회의록 데이터 반환
        mock_redis.get.return_value = json.dumps(valid_minutes_data)

        app = _make_export_app(mock_redis)
        client = TestClient(app)

        response = client.get("/api/v1/export/pdf/minutes-task-001")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        # PDF 시그니처 확인
        assert response.content[:5] == b"%PDF-"

    def test_export_pdf_not_found(self) -> None:
        """
        REQ-EXPORT-011: Redis와 DB 모두에 데이터가 없으면 404 반환
        """
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # Redis 미스

        app = _make_export_app(mock_redis)

        # DB도 None 반환하도록 override 재설정
        from backend.app.dependencies import get_db_session

        async def override_db_none():
            db_mock = AsyncMock()
            result_mock = MagicMock()
            result_mock.scalars.return_value.first.return_value = None
            db_mock.execute.return_value = result_mock
            yield db_mock

        app.dependency_overrides[get_db_session] = override_db_none

        client = TestClient(app)
        response = client.get("/api/v1/export/pdf/nonexistent-task-id")

        assert response.status_code == 404

    def test_export_pdf_incomplete_data(self, incomplete_minutes_data: dict) -> None:
        """
        REQ-EXPORT-012: segments가 비어있으면 422 반환
        """
        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(incomplete_minutes_data)

        app = _make_export_app(mock_redis)
        client = TestClient(app)

        response = client.get("/api/v1/export/pdf/minutes-task-incomplete")

        assert response.status_code == 422

    def test_export_pdf_content_disposition_header(self, valid_minutes_data: dict) -> None:
        """
        REQ-EXPORT-013: 응답 헤더에 Content-Disposition이 attachment로 설정되어야 함
        파일명에 minutes_{task_id}.pdf 형식이 포함되어야 함
        """
        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(valid_minutes_data)

        app = _make_export_app(mock_redis)
        client = TestClient(app)

        task_id = "minutes-task-001"
        response = client.get(f"/api/v1/export/pdf/{task_id}")

        assert response.status_code == 200
        content_disposition = response.headers.get("content-disposition", "")
        assert "attachment" in content_disposition
        assert f"minutes_{task_id}.pdf" in content_disposition

    def test_export_pdf_with_summary(
        self, valid_minutes_data: dict, valid_summary_data: dict
    ) -> None:
        """
        REQ-EXPORT-014: summary_task_id 쿼리 파라미터가 있으면 요약 포함 PDF 생성
        요약 없는 경우보다 PDF 크기가 커야 함
        """
        # 첫 번째 요청: 요약 없는 PDF
        mock_redis_no_summary = AsyncMock()
        mock_redis_no_summary.get.return_value = json.dumps(valid_minutes_data)

        app = _make_export_app(mock_redis_no_summary)
        client_no_summary = TestClient(app)
        response_no_summary = client_no_summary.get("/api/v1/export/pdf/minutes-task-001")
        assert response_no_summary.status_code == 200

        # 두 번째 요청: 요약 포함 PDF
        def redis_side_effect(key: str) -> str | None:
            """Redis 키에 따라 다른 데이터 반환"""
            if "min:result" in key:
                return json.dumps(valid_minutes_data)
            if "sum:result" in key:
                return json.dumps(valid_summary_data)
            return None

        mock_redis_with_summary = AsyncMock()
        mock_redis_with_summary.get.side_effect = redis_side_effect

        app_with_summary = _make_export_app(mock_redis_with_summary)
        client_with_summary = TestClient(app_with_summary)
        response_with_summary = client_with_summary.get(
            "/api/v1/export/pdf/minutes-task-001?summary_task_id=summary-task-001"
        )
        assert response_with_summary.status_code == 200

        # 요약 포함 PDF가 더 커야 함
        assert len(response_with_summary.content) > len(response_no_summary.content), (
            "요약 포함 PDF가 요약 없는 PDF보다 커야 함"
        )

    def test_export_pdf_without_summary(self, valid_minutes_data: dict) -> None:
        """
        REQ-EXPORT-015: summary_task_id 없이도 PDF 생성 성공
        """
        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(valid_minutes_data)

        app = _make_export_app(mock_redis)
        client = TestClient(app)

        # summary_task_id 없이 요청
        response = client.get("/api/v1/export/pdf/minutes-task-001")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content[:5] == b"%PDF-"

    def test_export_pdf_db_fallback_hit(self, valid_minutes_data: dict) -> None:
        """
        Redis 미스 후 DB 폴백에서 데이터를 찾으면 200 반환
        """
        from backend.app.api.v1 import export
        from backend.app.dependencies import get_db_session, get_redis_client
        from backend.app.middleware.auth import verify_api_key
        from backend.db.models import TaskResult

        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(export.router, prefix="/api/v1")

        # Redis: 항상 None 반환 (미스)
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        async def override_redis():
            return mock_redis

        # DB: 회의록 데이터 반환
        async def override_db_with_data():
            db_mock = AsyncMock()
            record_mock = MagicMock(spec=TaskResult)
            record_mock.result_data = valid_minutes_data
            result_mock = MagicMock()
            result_mock.scalars.return_value.first.return_value = record_mock
            db_mock.execute.return_value = result_mock
            yield db_mock

        async def override_auth():
            return "test-bypass"

        app.dependency_overrides[get_redis_client] = override_redis
        app.dependency_overrides[get_db_session] = override_db_with_data
        app.dependency_overrides[verify_api_key] = override_auth

        client = TestClient(app)
        response = client.get("/api/v1/export/pdf/minutes-task-001")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content[:5] == b"%PDF-"

    def test_export_pdf_summary_task_id_not_found(
        self, valid_minutes_data: dict
    ) -> None:
        """
        summary_task_id가 지정됐지만 데이터를 찾을 수 없으면
        요약 없이 PDF 생성 (200 반환, 경고 로그)
        """
        def redis_side_effect(key: str):
            # 회의록은 반환, 요약은 None
            if "min:result" in key:
                return json.dumps(valid_minutes_data)
            return None

        mock_redis = AsyncMock()
        mock_redis.get.side_effect = redis_side_effect

        app = _make_export_app(mock_redis)
        client = TestClient(app)

        # summary_task_id가 있지만 데이터 없음
        response = client.get(
            "/api/v1/export/pdf/minutes-task-001?summary_task_id=nonexistent-summary"
        )

        # 요약 없이도 PDF 생성 성공
        assert response.status_code == 200
        assert response.content[:5] == b"%PDF-"

    def test_export_pdf_pdf_generation_error(self) -> None:
        """
        PDF 생성 중 예외 발생 시 500 반환
        (MinutesPDFGenerator.generate가 예외를 던지는 경우)
        """
        from unittest.mock import patch

        minutes_with_segments = {
            "task_id": "minutes-error-test",
            "segments": [{"speaker_name": "테스트", "text": "테스트", "start": 0.0, "end": 1.0}],
            "speakers": [],
            "total_duration": 1.0,
            "total_speakers": 0,
            "markdown": "",
            "created_at": "2026-03-22T14:00:00",
        }

        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(minutes_with_segments)

        app = _make_export_app(mock_redis)

        # MinutesPDFGenerator.generate를 예외 발생하도록 패치
        with patch(
            "backend.pipeline.pdf_generator.MinutesPDFGenerator.generate",
            side_effect=RuntimeError("PDF 생성 내부 오류"),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/api/v1/export/pdf/minutes-error-test")

        assert response.status_code == 500

    def test_export_pdf_value_error_returns_422(self) -> None:
        """
        MinutesPDFGenerator.generate가 ValueError를 던지면 422 반환
        (segments가 API 레벨 검증 후에도 PDF 생성기에서 ValueError가 발생하는 경우)
        """
        from unittest.mock import patch

        minutes_with_segments = {
            "task_id": "minutes-value-error-test",
            "segments": [{"speaker_name": "테스트", "text": "테스트", "start": 0.0, "end": 1.0}],
            "speakers": [],
            "total_duration": 1.0,
            "total_speakers": 0,
            "markdown": "",
            "created_at": "2026-03-22T14:00:00",
        }

        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(minutes_with_segments)

        app = _make_export_app(mock_redis)

        # MinutesPDFGenerator.generate를 ValueError로 패치
        with patch(
            "backend.pipeline.pdf_generator.MinutesPDFGenerator.generate",
            side_effect=ValueError("유효하지 않은 데이터"),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/api/v1/export/pdf/minutes-value-error-test")

        assert response.status_code == 422
