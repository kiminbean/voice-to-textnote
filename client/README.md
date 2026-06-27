# Voice TextNote Client

Flutter client for Voice TextNote.

## iPhone 실기기 실행

홈 화면에서 직접 실행할 앱은 debug 빌드가 아니라 profile 빌드로 설치합니다. iOS 14+에서 Flutter debug 빌드를 `flutter run`/Xcode 없이 아이콘으로 실행하면 바로 종료됩니다.

```bash
flutter run --profile \
  -d 00008150-000239020C08401C \
  --dart-define=ENV=dev \
  --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1
```

`API_BASE_URL`은 iPhone에서 접근 가능한 Mac의 LAN/Tailscale IP를 사용합니다. 앱 내부 `localhost`는 Mac이 아니라 iPhone 자신입니다.

## Google Sign-In

Google 로그인 설정과 문제 해결은 상위 문서 `../docs/google-auth-ios-runbook.md`를 먼저 확인합니다.

필수 체크:

- `ios/Runner/Info.plist`에 `GIDClientID`, `GIDServerClientID`, Google callback URL scheme이 있어야 합니다.
- `macos/Runner/Info.plist`에도 macOS client ID와 Web server client ID가 있어야 합니다.
- 백엔드 `.env`의 `GOOGLE_CLIENT_ID`는 Web/iOS/Android/macOS OAuth client ID를 쉼표로 모두 포함해야 합니다.
- Google 로그인 실패 메시지가 나오면 앱 메시지만 보지 말고 백엔드 `/api/v1/auth/google` 로그를 확인합니다.

## Verification

```bash
flutter analyze
flutter test test/providers/auth_provider_google_test.dart test/config/ios_permission_config_test.dart
```
