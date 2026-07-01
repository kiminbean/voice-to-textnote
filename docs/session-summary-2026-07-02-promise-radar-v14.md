# Promise Radar v14 Session Summary

> Current baseline note: v14 counts are preserved as session history. The latest Promise Radar baseline is v16 in `docs/session-summary-2026-07-02-promise-radar-v16.md`: 569 total accuracy cases, 502 real-meeting/audio-derived labels, evaluator accuracy 1.0, extraction recall 50/50.

## Scope

- Completed the next 1-7 Promise Radar hardening pass for operational reliability.
- Added a single Command Center surface so review, learning, evidence, digest, external sync, and accuracy state are not scattered across separate menus.
- Expanded the real-meeting accuracy set with Creative Commons Town Meeting TV YouTube-derived meeting labels and representative audio clip rebuild commands.

## Implemented

- Added `GET /api/v1/promise-radar/command-center`.
  - Aggregates dashboard, Autopilot Review Queue, Learning Loop insight, Daily Digest, pre-meeting brief, external-task reconcile, accuracy report, Evidence Audit, Google Tasks OAuth guide, and prioritized focus items.
- Upgraded Learning Loop to v3.
  - Exposes status-specific sample counts and false-positive rates.
  - Exposes alias graph size and Evidence Lock state.
  - Keeps completed/delayed/changed/dismissed feedback isolated by status.
- Added Command Center Flutter support.
  - `PromiseCommandCenter` model, API method, Riverpod provider, and `약속 레이더 Command Center` UI.
  - Shows focus items, Learning Loop v3 chips, Evidence Audit, Digest/Brief summary, Google Tasks OAuth guide, and accuracy baseline.
- Added Evidence Audit rollups.
  - Locked/weak evidence counts, missing timestamp/speaker counts, marker-hit count, average similarity, and operator notes are available in the Command Center.
- Added Google Tasks OAuth guide.
  - Documents the `https://www.googleapis.com/auth/tasks` scope, app-driven approval steps, one-request access-token handling, and no-token-storage rule in the API response and UI.
- Fixed duplicate daily send detection.
  - Digest and pre-meeting duplicate checks now compare the event payload `sent_at` local date first instead of relying on UTC-naive `created_at` filtering.
- Expanded accuracy fixtures from `179` to `193` cases.
  - Real meeting/audio-derived labels increased from `112` to `126`.
  - Added 14 labels from two Burlington Airport Commission/Town Meeting TV YouTube sources.
  - Representative `.mp3` clips were extracted under `.cache/promise-radar-audio-v12/`; cache/audio files are intentionally not tracked by git.

## Verification

- `.venv/bin/pytest backend/tests/unit/test_promise_radar_service.py::test_ledger_merge_split_history_dashboard_and_due_push -q --no-cov` -> `1 passed`.
- `.venv/bin/pytest backend/tests/unit/test_promise_radar_service.py::test_command_center_aggregates_learning_accuracy_and_oauth backend/tests/unit/test_promise_radar_route_registration.py -q --no-cov` -> `2 passed`.
- `python backend/scripts/evaluate_promise_radar_accuracy.py --report --target-real-cases 100` -> `case_count: 193`, `correct_count: 193`, `accuracy: 1.0`, `failures: []`.
- `python backend/scripts/audit_promise_radar_accuracy_set.py --target-real-cases 100` -> passed; no fixture/source mismatch errors.
- `flutter analyze` -> `No issues found`.

## Release Notes

- The v14 Command Center is a feature/readiness improvement, not a new strict release E2E scenario by itself.
- Do not add Command Center or new Promise Radar checks to `REQUIRED_E2E_SCENARIOS` unless the strict readiness constants, scaffold/example evidence, and release-readiness tests are updated in the same change.
- Historical v10/v11/v12/v13/v14 session summaries keep their original counts for traceability. Current docs should use the v16 baseline: `569` total cases, `502` real-meeting/audio-derived labels, evaluator accuracy `1.0`, extraction recall `50/50`.
- The next accuracy target is 300~500 real meeting/audio-derived labels.
