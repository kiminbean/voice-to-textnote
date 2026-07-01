# Promise Radar v16 Session Summary

## Scope

- Completed the next autonomous 1-7 Promise Radar hardening pass after v15 Command Center.
- Raised the real-meeting accuracy target from 300+ to 500+ labels.
- Added a separate false-negative extraction recall gate so missed promises are caught before status scoring.
- Extended Command Center with operator actions, Google Tasks OAuth readiness, learning scope context, and Memory Graph relationship previews.

## Implemented

- Expanded `backend/tests/fixtures/promise_radar_accuracy_cases.json` to `569` total cases.
  - `502` cases are real-meeting/audio-derived labels.
  - Evaluator result: `569/569`, accuracy `1.0`.
- Updated `backend/tests/fixtures/promise_radar_real_meeting_sources.json` so source `golden_case_count` values match the 502 real labels.
- Added `backend/tests/fixtures/promise_radar_extraction_cases.json`.
  - `50` false-negative guard cases.
  - Mixed English/Korean action item and next-step payload shapes.
  - Covers dict and string forms for `action_items` and `next_steps`.
- Added `backend/scripts/evaluate_promise_radar_extraction.py`.
  - Default target: 50 cases.
  - Default minimum recall: 0.95.
- Broadened deterministic promise extraction.
  - `action_items` can now be dict or string.
  - Dict payload text can come from `task`, `title`, `text`, `description`, or `summary`.
  - `next_steps` can now be dict or string and can preserve owner/due/priority when available.
- Tightened the Korean completed marker.
  - Replaced overly broad standalone `반영` with narrower `반영했` and `반영 완료`.
- Extended Command Center backend contract.
  - `extraction_recall`: false-negative recall report.
  - `actions`: existing navigable/API operator actions only.
  - `google_tasks_oauth.production_ready`, `missing_setup`, `required_backend_env`, `verification_steps`.
  - `learning_insight.scope_breakdown` and `scope_recommendations`.
- Extended Flutter Command Center UI/model/tests.
  - Accuracy panel now shows status accuracy and extraction recall.
  - Memory Graph panel now shows top nodes and edges.
  - Learning panel shows scope sample breakdown and recommendations.
  - Google Tasks panel shows production readiness/missing setup.
  - Command Center shows operator action rows.
- Updated `backend/scripts/generate_promise_radar_e2e_evidence.py`.
  - Calls Command Center with `target_case_count=500`.
  - Requires 500+ accuracy cases, 500+ real labels, 50+ extraction cases, extraction recall >= 0.95, operator actions, and OAuth readiness field.
- Added sanitized release evidence summary:
  - `docs/promise-radar-e2e-evidence-2026-07-02-v16-summary.json`
  - Raw `.cache` evidence remains uncommitted because it contains device command output.

## Verification

- `python backend/scripts/evaluate_promise_radar_accuracy.py --report --target-real-cases 500`
  - `case_count: 569`, `correct_count: 569`, `accuracy: 1.0`, `failures: []`, `real_meeting_case_count: 502`.
- `python backend/scripts/evaluate_promise_radar_extraction.py --target-cases 50 --min-recall 0.95`
  - `case_count: 50`, `expected: 50`, `matched: 50`, `recall: 1.0`, `failures: []`.
- `python -m ruff check backend/schemas/promise_radar.py backend/services/promise_radar_service.py backend/app/api/v1/minutes/promise_radar.py backend/scripts/evaluate_promise_radar_extraction.py backend/scripts/generate_promise_radar_e2e_evidence.py backend/tests/unit/test_promise_radar_service.py backend/tests/unit/test_promise_radar_route_registration.py`
  - `All checks passed!`
- `python -m pytest backend/tests/unit/test_promise_radar_route_registration.py backend/tests/unit/test_promise_radar_service.py -q --no-cov`
  - `18 passed`.
- `flutter analyze lib/models/promise_radar.dart lib/screens/promise_review_inbox_screen.dart test/models/promise_radar_test.dart`
  - `No issues found!`
- `flutter test test/models/promise_radar_test.dart`
  - `All tests passed!`

## Release Notes

- v16 is a feature/readiness improvement and does not add strict release required keys by itself.
- If v16 Command Center checks become strict release evidence, update `REQUIRED_E2E_SCENARIOS`, scaffold/example evidence, release-readiness tests, and `docs/e2e-device-checklist.md` in the same change.
- Historical v10-v15 session summaries keep their original counts for traceability. Current docs should use the v16 baseline: `569` total cases, `502` real-meeting/audio-derived labels, evaluator accuracy `1.0`, extraction recall `50/50`.
- The physical-device E2E cache collected before v16 passed the v15 Command Center contract. Rerun the updated generator after deploying/restarting the v16 backend to collect v16 physical-device evidence.
