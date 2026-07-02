# iOS Badge and Backend LaunchAgent Session Summary — 2026-07-02

This is the current handoff note for the iPhone badge fix, Promise Radar deep-link
verification work, and Mac mini private staging backend uptime change. Use this
file before re-diagnosing "서버에 연결할 수 없습니다" on the connected iPhone.

## Current Device/Backend Baseline

- iPhone: `00008150-000239020C08401C`, CoreDevice `C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA`, iPhone 17 Pro, iOS 26.5.1.
- Android: `76aadc20`, Redmi Note 9 Pro, Android 12.
- Private staging API URL: `http://100.69.69.119:8000/api/v1`.
- Production URL `https://api.voicetextnote.com/api/v1` is still not the live device-test target.
- Mac mini backend API is now supervised by macOS LaunchAgent `com.voicetextnote.backend-api`.
- LaunchAgent plist: `/Users/ibkim/Library/LaunchAgents/com.voicetextnote.backend-api.plist`.
- Logs:
  - `logs/backend-api.launchd.out.log`
  - `logs/backend-api.launchd.err.log`

## Work Completed

- Fixed stale iOS app icon badge count:
  - `client/ios/Runner/AppDelegate.swift`
    - Clears badge at launch, app active, and notification tap.
    - Uses `UNUserNotificationCenter.setBadgeCount(0)` on iOS 16+ and `applicationIconBadgeNumber = 0` fallback for iOS 15.
  - `client/lib/services/push_notification_service.dart`
    - Added `clearAppBadge()` platform-channel call.
  - `client/lib/main.dart`
    - Calls badge clear at app startup and on `AppLifecycleState.resumed`.
  - Tests added in:
    - `client/test/services/push_notification_service_test.dart`
    - `client/test/services/app_delegate_method_channel_test.dart`
- Installed the updated Release app on the iPhone and launched it.
- User verified the icon badge number `1` disappeared.
- Diagnosed the later "서버에 연결할 수 없습니다" message:
  - `curl http://100.69.69.119:8000/api/v1/health` initially failed with connection refused.
  - Root cause was the backend API process being stopped, not an app code regression.
- Added persistent backend API supervisor scripts:
  - `scripts/run_backend_api.sh`
  - `scripts/install_backend_api_launch_agent.sh`
- Installed LaunchAgent `com.voicetextnote.backend-api`.
- Updated related docs:
  - `README.md`
  - `docs/release-procedure.md`
  - `docs/google-auth-ios-runbook.md`
  - `docs/stt-processing-runbook.md`
  - `docs/e2e-device-checklist.md`

## Verification Evidence

- Flutter analyzer:
  - `flutter analyze lib/main.dart lib/services/push_notification_service.dart test/services/push_notification_service_test.dart test/services/app_delegate_method_channel_test.dart`
  - Result: `No issues found!`
- Flutter tests:
  - `flutter test test/services/push_notification_service_test.dart test/services/app_delegate_method_channel_test.dart`
  - Result: `+30: All tests passed!`
- iOS Release native build:
  - `xcodebuild -workspace ios/Runner.xcworkspace -scheme Runner -configuration Release -destination 'id=00008150-000239020C08401C' build`
  - Result: `** BUILD SUCCEEDED **`
- iPhone install/launch:
  - `xcrun devicectl device install app --device 00008150-000239020C08401C .../Runner.app`
  - `xcrun devicectl device process launch --device 00008150-000239020C08401C --terminate-existing com.voicetextnote.app`
  - Result: app installed and launched.
- LaunchAgent:
  - `launchctl print gui/$(id -u)/com.voicetextnote.backend-api`
  - Result: `state = running`, `properties = keepalive | runatload | inferred program`.
- Health:
  - `curl http://100.69.69.119:8000/api/v1/health`
  - Result: HTTP 200, API/Redis/Celery healthy, active Celery worker count 1.
- Restart resilience:
  - Killed the API process listening on port 8000.
  - LaunchAgent restarted it with a new PID.
  - `/api/v1/health` returned 200 again.
- iPhone app after LaunchAgent:
  - Relaunched app.
  - Backend log showed iPhone `Dart/3.12` requests returning 200 for:
    - `/api/v1/promise-radar/digest`
    - `/api/v1/promise-radar/dashboard`
    - `/api/v1/history`

## Current Known State

- LaunchAgent keeps the backend API alive after user login and after process crashes.
- It is not a system LaunchDaemon, so it does not start before the `ibkim` user logs in.
- Celery is still managed separately by existing session/service state. Current health confirmed one active Celery worker.
- `.omx/*`, Gradle cache locks, `.cache/`, `client/.cache/`, and `.xcresult` bundles are runtime artifacts unless a later release-evidence commit explicitly stages sanitized outputs.

## Recurrence Prevention

- If iPhone says "서버에 연결할 수 없습니다", check backend process health before changing app code:

```bash
launchctl print gui/$(id -u)/com.voicetextnote.backend-api | rg 'state =|pid =|properties ='
curl http://100.69.69.119:8000/api/v1/health
tail -80 logs/backend-api.launchd.err.log
```

- Do not revive private staging with a one-off `tmux` API process unless explicitly debugging; use:

```bash
./scripts/install_backend_api_launch_agent.sh
```

- If the iOS icon badge returns, verify the installed app includes the badge clear changes and launch it once. Badge should clear when the app becomes active.
