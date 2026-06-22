from backend.app.api.v1.collaboration import speaker_groups, speaker_statistics
from backend.app.api.v1.registry import ROUTER_REGISTRY
from backend.db.models import Base
from backend.db.speaker_group_models import SpeakerGroup, SpeakerGroupMember
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
