"""
SPEC-EXPORT-001: Export API v3 테스트
DOCX와 Markdown 엔드포인트 커버리지를 위한 테스트
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.middleware.auth import verify_api_key

# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_minutes_data() -> dict:
    """유효한 회의록 데이터"""
    return {
        "task_id": "minutes-task-001",
        "segments": [
            {
                "speaker": "김팀장",
                "text": "안녕하세요, 오늘 회의를 시작하겠습니다.",
                "start": 0.0,
                "end": 5.0,
            },
            {
                "speaker": "이개발",
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
    """유효한 요약 데이터"""
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
        "key_decisions": ["결정 사항 1", "결정 사항 2"],
        "next_steps": ["다음 단계 1", "다음 단계 2"],
    }


def _make_export_app(mock_redis: AsyncMock) -> FastAPI:
    """테스트용 FastAPI 앱 생성"""
    from backend.app.api.v1 import export
    from backend.app.dependencies import get_db_session, get_redis_client

    app = FastAPI()
    app.include_router(export.router, prefix="/api/v1")

    async def override_redis():
        return mock_redis

    async def override_db():
        db_mock = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.first.return_value = None
        db_mock.execute.return_value = result_mock
        yield db_mock

    async def override_auth():
        return "test-bypass"

    app.dependency_overrides[get_redis_client] = override_redis
    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[verify_api_key] = override_auth

    return app


# ---------------------------------------------------------------------------
# DOCX 엔드포인트 테스트 (라인 195-278)
# ---------------------------------------------------------------------------


class TestExportDocxApi:
    """DOCX 내보내기 엔드포인트 테스트"""

    def test_export_docx_success(self, valid_minutes_data: dict) -> None:
        """DOCX 내보내기 성공 케이스"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(valid_minutes_data)

        app = _make_export_app(mock_redis)
        client = TestClient(app)

        response = client.get("/api/v1/export/docx/minutes-task-001")

        assert response.status_code == 200
        # DOCX 파일 시그니처 확인 (PK 워드로 시작)
        assert response.content[:2] == b"PK"

    def test_export_docx_not_found(self) -> None:
        """회의록 데이터를 찾을 수 없을 때 404 반환"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        app = _make_export_app(mock_redis)
        client = TestClient(app)

        response = client.get("/api/v1/export/docx/nonexistent-task")

        assert response.status_code == 404

    def test_export_docx_incomplete_data(self) -> None:
        """segments가 비어있으면 422 반환"""
        incomplete_data = {
            "task_id": "incomplete",
            "segments": [],  # 빈 segments
            "speakers": [],
        }

        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(incomplete_data)

        app = _make_export_app(mock_redis)
        client = TestClient(app)

        response = client.get("/api/v1/export/docx/incomplete")

        assert response.status_code == 422

    def test_export_docx_with_summary(
        self, valid_minutes_data: dict, valid_summary_data: dict
    ) -> None:
        """요약 포함 DOCX 생성"""
        def redis_side_effect(key: str):
            if "min:result" in key:
                return json.dumps(valid_minutes_data)
            if "sum:result" in key:
                return json.dumps(valid_summary_data)
            return None

        mock_redis = AsyncMock()
        mock_redis.get.side_effect = redis_side_effect

        app = _make_export_app(mock_redis)
        client = TestClient(app)

        response = client.get(
            "/api/v1/export/docx/minutes-task-001?summary_task_id=summary-task-001"
        )

        assert response.status_code == 200
        assert response.content[:2] == b"PK"

    def test_export_docx_content_disposition(self, valid_minutes_data: dict) -> None:
        """Content-Disposition 헤더 확인"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(valid_minutes_data)

        app = _make_export_app(mock_redis)
        client = TestClient(app)

        response = client.get("/api/v1/export/docx/minutes-task-001")

        assert response.status_code == 200
        content_disposition = response.headers.get("content-disposition", "")
        assert "attachment" in content_disposition
        assert "minutes_minutes-task-001.docx" in content_disposition

    def test_export_docx_value_error_returns_422(self) -> None:
        """DOCX 생성 중 ValueError 발생 시 422 반환"""
        minutes_with_segments = {
            "task_id": "minutes-value-error",
            "segments": [{"speaker_name": "테스트", "text": "테스트", "start": 0.0, "end": 1.0}],
            "speakers": [],
        }

        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(minutes_with_segments)

        app = _make_export_app(mock_redis)

        with patch(
            "backend.pipeline.docx_generator.MinutesDOCXGenerator.generate",
            side_effect=ValueError("유효하지 않은 데이터"),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/api/v1/export/docx/minutes-value-error")

        assert response.status_code == 422

    def test_export_docx_generation_error_returns_500(self) -> None:
        """DOCX 생성 중 일반 예외 발생 시 500 반환"""
        minutes_with_segments = {
            "task_id": "minutes-gen-error",
            "segments": [{"speaker_name": "테스트", "text": "테스트", "start": 0.0, "end": 1.0}],
            "speakers": [],
        }

        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(minutes_with_segments)

        app = _make_export_app(mock_redis)

        with patch(
            "backend.pipeline.docx_generator.MinutesDOCXGenerator.generate",
            side_effect=RuntimeError("내부 오류"),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/api/v1/export/docx/minutes-gen-error")

        assert response.status_code == 500

    def test_export_docx_summary_not_found_continues(self, valid_minutes_data: dict) -> None:
        """요약 데이터를 찾을 수 없어도 DOCX 생성 계속 진행"""
        def redis_side_effect(key: str):
            if "min:result" in key:
                return json.dumps(valid_minutes_data)
            return None  # 요약 없음

        mock_redis = AsyncMock()
        mock_redis.get.side_effect = redis_side_effect

        app = _make_export_app(mock_redis)
        client = TestClient(app)

        response = client.get(
            "/api/v1/export/docx/minutes-task-001?summary_task_id=nonexistent-summary"
        )

        # 요약 없이도 성공
        assert response.status_code == 200
        assert response.content[:2] == b"PK"


# ---------------------------------------------------------------------------
# Markdown 엔드포인트 테스트 (라인 281-358)
# ---------------------------------------------------------------------------


class TestExportMarkdownApi:
    """Markdown 내보내기 엔드포인트 테스트"""

    def test_export_markdown_success(self, valid_minutes_data: dict) -> None:
        """Markdown 내보내기 성공 케이스"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(valid_minutes_data)

        app = _make_export_app(mock_redis)
        client = TestClient(app)

        response = client.get("/api/v1/export/markdown/minutes-task-001")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/markdown; charset=utf-8"

        # Markdown 내용 확인
        md_content = response.content.decode("utf-8")
        assert "# 회의록" in md_content
        assert "**김팀장**:" in md_content
        assert "**이개발**:" in md_content

    def test_export_markdown_not_found(self) -> None:
        """회의록 데이터를 찾을 수 없을 때 404 반환"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        app = _make_export_app(mock_redis)
        client = TestClient(app)

        response = client.get("/api/v1/export/markdown/nonexistent-task")

        assert response.status_code == 404

    def test_export_markdown_incomplete_data(self) -> None:
        """segments가 비어있으면 422 반환"""
        incomplete_data = {
            "task_id": "incomplete",
            "segments": [],
        }

        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(incomplete_data)

        app = _make_export_app(mock_redis)
        client = TestClient(app)

        response = client.get("/api/v1/export/markdown/incomplete")

        assert response.status_code == 422

    def test_export_markdown_with_summary(
        self, valid_minutes_data: dict, valid_summary_data: dict
    ) -> None:
        """요약 포함 Markdown 생성"""
        def redis_side_effect(key: str):
            if "min:result" in key:
                return json.dumps(valid_minutes_data)
            if "sum:result" in key:
                return json.dumps(valid_summary_data)
            return None

        mock_redis = AsyncMock()
        mock_redis.get.side_effect = redis_side_effect

        app = _make_export_app(mock_redis)
        client = TestClient(app)

        response = client.get(
            "/api/v1/export/markdown/minutes-task-001?summary_task_id=summary-task-001"
        )

        assert response.status_code == 200

        md_content = response.content.decode("utf-8")
        # 요약 섹션 확인
        assert "## AI 요약" in md_content
        assert "회의 요약 텍스트입니다." in md_content
        assert "### 주요 결정 사항" in md_content
        assert "1. 결정 사항 1" in md_content
        assert "2. 결정 사항 2" in md_content
        assert "### 다음 단계" in md_content
        assert "1. 다음 단계 1" in md_content

    def test_export_markdown_content_disposition(self, valid_minutes_data: dict) -> None:
        """Content-Disposition 헤더 확인"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(valid_minutes_data)

        app = _make_export_app(mock_redis)
        client = TestClient(app)

        response = client.get("/api/v1/export/markdown/minutes-task-001")

        assert response.status_code == 200
        content_disposition = response.headers.get("content-disposition", "")
        assert "attachment" in content_disposition
        assert "minutes_minutes-task-001.md" in content_disposition

    def test_export_markdown_with_empty_summary_fields(
        self, valid_minutes_data: dict
    ) -> None:
        """요약 데이터가 있지만 필드가 비어있을 때"""
        empty_summary = {
            "task_id": "empty-summary",
            "summary_text": "",  # 빈 텍스트
            "key_decisions": [],  # 빈 배열
            "next_steps": [],  # 빈 배열
        }

        def redis_side_effect(key: str):
            if "min:result" in key:
                return json.dumps(valid_minutes_data)
            if "sum:result" in key:
                return json.dumps(empty_summary)
            return None

        mock_redis = AsyncMock()
        mock_redis.get.side_effect = redis_side_effect

        app = _make_export_app(mock_redis)
        client = TestClient(app)

        response = client.get(
            "/api/v1/export/markdown/minutes-task-001?summary_task_id=empty-summary"
        )

        assert response.status_code == 200

        md_content = response.content.decode("utf-8")
        # 빈 필드는 섹션 자체가 생성되지 않아야 함
        assert "# 회의록" in md_content
        # 빈 요약 텍스트로는 "## AI 요약" 섹션이 생성되지 않음
        assert "## AI 요약" not in md_content
        # 빈 결정/다음단계로는 섹션 자체가 생성되지 않음
        assert "### 주요 결정 사항" not in md_content
        assert "### 다음 단계" not in md_content

    def test_export_markdown_segments_without_speaker(self, valid_minutes_data: dict) -> None:
        """segment에 speaker가 없을 때 기본값 사용"""
        # speaker가 없는 segments
        minutes_without_speaker = {
            "task_id": "no-speaker",
            "segments": [
                {"text": "발화 내용", "start": 0.0, "end": 1.0}
                # speaker 누락
            ],
        }

        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(minutes_without_speaker)

        app = _make_export_app(mock_redis)
        client = TestClient(app)

        response = client.get("/api/v1/export/markdown/no-speaker")

        assert response.status_code == 200

        md_content = response.content.decode("utf-8")
        # 기본값 "알 수 없음"이 사용되어야 함
        assert "**알 수 없음**:" in md_content

    def test_export_markdown_summary_without_text(self, valid_minutes_data: dict) -> None:
        """요약에 key_decisions나 next_steps만 있을 때"""
        summary_only_decisions = {
            "task_id": "only-decisions",
            "key_decisions": ["결정 1", "결정 2"],
            "next_steps": ["단계 1"],
            # summary_text 없음
        }

        def redis_side_effect(key: str):
            if "min:result" in key:
                return json.dumps(valid_minutes_data)
            if "sum:result" in key:
                return json.dumps(summary_only_decisions)
            return None

        mock_redis = AsyncMock()
        mock_redis.get.side_effect = redis_side_effect

        app = _make_export_app(mock_redis)
        client = TestClient(app)

        response = client.get(
            "/api/v1/export/markdown/minutes-task-001?summary_task_id=only-decisions"
        )

        assert response.status_code == 200

        md_content = response.content.decode("utf-8")
        # summary_text가 없어도 key_decisions/next_steps가 있으면 섹션 생성됨
        assert "### 주요 결정 사항" in md_content
        assert "1. 결정 1" in md_content
        assert "2. 결정 2" in md_content
        assert "### 다음 단계" in md_content
        assert "1. 단계 1" in md_content
