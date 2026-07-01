#!/usr/bin/env python3
"""Evaluate Promise Radar Autopilot accuracy against labeled fixture cases."""

from __future__ import annotations

import json
import sys
from argparse import ArgumentParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from backend.schemas.promise_radar import PromiseAccuracyCase
    from backend.services.promise_radar_service import PromiseRadarService

    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true", help="Print the full operator report")
    parser.add_argument("--target-real-cases", type=int, default=100)
    args = parser.parse_args()

    fixture_path = ROOT / "backend" / "tests" / "fixtures" / "promise_radar_accuracy_cases.json"
    source_manifest_path = (
        ROOT / "backend" / "tests" / "fixtures" / "promise_radar_real_meeting_sources.json"
    )
    raw_cases = json.loads(fixture_path.read_text(encoding="utf-8"))
    cases = [PromiseAccuracyCase(**item) for item in raw_cases]
    service = PromiseRadarService()
    result = (
        service.build_accuracy_report(
            cases,
            fixture_path=str(fixture_path),
            source_manifest_path=str(source_manifest_path)
            if source_manifest_path.exists()
            else None,
            target_case_count=args.target_real_cases,
        )
        if args.report
        else service.evaluate_accuracy_cases(cases)
    )
    print(result.model_dump_json(indent=2))
    accuracy = result.evaluation.accuracy if args.report else result.accuracy
    below_target = bool(getattr(result, "below_target", False))
    return 0 if accuracy >= 0.75 and not below_target else 1


if __name__ == "__main__":
    raise SystemExit(main())
