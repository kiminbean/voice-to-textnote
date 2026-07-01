from fastapi.routing import APIRoute

from backend.app.main import app


def test_promise_radar_routes_are_registered_in_app_openapi():
    paths = {
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
    }

    assert "/api/v1/promise-radar/{task_id}" in paths
    assert "/api/v1/promise-radar/autopilot/{task_id}/review-queue" in paths

    openapi_paths = set(app.openapi()["paths"].keys())
    assert "/api/v1/promise-radar/{task_id}" in openapi_paths
    assert "/api/v1/promise-radar/briefing/pre-meeting" in openapi_paths
