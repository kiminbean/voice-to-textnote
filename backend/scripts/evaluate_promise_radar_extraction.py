#!/usr/bin/env python3
"""Evaluate Promise Radar extraction recall against false-negative fixtures."""

from __future__ import annotations

import json
import sys
from argparse import ArgumentParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from backend.schemas.promise_radar import PromiseExtractionCase
    from backend.services.promise_radar_service import PromiseRadarService

    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--target-cases", type=int, default=50)
    parser.add_argument("--min-recall", type=float, default=0.95)
    args = parser.parse_args()

    fixture_path = ROOT / "backend" / "tests" / "fixtures" / "promise_radar_extraction_cases.json"
    raw_cases = json.loads(fixture_path.read_text(encoding="utf-8"))
    cases = [PromiseExtractionCase(**item) for item in raw_cases]
    service = PromiseRadarService()
    report = service.build_extraction_recall_report(
        cases,
        fixture_path=str(fixture_path),
        target_case_count=args.target_cases,
    )
    print(report.model_dump_json(indent=2))
    return 0 if report.evaluation.recall >= args.min_recall and not report.below_target else 1


if __name__ == "__main__":
    raise SystemExit(main())
