# Session Summary: Release Builds, Google OAuth, MVP Backend Gaps

Date: 2026-06-30

## Summary

Android release APK and iOS release IPA/archive were built. The iOS release app was installed and launched on the USB-connected iPhone. Android Google Sign-In was traced to Google OAuth console registration, not backend connectivity. Backend MVP gap implementations were committed and pushed.

Later in the same session, a broader client audit fixed six release/UI findings. The most important follow-up was an iPhone release login failure after Google account selection: Google OAuth completed, but the app was built against the unresolved production API host `https://api.voicetextnote.com/api/v1`, while the reachable backend was the private Tailscale staging server `http://100.69.69.119:8000/api/v1`. Rebuilding iOS release with `--dart-define=ENV=staging` and scoped ATS/network-security exceptions for `100.69.69.119` fixed the issue.

## Backend Work

Committed and pushed:

```text
12d077b Complete real backend behavior for MVP gaps
```

Main implemented areas:

- Advanced search now uses real stored data, saved searches, result snippets, tags, speakers, and search metrics.
- Enhanced audio processor uses real spectral gate noise reduction instead of placeholder AI behavior.
- Action item service computes real weekly/productivity metrics and extraction rules.
- Push service has operational fallback naming and invalid-token invalidation behavior.

Verification performed before commit:

```text
backend pytest suite: 66 passed
ruff: clean
flutter Google configuration test: All tests passed
```

## Android Release Build

Release APK built and installed during testing:

```bash
cd client
flutter build apk --release --target-platform android-arm64
```

Final local test APK signing identity:

```text
Package name: com.voicetextnote.app
SHA-1: 1F:84:A6:04:D6:18:F5:17:EE:AC:5D:6D:5A:D5:EE:62:B0:C0:FC:66
SHA-256: 22:9C:9D:7D:E9:8F:17:9C:AC:D4:65:E3:E9:FD:BA:D4:59:01:9C:BF:7C:21:F0:37:BF:0C:C5:04:D4:71:0D:1B
```

Local signing files are ignored and must not be committed:

```text
client/android/key.properties
client/android/voice-to-textnote-release.jks
client/build/
```

## Android Google Sign-In Diagnosis

Observed failure after selecting `kiminbean@gmail.com`:

```text
This android application is not registered to use OAuth2.0,
please confirm the package name and SHA-1 certificate fingerprint match
what you registered in Google Developer Console.
```

Interpretation:

- Google Play Services rejects the request before backend `/auth/google`.
- The app package is `com.voicetextnote.app`.
- The installed APK SHA-1 must be present on an Android OAuth client in Google Cloud Console / Firebase.
- `google-services.json` containing an old client entry is not enough if the Cloud Console OAuth client was deleted or disabled.

Rejected workaround:

```text
serverClientId = Android OAuth client ID
```

Reason:

```text
You must use a Web client as the server client ID.
```

Correct rule:

- `serverClientId` must be the Web OAuth client ID.
- Android OAuth client is selected by package name and signing SHA-1.
- Production/upload signing SHA-1 must be registered separately for real distribution builds.

## iOS Release Build And Install

Release artifacts:

```text
client/build/ios/ipa/Voice TextNote.ipa
client/build/ios/archive/Runner.xcarchive
client/build/ios/iphoneos/Runner.app
```

Build commands:

```bash
cd client
flutter build ios --release --no-codesign
flutter build ipa --release
```

Verified app settings:

```text
Display Name: Voice TextNote
Bundle Identifier: com.voicetextnote.app
Version Number: 1.0.0
Build Number: 1
Deployment Target: 15.0
```

Device:

```text
Name: Inbean의 iPhone
UDID: 00008150-000239020C08401C
CoreDevice ID: C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA
iOS: 26.5.1
State: available (paired), wired
Developer Mode: enabled
```

Flutter incorrectly reported Developer Mode as disabled, but `devicectl` showed the device was enabled and install-capable. The signed archive app was installed directly:

```bash
xcrun devicectl device install app \
  --device C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA \
  client/build/ios/archive/Runner.xcarchive/Products/Applications/Runner.app

xcrun devicectl device process launch \
  --device C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA \
  com.voicetextnote.app
```

Success evidence:

```text
App installed:
• bundleID: com.voicetextnote.app

Launched application with com.voicetextnote.app bundle identifier.

Voice TextNote   com.voicetextnote.app   1.0.0   1
```

## 2026-06-30 Client Audit Fixes

Six findings were fixed and verified:

- Release API default now uses production HTTPS instead of implicitly pointing at HTTP staging.
- Explicit staging release builds can use the private Tailscale backend at `http://100.69.69.119:8000/api/v1`.
- Release cleartext exceptions are scoped to `100.69.69.119` only:
  - iOS ATS: `NSExceptionDomains` entry for `100.69.69.119`.
  - Android release/profile network security config: one cleartext domain exception for `100.69.69.119`.
- Android Google OAuth/SHA registration failures are shown as configuration errors, not generic retry messages.
- `ProcessingScreen` uses `ref.listenManual` for the SSE task listener instead of calling `ref.listen` outside build.
- Product naming is unified as `Voice TextNote`; internal benchmark/home copy was removed.
- iPhone orientation is portrait-only, matching Android phone behavior.

Verification after the fixes:

```text
flutter analyze --no-pub: No issues found
flutter test --no-pub --reporter=compact: 463 tests passed
flutter build apk --release --no-pub: built app-release.apk
flutter build ios --release --dart-define=ENV=staging: built Runner.app
```

## iPhone Google Login Root Cause

Observed symptom:

```text
After tapping "Continue with Google", selecting a Gmail account, the app showed:
"서버에 연결할 수 없습니다."
```

Confirmed facts:

```text
curl https://api.voicetextnote.com/api/v1/health
=> Could not resolve host: api.voicetextnote.com

curl http://100.69.69.119:8000/api/v1/health
=> {"status":"healthy", ...}

POST http://100.69.69.119:8000/api/v1/auth/google with an invalid token
=> 401 Unauthorized from backend, proving the endpoint is reachable
```

Root cause:

- Google account selection succeeded.
- The failure happened in the next step, when the app posted the Google ID token to backend `/auth/google`.
- The installed release build was using the unresolved production host `api.voicetextnote.com`.
- The actual active backend was `100.69.69.119`.

Fix applied:

```bash
cd client
flutter build ios --release --dart-define=ENV=staging
xcrun devicectl device install app \
  --device C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA \
  build/ios/iphoneos/Runner.app
xcrun devicectl device process launch \
  --device C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA \
  com.voicetextnote.app
```

The user confirmed the iPhone Google login worked after installing this staging release build.

## Backend Server Note

The backend PC was not pulled or restarted during this follow-up because SSH access failed:

```text
ssh 100.69.69.119
=> Permission denied (publickey,password,keyboard-interactive)
```

The backend was already healthy and serving:

```text
Host: 100.69.69.119
Health: healthy
started_at: 2026-06-29T16:28:57.568313+00:00
```

Therefore, the final successful login was caused by the corrected client release build pointing to the currently running backend, not by a backend restart.

## Current Worktree Note

After iOS archive/build, CocoaPods/Xcode updated:

```text
client/ios/Podfile.lock
client/ios/Runner.xcodeproj/project.pbxproj
```

The `.omx` runtime metric files are session noise and should not be committed.
