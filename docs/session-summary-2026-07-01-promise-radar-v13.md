# Promise Radar v13 Session Summary

> Current baseline note: v13 is preserved as session history. The latest Promise Radar baseline is v14 in `docs/session-summary-2026-07-02-promise-radar-v14.md`: 193 total accuracy cases, 126 real-meeting/audio-derived labels, evaluator accuracy 1.0.

Date: 2026-07-01

## Scope

- Implemented the next Promise Radar hardening pass for priorities 1-7:
  Android device E2E gate, pre-meeting push, owner responsibility scores,
  review/evidence UI reinforcement, Google Tasks sync visibility, recurring
  meeting series linking, and regression coverage.

## Code Updates

- Added backend schemas for `PromiseResponsibilityScore` and `PromiseMeetingSeries`.
- Extended dashboard and next-meeting briefing responses with responsibility scores and recurring meeting series.
- Added API endpoints:
  - `GET /api/v1/promise-radar/responsibility-scores`
  - `GET /api/v1/promise-radar/meeting-series`
  - `POST /api/v1/promise-radar/briefing/pre-meeting/notifications`
- Added `PromiseRadarService.dispatch_pre_meeting_brief_notifications`.
  It sends `promise_radar_pre_meeting_brief` FCM data once per user/day and does not touch due-promise `notification_sent_at`.
- Added scheduler support behind `PROMISE_RADAR_PRE_MEETING_PUSH_ENABLED=true`.
- Added Flutter model/API/provider support for responsibility scores and meeting series.
- Added Result-screen sections:
  - `담당자 책임 점수`
  - `반복회의 연결`
  - `회의 전 브리프 푸시` toolbar action
- Added Android gate script:
  - `client/scripts/verify_promise_radar_device_gate.py`
  - Checks install metadata, UIAutomator `약속 레이더`/`탭 12개`, and APK staging URL guard.

## Verification

- `.venv/bin/ruff check ...` -> passed.
- `.venv/bin/pytest --no-cov backend/tests/test_promise_radar_device_gate.py backend/tests/unit/test_promise_radar_route_registration.py backend/tests/unit/test_promise_radar_service.py -q` -> `17 passed, 1 warning`.
- `flutter analyze lib/models/promise_radar.dart lib/services/promise_radar_api.dart lib/providers/result_provider.dart lib/screens/result_screen.dart test/models/promise_radar_test.dart` -> no issues.
- `flutter test test/models/promise_radar_test.dart` -> all tests passed.
- `python3 client/scripts/verify_promise_radar_device_gate.py --serial 76aadc20` -> `PASS Promise Radar Android device gate`.

## Notes

- During Flutter test startup, `client/ios/Flutter/ephemeral/Packages/.packages`
  existed as a generated directory and blocked Flutter cleanup. It was removed
  because it is an ephemeral generated artifact, then the model test passed.
- Android `Redmi Note 9 Pro` serial `76aadc20` was connected after implementation and the full device gate passed. Future Android Promise Radar menu regressions should run:

```bash
python3 client/scripts/verify_promise_radar_device_gate.py --serial 76aadc20
```

If the gate reports `탭 11개` or missing `약속 레이더`, reinstall the staging release with:

```bash
cd client
flutter run --release --no-pub --no-resident \
  -d 76aadc20 \
  --dart-define=ENV=staging \
  --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1
```
