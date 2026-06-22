# 실기기 E2E 테스트 체크리스트 (T-020)

**SPEC-MOBILE-004 | 작성일: 2026-06-13**

---

## 사전 준비

- [ ] 백엔드 서버 실행 (FastAPI + Celery + Redis)
- [ ] 클라이언트 디바이스 등록 (로그인 → FCM 토큰 등록)
- [ ] Firebase 프로젝트 설정 완료 (T-019)
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
| `FIREBASE_CREDENTIALS_PATH` | Backend Firebase Admin SDK 서비스 계정 JSON |
| `APNS_AUTH_KEY_PATH` | Firebase Console에 업로드한 APNs `.p8` 키 파일 |
| `APNS_KEY_ID` / `APNS_TEAM_ID` | Apple Developer APNs 키 식별자 |
| `APP_STORE_CONNECT_API_KEY_PATH` | App Store Connect API `.p8` 키 파일 |
| `APP_STORE_CONNECT_KEY_ID` / `APP_STORE_CONNECT_ISSUER_ID` | App Store Connect API 식별자 |
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

이 job은 먼저 `python3 client/scripts/verify_mobile_release_runner.py`로 macOS runner, Flutter doctor, `xcodebuild -version`, Android authorized device, iOS available device를 확인한다. 그 다음 Android signing secret을 임시 keystore와 `client/android/key.properties`로 materialize하고 `REQUIRE_ANDROID_RELEASE_SIGNING=true client/scripts/verify_mobile.sh --native`로 Flutter analyze/test/local STT smoke/Android signed release APK/iOS no-codesign build를 실행한 뒤, Firebase/APNs/App Store Connect secret을 임시 파일로 materialize하고 `python3 client/scripts/verify_release_readiness.py --strict`를 실행한다. `evidence_path` 입력값은 실제 release evidence JSON을 가리켜야 하며, `ios_entitlements_path` 입력값은 signed iOS release app에서 추출한 repo 내부 plist여야 한다. 예제 파일을 그대로 사용하면 device id와 artifact/evidence가 실제 strict 입력과 맞지 않아 실패해야 정상이다.

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

`--strict`는 환경변수 존재만 확인하지 않는다. `REQUIRE_ANDROID_RELEASE_SIGNING=true`가 설정되어 signed Android release gate와 같은 release 조건임을 먼저 확인하고, `docs/app-store-metadata.md`, `docs/privacy-policy.md`, `docs/e2e-device-checklist.md`에 release placeholder가 없어야 한다. 또한 `ANDROID_DEVICE_SERIAL`은 `adb devices -l`에 `device` 상태로 표시되어야 하고, `IOS_DEVICE_UDID`는 `xcrun devicectl list devices`에서 `available` 상태로 표시되어야 한다. `IOS_RELEASE_ENTITLEMENTS_PATH`는 체크아웃된 repo 내부 plist여야 하며 signed iOS release app에서 추출한 `aps-environment=production`, `get-task-allow=false`, App ID/Team ID 일치를 증명해야 한다. `RELEASE_E2E_EVIDENCE_PATH`는 체크아웃된 repo 내부 JSON 파일이어야 하며 `release_gate.android_release_signing=true`, `release_gate.ios_production_entitlements=true`, `release_gate.ios_entitlements_sha256`이 실제 `IOS_RELEASE_ENTITLEMENTS_PATH` SHA-256과 일치해야 한다. Android/iOS device id가 strict 환경변수와 일치하고, Push/딥링크/백그라운드 녹음/HTTP 정책/PDF 공유 시나리오가 모두 `pass: true`와 증거 문구를 가져야 한다. 따라서 signed Android release 모드, Firebase/APNs/App Store Connect secret이 있어도 문서 placeholder가 남아 있거나 물리 기기가 연결되지 않았거나 trust/pairing이 완료되지 않았거나 실제 시나리오 증거가 없으면 E2E 진입 전 실패한다.

### Release E2E evidence scaffold

아래 명령은 현재 git revision, `ANDROID_DEVICE_SERIAL`, `IOS_DEVICE_UDID`, 기본 Android/iOS build artifact 경로, `artifact_sha256`, 모든 required scenario key를 포함한 JSON scaffold를 repo 내부에 생성한다. `artifacts` 값은 운영 장비 절대경로가 아니라 repo-relative 경로여야 하며, Android는 `client/build/app/outputs/flutter-apk/app-release.apk`, iOS는 `client/build/ios/iphoneos/Runner.app`만 허용된다. 생성 직후 scenario는 모두 `pass: false`이며, 실제 실기기 관측 증거를 채우기 전에는 strict readiness가 실패해야 정상이다.

```bash
ANDROID_DEVICE_SERIAL=<adb-device-serial> \
IOS_DEVICE_UDID=<ios-device-udid> \
REQUIRE_ANDROID_RELEASE_SIGNING=true \
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

---

## Release E2E Evidence JSON 매핑

`RELEASE_E2E_EVIDENCE_PATH`는 아래 scenario key를 모두 포함해야 한다. 각 항목은 `pass: true`와 실제 관측 증거 문구를 가져야 하며, 해당 scenario 플랫폼의 Android serial/iOS UDID를 증거 문구에 포함해야 한다. Android/iOS device id는 strict 환경변수와 일치해야 한다. `release_gate.android_release_signing=true`, `release_gate.ios_production_entitlements=true`, `release_gate.ios_entitlements_sha256=<IOS_RELEASE_ENTITLEMENTS_PATH SHA-256>`를 기록해 signed Android APK와 production iOS entitlement 조건에서 수행된 evidence임을 남겨야 한다. `artifacts`는 repo-relative 표준 release output 경로만 허용되며, `artifact_sha256`은 `artifacts`의 모든 key를 포함하고 실제 release 산출물 파일/디렉터리 내용의 SHA-256과 일치해야 한다.

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
| `android_release_cleartext_blocked` | SPEC-SEC-002 AC-M03 Android Release HTTP 차단 |
| `ios_release_http_blocked` | SPEC-SEC-002 AC-M01 iOS Release HTTP 차단 |
| `export_share_android` | SPEC-EXPORT-001 Android PDF 공유 시트 |
| `export_share_ios` | SPEC-EXPORT-001 iOS PDF 공유 시트 |

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
