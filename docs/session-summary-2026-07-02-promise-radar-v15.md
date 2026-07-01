# Promise Radar v15 Session Summary

> Current baseline note: v15 counts are preserved as session history. The latest Promise Radar baseline is v16 in `docs/session-summary-2026-07-02-promise-radar-v16.md`: 569 total accuracy cases, 502 real-meeting/audio-derived labels, evaluator accuracy 1.0, extraction recall 50/50.

## Scope

- Completed the next 1-7 Promise Radar hardening pass after v14 Command Center.
- Expanded the real-meeting Accuracy Set beyond the 300-case target with Creative Commons YouTube meeting sources, including Korean and multi-speaker material.
- Added Command Center v15 operating panels for Promise Memory Graph, Autopilot Shadow Mode, Evidence Permission, and Team Scorecard.

## Implemented

- Expanded `backend/tests/fixtures/promise_radar_accuracy_cases.json` to `369` total cases.
  - `302` cases are real-meeting/audio-derived labels.
  - Evaluator result: `369/369`, accuracy `1.0`.
- Added v15 real meeting sources to `backend/tests/fixtures/promise_radar_real_meeting_sources.json`.
  - English Town Meeting TV: South Burlington Library Board, Winooski City Council, Burlington Ward 6 NPA.
  - Korean sources: Welfare TV Yangju Social Welfare Council, Korean Social Worker Association candidate debate, disability rights policy discussion, and DKO Mongolia mission roundtable.
  - Each v15 source stores license, verification command, subtitle cache path, representative audio clip path, golden case prefix/count, and rebuild commands.
- Added Command Center v15 backend contract:
  - `memory_graph`: owner/promise/series/status nodes, edges, delayed/changed clusters, owner alias links, narrative.
  - `shadow_mode`: preview-only Autopilot simulation, would-apply count, Evidence Lock blocks, conflict count, status distribution, learning notes.
  - `evidence_permissions`: scope, export gate, redaction requirement, speaker/timestamp data flags, blocked export count, policy notes.
  - `team_scorecard`: team risk score, owner/open/overdue/high-risk counts, recurring series count, weakest/strongest owner, recommendations.
- Added Flutter model parsing and Command Center panels for the four v15 sections.
- Updated `backend/scripts/generate_promise_radar_e2e_evidence.py` so real-device evidence generation also checks the Command Center v15 contract and the 300+ real-meeting baseline.
- Tightened Autopilot changed-state markers.
  - Removed overly broad `explanation` and standalone `전환`.
  - Added narrower Korean markers `로 전환` and `으로 전환`.

## Source And Cache Policy

- YouTube audio/subtitle artifacts were generated under local `.cache/promise-radar-youtube-v15/` and `.cache/promise-radar-audio-v15/`.
- These cache/audio files are reproducible from the manifest rebuild commands and must not be committed.
- The committed artifact is the fixture/manifest metadata and labels, not downloaded media.

## Verification

- `python backend/scripts/evaluate_promise_radar_accuracy.py --report --target-real-cases 300`
  - `case_count: 369`, `correct_count: 369`, `accuracy: 1.0`, `failures: []`, `real_meeting_case_count: 302`.
- `python backend/scripts/audit_promise_radar_accuracy_set.py --target-real-cases 300`
  - `passed: true`, `case_count: 369`, `real_case_count: 302`, `errors: []`.
- `.venv/bin/ruff check backend/services/promise_radar_service.py backend/schemas/promise_radar.py backend/scripts/generate_promise_radar_e2e_evidence.py backend/tests/unit/test_promise_radar_service.py`
  - `All checks passed!`
- `.venv/bin/pytest backend/tests/unit/test_promise_radar_service.py backend/tests/unit/test_promise_radar_route_registration.py backend/tests/test_promise_radar_device_gate.py -q --no-cov`
  - `24 passed, 1 warning`.
- `flutter test test/models/promise_radar_test.dart`
  - `All tests passed!`
- `flutter analyze`
  - `No issues found!`

## Release Notes

- v15 is a feature/readiness improvement. It does not by itself add new strict release required scenarios.
- If Command Center v15 becomes strict release evidence, update `REQUIRED_E2E_SCENARIOS`, example/scaffold evidence, release-readiness tests, and `docs/e2e-device-checklist.md` in the same change.
- Historical v10-v15 session summaries keep their original counts for traceability. Current docs should use the v16 baseline: `569` total cases, `502` real-meeting/audio-derived labels, evaluator accuracy `1.0`, extraction recall `50/50`.
