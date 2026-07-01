from fastapi.routing import APIRoute

from backend.app.main import app


def test_promise_radar_routes_are_registered_in_app_openapi():
    route_paths = [route.path for route in app.routes if isinstance(route, APIRoute)]
    paths = set(route_paths)

    assert "/api/v1/promise-radar/{task_id}" in paths
    assert "/api/v1/promise-radar/autopilot/{task_id}/review-queue" in paths
    assert "/api/v1/promise-radar/responsibility-scores" in paths
    assert "/api/v1/promise-radar/responsibility-trends" in paths
    assert "/api/v1/promise-radar/meeting-series" in paths
    assert "/api/v1/promise-radar/meeting-series/{series_key}/timeline" in paths
    assert "/api/v1/promise-radar/briefing/pre-meeting/notifications" in paths
    assert "/api/v1/promise-radar/learning-insights" in paths
    assert "/api/v1/promise-radar/autopilot/review-inbox" in paths
    assert "/api/v1/promise-radar/external-task/reconcile" in paths
    assert "/api/v1/promise-radar/accuracy/extraction-report" in paths
    assert "/api/v1/promise-radar/command-center" in paths
    assert route_paths.index("/api/v1/promise-radar/command-center") < route_paths.index(
        "/api/v1/promise-radar/{task_id}"
    )
    assert route_paths.index(
        "/api/v1/promise-radar/accuracy/extraction-report"
    ) < route_paths.index("/api/v1/promise-radar/{task_id}")

    openapi_paths = set(app.openapi()["paths"].keys())
    assert "/api/v1/promise-radar/{task_id}" in openapi_paths
    assert "/api/v1/promise-radar/briefing/pre-meeting" in openapi_paths
    assert "/api/v1/promise-radar/responsibility-scores" in openapi_paths
    assert "/api/v1/promise-radar/responsibility-trends" in openapi_paths
    assert "/api/v1/promise-radar/meeting-series" in openapi_paths
    assert "/api/v1/promise-radar/meeting-series/{series_key}/timeline" in openapi_paths
    assert "/api/v1/promise-radar/briefing/pre-meeting/notifications" in openapi_paths
    assert "/api/v1/promise-radar/learning-insights" in openapi_paths
    assert "/api/v1/promise-radar/autopilot/review-inbox" in openapi_paths
    assert "/api/v1/promise-radar/external-task/reconcile" in openapi_paths
    assert "/api/v1/promise-radar/accuracy/extraction-report" in openapi_paths
    assert "/api/v1/promise-radar/command-center" in openapi_paths
