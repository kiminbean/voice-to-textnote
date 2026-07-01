# Promise Radar v10 Session Summary

> Current baseline note: v10 counts and scope are preserved as session history. The latest Promise Radar baseline is v17 in `docs/session-summary-2026-07-02-promise-radar-v17.md`: 629 total accuracy cases, 562 real-meeting/audio-derived labels, evaluator accuracy 1.0, extraction recall 50/50, and physical-device E2E generator `overall_pass=true`.

## Scope

- Expanded `backend/tests/fixtures/promise_radar_accuracy_cases.json` from 72 to 172 cases.
- Raised real meeting/audio-derived labels from 12 to 112 cases, meeting the 100+ target.
- Added Creative Commons Town Meeting TV Burlington Airport Commission sources to `backend/tests/fixtures/promise_radar_real_meeting_sources.json`.
- Extracted representative audio clips for every v10 source that contributed labels. Audio and subtitle caches stay under `.cache/promise-radar-*` and are not committed.

## v10 Product Changes

- Added `GET /api/v1/promise-radar/accuracy/report` and Flutter accuracy report sheet.
- Added Review Queue filters: all, conflict, weak evidence, high risk, due.
- Added `GET /api/v1/promise-radar/ledger/{entry_id}/evidence-comparison` and Flutter `근거 비교`.
- Added digest local-time one-hour window and quiet-hours enforcement.
- Added `POST /api/v1/promise-radar/ledger/{entry_id}/external-task/update` for Google Tasks state/title push-update.
- Added ledger `identity_confidence` and `identity_confidence_factors` from owner, assignee, speaker label/profile, evidence speaker, and voiceprint similarity.

## Real Meeting Sources

Direct v10 label sources:

- https://www.youtube.com/watch?v=4P6bVZqSKpw
- https://www.youtube.com/watch?v=PPELeoDMr2s
- https://www.youtube.com/watch?v=yLXVG8ktaag
- https://www.youtube.com/watch?v=1j1rB2aupYQ
- https://www.youtube.com/watch?v=KHcsyoDitJg

Candidate CC sources retained for future expansion:

- https://www.youtube.com/watch?v=tU_US5LxsXk
- https://www.youtube.com/watch?v=BhhxfrZc6sg

Previous v9 real-meeting sources remain:

- https://www.youtube.com/watch?v=oq1XYJ6ggms
- https://www.youtube.com/watch?v=mo7lRpB8ao8

## Rebuild Notes

- Use `yt-dlp --dump-single-json <url>` to verify `Creative Commons Attribution license (reuse allowed)`.
- Use the source manifest `rebuild_commands` to regenerate subtitle JSON3 and representative audio clips.
- Do not commit `.cache/promise-radar-*`; only commit fixture labels and source provenance.
- When adding or changing labels, run `python backend/scripts/evaluate_promise_radar_accuracy.py` and keep `GET /api/v1/promise-radar/accuracy/report` above the real-meeting target.

## Verification

- `python backend/scripts/evaluate_promise_radar_accuracy.py`
  - `case_count: 172`, `correct_count: 172`, `accuracy: 1.0`
- Full backend/Flutter verification was run before commit; see final session report for command output.
