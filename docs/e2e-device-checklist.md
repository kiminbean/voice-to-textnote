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
- [ ] 네이티브 빌드 게이트 통과: `cd client && ./scripts/verify_mobile.sh --native`
- [ ] Android APK 산출물 확인: `client/build/app/outputs/flutter-apk/app-debug.apk`
- [ ] iOS no-codesign 산출물 확인: `client/build/ios/iphoneos/Runner.app`
- [ ] Release readiness 기본 사전검사 통과: `python3 client/scripts/verify_release_readiness.py`
- [ ] Release E2E evidence 작성: `docs/release-e2e-evidence.example.json`을 복사해 실제 기기/빌드/시나리오 증거로 채운 뒤 `RELEASE_E2E_EVIDENCE_PATH`에 지정
- [ ] Strict release readiness 통과(placeholder 없는 release 문서, 서비스 계정/APNs/App Store Connect/실기기 secret 및 실제 연결 기기 포함): `python3 client/scripts/verify_release_readiness.py --strict`

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
| `FIREBASE_CREDENTIALS_PATH` | Backend Firebase Admin SDK 서비스 계정 JSON |
| `APNS_AUTH_KEY_PATH` | Firebase Console에 업로드한 APNs `.p8` 키 파일 |
| `APNS_KEY_ID` / `APNS_TEAM_ID` | Apple Developer APNs 키 식별자 |
| `APP_STORE_CONNECT_API_KEY_PATH` | App Store Connect API `.p8` 키 파일 |
| `APP_STORE_CONNECT_KEY_ID` / `APP_STORE_CONNECT_ISSUER_ID` | App Store Connect API 식별자 |
| `ANDROID_DEVICE_SERIAL` | `adb devices`에 표시되는 Android 실기기 serial |
| `IOS_DEVICE_UDID` | Xcode/idevice_id에 표시되는 iOS 실기기 UDID |
| `FIREBASE_TEST_DEVICE_TOKEN` | 앱이 서버에 등록한 테스트용 FCM token |
| `RELEASE_E2E_EVIDENCE_PATH` | 실기기 Push/딥링크/백그라운드 녹음/공유/HTTP 정책 시나리오 pass 증거 JSON |

`--strict`는 환경변수 존재만 확인하지 않는다. `docs/app-store-metadata.md`, `docs/privacy-policy.md`, `docs/e2e-device-checklist.md`에 release placeholder가 없어야 한다. 또한 `ANDROID_DEVICE_SERIAL`은 `adb devices -l`에 `device` 상태로 표시되어야 하고, `IOS_DEVICE_UDID`는 `xcrun devicectl list devices`에서 `available` 상태로 표시되어야 한다. `RELEASE_E2E_EVIDENCE_PATH`는 JSON 파일이어야 하며 Android/iOS device id가 strict 환경변수와 일치하고, Push/딥링크/백그라운드 녹음/HTTP 정책/PDF 공유 시나리오가 모두 `pass: true`와 증거 문구를 가져야 한다. 따라서 Firebase/APNs/App Store Connect secret이 있어도 문서 placeholder가 남아 있거나 물리 기기가 연결되지 않았거나 trust/pairing이 완료되지 않았거나 실제 시나리오 증거가 없으면 E2E 진입 전 실패한다.

> 참고: Kotlin Gradle Plugin의 Built-in Kotlin 마이그레이션 경고는 현재 빌드 실패가 아니라 미래 호환성 경고다. 경고가 오류로 승격되면 plugin 버전 업그레이드 또는 Flutter Built-in Kotlin 마이그레이션을 별도 작업으로 처리한다.

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

`RELEASE_E2E_EVIDENCE_PATH`는 아래 scenario key를 모두 포함해야 한다. 각 항목은 `pass: true`와 실제 관측 증거 문구를 가져야 하며, Android/iOS device id는 strict 환경변수와 일치해야 한다.

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
