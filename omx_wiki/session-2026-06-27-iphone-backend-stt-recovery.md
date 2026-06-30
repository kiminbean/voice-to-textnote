# Session 2026-06-27: iPhone Backend and STT Recovery

Tags: session-log, ios, backend, stt, sse, tailscale, firebase, google-auth

## Summary

The app was stabilized against the Tailscale backend `100.69.69.119`, Google sign-in was repaired, the backend was pulled/restarted on the server, and the iPhone release build was installed. A later `STT 처리중 20%` stall was traced to the task progress receive path, not server-side STT failure.

## Canonical Environment

- Local repo: `/Users/ibkim/Projects/voice-to-textnote`
- Server repo: `/Users/ibkim/Projects/voice-to-textnote`
- Backend URL for app builds: `http://100.69.69.119:8000/api/v1`
- iPhone UDID: `00008150-000239020C08401C`
- Confirmed working commit: `537a0ac Keep STT progress from stalling on SSE gaps`

## Backend Deployment

Server-side actions completed:

- Pulled GitHub changes into `/Users/ibkim/Projects/voice-to-textnote`.
- Copied local `.env` to the server project.
- Restarted backend tmux services.
- Verified server health, OpenAPI, guest auth, and real STT/DIA completion.

Do not diagnose iPhone app failures until these checks pass:

```text
health:200
openapi:200
guest:200
```

## Google Auth Lessons

See `docs/google-auth-ios-runbook.md`.

Key rules:

- iPhone home-screen testing needs profile or release builds, not Flutter debug builds.
- Backend `GOOGLE_CLIENT_ID` must allow all native/Web OAuth client IDs.
- `verify_at_hash` remains disabled while issuer/audience are explicitly validated.
- Do not trust the app toast alone; inspect backend `/api/v1/auth/google` logs.

## STT 20 Percent Lesson

In the Flutter pipeline, 20% means upload succeeded and the app is waiting for STT/DIA completion. It is not evidence that upload failed.

Root issues fixed in `537a0ac`:

- SSE stream requests did not send guest/user bearer authorization.
- Parallel STT and DIA streams shared one mutable HTTP client and could interfere.
- Non-2xx SSE responses were not treated as connection failure.
- SSE streams could stay open without useful events; polling fallback needed a bounded transition.

Fix shape:

- `SseService` now has an async header provider.
- `sseServiceProvider` mirrors normal API auth headers.
- Each stream gets its own `http.Client`.
- Non-2xx stream response throws.
- Idle stream closes and falls back to polling.
- `ProcessingScreen` reads the provider-backed SSE service.

## Verification Evidence

Commands/results from this recovery:

```text
flutter test --no-pub test/services/sse_service_test.dart test/providers/pipeline_provider_test.dart
All tests passed

flutter analyze --no-pub
No issues found

Guest-authenticated SSE probe against http://100.69.69.119:8000/api/v1
HTTP 200 with status_update event
```

iPhone release install:

```bash
cd client
flutter run --release --no-pub --no-resident \
  -d 00008150-000239020C08401C \
  --dart-define=ENV=staging \
  --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1
```

User confirmed after release install:

```text
잘됩니다.
```

## Avoid Repeating

- Do not rebuild or reinstall without passing the backend health checks first.
- Do not assume 20% is an upload problem; inspect task status and stream auth.
- Do not construct raw `SseService(baseUrl: ...)` in UI code when authenticated streams are required.
- Do not commit generated lockfile or registrant churn caused by `flutter clean`, `flutter pub get`, or device builds unless dependency changes were intentional.
