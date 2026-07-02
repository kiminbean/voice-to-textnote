# Promise Radar v17 Session Summary

> Superseded: Promise Radar v19 is the current baseline as of 2026-07-02. Keep this file as historical context and use docs/session-summary-2026-07-02-promise-radar-v19.md for current counts, gates, and recurrence-prevention notes.

> Current baseline note: v17 counts are preserved as session history. The latest Promise Radar baseline is v18 in `docs/session-summary-2026-07-02-promise-radar-v18.md`: 849 total accuracy cases, 782 real-meeting/audio-derived labels, evaluator accuracy 1.0, extraction recall 50/50, Google Tasks OAuth callback/token exchange, preview-only Autopilot default, Live Promise Coach recording surface, Evidence Room v18 policy, and Command Center `target_case_count=700`.

## Scope

- Completed the next autonomous Promise Radar hardening pass after v16.
- Added production learning telemetry, Autopilot undo/quarantine, Live Promise Coach, privacy-safe Evidence Room, Meeting Recipe policy, and Google Tasks OAuth start URL.
- Expanded the YouTube real-meeting/audio-derived accuracy baseline from 502 to 562 labels.

## Implemented

- Expanded `backend/tests/fixtures/promise_radar_accuracy_cases.json` to `629` total cases.
  - `562` cases are real-meeting/audio-derived labels.
  - v17 added 60 labels from Creative Commons YouTube meeting audio/caption sources.
  - Added Korean policy/debate sources and an English multi-speaker city council source.
  - Evaluator result: `629/629`, accuracy `1.0`.
- Updated `backend/tests/fixtures/promise_radar_real_meeting_sources.json`.
  - Added v17 source manifests with `subtitle_cache`, `representative_audio_clip`, `golden_case_id_prefix`, and reproducible `yt-dlp` audio/subtitle extraction commands.
  - `.cache/promise-radar-youtube-*` and `.cache/promise-radar-audio-*` remain local, uncommitted caches.
- Added backend contracts and APIs:
  - `GET /api/v1/promise-radar/telemetry/learning`
  - `GET /api/v1/promise-radar/autopilot/quarantine`
  - `POST /api/v1/promise-radar/ledger/{entry_id}/autopilot-undo`
  - `GET /api/v1/promise-radar/live-coach`
  - `GET /api/v1/promise-radar/evidence-room`
  - `POST /api/v1/promise-radar/ledger/{entry_id}/evidence-room/share-link`
  - `GET /api/v1/promise-radar/meeting-recipe`
  - `POST /api/v1/promise-radar/external-task/google-oauth/start`
- Extended Command Center backend contract with:
  - `learning_telemetry`
  - `live_coach`
  - `evidence_room`
  - `autopilot_quarantine`
  - `meeting_recipe`
  - v17 focus/action items.
- Extended Flutter Command Center UI/model/tests.
  - Added Production Learning Telemetry, Live Promise Coach, Autopilot Undo/Quarantine, Privacy-Safe Evidence Room, and Meeting Recipe panels.
- Updated `backend/scripts/generate_promise_radar_e2e_evidence.py`.
  - Calls Command Center with `target_case_count=560`.
  - Requires 629+ total accuracy cases, 560+ real labels, extraction recall >= 0.95, and v17 Command Center fields.
- Added sanitized evidence summary:
  - `docs/promise-radar-e2e-evidence-2026-07-02-v17-summary.json`

## Verification

- `.venv/bin/python backend/scripts/evaluate_promise_radar_accuracy.py --report --target-real-cases 560`
  - `case_count: 629`, `correct_count: 629`, `accuracy: 1.0`, `failures: 0`, `real_meeting_case_count: 562`.
- `.venv/bin/python backend/scripts/audit_promise_radar_accuracy_set.py --target-real-cases 560`
  - `passed: true`, `case_count: 629`, `real_case_count: 562`, `errors: 0`, `warnings: 4`.
  - Warnings are historical v1 source-cache metadata gaps; v17 sources include subtitle/audio cache paths.
- `.venv/bin/python backend/scripts/evaluate_promise_radar_extraction.py --target-cases 50 --min-recall 0.95`
  - `case_count: 50`, `expected: 50`, `matched: 50`, `recall: 1.0`, `failures: []`.
- `.venv/bin/python -m ruff check backend/schemas/promise_radar.py backend/services/promise_radar_service.py backend/app/api/v1/minutes/promise_radar.py backend/tests/unit/test_promise_radar_service.py backend/tests/unit/test_promise_radar_route_registration.py backend/scripts/generate_promise_radar_e2e_evidence.py`
  - `All checks passed!`
- `.venv/bin/pytest backend/tests/unit/test_promise_radar_route_registration.py backend/tests/unit/test_promise_radar_service.py -q --no-cov`
  - `20 passed`.
- `flutter analyze lib/models/promise_radar.dart lib/screens/promise_review_inbox_screen.dart`
  - `No issues found!`
- `flutter test test/models/promise_radar_test.dart`
  - `All tests passed!`
- `.venv/bin/python backend/scripts/generate_promise_radar_e2e_evidence.py --output .cache/promise-radar-e2e-v17-check.json`
  - `overall_pass: true`.
  - Both iOS and Android USB devices were detected.
  - Command Center v17 contract passed against `http://100.69.69.119:8000/api/v1` after starting the local backend.
  - Sanitized highlights: `accuracy_case_count: 629`, `real_meeting_case_count: 562`, `learning_telemetry_event_count: 38`, `live_coach_prompt_count: 10`, `meeting_recipe_key: team_sync`.

## Release Notes

- v17 is a feature/readiness improvement and does not add strict release required keys by itself.
- If v17 Command Center checks become strict release evidence, update `REQUIRED_E2E_SCENARIOS`, scaffold/example evidence, release-readiness tests, and `docs/e2e-device-checklist.md` in the same change.
- Historical v10-v17 session summaries keep their original counts for traceability. Current docs should use the v18 baseline: `849` total cases, `782` real-meeting/audio-derived labels, evaluator accuracy `1.0`, extraction recall `50/50`.
- The updated physical-device E2E generator passed after the v17 backend was started locally. Raw device/API evidence remains in `.cache/promise-radar-e2e-v17-check.json` and is intentionally uncommitted.
