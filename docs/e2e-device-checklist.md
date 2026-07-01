# 실기기 E2E 테스트 체크리스트 (T-020)

**SPEC-MOBILE-004 | 작성일: 2026-06-13**

---

## 사전 준비

- [ ] 백엔드 서버 실행 (FastAPI + Celery + Redis)
- [ ] 클라이언트 디바이스 등록 (로그인 → FCM 토큰 등록)
- [ ] Firebase 프로젝트 설정 완료 (T-019)
- [ ] 개발 백엔드 PushService 실제 모드 확인: `mock_mode False`
- [ ] iOS 개발 Push 검증 시 원격 `.env`의 `FIREBASE_CREDENTIALS_PATH` 보존 확인
- [ ] 테스트 기기 준비 (Android / iOS 각 1대)
- [ ] Android SDK 확인: `flutter doctor -v`에서 Android toolchain이 `Android SDK version 36.0.0`으로 표시
- [ ] CocoaPods 확인: `cd client/ios && pod install`
- [ ] self-hosted runner 후보 장비 사전검사 통과: `ANDROID_DEVICE_SERIAL=<adb-device-serial> IOS_DEVICE_UDID=<ios-device-udid> python3 client/scripts/verify_mobile_release_runner.py`
- [ ] 네이티브 빌드 게이트 통과: `cd client && REQUIRE_ANDROID_RELEASE_SIGNING=true ./scripts/verify_mobile.sh --native`
- [ ] Android release APK 산출물 및 서명 확인: `client/build/app/outputs/flutter-apk/app-release.apk`, `apksigner verify --print-certs`
- [ ] iOS no-codesign 산출물 확인: `client/build/ios/iphoneos/Runner.app`
- [ ] Release readiness 기본 사전검사 통과: `python3 client/scripts/verify_release_readiness.py`
- [ ] Release E2E evidence scaffold 생성: `REQUIRE_ANDROID_RELEASE_SIGNING=true python3 client/scripts/create_release_e2e_evidence.py --output docs/release-e2e-evidence.json`
- [ ] Release E2E evidence 작성: 생성된 repo 내부 JSON을 실제 기기/빌드/시나리오 증거로 채운 뒤 `RELEASE_E2E_EVIDENCE_PATH`에 repo 내부 경로로 지정
- [ ] Strict release readiness 통과(placeholder 없는 release 문서, 서비스 계정/APNs/App Store Connect/실기기 secret 및 실제 연결 기기 포함): `python3 client/scripts/verify_release_readiness.py --strict`
- [ ] GitHub release environment 사전검사 통과: `python3 client/scripts/verify_github_mobile_release_env.py --repo kiminbean/voice-to-textnote`
- [ ] GitHub Actions strict release gate 통과: `.github/workflows/mobile.yml`의 `workflow_dispatch`를 실행하고 `evidence_path`에 실제 evidence JSON 경로를 입력

2026-07-01 Mac mini 기준 현재 상태:

- [x] APNs `.p8`, App Store Connect `.p8`, Firebase service account, FCM test token env 입력은 strict gate에서 PASS.
- [x] App Store distribution archive 생성 완료: `/Users/ibkim/secure/voice-to-textnote/apple-signing/Runner-production-final-20260701191705.xcarchive`
- [x] production entitlement 추출 완료: `docs/ios-release-entitlements.plist`, SHA-256 `e44b8d040b5abe77085420d347e186850201db6111dd89c8819b39c664924bd3`
- [x] iPhone 실기기 연결 확인: `C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA`, iPhone 17 Pro, iOS 26.5.1.
- [x] Android 실기기 연결 확인: `76aadc20`, Redmi Note 9 Pro, Android 12 API 31.
- [x] Android staging release APK 재빌드/설치 완료: `ENV=staging`, `API_BASE_URL=http://100.69.69.119:8000/api/v1`, SHA-256 `d75e70b96a30e03988a292658ef51086fbe67f19b8c084d28ff6744c6432ec2a`.
- [x] Android strict scenario 4개 실제 증거 PASS: `android_foreground_service`, `android_debug_tailscale_cleartext_allowed`, `android_release_cleartext_blocked`, `export_share_android`.
- [x] Android Promise Radar 메뉴/탭 gate 재확인: `python3 client/scripts/verify_promise_radar_device_gate.py --serial 76aadc20 --evidence-out docs/promise-radar-android-device-gate-2026-07-01-current.json` -> `PASS Promise Radar Android device gate`.
- [x] iOS Release XCUITest launch smoke PASS: `xcodebuild test -configuration Release -only-testing:RunnerUITests/RunnerUITests/testReleaseLaunchEvidence` on iPhone `00008150-000239020C08401C` -> `** TEST SUCCEEDED **`.
- [x] iOS Release launch screenshot/UI hierarchy attachments exported: `docs/release-e2e-artifacts/ios_release_launch_xcuitest_release_20260701205837_attachments/`.
- [ ] `docs/release-e2e-evidence.json`의 남은 13개 required scenario는 아직 실제 iOS 또는 Android+iOS screenshot/log/video/trace evidence와 `pass: true`가 필요.
- [x] Android+iOS 공통 scenario 3개 실제 증거 PASS: `permission_microphone_initial`, `permission_denied_recovery`, `unfinished_recording_recovery`는 Redmi Note 9 Pro `76aadc20` Android screenshot/UI dump/service log와 iPhone `00008150-000239020C08401C` Release XCUITest attachment를 모두 확보했고 `docs/release-e2e-evidence.json`에서 `pass:true`다.
- [ ] 나머지 iOS 시나리오별 UI 증거는 `RunnerUITests`를 계속 확장해서 수집한다. `devicectl`은 wired/available/tunnel connected 상태와 display info는 확인하지만 CLI screenshot/tap 명령을 제공하지 않고, `flutter screenshot -d 00008150-000239020C08401C`는 `Screenshot not supported for Inbean의 iPhone`으로 실패하며, `pymobiledevice3 remote browse`는 root 권한을 요구한다. 따라서 iOS 증거 수집의 기본 경로는 Xcode UI Test attachment다.

2026-07-01 iOS XCUITest 주의사항:

- Debug configuration XCUITest는 iPhone 17 Pro iOS 26.5.1에서 Flutter engine `VSyncClient` / `createTouchRateCorrectionVSyncClientIfNeeded` SIGSEGV를 재현한다.
- 같은 기기, 같은 앱에서 Release configuration XCUITest는 PASS했다.
- Strict release evidence에는 Debug crash를 blocker로 넣지 말고, Release configuration으로 실행한 `RunnerUITests` screenshot/UI hierarchy attachment를 사용한다.
- 앱을 uninstall한 뒤 Release `RunnerUITests`가 `The application could not be launched because the Developer App Certificate is not trusted`로 실패하면, iPhone에서 `설정 > 일반 > VPN 및 기기 관리`로 이동해 `Apple Development: Created via API (5WDG3L7L32)` 개발자 앱 인증서를 신뢰한다. Mac CLI에서 `devicectl`로 이 신뢰 상태를 강제 변경하는 명령은 없다. `xcodebuild build-for-testing`이 성공하고 `xcodebuild test` 실행만 실패하면 코드 문제가 아니라 기기 신뢰 설정 문제로 본다.

### 네이티브 빌드 기준선

| 항목 | 기준 |
|------|------|
| Android SDK | `/Users/ibkim/Library/Android/sdk` 또는 CI의 `ANDROID_HOME` |
| Android packages | `platforms;android-36`, `build-tools;36.0.0`, `build-tools;28.0.3`, `platform-tools`, `ndk;27.0.12077973`, `cmake;3.22.1` |
| Flutter Android config | `flutter config --android-sdk /Users/ibkim/Library/Android/sdk` |
| iOS CocoaPods | `pod install`이 `Pod installation complete!`로 종료 |
| iOS Profile config | `client/ios/Flutter/Profile.xcconfig`가 `Pods-Runner.profile.xcconfig`를 include |

### Strict release readiness 필수 입력

| 환경 변수 | 목적 |
|-----------|------|
| `REQUIRE_ANDROID_RELEASE_SIGNING=true` | strict readiness가 signed Android release APK 검증 모드와 같은 release 조건에서 실행되었는지 확인 |
| `FIREBASE_CREDENTIALS_PATH` | Backend Firebase Admin SDK 서비스 계정 JSON object (`type=service_account`, `project_id=voice-to-textnote`, private key PEM, `@voice-to-textnote.iam.gserviceaccount.com` email) |
| `APNS_AUTH_KEY_PATH` | Firebase Console에 업로드한 APNs `.p8` private key PEM 파일 |
| `APNS_KEY_ID` / `APNS_TEAM_ID` | Apple Developer APNs 키 식별자 |
| `APP_STORE_CONNECT_API_KEY_PATH` | App Store Connect API `.p8` private key PEM 파일 |
| `APP_STORE_CONNECT_KEY_ID` / `APP_STORE_CONNECT_ISSUER_ID` | App Store Connect API 식별자. Key ID는 10자리 대문자/숫자, Issuer ID는 UUID 형식 |
| `ANDROID_DEVICE_SERIAL` | `adb devices`에 표시되는 Android 실기기 serial |
| `IOS_DEVICE_UDID` | Xcode/idevice_id에 표시되는 iOS 실기기 UDID |
| `IOS_RELEASE_ENTITLEMENTS_PATH` | signed iOS release app에서 추출한 repo 내부 entitlements plist. `aps-environment=production`, `get-task-allow=false`, App ID/Team ID 일치 필요 |
| `FIREBASE_TEST_DEVICE_TOKEN` | 앱이 서버에 등록한 테스트용 FCM token |
| `RELEASE_E2E_EVIDENCE_PATH` | 실기기 Push/딥링크/백그라운드 녹음/공유/HTTP 정책 시나리오 pass 증거 JSON |

### GitHub Actions strict release gate

`.github/workflows/mobile.yml`의 `Strict Release Readiness With Physical Devices` job은 `workflow_dispatch`에서만 실행한다. GitHub-hosted runner는 Android/iOS 실기기, Xcode pairing, APNs/Firebase/App Store Connect 보안 파일을 보유하지 않으므로 이 job은 아래 조건을 갖춘 self-hosted macOS runner에서 실행해야 한다.

| 항목 | 값 |
|------|-----|
| Runner labels | `self-hosted`, `macOS`, `mobile-release` |
| Environment | `mobile-release` |
| Required secrets | `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`, `FIREBASE_SERVICE_ACCOUNT_JSON`, `APNS_AUTH_KEY_P8`, `APNS_KEY_ID`, `APNS_TEAM_ID`, `APP_STORE_CONNECT_API_KEY_P8`, `APP_STORE_CONNECT_KEY_ID`, `APP_STORE_CONNECT_ISSUER_ID`, `FIREBASE_TEST_DEVICE_TOKEN` |
| Required vars | `ANDROID_DEVICE_SERIAL`, `IOS_DEVICE_UDID` |

이 job은 먼저 `python3 client/scripts/verify_mobile_release_runner.py`로 macOS runner, Flutter doctor, `xcodebuild -version`, Android authorized device, iOS available device를 확인한다. 그 다음 `evidence_path`가 예제 JSON이 아니고 repo 내부 파일인지, `ios_entitlements_path`도 repo 내부 plist 파일인지 preflight로 확인한다. 이후 Android signing secret을 임시 keystore와 `client/android/key.properties`로 materialize하고 `REQUIRE_ANDROID_RELEASE_SIGNING=true client/scripts/verify_mobile.sh --native`로 Flutter analyze/test/local STT smoke/Android signed release APK/iOS no-codesign build를 실행한 뒤, Firebase/APNs/App Store Connect secret을 임시 파일로 materialize하고 `python3 client/scripts/verify_release_readiness.py --strict`를 실행한다. `evidence_path` 입력값은 실제 release evidence JSON을 가리켜야 하며, `ios_entitlements_path` 입력값은 signed iOS release app에서 추출한 repo 내부 plist여야 한다. 예제 파일을 그대로 사용하면 입력 preflight 또는 strict readiness에서 실패해야 정상이다.

GitHub runner를 등록하기 전 macOS 후보 장비에서 아래 명령을 먼저 실행한다. 이 검사는 macOS, Flutter doctor, Android SDK 36, Xcode/CocoaPods, `xcodebuild -version`, Android authorized device, iOS `available` device를 확인한다.

```bash
ANDROID_DEVICE_SERIAL=<adb-device-serial> \
IOS_DEVICE_UDID=<ios-device-udid> \
python3 client/scripts/verify_mobile_release_runner.py
```

GitHub 설정 자체는 아래 명령으로 먼저 검증한다. 이 검사는 secret 값은 출력하지 않고, Environment 존재 여부, secret/variable 이름, runner label만 확인한다.

```bash
python3 client/scripts/verify_github_mobile_release_env.py --repo kiminbean/voice-to-textnote
```

secret과 device id 값이 준비된 운영 장비에서는 아래 명령으로 GitHub Environment를 생성/갱신하고, 같은 이름의 로컬 환경변수에서 GitHub Environment secret/variable을 등록한 뒤 verifier를 실행한다.

```bash
FIREBASE_SERVICE_ACCOUNT_JSON="$(cat /secure/firebase-service-account.json)" \
ANDROID_KEYSTORE_BASE64="$(base64 < /secure/android-release.jks | tr -d '\n')" \
ANDROID_KEYSTORE_PASSWORD=<keystore-password> \
ANDROID_KEY_ALIAS=<key-alias> \
ANDROID_KEY_PASSWORD=<key-password> \
APNS_AUTH_KEY_P8="$(cat /secure/AuthKey_APNS.p8)" \
APNS_KEY_ID=XXXXXXXXXX \
APNS_TEAM_ID=XXXXXXXXXX \
APP_STORE_CONNECT_API_KEY_P8="$(cat /secure/AuthKey_ASC.p8)" \
APP_STORE_CONNECT_KEY_ID=YYYYYYYYYY \
APP_STORE_CONNECT_ISSUER_ID=<issuer-uuid> \
FIREBASE_TEST_DEVICE_TOKEN=<fcm-token> \
ANDROID_DEVICE_SERIAL=<adb-device-serial> \
IOS_DEVICE_UDID=<ios-device-udid> \
python3 client/scripts/configure_github_mobile_release_env.py --repo kiminbean/voice-to-textnote
```

`--strict`는 환경변수 존재만 확인하지 않는다. `REQUIRE_ANDROID_RELEASE_SIGNING=true`가 설정되어 signed Android release gate와 같은 release 조건임을 먼저 확인하고, `docs/app-store-metadata.md`, `docs/privacy-policy.md`, `docs/e2e-device-checklist.md`에 release placeholder가 없어야 한다. 또한 `FIREBASE_CREDENTIALS_PATH`는 JSON object여야 하고 `type=service_account`, `project_id=voice-to-textnote`, 문자열 private key PEM, 문자열 `@voice-to-textnote.iam.gserviceaccount.com` client email을 가져야 한다. `APNS_AUTH_KEY_PATH`와 `APP_STORE_CONNECT_API_KEY_PATH`는 `.p8` 확장자와 `-----BEGIN PRIVATE KEY-----` / `-----END PRIVATE KEY-----` PEM 본문을 가져야 하며, `APP_STORE_CONNECT_ISSUER_ID`는 UUID 형식이어야 한다. `ANDROID_DEVICE_SERIAL`은 `adb devices -l`에 `device` 상태로 표시되어야 하고, `IOS_DEVICE_UDID`는 `xcrun devicectl list devices`에서 `available` 또는 `connected` 상태로 표시되어야 한다. `IOS_RELEASE_ENTITLEMENTS_PATH`는 체크아웃된 repo 내부 plist여야 하며 signed iOS release app에서 추출한 `aps-environment=production`, `get-task-allow=false`, App ID/Team ID 일치를 증명해야 한다. `RELEASE_E2E_EVIDENCE_PATH`는 체크아웃된 repo 내부 JSON 파일이어야 하며 `release_gate.android_release_signing=true`, `release_gate.ios_production_entitlements=true`, `release_gate.ios_entitlements_sha256`이 실제 `IOS_RELEASE_ENTITLEMENTS_PATH` SHA-256과 일치해야 한다. Android/iOS device id가 strict 환경변수와 일치하고, Push/딥링크/백그라운드 녹음/HTTP 정책/PDF 공유/Promise Radar Autopilot/Promise Radar due push/Promise Radar calendar export/Promise Radar assignee-quality 시나리오가 모두 `pass: true`와 증거 문구를 가져야 한다. 따라서 signed Android release 모드, Firebase/APNs/App Store Connect secret이 있어도 문서 placeholder가 남아 있거나 private key PEM이 아니거나 물리 기기가 연결되지 않았거나 trust/pairing이 완료되지 않았거나 실제 시나리오 증거가 없으면 E2E 진입 전 실패한다.

현재 private staging release 검증은 `100.69.69.119` HTTP 예외만 허용한다.
`verify_release_readiness.py`는 iOS ATS와 Android release/profile network security에서
해당 host 하나만 통과시키고, 임의 cleartext domain 또는 비어 있는 cleartext 예외는
실패시킨다. Store 제출용 production 빌드는 HTTPS-only 백엔드가 준비된 뒤 HTTP 예외를
제거해서 별도로 검증한다.

### Release E2E evidence scaffold

아래 명령은 현재 git revision, `ANDROID_DEVICE_SERIAL`, `IOS_DEVICE_UDID`, 기본 Android/iOS build artifact 경로, `artifact_sha256`, 모든 required scenario key를 포함한 JSON scaffold를 repo 내부에 생성한다. `artifacts` 값은 운영 장비 절대경로가 아니라 repo-relative 경로여야 하며, Android는 `client/build/app/outputs/flutter-apk/app-release.apk`, iOS는 `client/build/ios/iphoneos/Runner.app`만 허용된다. 생성 직후 scenario는 모두 `pass: false`이며, 실제 실기기 관측 증거를 채우기 전에는 strict readiness가 실패해야 정상이다.

```bash
ANDROID_DEVICE_SERIAL=<adb-device-serial> \
IOS_DEVICE_UDID=<ios-device-udid> \
REQUIRE_ANDROID_RELEASE_SIGNING=true \
IOS_RELEASE_ENTITLEMENTS_PATH=docs/ios-release-entitlements.plist \
python3 client/scripts/create_release_e2e_evidence.py \
  --output docs/release-e2e-evidence.json
```

> 참고: Kotlin Gradle Plugin의 Built-in Kotlin 마이그레이션 경고는 현재 빌드 실패가 아니라 미래 호환성 경고다. 경고가 오류로 승격되면 plugin 버전 업그레이드 또는 Flutter Built-in Kotlin 마이그레이션을 별도 작업으로 처리한다.

> 참고: Flutter analyze/test에서 `whisper_ggml_plus`, `sign_in_with_apple`, `flutter_secure_storage`, `flutter_local_notifications` 계열 플러그인이 iOS/macOS Swift Package Manager를 아직 지원하지 않는다는 경고가 출력될 수 있다. 현재는 빌드 실패가 아니지만 Flutter가 이 경고를 오류로 승격하면 Swift Package Manager 지원 플러그인 버전 업그레이드, CocoaPods 유지 정책, 또는 대체 플러그인 검토를 별도 release blocker로 처리한다.

---

## 테스트 항목

### 1. 권한 요청 (REQ-002)

| # | 시나리오 | 예상 결과 | Pass/Fail |
|---|---------|----------|-----------|
| 1.1 | 최초 설치 후 녹음 탭 | 마이크 권한 다이얼로그 표시 | ☐ |
| 1.2 | 권한 허용 후 녹음 시작 | 녹음 정상 시작 | ☐ |
| 1.3 | 권한 거부 후 녹음 탭 | "설정에서 권한 허용" 안내 | ☐ |
| 1.4 | 영구 거부 후 녹음 탭 | 설정 앱 이동 다이얼로그 | ☐ |
| 1.5 | 설정 앱에서 권한 변경 후 복귀 | UI 자동 갱신 (permissionRecheck) | ☐ |

### 2. 백그라운드 녹음 (REQ-001)

| # | 시나리오 | 예상 결과 | Pass/Fail |
|---|---------|----------|-----------|
| 2.1 | 녹음 중 홈 버튼 | 백그라운드 녹음 계속 | ☐ |
| 2.2 | 백그라운드 30초 후 복귀 | 녹음 진행 상태 유지 | ☐ |
| 2.3 | 녹음 중 전화 수신 | 인터럽트 후 자동 재개 (iOS) | ☐ |
| 2.4 | 녹음 중 앱 강제 종료 | SharedPreferences에 경로 저장 | ☐ |
| 2.5 | 앱 재시작 | 미완료 녹음 복구 다이얼로그 | ☐ |
| 2.6 | 복구 다이얼로그 "삭제" | 녹음 데이터 삭제 | ☐ |
| 2.7 | 녹음 중지 후 파일 재생 | 정상 오디오 재생 | ☐ |

### 3. Pause / Resume (REQ-001)

| # | 시나리오 | 예상 결과 | Pass/Fail |
|---|---------|----------|-----------|
| 3.1 | 녹음 중 일시정지 | 상태 paused, 타이머 정지 | ☐ |
| 3.2 | 일시정지 후 재개 | 상태 recording, 타이머 재개 | ☐ |

### 4. 푸시 알림 (REQ-003)

| # | 시나리오 | 예상 결과 | Pass/Fail |
|---|---------|----------|-----------|
| 4.1 | STT 처리 완료 | "전사 완료" 푸시 수신 | ☐ |
| 4.2 | 요약 처리 완료 | "요약 완료" 푸시 수신 | ☐ |
| 4.3 | 처리 실패 | 에러 푸시 수신 | ☐ |
| 4.4 | 앱 백그라운드 시 푸시 | 알림 배지 표시 | ☐ |
| 4.5 | 푸시 탭 → 결과 화면 | 딥링크로 이동 | ☐ |
| 4.6 | 콜드 스타트 시 푸시 | 앱 실행 후 결과 화면 | ☐ |

#### iOS 개발 Push 사전 검증

2026-06-30 기준 iPhone `00008150-000239020C08401C`와 원격 백엔드 `100.69.69.119`에서 실제 FCM/APNs 전송이 검증되었다.

백엔드 실제 모드 확인:

```bash
ssh 100.69.69.119 'cd /Users/ibkim/Projects/voice-to-textnote && .venv/bin/python - <<'"'"'PY'"'"'
from backend.services.push_service import PushService

svc = PushService()
svc._ensure_firebase_initialized()
print("mock_mode", svc._is_mock_mode)
PY'
```

기대값:

```text
mock_mode False
```

iPhone에 profile build 설치:

```bash
cd client
flutter run --profile --no-pub \
  -d 00008150-000239020C08401C \
  --dart-define=ENV=staging \
  --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1
```

앱/서버 로그 기대값:

- 앱 로그: `APNs 토큰 준비 완료`
- 앱 로그: `토픽 구독 완료: all`
- 서버 로그: `/api/v1/devices/register` 201
- DB: 최신 `device_tokens.platform = ios`

실제 전송 성공 evidence 예:

```text
Firebase message id: projects/voice-to-textnote/messages/1782749586143713
```

앱이 포그라운드이면 iOS가 배너를 표시하지 않을 수 있다. 배너 UI까지 확인하는 시나리오는 앱을 백그라운드로 보내거나 화면 잠금 상태에서 전송한다.

### 5. 딥링크 (REQ-004)

| # | 시나리오 | 예상 결과 | Pass/Fail |
|---|---------|----------|-----------|
| 5.1 | `voicetextnote://meeting/{id}` | 결과 화면 이동 | ☐ |
| 5.2 | 백그라운드 복귀 시 보류 딥링크 | 자동 처리 | ☐ |

### 6. Android Foreground Service

| # | 시나리오 | 예상 결과 | Pass/Fail |
|---|---------|----------|-----------|
| 6.1 | 녹음 중 알림 표시 | "녹음 중" 알림 | ☐ |
| 6.2 | 10초 주기 알림 갱신 | flushRecording 동작 | ☐ |
| 6.3 | 녹음 중지 후 알림 제거 | Foreground Service 종료 | ☐ |

### 7. Android Staging Release Menu Visibility

| # | 시나리오 | 예상 결과 | Pass/Fail |
|---|---------|----------|-----------|
| 7.1 | 최신 Android staging release 설치 | `lastUpdateTime`이 현재 검증 시각으로 갱신 | ☑ |
| 7.2 | 결과 화면 탭 목록 확인 | `약속 레이더`가 `탭 12개 중 4번째`로 표시 | ☑ |
| 7.3 | APK URL guard | `libapp.so`에 `http://100.69.69.119:8000/api/v1` 포함, production host 미사용 | ☑ |
| 7.4 | 자동 gate 실행 | `python3 client/scripts/verify_promise_radar_device_gate.py --serial 76aadc20`가 `PASS Promise Radar Android device gate` 출력 | ☑ |

---

## Release E2E Evidence JSON 매핑

`RELEASE_E2E_EVIDENCE_PATH`는 아래 scenario key를 모두 포함해야 한다. `tested_at`은 timezone을 포함한 ISO-8601이어야 하며 14일보다 오래된 증거는 실패해야 정상이다. 각 항목은 `pass: true`와 실제 관측 증거 문구를 가져야 하며, 해당 scenario 플랫폼의 Android serial/iOS UDID를 증거 문구에 포함해야 한다. 통과 evidence 문구는 서로 복붙되면 안 되고, 각 scenario별 screenshot, screen recording, device log, trace, attachment 또는 이에 준하는 스크린샷/화면 녹화/로그/첨부 관측 산출물 단서와 실제 파일명/URL/`artifact:`/`attachment:` 식별자를 포함해야 한다. 관측 산출물 식별자는 시나리오별로 고유해야 하며, 해당 scenario key를 포함한 참조가 최소 1개 있어야 한다. 같은 스크린샷/로그/첨부 참조를 여러 scenario에서 재사용하거나 다른 scenario key의 산출물만 참조하면 strict readiness가 실패해야 정상이다. Android/iOS device id는 strict 환경변수와 일치해야 한다. `release_gate.android_release_signing=true`, `release_gate.ios_production_entitlements=true`, `release_gate.ios_entitlements_sha256=<IOS_RELEASE_ENTITLEMENTS_PATH SHA-256>`를 기록해 signed Android APK와 production iOS entitlement 조건에서 수행된 evidence임을 남겨야 한다. `artifacts`는 repo-relative 표준 release output 경로만 허용되며, `artifact_sha256`은 `artifacts`의 모든 key를 포함하고 실제 release 산출물 파일/디렉터리 내용의 SHA-256과 일치해야 한다.

| Evidence key | 체크리스트 범위 |
|--------------|----------------|
| `permission_microphone_initial` | 1.1 최초 마이크 권한 요청 |
| `permission_denied_recovery` | 1.3-1.5 권한 거부/설정 복구 |
| `ios_background_recording_lock` | 2.1-2.2 iOS 화면 잠금/백그라운드 녹음 지속 |
| `ios_interruption_resume` | 2.3 전화 수신 후 인터럽션 복구 |
| `ios_bluetooth_route_change` | iOS Bluetooth route 변경 수동 검증 |
| `unfinished_recording_recovery` | 2.4-2.6 강제 종료 후 미완료 녹음 복구 |
| `push_stt_complete` | 4.1 STT 완료 Push |
| `push_summary_complete` | 4.2 요약 완료 Push |
| `push_failure` | 4.3 실패 Push |
| `push_deeplink_background` | 4.4-4.5 백그라운드 Push 딥링크 |
| `push_deeplink_cold_start` | 4.6 cold-start Push 딥링크 |
| `android_foreground_service` | 6.1-6.3 Android Foreground Service 알림 |
| `android_debug_tailscale_cleartext_allowed` | SPEC-SEC-002 AC-M02 Android Debug Tailscale HTTP 허용 |
| `android_release_cleartext_blocked` | SPEC-SEC-002 AC-M03 Android Release 허용 목록 외 HTTP 차단 |
| `ios_release_http_blocked` | SPEC-SEC-002 AC-M01 iOS Release 허용 목록 외 HTTP 차단 |
| `export_share_android` | SPEC-EXPORT-001 Android PDF 공유 시트 |
| `export_share_ios` | SPEC-EXPORT-001 iOS PDF 공유 시트 |
| `promise_radar_autopilot_status` | Promise Radar 자동 판정 실행 후 완료/지연/변경/제외 상태 적용과 근거 표시 |
| `promise_radar_due_push` | Promise Radar due/reminder FCM 수신 및 약속 원장 진입 |
| `promise_radar_calendar_export` | Promise Radar 캘린더 버튼으로 Google Calendar 열기 또는 ICS 복사 |
| `promise_radar_assignee_quality` | Promise Radar 담당자 추천과 품질 점수/보강 이슈 표시 |

### Promise Radar v16 추가 수동 확인

아래 항목은 2026-07-02 기준 구현된 v6~v16 기능이다. 현재 strict release evidence required key에는 추가하지 않는다. strict key를 늘리려면 `REQUIRED_E2E_SCENARIOS`, example/scaffold evidence, release-readiness 테스트를 같은 커밋에서 함께 갱신해야 한다.

`backend/scripts/generate_promise_radar_e2e_evidence.py`는 v16부터 `GET /api/v1/promise-radar/command-center?target_case_count=500`을 호출해 Command Center 응답이 Promise Memory Graph, Autopilot Shadow Mode, Evidence Permission, Team Scorecard, operator actions, Google Tasks OAuth readiness, extraction recall 필드를 포함하고 실제 회의 label 500건 이상 및 extraction recall 0.95 이상을 반환하는지 확인한다. 이 스크립트가 실패하면 evidence JSON을 수동으로 조작하지 말고 서버/DB/기기 연결 원인을 먼저 해결한다.

- `promise_radar_learning_loop`: Result 화면 `오판` 버튼으로 `learning_feedback` 저장 후 learning profile threshold가 갱신되는지 확인한다.
- `promise_radar_timeline`: Result 화면 `타임라인` 버튼에서 감지/자동 판정/사용자 피드백/병합/분리 이벤트가 시간순으로 표시되는지 확인한다.
- `promise_radar_pre_meeting_brief`: 녹음 시작 전 화면에서 미해결 약속 3개와 질문이 표시되는지 확인한다.
- `promise_radar_daily_digest`: Home Promise Radar 카드에서 Daily Digest 라인이 표시되고 새로고침으로 갱신되는지 확인한다.
- `promise_radar_scheduled_digest_push`: `PROMISE_RADAR_DIGEST_PUSH_ENABLED=true` 환경에서 Daily/Weekly Digest FCM이 발송되고 같은 날짜/사용자/cadence 중복 발송이 차단되는지 확인한다.
- `promise_radar_evidence_lock`: 근거가 약한 자동 판정은 assessment만 표시되고 원장 상태가 자동 변경되지 않는지 확인한다.
- `promise_radar_slack_dry_run`: `Slack` 버튼이 webhook 없이 payload를 생성/복사하고, 실제 전송은 `PROMISE_RADAR_SLACK_WEBHOOK_URL` 설정 시에만 수행되는지 확인한다.
- `promise_radar_autopilot_review_queue`: `자동 판정` 버튼이 즉시 원장을 바꾸지 않고 `확정 대기 약속함`을 표시하며, `모두 맞음`, 개별 `맞음`, `거절` 동작이 정상인지 확인한다.
- `promise_radar_autopilot_reject_persistence`: Review Queue에서 `거절`한 후보가 학습 반영 후 같은 회의/상태 후보로 다시 표시되지 않는지 확인한다.
- `promise_radar_status_thresholds`: 완료 오판 피드백 후 completed threshold만 올라가고 delayed/changed/dismissed threshold는 그대로 유지되는지 확인한다.
- `promise_radar_evidence_pack`: Review Queue `근거` 버튼과 원장 행 `증거팩` 버튼에서 matched text, marker hit, similarity, timestamp, source evidence가 감사 화면처럼 표시되는지 확인한다.
- `promise_radar_conflict_resolution`: “완료했지만 아직 못했다”처럼 충돌 신호가 있는 약속이 자동 적용되지 않고, 사용자가 완료/지연/변경/제외/분리 추천 중 해결 경로를 선택하며 충돌 근거 비교가 표시되는지 확인한다.
- `promise_radar_google_tasks_oauth_send`: `Tasks` 버튼이 Google 계정 선택과 `https://www.googleapis.com/auth/tasks` scope 승인을 거쳐 tasklist 선택 후 실제 Google Tasks에 전송 완료 메시지를 보여주는지 확인한다.
- `promise_radar_google_tasks_sync`: Google Tasks에서 완료한 task가 앱의 `Tasks 동기화` 버튼으로 Promise Ledger 완료 상태에 반영되는지 확인한다.
- `promise_radar_google_tasks_update`: 앱에서 약속 상태를 변경한 뒤 `Tasks 업데이트` 버튼으로 Google Tasks 상태/title이 반영되는지 확인한다. OAuth access token은 저장하지 않고 요청 1회에만 사용해야 한다.
- `promise_radar_team_automation_policy`: 원장 헤더의 정책 아이콘에서 안전 자동/항상 미리보기/완료만 자동/모두 수동 정책을 저장하고 이후 자동 판정 적용 방식이 정책을 따르는지 확인한다. 팀 범위 정책 변경은 admin 멤버만 허용되는지 확인한다.
- `promise_radar_digest_preference`: 원장 헤더의 Digest 설정에서 Daily/Weekly와 켬/끔 상태를 저장하고, 예약 digest push는 사용자가 켠 경우에만 발송되는지 확인한다.
- `promise_radar_digest_time_window`: Digest Push가 사용자의 `local_time` 1시간 window 안에서만 발송되고 quiet hours에는 발송되지 않는지 확인한다.
- `promise_radar_review_queue_filters`: Autopilot Review Queue에서 전체/충돌/약한 근거/고위험/기한 있음 필터가 동작하고 `현재 모두 맞음`은 표시된 후보에만 적용되는지 확인한다.
- `promise_radar_review_queue_diff_preview`: Autopilot Review Queue 상단에서 표시/확정 가능/근거 잠김/약한 근거/고위험/기한 수와 상태 변경 분포가 일괄 확정 전에 표시되는지 확인한다.
- `promise_radar_evidence_comparison`: 원장 행의 `근거 비교` 버튼이 기존 원장 근거와 최신 Evidence Pack의 유사도, 공유 핵심어, marker hit를 표시하는지 확인한다.
- `promise_radar_command_center`: `약속 레이더 Command Center` 화면이 dashboard, focus item, operator actions, Autopilot Review Queue, Learning Loop v3, Evidence Audit, Daily Digest, Google Tasks OAuth guide/readiness, accuracy report, extraction recall report, Promise Memory Graph, Autopilot Shadow Mode, Evidence Permission, Team Scorecard를 한 화면에서 표시하는지 확인한다.
- `promise_radar_memory_graph`: Command Center의 Promise Memory Graph가 owner/promise/series/status node 수, edge 수, 반복 회의 수, 지연/변경 cluster, owner alias 수, 상위 node/edge 관계와 narrative를 표시하는지 확인한다.
- `promise_radar_shadow_mode`: Command Center의 Autopilot Shadow Mode가 후보 수, 자동 적용 가능 수, preview-only 수, Evidence Lock 보류 수, 충돌 수, status 분포와 학습 반영 안내를 표시하는지 확인한다.
- `promise_radar_evidence_permission`: Command Center의 Evidence Permission이 export 가능 여부, redaction 필요 여부, speaker/timestamp 포함 여부, 허용/차단 evidence 수와 policy note를 표시하는지 확인한다.
- `promise_radar_team_scorecard`: Command Center의 Team Scorecard가 팀 위험 점수, 담당자 수, 열린/초과/고위험 약속 수, 우선 확인 owner와 추천 조치를 표시하는지 확인한다.
- `promise_radar_learning_loop_v3`: Command Center 또는 learning profile에서 status별 sample count/false-positive rate, alias graph size, learning scope breakdown/recommendation, Evidence Lock 상태가 표시되고 완료 오판 피드백은 completed rate/threshold에만 영향을 주는지 확인한다.
- `promise_radar_evidence_audit`: Command Center Evidence Audit이 locked/weak evidence, missing timestamp/speaker, marker hit, average similarity를 표시하고 약한 근거가 있으면 focus item으로 승격되는지 확인한다.
- `promise_radar_google_tasks_oauth_guide`: Command Center의 Google Tasks 영역이 `https://www.googleapis.com/auth/tasks` scope, OAuth 승인 순서, production readiness, missing setup, token one-request 처리, 저장 금지 보안 안내를 표시하는지 확인한다.
- `promise_radar_accuracy_report`: 원장 헤더 또는 Command Center 정확도 패널에서 569건 fixture, 실제 회의 label 502건, accuracy 1.0, confidence bucket, coverage, source quality warning이 표시되는지 확인한다.
- `promise_radar_extraction_recall_report`: Command Center 정확도 패널 또는 `GET /api/v1/promise-radar/accuracy/extraction-report`에서 50건 extraction fixture, expected 50건, matched 50건, recall 1.0이 표시되는지 확인한다.
- `promise_radar_accuracy_audit_gate`: `python backend/scripts/audit_promise_radar_accuracy_set.py --target-real-cases 500`가 오류 없이 통과하고 fixture/manifest mismatch가 없음을 확인한다.
- `promise_radar_extraction_recall_gate`: `python backend/scripts/evaluate_promise_radar_extraction.py --target-cases 50 --min-recall 0.95`가 오류 없이 통과하고 false negative failures가 없음을 확인한다.
- `promise_radar_identity_confidence`: 원장 행에서 화자/담당자 신뢰도 pill이 표시되고, speaker/owner/assigned user가 없는 항목은 표시되지 않거나 낮은 값으로 표시되는지 확인한다.
- `promise_radar_responsibility_scores`: Result 화면 `담당자 책임 점수` 섹션에서 owner별 open/completed/overdue/completion rate와 risk chip이 표시되는지 확인한다.
- `promise_radar_meeting_series`: Result 화면 `반복회의 연결` 섹션에서 같은 회의 제목/시리즈의 열린 약속, 기한 초과, 고위험 수와 확인 질문이 표시되는지 확인한다.
- `promise_radar_pre_meeting_push`: 원장 헤더의 `회의 전 브리프 푸시` 버튼 또는 `PROMISE_RADAR_PRE_MEETING_PUSH_ENABLED=true` scheduler tick으로 `promise_radar_pre_meeting_brief` FCM data가 발송되고 같은 사용자/일자 중복 발송이 차단되는지 확인한다.
- `promise_radar_android_device_gate`: Android staging release에서 `client/scripts/verify_promise_radar_device_gate.py`가 설치 metadata, UIAutomator `약속 레이더`/`탭 12개`, APK staging URL guard를 모두 통과하는지 확인한다.

### 2026-07-01 iPhone 실기기 release evidence

- 기기: `Inbean의 iPhone`, UDID `00008150-000239020C08401C`, iOS `26.5.1 23F81`
- Backend health: `http://100.69.69.119:8000/api/v1/health` -> HTTP 200 healthy
- Build: `flutter build ios --release --dart-define=ENV=staging --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1` -> `Runner.app (38.3MB)`
- Install: `xcrun devicectl device install app --device 00008150-000239020C08401C build/ios/iphoneos/Runner.app` -> bundleID `com.voicetextnote.app`
- Launch: `xcrun devicectl device process launch --device 00008150-000239020C08401C com.voicetextnote.app` -> launched
- URL guard: built App.framework strings contained `http://100.69.69.119:8000/api/v1` and did not emit the production host in the same check.

### 2026-07-01 Android 실기기 staging release evidence

- 기기: `Redmi Note 9 Pro`, ADB serial `76aadc20`, Android 12 API 31
- Build/install: `flutter run --release --no-pub --no-resident -d 76aadc20 --dart-define=ENV=staging --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1`
- Install evidence: `adb shell dumpsys package com.voicetextnote.app` -> `versionName=1.0.0`, `lastUpdateTime=2026-07-01 15:39:18`
- UI evidence: UIAutomator dump after reinstall showed `약속 레이더\n탭 12개 중 4번째`
- URL guard: APK `lib/arm64-v8a/libapp.so` strings contained `http://100.69.69.119:8000/api/v1`
- Automated gate: `python3 client/scripts/verify_promise_radar_device_gate.py --serial 76aadc20` -> `PASS Promise Radar Android device gate`
- Root cause for missing menu: stale Android release APK. The stale install showed `탭 11개` and no `약속 레이더` tab.

## 결과 기록

- 테스터: _______
- 기기 (Android): _______  OS 버전: _______
- 기기 (iOS): _______  OS 버전: _______
- 백엔드 버전: _______
- 클라이언트 버전: _______
- 테스트 일자: _______
- E2E evidence JSON 경로: _______
- 실패 항목 상세:
  ```
  
  ```
