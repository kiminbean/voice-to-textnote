# Promise Radar v9 Session Summary

> Superseded: Promise Radar v19 is the current baseline as of 2026-07-02. Keep this file as historical context and use docs/session-summary-2026-07-02-promise-radar-v19.md for current counts, gates, and recurrence-prevention notes.

> Current baseline note: v9 counts and scope are preserved as session history. The latest Promise Radar baseline is v18 in `docs/session-summary-2026-07-02-promise-radar-v18.md`: 849 total accuracy cases, 782 real-meeting/audio-derived labels, evaluator accuracy 1.0, extraction recall 50/50, Google Tasks OAuth callback/token exchange, preview-only Autopilot default, Live Promise Coach recording surface, and Command Center `target_case_count=700`.

Date: 2026-07-01

## What Changed

- Expanded the Promise Radar golden accuracy set from 60 to 72 cases.
- Added 12 real-meeting-derived labels from Creative Commons Town Meeting TV Burlington Airport Commission meetings:
  - https://www.youtube.com/watch?v=oq1XYJ6ggms
  - https://www.youtube.com/watch?v=mo7lRpB8ao8
- Added `backend/tests/fixtures/promise_radar_real_meeting_sources.json` with source URL, CC license string, segment ranges, label IDs, and `yt-dlp` rebuild commands.
- Strengthened Autopilot status markers for public-meeting motion language such as approval/adoption/order/filed signals.
- Persisted Review Queue rejection via `POST /api/v1/promise-radar/ledger/{entry_id}/autopilot-reject`; rejected candidates are filtered out for the same task/status candidate.
- Added latest Evidence Pack lookup via `GET /api/v1/promise-radar/ledger/{entry_id}/evidence-pack` and exposed it from the Flutter ledger row.
- Added Google Tasks tasklist selection and sync-back:
  - `POST /api/v1/promise-radar/external-task/google-tasklists`
  - `POST /api/v1/promise-radar/ledger/{entry_id}/external-task/sync`
- Added scheduled digest opt-in preference:
  - `GET|PUT /api/v1/promise-radar/digest-preference`
  - Scheduler now requires enabled user preference for scheduled digest pushes.
- Team automation policy updates now require an admin team member for team-scoped changes.
- Conflict Review Queue UI now shows side-by-side signal evidence and labels split as `분리 추천`.

## Regression Prevention

- Do not commit extracted YouTube audio or subtitle cache. Keep `.cache/promise-radar-*/` ignored.
- Keep source provenance in `promise_radar_real_meeting_sources.json` whenever real meeting labels are added.
- Run the accuracy evaluator after marker or label changes; current release gate is 72/72.
- Review Queue rejection must store `autopilot_review_rejected`, not only `learning_feedback`, otherwise the same rejected candidate can reappear.
- Scheduled digest push should remain opt-in; scheduler calls must use `require_enabled_preference=True`.
- Google OAuth access tokens are one-request inputs only and must not be persisted in ledger metadata.

## Verification

- `.venv/bin/ruff check backend/schemas/promise_radar.py backend/services/promise_radar_service.py backend/app/api/v1/minutes/promise_radar.py backend/app/promise_radar_scheduler.py backend/tests/unit/test_promise_radar_service.py backend/scripts/evaluate_promise_radar_accuracy.py`
  - `All checks passed!`
- `.venv/bin/python -m pytest backend/tests/unit/test_promise_radar_service.py -q --no-cov`
  - `9 passed in 0.49s`
- `python backend/scripts/evaluate_promise_radar_accuracy.py`
  - `case_count: 72`, `correct_count: 72`, `accuracy: 1.0`
- `python -m compileall -q backend/schemas/promise_radar.py backend/services/promise_radar_service.py backend/app/api/v1/minutes/promise_radar.py backend/app/promise_radar_scheduler.py`
  - passed with no output
- `cd client && flutter analyze lib/models/promise_radar.dart lib/services/promise_radar_api.dart lib/screens/result_screen.dart test/models/promise_radar_test.dart`
  - `No issues found!`
- `cd client && flutter test test/models/promise_radar_test.dart`
  - `All tests passed!`

## Notes

- A parallel `flutter analyze` run initially failed because another Flutter command held startup/ephemeral state. Re-running analyze alone passed.
- No release build was performed in this session.
