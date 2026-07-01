# Promise Radar v12 Session Summary

> Current baseline note: v12 counts are preserved as session history. The latest Promise Radar baseline is v14 in `docs/session-summary-2026-07-02-promise-radar-v14.md`: 193 total accuracy cases, 126 real-meeting/audio-derived labels, evaluator accuracy 1.0.

## Scope

- Completed the next 1-7 Promise Radar hardening pass.
- Generated real-recording Promise Radar E2E evidence against `http://100.69.69.119:8000/api/v1`.
- Preserved release-gate honesty: iPhone and Android physical-device connectivity is recorded in the Promise Radar evidence, while full production release E2E evidence remains a separate strict gate.

## Implemented

- Added `backend/scripts/generate_promise_radar_e2e_evidence.py`.
  - Uses the latest completed real summary task by default.
  - Creates a short-lived JWT for the selected task owner.
  - Verifies Promise Radar load, Autopilot preview, Review Queue, pre-meeting brief, calendar export, assignee/quality endpoint, and due-push dispatch contract.
  - Captures iPhone/Android device state and redacts hardware serial, ADB serial, ECID, UDID, and tunnel IP values.
- Added `docs/promise-radar-e2e-evidence-2026-07-01.json`.
  - Actual recording task: `7f9942fe-dbc9-4ead-a712-098954363979`.
  - Recording chain: minutes `12c1b7e0-cdf8-4ac2-9c52-650085547838`, diarization `696c1a31-d2de-4f07-b761-83cca23cd660`, STT `35b3fe87-5cf4-4bdb-9ff4-b28cbc3938aa`.
  - Duration: `60.973` seconds.
  - All Promise Radar API contract checks passed with HTTP 200.
- Added a direct route-registration regression test for `/api/v1/promise-radar/{task_id}` and related OpenAPI paths.
- Added pre-meeting `checkpoints` to the backend schema and Flutter model/UI.
- Strengthened assignee matching for Korean honorifics/titles and email-local aliases.
- Added `X-VOICE-TEXTNOTE-PROMISE-ID` to ICS exports.
- Added Google Tasks sync-contract/idempotency metadata to export/sync/update flows.
- Added Promise Radar Prometheus metrics for build, Autopilot, review queue, notifications, and external sync.
- Expanded the accuracy fixture to `179` cases while preserving `112` real-meeting labels.
- Updated release/benchmark/privacy docs to reflect ZAI and the current Promise Radar state.
- Follow-up: Android `Redmi Note 9 Pro` was running a stale release APK, so the result screen showed 11 tabs and no `약속 레이더` menu. Reinstalling the latest staging release with `API_BASE_URL=http://100.69.69.119:8000/api/v1` restored the 12-tab result screen and placed `약속 레이더` at tab 4.

## Verification

- `.venv/bin/pytest --no-cov backend/tests/unit/test_promise_radar_service.py backend/tests/unit/test_promise_radar_route_registration.py -q` -> `13 passed`.
- `.venv/bin/python backend/scripts/evaluate_promise_radar_accuracy.py --report --target-real-cases 100` -> `179/179`, accuracy `1.0`, failures `[]`.
- `.venv/bin/python backend/scripts/audit_promise_radar_accuracy_set.py --target-real-cases 100` -> passed, real case count `112`.
- `.venv/bin/ruff check ...` -> `All checks passed!`.
- `flutter analyze lib/models/promise_radar.dart lib/screens/recording_screen.dart test/models/promise_radar_test.dart` -> `No issues found`.
- `flutter test test/models/promise_radar_test.dart` -> `All tests passed`.
- `backend/scripts/generate_promise_radar_e2e_evidence.py` -> `overall_pass: true`; Android ADB device connected with model `Redmi_Note_9_Pro`, ADB serial redacted.
- `client/scripts/verify_release_readiness.py --strict` with current Android/iOS device env -> staging cleartext allow-list, Android device, iOS device, and Firebase service account checks pass; remaining failures are 9 external production-release inputs.
- `flutter run --release --no-pub --no-resident -d 76aadc20 --dart-define=ENV=staging --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1` -> Android release APK installed; `lastUpdateTime=2026-07-01 15:39:18`; UIAutomator showed `약속 레이더\n탭 12개 중 4번째`.

## Remaining Release Notes

- `client/scripts/verify_release_readiness.py --strict` still fails without production release inputs: APNs auth key/key id/team id, App Store Connect API key/key id/issuer id, production entitlements evidence, Firebase test token, and full release E2E evidence.
- The app intentionally uses `100.69.69.119` for private staging release testing. Readiness checks allow only that scoped staging cleartext exception and continue to fail arbitrary HTTP domains.
