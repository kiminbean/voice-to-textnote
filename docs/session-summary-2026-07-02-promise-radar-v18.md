# Promise Radar v18 Session Summary

> Superseded: Promise Radar v19 is the current baseline as of 2026-07-02. Keep this file as historical context and use docs/session-summary-2026-07-02-promise-radar-v19.md for current counts, gates, and recurrence-prevention notes.

## Scope

- Completed the autonomous Promise Radar priority 2-7 hardening pass after v17.
- Expanded the real-meeting accuracy label baseline beyond YouTube-only sources.
- Hardened Autopilot, Evidence Room, Live Coach, SLA scorecard, Google Tasks OAuth, and Command Center release gates.

## Implemented

- Expanded `backend/tests/fixtures/promise_radar_accuracy_cases.json` to `849` total cases.
  - `782` cases are real-meeting/audio-derived labels.
  - Added YouTube-external public meeting sources:
    - Hugging Face `lytang/MeetingBank-transcript`: `120` v18 labels, CC BY-NC-SA 4.0.
    - Hugging Face `pszemraj/qmsum-cleaned`: `100` v18 labels, Apache-2.0 public QMSum mirror.
  - AMI was inspected as a candidate source, but the Hugging Face raw CSV path returned unauthorized access in this environment, so it was not used for v18 fixture labels.
  - Evaluator result: `849/849`, accuracy `1.0`.
- Updated `backend/tests/fixtures/promise_radar_real_meeting_sources.json`.
  - v18 source manifests include URL, license, verification command, local sample/cache path, case prefix, and rebuild commands.
  - `.cache/promise-radar-hf-v18/` remains a local, uncommitted provenance cache.
- Added Google Tasks OAuth callback/token exchange:
  - Backend endpoint: `POST /api/v1/promise-radar/external-task/google-oauth/callback`.
  - Flutter API method: `exchangeGoogleTasksOAuthCode`.
  - Raw `access_token` is omitted by default; the response uses redacted previews for operator verification.
- Changed Autopilot default safety posture:
  - Default automation policy mode is now `preview_only`.
  - Explicit `safe_auto` policy is required before automatic status application.
  - Command Center quarantine summary reports safe mode and auto-apply blocked count.
- Added SLA/responsibility scoring fields:
  - `due_today_count`
  - `sla_watch_count`
  - `escalation_count`
- Hardened Evidence Room v18:
  - Max TTL policy is exposed.
  - Evidence share links require authentication.
  - Audit log event and effective TTL are returned.
- Exposed Live Promise Coach in the recording screen.
  - `GET /api/v1/promise-radar/live-coach` is now wired through Flutter provider/API.
  - Recording UI shows the coach panel only while recording and only when prompt data exists.
- Updated release evidence gate:
  - `backend/scripts/generate_promise_radar_e2e_evidence.py` calls Command Center with `target_case_count=700`.
  - The gate now requires `849+` total accuracy cases and `700+` real labels.
- Added sanitized v18 local verification summary:
  - `docs/promise-radar-e2e-evidence-2026-07-02-v18-summary.json`

## Verification

- `python backend/scripts/evaluate_promise_radar_accuracy.py --report --target-real-cases 700`
  - `case_count: 849`, `correct_count: 849`, `accuracy: 1.0`, `failures: 0`, `real_meeting_case_count: 782`.
- `python backend/scripts/audit_promise_radar_accuracy_set.py --target-real-cases 700`
  - `passed: true`, `case_count: 849`, `real_case_count: 782`, `errors: 0`, `warnings: 4`.
  - Warnings are historical v1 source-cache metadata gaps; v18 Hugging Face sources include provenance sample/cache paths.
- `.venv/bin/python -m pytest backend/tests/unit/test_promise_radar_service.py backend/tests/unit/test_promise_radar_route_registration.py -q`
  - Functional result: `22 passed`.
  - Repo-wide coverage gate fails for this targeted subset because total coverage is `40.35%` below the configured `85%` threshold; this is not a Promise Radar test failure.
- `flutter test test/models/promise_radar_test.dart`
  - `All tests passed!`

## Source Notes

- Google OAuth native/installed app flow should use authorization code exchange and PKCE. See `https://developers.google.com/identity/protocols/oauth2/native-app`.
- Google Tasks uses the `https://www.googleapis.com/auth/tasks` scope. See `https://developers.google.com/workspace/tasks/auth`.
- MeetingBank dataset: `https://meetingbank.github.io/dataset/` and `https://huggingface.co/datasets/lytang/MeetingBank-transcript`.
- QMSum dataset: `https://github.com/Yale-LILY/QMSum` and `https://huggingface.co/datasets/pszemraj/qmsum-cleaned`.

## Release Notes

- v18 is a feature/readiness improvement and does not itself mark strict production release readiness complete.
- Do not lower `target_case_count` from `700` or real-label gate from `700` without adding an explicit migration note.
- Do not change Autopilot default back to `safe_auto`; `safe_auto` must remain an explicit team/operator policy decision.
- Google OAuth callback responses must not log or persist raw access tokens by default.
