#!/usr/bin/env python3
"""Audit Promise Radar fixture labels and source provenance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "backend" / "tests" / "fixtures" / "promise_radar_accuracy_cases.json"
SOURCE_MANIFEST_PATH = (
    ROOT / "backend" / "tests" / "fixtures" / "promise_radar_real_meeting_sources.json"
)
PUBLIC_LABEL_LICENSE_TOKENS = (
    "creative commons",
    "cc-by",
    "cc by",
    "apache",
    "mit",
)


def _public_label_license_allowed(license_text: str) -> bool:
    lowered = license_text.lower()
    return any(token in lowered for token in PUBLIC_LABEL_LICENSE_TOKENS)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _golden_case_count(source: dict[str, Any]) -> int:
    explicit = int(source.get("golden_case_count") or 0)
    if explicit:
        return explicit
    total = 0
    segments = source.get("segments")
    if not isinstance(segments, list):
        return total
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        if "golden_case_count" in segment:
            total += int(segment.get("golden_case_count") or 0)
            continue
        golden_ids = segment.get("golden_case_ids")
        if isinstance(golden_ids, list):
            total += len(golden_ids)
    return total


def _source_lookup(sources: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, str]]:
    prefix_to_source: dict[str, str] = {}
    explicit_case_to_source: dict[str, str] = {}
    for source in sources:
        source_id = str(source.get("source_id") or "unknown")
        prefix = source.get("golden_case_id_prefix")
        if isinstance(prefix, str) and prefix:
            prefix_to_source[prefix] = source_id
        for segment in source.get("segments") or []:
            if not isinstance(segment, dict):
                continue
            for case_id in segment.get("golden_case_ids") or []:
                if isinstance(case_id, str):
                    explicit_case_to_source[case_id] = source_id
    return prefix_to_source, explicit_case_to_source


def _case_source_id(
    case_id: str,
    *,
    prefix_to_source: dict[str, str],
    explicit_case_to_source: dict[str, str],
) -> str | None:
    if case_id in explicit_case_to_source:
        return explicit_case_to_source[case_id]
    for prefix, source_id in prefix_to_source.items():
        if case_id.startswith(prefix):
            return source_id
    return None


def audit_accuracy_set(
    *,
    fixture_path: Path = FIXTURE_PATH,
    source_manifest_path: Path = SOURCE_MANIFEST_PATH,
    target_real_cases: int = 100,
    require_cache: bool = False,
) -> dict[str, Any]:
    cases = _load_json(fixture_path)
    sources = _load_json(source_manifest_path)
    if not isinstance(cases, list):
        raise ValueError(f"{fixture_path} must contain a JSON list")
    if not isinstance(sources, list):
        raise ValueError(f"{source_manifest_path} must contain a JSON list")

    errors: list[str] = []
    warnings: list[str] = []
    status_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    prefix_to_source, explicit_case_to_source = _source_lookup(sources)

    real_cases = [case for case in cases if str(case.get("id", "")).startswith("real-")]
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"case[{index}] is not an object")
            continue
        case_id = str(case.get("id") or "")
        for field in ("id", "entry_text", "current_text", "expected_status"):
            if not case.get(field):
                errors.append(f"{case_id or f'case[{index}]'} missing {field}")
        status = str(case.get("expected_status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        if case_id.startswith("real-"):
            source_id = _case_source_id(
                case_id,
                prefix_to_source=prefix_to_source,
                explicit_case_to_source=explicit_case_to_source,
            )
            if source_id is None:
                errors.append(f"{case_id} has no matching source manifest entry")
                source_id = "unknown"
            source_counts[source_id] = source_counts.get(source_id, 0) + 1
            if not case.get("owner"):
                warnings.append(f"{case_id} has no owner label")
        else:
            source_counts["synthetic"] = source_counts.get("synthetic", 0) + 1

    source_quality: dict[str, dict[str, Any]] = {}
    rebuild_plan: list[dict[str, Any]] = []
    manifest_golden_total = 0
    for source in sources:
        if not isinstance(source, dict):
            errors.append("source manifest contains a non-object entry")
            continue
        source_id = str(source.get("source_id") or "unknown")
        golden_count = _golden_case_count(source)
        manifest_golden_total += golden_count
        commands = source.get("rebuild_commands")
        commands = commands if isinstance(commands, list) else []
        source_quality[source_id] = {
            "golden_case_count": golden_count,
            "candidate_only": bool(source.get("candidate_only")),
            "has_url": bool(source.get("url")),
            "has_verified_with": bool(source.get("verified_with")),
            "has_rebuild_commands": bool(commands),
            "has_subtitle_cache": bool(source.get("subtitle_cache")),
            "has_representative_audio_clip": bool(source.get("representative_audio_clip")),
            "license": source.get("license"),
        }
        if commands:
            rebuild_plan.append({"source_id": source_id, "commands": commands})
        if golden_count <= 0:
            continue
        license_text = str(source.get("license") or "").lower()
        if not _public_label_license_allowed(license_text):
            errors.append(f"{source_id} does not declare an approved public label license")
        for field in ("url", "verified_with", "rebuild_commands"):
            if not source.get(field):
                errors.append(f"{source_id} missing {field}")
        if not source.get("subtitle_cache"):
            warnings.append(f"{source_id} has no subtitle_cache path")
        if not source.get("representative_audio_clip"):
            warnings.append(f"{source_id} has no representative_audio_clip path")
        if require_cache:
            for field in ("subtitle_cache", "representative_audio_clip"):
                cache_path = source.get(field)
                if cache_path and not (ROOT / str(cache_path)).exists():
                    errors.append(f"{source_id} cache path missing on disk: {cache_path}")

    real_case_count = len(real_cases)
    if real_case_count < target_real_cases:
        errors.append(f"real meeting labels below target: {real_case_count}/{target_real_cases}")
    if manifest_golden_total != real_case_count:
        errors.append(
            f"manifest golden label total {manifest_golden_total} != fixture real label count {real_case_count}"
        )

    return {
        "fixture_path": str(fixture_path),
        "source_manifest_path": str(source_manifest_path),
        "case_count": len(cases),
        "real_case_count": real_case_count,
        "target_real_cases": target_real_cases,
        "status_counts": dict(sorted(status_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "source_quality": source_quality,
        "rebuild_plan": rebuild_plan,
        "errors": errors,
        "warnings": warnings,
        "passed": not errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=FIXTURE_PATH)
    parser.add_argument("--source-manifest", type=Path, default=SOURCE_MANIFEST_PATH)
    parser.add_argument("--target-real-cases", type=int, default=100)
    parser.add_argument("--require-cache", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--rebuild-plan-output", type=Path)
    args = parser.parse_args()

    report = audit_accuracy_set(
        fixture_path=args.fixture,
        source_manifest_path=args.source_manifest,
        target_real_cases=args.target_real_cases,
        require_cache=args.require_cache,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    if args.rebuild_plan_output:
        args.rebuild_plan_output.parent.mkdir(parents=True, exist_ok=True)
        args.rebuild_plan_output.write_text(
            json.dumps(report["rebuild_plan"], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
