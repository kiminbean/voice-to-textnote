import uuid

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import backend.db.auth_models  # noqa: F401 - register SQLAlchemy metadata
import backend.db.speaker_models  # noqa: F401 - register SQLAlchemy metadata
from backend.app.api.v1.collaboration import speaker_groups, speaker_statistics
from backend.app.api.v1.registry import ROUTER_REGISTRY
from backend.db.auth_models import User
from backend.db.models import Base, TaskResult
from backend.db.speaker_group_models import SpeakerGroup, SpeakerGroupMember
from backend.db.speaker_models import SpeakerProfile
from backend.schemas.speaker_group import SpeakerGroupCreate
from backend.services.speaker_group_service import SpeakerGroupService
from backend.services.speaker_statistics_service import SpeakerStatisticsService


def route_paths(router) -> set[str]:
    return {route.path for route in router.routes}


def test_speaker_group_router_exposes_expected_routes():
    assert route_paths(speaker_groups.router) == {
        "/speaker-groups",
        "/speaker-groups/{group_id}",
        "/speaker-groups/{group_id}/members",
        "/speaker-groups/{group_id}/members/{speaker_id}",
    }


def test_speaker_statistics_router_exposes_expected_routes():
    assert route_paths(speaker_statistics.router) == {
        "/speakers/{speaker_id}/meetings",
        "/speakers/{speaker_id}/statistics",
        "/speakers/{speaker_id}/activity-timeline",
        "/speakers/{speaker_id}/participation",
    }


def test_speaker_routers_are_registered_once():
    registered_routers = [router for router, _requires_api_key in ROUTER_REGISTRY]

    assert registered_routers.count(speaker_groups.router) == 1
    assert registered_routers.count(speaker_statistics.router) == 1


def test_speaker_group_models_are_registered_in_metadata():
    assert SpeakerGroup.__tablename__ in Base.metadata.tables
    assert SpeakerGroupMember.__tablename__ in Base.metadata.tables


def test_speaker_service_factories_return_services():
    assert isinstance(
        speaker_groups.get_speaker_group_service(),
        SpeakerGroupService,
    )
    assert isinstance(
        speaker_statistics.get_speaker_statistics_service(),
        SpeakerStatisticsService,
    )


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_speaker_db(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    user = User(
        id=uuid.uuid4(),
        email="speaker-groups@example.com",
        password_hash="x",
        display_name="Speaker Groups",
        is_active=True,
    )
    other_user = User(
        id=uuid.uuid4(),
        email="speaker-groups-other@example.com",
        password_hash="x",
        display_name="Other",
        is_active=True,
    )
    speaker = SpeakerProfile(
        user_id=user.id,
        speaker_label="SPEAKER_00",
        display_name="Alice",
    )
    other_speaker = SpeakerProfile(
        user_id=user.id,
        speaker_label="SPEAKER_01",
        display_name="Bob",
    )
    task_with_target = TaskResult(
        task_id="meeting-target",
        task_type="minutes",
        status="completed",
        result_data={
            "title": "Target speaker meeting",
            "segments": [
                {"start": 0, "end": 10, "speaker": "SPEAKER_00", "text": "hello"},
                {"start": 10, "end": 25, "speaker": "SPEAKER_01", "text": "reply"},
                {"start": 25, "end": 40, "speaker": "SPEAKER_00", "text": "wrap"},
            ],
        },
    )
    task_without_target = TaskResult(
        task_id="meeting-other",
        task_type="minutes",
        status="completed",
        result_data={
            "title": "Other speaker meeting",
            "segments": [
                {"start": 0, "end": 30, "speaker": "SPEAKER_01", "text": "only bob"},
            ],
        },
    )

    async with session_factory() as session:
        session.add_all([user, other_user, speaker, other_speaker, task_with_target, task_without_target])
        await session.commit()

    return {
        "user": user,
        "other_user": other_user,
        "speaker": speaker,
        "other_speaker": other_speaker,
    }


def _make_group_app(db_engine, acting_user: User) -> FastAPI:
    from backend.app.dependencies import get_current_user, get_db_session

    app = FastAPI()
    app.include_router(speaker_groups.router, prefix="/api/v1")

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_db_session():
        async with session_factory() as session:
            yield session

    async def override_current_user():
        return acting_user

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_current_user] = override_current_user
    return app


@pytest.mark.asyncio
async def test_group_detail_endpoint_returns_loaded_members(db_engine, seeded_speaker_db):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    service = SpeakerGroupService()

    async with session_factory() as session:
        group = await service.create(
            session,
            seeded_speaker_db["user"].id,
            SpeakerGroupCreate(name="Engineering", color="#336699"),
        )
        await service.add_member(
            session,
            group.id,
            seeded_speaker_db["speaker"].id,
            seeded_speaker_db["user"].id,
        )

    app = _make_group_app(db_engine, seeded_speaker_db["user"])
    with TestClient(app) as client:
        response = client.get(f"/api/v1/speaker-groups/{group.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Engineering"
    assert body["members"][0]["speaker_id"] == str(seeded_speaker_db["speaker"].id)


@pytest.mark.asyncio
async def test_speaker_meetings_filters_before_pagination(db_engine, seeded_speaker_db):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    service = SpeakerStatisticsService()

    async with session_factory() as session:
        meetings, total = await service.get_speaker_meetings(
            session,
            seeded_speaker_db["speaker"].id,
            seeded_speaker_db["user"].id,
            limit=1,
            offset=0,
        )

    assert total == 1
    assert [meeting.task_id for meeting in meetings] == ["meeting-target"]
    assert meetings[0].title == "Target speaker meeting"
    assert meetings[0].duration_seconds == 40
    assert meetings[0].speaker_segments_count == 2
    assert meetings[0].speaker_duration_seconds == 25


@pytest.mark.asyncio
async def test_speaker_statistics_derives_duration_from_segments(db_engine, seeded_speaker_db):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    service = SpeakerStatisticsService()

    async with session_factory() as session:
        response = await service.get_speaker_statistics(
            session,
            seeded_speaker_db["speaker"].id,
            seeded_speaker_db["user"].id,
        )

    stats = response.statistics
    assert stats.total_meetings == 1
    assert stats.total_speaker_duration_seconds == 25
    assert stats.total_meetings_duration_seconds == 40
    assert stats.average_speaker_percentage == 62.5
    assert stats.speaker_segments_count == 2
    assert stats.average_segment_duration_seconds == 12.5
    assert stats.most_active_meeting == "meeting-target"
