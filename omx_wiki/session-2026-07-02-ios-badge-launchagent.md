# Session 2026-07-02: iOS Badge Reset and Backend LaunchAgent

Tags: session-log, ios, backend, launchagent, release, device-e2e, badge

## Summary

The latest iPhone release install fixed the Voice TextNote home-screen badge count that stayed at `1`. A follow-up "서버에 연결할 수 없습니다" message was traced to the Mac mini private staging backend API process being stopped, not to the app build. The API is now supervised by macOS LaunchAgent `com.voicetextnote.backend-api`.

## Current Runtime Baseline

- Repo: `/Users/ibkim/Projects/voice-to-textnote`
- Private staging API base URL: `http://100.69.69.119:8000/api/v1`
- API supervisor: LaunchAgent `com.voicetextnote.backend-api`
- Plist: `/Users/ibkim/Library/LaunchAgents/com.voicetextnote.backend-api.plist`
- Installer: `scripts/install_backend_api_launch_agent.sh`
- Runner: `scripts/run_backend_api.sh`
- Logs:
  - `logs/backend-api.launchd.out.log`
  - `logs/backend-api.launchd.err.log`

## Fixes

- iOS badge count is cleared on app launch, app active, notification tap, and Flutter resume.
- Flutter push notification service exposes `clearAppBadge()` through the existing method channel.
- iPhone release app was rebuilt, installed, and launched on the connected iPhone.
- Backend API runtime moved from a temporary process to LaunchAgent `RunAtLoad + KeepAlive`.

## Verification

- `flutter analyze` for badge-related files: no issues.
- `flutter test test/services/push_notification_service_test.dart test/services/app_delegate_method_channel_test.dart`: all tests passed.
- iOS Release `xcodebuild` build: succeeded.
- `curl http://100.69.69.119:8000/api/v1/health`: HTTP 200 with API, Redis, and Celery healthy.
- API process was terminated once and LaunchAgent restarted it with a new PID.
- User confirmed the iPhone icon badge `1` disappeared.

## Next Session Checks

```bash
cd /Users/ibkim/Projects/voice-to-textnote
launchctl print gui/$(id -u)/com.voicetextnote.backend-api | rg 'state =|pid =|properties ='
curl http://100.69.69.119:8000/api/v1/health
tail -80 logs/backend-api.launchd.err.log
```

If the app shows "서버에 연결할 수 없습니다", check the LaunchAgent and health endpoint before rebuilding or reinstalling the app. Do not start a duplicate temporary API server in tmux for normal Mac mini private staging.
