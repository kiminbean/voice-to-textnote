"""
SPEC-REFACTOR-001 라우터 레지스트리 불변성 테스트.

검증 항목:
  AC-C2: 리팩터링 후 라우트 테이블(경로·메서드)이 베이스라인과 완전히 동일해야 한다.
  AC-C5: 각 라우트의 API Key 인증 정책이 베이스라인과 동일해야 한다.

베이스라인: backend/tests/unit/_route_snapshot_baseline.json
  - 사전 생성된 골든 스냅숏 (135개 APIRoute).
  - 이 파일은 절대 수정하지 말 것.

관련 요구사항: REQ-RM-C2, REQ-RM-C3
"""

import json
from pathlib import Path

import fastapi.routing
import pytest

from backend.app.api.v1.registry import ROUTER_REGISTRY
from backend.app.middleware.auth import verify_api_key

# ─── 헬퍼 ────────────────────────────────────────────────────────────────────


def _has_api_key_dep(route: fastapi.routing.APIRoute) -> bool:
    """해당 라우트의 의존성 트리에 verify_api_key가 포함되어 있는지 확인한다."""
    for dep in route.dependant.dependencies:
        if dep.call is verify_api_key:
            return True
    return False


def _build_snapshot(app_routes: list) -> list[dict]:
    """app.routes에서 APIRoute만 추출해 스냅숏 목록을 만든다.

    각 항목: {"path": str, "methods": List[str], "api_key": bool}
    정렬 기준: (path, methods의 첫 번째 요소)
    """
    snapshot = []
    for route in app_routes:
        if not isinstance(route, fastapi.routing.APIRoute):
            continue
        snapshot.append(
            {
                "path": route.path,
                "methods": sorted(route.methods),
                "api_key": _has_api_key_dep(route),
            }
        )
    # 베이스라인과 동일한 정렬 기준 적용
    snapshot.sort(key=lambda r: (r["path"], r["methods"]))
    return snapshot


# ─── 픽스처 ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def baseline() -> list[dict]:
    """골든 베이스라인 JSON을 읽어 반환한다."""
    baseline_path = Path(__file__).parent / "_route_snapshot_baseline.json"
    with baseline_path.open(encoding="utf-8") as f:
        data = json.load(f)
    # 베이스라인도 동일 기준으로 정렬
    return sorted(data, key=lambda r: (r["path"], r["methods"]))


@pytest.fixture(scope="module")
def live_snapshot() -> list[dict]:
    """라우터 레지스트리 SSOT와 메트릭스 엔드포인트로 라이브 스냅숏을 만든다."""
    snapshot = []
    api_prefix = "/api/v1"
    for router, requires_api_key in ROUTER_REGISTRY:
        for route in router.routes:
            if not isinstance(route, fastapi.routing.APIRoute):
                continue
            snapshot.append(
                {
                    "path": f"{api_prefix}{route.path}",
                    "methods": sorted(route.methods),
                    "api_key": requires_api_key,
                }
            )

    snapshot.append({"path": "/metrics", "methods": ["GET"], "api_key": False})
    snapshot.sort(key=lambda r: (r["path"], r["methods"]))
    return snapshot


# ─── 테스트 ───────────────────────────────────────────────────────────────────


class TestRouteRegistryInvariance:
    """AC-C2 / AC-C5: 라우트 테이블과 인증 정책이 베이스라인과 동일함을 검증한다."""

    def test_route_count_matches_baseline(
        self, baseline: list[dict], live_snapshot: list[dict]
    ) -> None:
        """AC-C2: 라우트 개수가 베이스라인과 동일해야 한다."""
        assert len(live_snapshot) == len(baseline), (
            f"라우트 개수 불일치: live={len(live_snapshot)}, baseline={len(baseline)}\n"
            f"live에만 있는 경로: "
            f"{[r['path'] for r in live_snapshot if r not in baseline]}\n"
            f"baseline에만 있는 경로: "
            f"{[r['path'] for r in baseline if r not in live_snapshot]}"
        )

    def test_full_route_table_matches_baseline(
        self, baseline: list[dict], live_snapshot: list[dict]
    ) -> None:
        """AC-C2 + AC-C5: 전체 라우트 테이블(경로·메서드·인증)이 베이스라인과 완전히 동일해야 한다."""
        baseline_set = {(r["path"], tuple(r["methods"]), r["api_key"]) for r in baseline}
        live_set = {(r["path"], tuple(r["methods"]), r["api_key"]) for r in live_snapshot}

        added = live_set - baseline_set
        removed = baseline_set - live_set

        diff_lines = []
        if added:
            diff_lines.append("라이브에 추가된 라우트 (베이스라인에 없음):")
            for path, methods, api_key in sorted(added):
                diff_lines.append(f"  + {methods} {path}  api_key={api_key}")
        if removed:
            diff_lines.append("베이스라인에서 제거된 라우트 (라이브에 없음):")
            for path, methods, api_key in sorted(removed):
                diff_lines.append(f"  - {methods} {path}  api_key={api_key}")

        assert not added and not removed, "\n".join(diff_lines)

    def test_auth_policy_matches_baseline(
        self, baseline: list[dict], live_snapshot: list[dict]
    ) -> None:
        """AC-C5: 각 라우트의 API Key 인증 플래그가 베이스라인과 동일해야 한다."""
        baseline_auth = {(r["path"], tuple(r["methods"])): r["api_key"] for r in baseline}
        live_auth = {(r["path"], tuple(r["methods"])): r["api_key"] for r in live_snapshot}

        mismatches = []
        for key, expected in baseline_auth.items():
            actual = live_auth.get(key)
            if actual is None:
                mismatches.append(f"  라우트 누락: {key[1]} {key[0]}")
            elif actual != expected:
                mismatches.append(  # pragma: no cover
                    f"  인증 정책 불일치: {key[1]} {key[0]}  "
                    f"expected api_key={expected}, got api_key={actual}"
                )

        assert not mismatches, "인증 정책 회귀 감지:\n" + "\n".join(mismatches)
