"""
History API 테스트 - SPEC-HISTORY-001

테스트 범위:
- GET /api/v1/history: 페이지네이션 목록 조회 (REQ-HIST-001~004)
- GET /api/v1/history/{task_id}: 단건 상세 조회 (REQ-HIST-005~006)
- DELETE /api/v1/history/{task_id}: 삭제 (REQ-HIST-007)
"""

import uuid

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.error_handlers import register_exception_handlers
from backend.db.auth_models import MeetingOwnership, Team, User
from backend.db.models import Base, TaskResult

OWNER_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")

# ---------------------------------------------------------------------------
# 테스트용 DB 픽스처 (인메모리 SQLite)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_engine():
    """인메모리 SQLite 엔진 픽스처"""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """비동기 DB 세션 픽스처"""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def populated_db(db_session: AsyncSession):
    """
    테스트용 TaskResult 레코드 사전 삽입 픽스처

    다양한 task_type, status 조합으로 10건 삽입하여
    필터링/페이지네이션 테스트를 지원합니다.
    """
    from datetime import datetime

    records = [
        TaskResult(
            task_id="stt-001",
            task_type="stt",
            status="completed",
            result_data={"text": "안녕하세요"},
            input_metadata={"filename": "a.wav"},
            completed_at=datetime(2024, 1, 1, 9, 0, 0),
        ),
        TaskResult(
            task_id="stt-002",
            task_type="stt",
            status="failed",
            error_message="파일 형식 오류",
        ),
        TaskResult(
            task_id="dia-001",
            task_type="diarization",
            status="completed",
            result_data={"speakers": 2},
            completed_at=datetime(2024, 1, 1, 9, 5, 0),
        ),
        TaskResult(
            task_id="dia-002",
            task_type="diarization",
            status="processing",
        ),
        TaskResult(
            task_id="minutes-001",
            task_type="minutes",
            status="completed",
            result_data={"markdown": "# 회의록"},
            completed_at=datetime(2024, 1, 1, 9, 10, 0),
        ),
        TaskResult(
            task_id="summary-001",
            task_type="summary",
            status="completed",
            result_data={"text": "요약 내용", "minutes_task_id": "minutes-001"},
            completed_at=datetime(2024, 1, 1, 9, 15, 0),
        ),
        TaskResult(
            task_id="guest-summary-001",
            task_type="summary",
            status="completed",
            result_data={"text": "게스트 요약"},
            is_guest=True,
            guest_session_id="guest-session-001",
            completed_at=datetime(2024, 1, 1, 9, 16, 0),
        ),
        TaskResult(
            task_id="stt-003",
            task_type="stt",
            status="completed",
            result_data={"text": "세 번째 STT"},
            completed_at=datetime(2024, 1, 1, 9, 20, 0),
        ),
        TaskResult(
            task_id="stt-004",
            task_type="stt",
            status="completed",
            result_data={"text": "네 번째 STT"},
            completed_at=datetime(2024, 1, 1, 9, 25, 0),
        ),
        TaskResult(
            task_id="stt-005",
            task_type="stt",
            status="failed",
            error_message="처리 시간 초과",
        ),
        TaskResult(
            task_id="dia-003",
            task_type="diarization",
            status="completed",
            result_data={"speakers": 3},
            completed_at=datetime(2024, 1, 1, 9, 30, 0),
        ),
    ]

    for record in records:
        db_session.add(record)
    owner_id = OWNER_ID
    team_id = uuid.uuid4()
    db_session.add(
        User(
            id=owner_id,
            email="owner@example.com",
            password_hash="hash",
            display_name="Owner",
        )
    )
    db_session.add(
        Team(
            id=team_id,
            name="Research Team",
            description=None,
            created_by=owner_id,
        )
    )
    db_session.add(
        MeetingOwnership(
            task_id="summary-001",
            owner_id=owner_id,
            team_id=None,
        )
    )
    db_session.add(
        MeetingOwnership(
            task_id="summary-001",
            owner_id=owner_id,
            team_id=team_id,
        )
    )
    await db_session.commit()

    yield db_session


@pytest.fixture
def test_app(db_engine):
    """
    테스트용 FastAPI 앱 픽스처

    get_db_session 의존성을 인메모리 SQLite로 오버라이드합니다.
    """

    from backend.app.api.v1.admin.history import router
    from backend.app.dependencies import get_db_session

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")

    @app.middleware("http")
    async def inject_test_user_id(request, call_next):
        user_id = request.headers.get("X-Test-User-ID")
        if user_id:
            request.state.user_id = user_id
        guest_session_id = request.headers.get("X-Test-Guest-Session-ID")
        if guest_session_id:
            request.state.is_guest = True
            request.state.guest_session_id = guest_session_id
        return await call_next(request)

    # DB 세션 의존성 오버라이드
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_db_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session

    return app


@pytest.fixture
def client(test_app, populated_db):
    """사전 데이터가 삽입된 TestClient"""

    return TestClient(test_app)


@pytest.fixture
def empty_client(test_app):
    """빈 DB를 사용하는 TestClient"""

    return TestClient(test_app)


# ---------------------------------------------------------------------------
# REQ-HIST-001: GET /api/v1/history 기본 페이지네이션 목록 조회
# ---------------------------------------------------------------------------


class TestHistoryList:
    """REQ-HIST-001~004: 목록 조회 API 테스트"""

    def test_list_returns_200(self, client):
        """기본 목록 조회 시 200 반환"""
        resp = client.get("/api/v1/history")
        assert resp.status_code == 200

    def test_list_response_schema(self, client):
        """REQ-HIST-004: 응답 스키마 검증 {items, total, page, page_size}"""
        resp = client.get("/api/v1/history")
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data

    def test_list_default_pagination(self, client):
        """기본 페이지네이션 파라미터 (page=1, page_size=20)"""
        resp = client.get("/api/v1/history")
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 20

    def test_list_total_count(self, client):
        """총 레코드 수 반환"""
        resp = client.get("/api/v1/history")
        data = resp.json()
        # populated_db에 11건 삽입
        assert data["total"] == 11

    def test_list_items_count(self, client):
        """items 배열 항목 수 확인 (10건, page_size 기본 20)"""
        resp = client.get("/api/v1/history")
        data = resp.json()
        assert len(data["items"]) == 11

    def test_list_item_fields(self, client):
        """HistoryItem 필드 구조 검증"""
        resp = client.get("/api/v1/history")
        item = resp.json()["items"][0]
        # 필수 필드 존재
        assert "task_id" in item
        assert "task_type" in item
        assert "status" in item
        assert "created_at" in item
        assert "shared_team_ids" in item
        # result_data는 목록에서 제외
        assert "result_data" not in item

    def test_list_item_includes_shared_team_ids(self, client):
        """공유된 회의는 history 목록에서 공유 팀 ID를 포함해야 함"""
        resp = client.get("/api/v1/history")
        data = resp.json()
        item = next(item for item in data["items"] if item["task_id"] == "summary-001")
        assert len(item["shared_team_ids"]) == 1

    def test_list_item_includes_source_task_id(self, client):
        """파생 작업은 원본 task_id를 history 목록에 포함해야 함"""
        resp = client.get("/api/v1/history")
        data = resp.json()
        item = next(item for item in data["items"] if item["task_id"] == "summary-001")
        assert item["source_task_id"] == "minutes-001"

    def test_list_page_size_param(self, client):
        """page_size 파라미터 적용"""
        resp = client.get("/api/v1/history?page_size=3")
        data = resp.json()
        assert len(data["items"]) == 3
        assert data["page_size"] == 3

    def test_list_page_param(self, client):
        """page 파라미터로 페이지 이동"""
        resp1 = client.get("/api/v1/history?page=1&page_size=3")
        resp2 = client.get("/api/v1/history?page=2&page_size=3")
        ids1 = {item["task_id"] for item in resp1.json()["items"]}
        ids2 = {item["task_id"] for item in resp2.json()["items"]}
        # 페이지 간 중복 없음
        assert ids1.isdisjoint(ids2)

    def test_list_empty_db(self, empty_client):
        """빈 DB에서 목록 조회 시 빈 배열 반환"""
        resp = empty_client.get("/api/v1/history")
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_filters_to_authenticated_owner(self, client):
        """JWT 사용자는 자기 소유 작업 이력만 조회해야 함"""
        resp = client.get("/api/v1/history", headers={"X-Test-User-ID": str(OWNER_ID)})
        data = resp.json()
        assert data["total"] == 1
        assert [item["task_id"] for item in data["items"]] == ["summary-001"]

    def test_detail_hides_unowned_task_for_authenticated_owner(self, client):
        """JWT 사용자는 소유하지 않은 task_id 상세를 볼 수 없어야 함"""
        resp = client.get(
            "/api/v1/history/minutes-001",
            headers={"X-Test-User-ID": str(OWNER_ID)},
        )
        assert resp.status_code == 404

    def test_list_filters_to_guest_session(self, client):
        """게스트 사용자는 자기 guest_session_id의 작업 이력만 조회해야 함"""
        resp = client.get(
            "/api/v1/history",
            headers={"X-Test-Guest-Session-ID": "guest-session-001"},
        )
        data = resp.json()
        assert data["total"] == 1
        assert [item["task_id"] for item in data["items"]] == ["guest-summary-001"]

    def test_detail_hides_other_records_for_guest_session(self, client):
        """게스트 사용자는 다른 세션/로그인 사용자 task 상세를 볼 수 없어야 함"""
        resp = client.get(
            "/api/v1/history/summary-001",
            headers={"X-Test-Guest-Session-ID": "guest-session-001"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# REQ-HIST-002: task_type 필터링
# ---------------------------------------------------------------------------


class TestHistoryListFilterByTaskType:
    """REQ-HIST-002: task_type 필터 테스트"""

    def test_filter_stt(self, client):
        """task_type=stt 필터링"""
        resp = client.get("/api/v1/history?task_type=stt")
        data = resp.json()
        assert all(item["task_type"] == "stt" for item in data["items"])

    def test_filter_diarization(self, client):
        """task_type=diarization 필터링"""
        resp = client.get("/api/v1/history?task_type=diarization")
        data = resp.json()
        assert all(item["task_type"] == "diarization" for item in data["items"])

    def test_filter_minutes(self, client):
        """task_type=minutes 필터링"""
        resp = client.get("/api/v1/history?task_type=minutes")
        data = resp.json()
        assert all(item["task_type"] == "minutes" for item in data["items"])

    def test_filter_summary(self, client):
        """task_type=summary 필터링"""
        resp = client.get("/api/v1/history?task_type=summary")
        data = resp.json()
        assert all(item["task_type"] == "summary" for item in data["items"])

    def test_filter_task_type_total_matches(self, client):
        """task_type 필터 적용 시 total도 필터된 수 반환"""
        resp = client.get("/api/v1/history?task_type=stt")
        data = resp.json()
        # stt 건수: stt-001, stt-002, stt-003, stt-004, stt-005 = 5건
        assert data["total"] == 5

    def test_filter_nonexistent_task_type(self, client):
        """존재하지 않는 task_type 필터 시 빈 목록 반환"""
        resp = client.get("/api/v1/history?task_type=unknown")
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0


# ---------------------------------------------------------------------------
# REQ-HIST-003: status 필터링
# ---------------------------------------------------------------------------


class TestHistoryListFilterByStatus:
    """REQ-HIST-003: status 필터 테스트"""

    def test_filter_completed(self, client):
        """status=completed 필터링"""
        resp = client.get("/api/v1/history?status=completed")
        data = resp.json()
        assert all(item["status"] == "completed" for item in data["items"])

    def test_filter_failed(self, client):
        """status=failed 필터링"""
        resp = client.get("/api/v1/history?status=failed")
        data = resp.json()
        assert all(item["status"] == "failed" for item in data["items"])

    def test_filter_processing(self, client):
        """status=processing 필터링"""
        resp = client.get("/api/v1/history?status=processing")
        data = resp.json()
        assert all(item["status"] == "processing" for item in data["items"])

    def test_filter_status_total_matches(self, client):
        """status 필터 적용 시 total도 필터된 수 반환"""
        resp = client.get("/api/v1/history?status=failed")
        data = resp.json()
        # failed 건수: stt-002, stt-005 = 2건
        assert data["total"] == 2

    def test_filter_task_type_and_status_combined(self, client):
        """task_type + status 복합 필터"""
        resp = client.get("/api/v1/history?task_type=stt&status=completed")
        data = resp.json()
        for item in data["items"]:
            assert item["task_type"] == "stt"
            assert item["status"] == "completed"
        # stt + completed: stt-001, stt-003, stt-004 = 3건
        assert data["total"] == 3


# ---------------------------------------------------------------------------
# REQ-HIST-005~006: GET /api/v1/history/{task_id} 상세 조회
# ---------------------------------------------------------------------------


class TestHistoryDetail:
    """REQ-HIST-005~006: 단건 상세 조회 API 테스트"""

    def test_detail_returns_200(self, client):
        """존재하는 task_id 상세 조회 시 200 반환"""
        resp = client.get("/api/v1/history/stt-001")
        assert resp.status_code == 200

    def test_detail_returns_correct_task_id(self, client):
        """올바른 task_id 반환"""
        resp = client.get("/api/v1/history/stt-001")
        data = resp.json()
        assert data["task_id"] == "stt-001"

    def test_detail_includes_result_data(self, client):
        """REQ-HIST-005: 상세 조회에는 result_data 포함"""
        resp = client.get("/api/v1/history/stt-001")
        data = resp.json()
        assert "result_data" in data
        assert data["result_data"] == {"text": "안녕하세요"}

    def test_detail_includes_input_metadata(self, client):
        """상세 조회에는 input_metadata 포함"""
        resp = client.get("/api/v1/history/stt-001")
        data = resp.json()
        assert "input_metadata" in data

    def test_detail_404_for_nonexistent(self, client):
        """REQ-HIST-006: 존재하지 않는 task_id 조회 시 404 반환"""
        resp = client.get("/api/v1/history/nonexistent-task-id")
        assert resp.status_code == 404

    def test_detail_404_error_message(self, client):
        """404 응답에 적절한 오류 메시지 포함"""
        resp = client.get("/api/v1/history/nonexistent-task-id")
        data = resp.json()
        assert "message" in data

    def test_detail_with_error_message(self, client):
        """실패한 작업의 error_message 포함"""
        resp = client.get("/api/v1/history/stt-002")
        data = resp.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "파일 형식 오류"

    def test_detail_completed_at_included(self, client):
        """완료된 작업의 completed_at 포함"""
        resp = client.get("/api/v1/history/stt-001")
        data = resp.json()
        assert "completed_at" in data
        assert data["completed_at"] is not None


# ---------------------------------------------------------------------------
# REQ-HIST-007: DELETE /api/v1/history/{task_id} 삭제
# ---------------------------------------------------------------------------


class TestHistoryDelete:
    """REQ-HIST-007: 삭제 API 테스트"""

    def test_delete_returns_204(self, client):
        """존재하는 task_id 삭제 시 204 반환"""
        resp = client.delete("/api/v1/history/stt-001")
        assert resp.status_code == 204

    def test_delete_no_content_body(self, client):
        """204 응답에 본문 없음"""
        resp = client.delete("/api/v1/history/stt-001")
        assert resp.content == b""

    def test_delete_removes_record(self, client):
        """삭제 후 상세 조회 시 404 반환"""
        client.delete("/api/v1/history/stt-001")
        resp = client.get("/api/v1/history/stt-001")
        assert resp.status_code == 404

    def test_delete_reduces_total_count(self, client):
        """삭제 후 목록 total 감소"""
        before = client.get("/api/v1/history").json()["total"]
        client.delete("/api/v1/history/stt-001")
        after = client.get("/api/v1/history").json()["total"]
        assert after == before - 1

    def test_delete_404_for_nonexistent(self, client):
        """존재하지 않는 task_id 삭제 시 404 반환"""
        resp = client.delete("/api/v1/history/nonexistent-task-id")
        assert resp.status_code == 404
