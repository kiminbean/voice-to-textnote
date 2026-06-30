# Session Summary: Firebase / Google Sign-In Stabilization

Date: 2026-06-27

## Summary

Firebase project setup, Google Sign-In configuration, backend OAuth token validation, and iPhone profile-build testing were stabilized for `voice-to-textnote`. Later in the same session, the STT processing flow that stalled at 20% on iPhone was diagnosed and fixed.

## Important Outcomes

- Firebase CLI was available and authenticated.
- Firebase project `voice-to-textnote` and app configs were verified.
- Downloaded Firebase config files from `/Users/ibkim/Downloads` were applied:
  - `google-services.json`
  - `GoogleService-Info.plist`
  - `GoogleService-Info (1).plist`
- iOS and macOS `Info.plist` now include Google callback URL schemes and explicit Google client/server IDs.
- iOS local network and ATS development exceptions were added for local backend testing.
- Backend Google token verification now accepts comma-separated OAuth audiences and disables `at_hash` auto-validation while still validating issuer/audience explicitly.
- iPhone profile build was installed because debug builds cannot be launched directly from the home screen.
- Backend server for the app is `http://100.69.69.119:8000/api/v1`.
- Backend project on the server is `/Users/ibkim/Projects/voice-to-textnote`; local project is `/Users/ibkim/Projects/voice-to-textnote`.
- Commit `537a0ac` fixes the STT 20% stall by authenticating SSE task streams, allowing independent parallel SSE clients, and falling back to polling when SSE is idle or misses events.
- iPhone release build was installed successfully with:

```bash
cd client
flutter run --release --no-pub --no-resident \
  -d 00008150-000239020C08401C \
  --dart-define=ENV=staging \
  --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1
```

## Failures And Lessons

| Failure | Lesson |
| --- | --- |
| Debug app terminated immediately on iPhone | Install profile builds for home-screen testing. |
| Google account picker succeeded but backend returned 401 | Check backend `/api/v1/auth/google` logs; the SDK step had already succeeded. |
| `Invalid audience` | `GOOGLE_CLIENT_ID` must include all native/Web OAuth client IDs. |
| `No access_token provided to compare against at_hash claim` | Disable `verify_at_hash`; validate issuer/audience manually. |
| App showed email/password error for Google login | Social login errors need separate user-facing messages. |
| Guest endpoint failed with 500 | Redis was not running. |
| OpenAPI failed with 500 | Pydantic package files and metadata were out of sync. |
| STT processing stayed at 20% | 20% means upload succeeded and the app is waiting for STT/DIA. The client SSE stream lacked bearer/guest auth, reused one HTTP client for parallel STT/DIA streams, and could wait too long before polling fallback. |
| `flutter run --profile` failed with precompiled header cache error | Run `flutter clean`, regenerate Flutter metadata with `flutter pub get`, then rebuild. Restore unrelated generated/lock-file diffs before committing. |

## Canonical Runbook

Use:

- `docs/google-auth-ios-runbook.md`
- `docs/stt-processing-runbook.md`

## Verification Performed

```bash
pytest backend/tests/unit/test_oauth_service.py -q --no-cov
flutter analyze
flutter test test/providers/auth_provider_google_test.dart test/config/ios_permission_config_test.dart
flutter test --no-pub test/services/sse_service_test.dart test/providers/pipeline_provider_test.dart
flutter analyze --no-pub
```

Backend and Redis were running in tmux:

```text
voice-to-textnote-server
voice-to-textnote-redis
```

Expected endpoint checks:

```text
guest:200
openapi:200
PONG
```

Additional server verification for the STT/SSE fix:

```text
external_health:200
external_openapi:200
external_guest:200
guest-authenticated SSE probe: HTTP 200 with status_update event
```
