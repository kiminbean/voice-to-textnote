# Session 2026-06-30: Release Builds And Google Auth

## Durable Facts

- Backend MVP gap commit pushed: `12d077b`.
- Android package: `com.voicetextnote.app`.
- Android local test release APK SHA-1: `1F:84:A6:04:D6:18:F5:17:EE:AC:5D:6D:5A:D5:EE:62:B0:C0:FC:66`.
- Android local test release APK SHA-256: `22:9C:9D:7D:E9:8F:17:9C:AC:D4:65:E3:E9:FD:BA:D4:59:01:9C:BF:7C:21:F0:37:BF:0C:C5:04:D4:71:0D:1B`.
- Android Google Sign-In is blocked at Google Play Services if this package/SHA-1 is not registered in Google Cloud/Firebase Android OAuth client settings.
- `serverClientId` must be a Web OAuth client ID. Android OAuth client ID as `serverClientId` returns `You must use a Web client as the server client ID`.
- iOS release IPA built: `client/build/ios/ipa/Voice TextNote.ipa`.
- iOS archive built: `client/build/ios/archive/Runner.xcarchive`.
- iPhone CoreDevice ID: `C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA`.
- iPhone UDID: `00008150-000239020C08401C`.
- iPhone release app install and launch succeeded through `xcrun devicectl`.
- 2026-06-30 iPhone Google login failure after account selection was not an OAuth picker problem. The release app was built against unresolved `https://api.voicetextnote.com/api/v1`; the reachable backend was `http://100.69.69.119:8000/api/v1`.
- For current private staging validation, build release apps with `--dart-define=ENV=staging`. This points the client at `http://100.69.69.119:8000/api/v1`.
- iOS ATS and Android release network security now have scoped cleartext exceptions for `100.69.69.119` only. Production default remains HTTPS.
- Backend PC was not pulled/restarted in this fix because SSH returned `Permission denied`; the running backend was already healthy.

## Commands That Worked

```bash
cd client
flutter build apk --release --target-platform android-arm64
flutter build ipa --release
flutter build ios --release --dart-define=ENV=staging --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1

xcrun devicectl device install app \
  --device C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA \
  build/ios/iphoneos/Runner.app

xcrun devicectl device process launch \
  --device C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA \
  com.voicetextnote.app
```

## Operational Warning

Flutter can report Developer Mode as disabled even when `devicectl` says:

```text
developerModeStatus: enabled
pairingState: paired
transportType: wired
tunnelState: connected
```

In that case, use `devicectl` to install the signed archive app directly.

## 2026-06-30 iPhone Google Login Root Cause

Observed:

```text
Google account selection succeeded, then the app showed "서버에 연결할 수 없습니다."
```

Evidence:

```text
https://api.voicetextnote.com/api/v1/health
=> DNS failure / host not resolved

http://100.69.69.119:8000/api/v1/health
=> healthy
```

Resolution:

```bash
cd client
flutter build ios --release --dart-define=ENV=staging --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1
xcrun devicectl device install app \
  --device C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA \
  build/ios/iphoneos/Runner.app
xcrun devicectl device process launch \
  --device C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA \
  com.voicetextnote.app
```

User confirmed Google login worked after this install.
