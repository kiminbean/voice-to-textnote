#!/usr/bin/env python3
"""Evaluate Promise Radar Autopilot accuracy against labeled fixture cases."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from backend.schemas.promise_radar import PromiseAccuracyCase
    from backend.services.promise_radar_service import PromiseRadarService

    fixture_path = ROOT / "backend" / "tests" / "fixtures" / "promise_radar_accuracy_cases.json"
    raw_cases = json.loads(fixture_path.read_text(encoding="utf-8"))
    cases = [PromiseAccuracyCase(**item) for item in raw_cases]
    result = PromiseRadarService().evaluate_accuracy_cases(cases)
    print(result.model_dump_json(indent=2))
    return 0 if result.accuracy >= 0.75 else 1


if __name__ == "__main__":
    raise SystemExit(main())
