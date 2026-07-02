# Release Readiness 실행 절차

**SPEC-RELEASE-001 | 작성일: 2026-06-15**

이 문서는 Release Candidate를 Production Ready로 전환하기 위한 단계별 실행 가이드입니다.

## 사전 조건

- [x] 36개 SPEC 전부 완료
- [x] `verify_release_readiness.py` (default) — 0 errors
- [x] CI: Test & Lint PASS, Flutter Android PASS, Flutter iOS PASS
- [x] 백엔드: 4005 passed, Flutter: 415 passed, backend coverage 100.00%
- [ ] `verify_release_readiness.py --strict` — Mac mini 로컬 secret/device env는 PASS이며, 2026-07-01 현재 **13 errors, 1 warning**이 남아 있다.
  Android-only scenario 4개, iOS HTTP 정책 scenario 1개, Android+iOS 공통 scenario 3개(`permission_microphone_initial`, `permission_denied_recovery`, `unfinished_recording_recovery`)는 실제 evidence로 `pass:true`다. 나머지 iOS-only 또는 Android+iOS 공통 실기기 E2E scenario는 아직 실제 screenshot/log/video/trace evidence가 필요하다.

---

## Phase 1: 외부 계정 설정 (병렬 가능)

### 1.1 Firebase 서비스 계정

```bash
# 1. Firebase Console → 프로젝트 설정 → 서비스 계정 → Python → 새 비공개 키 생성
# 2. 다운로드한 JSON을 안전한 위치에 저장
# 3. 환경 변수 설정
export FIREBASE_CREDENTIALS_PATH=/secure/path/service-account.json
export REQUIRE_ANDROID_RELEASE_SIGNING=true

# 4. 백엔드 재시작 후 MOCK 모드 해제 확인
# 로그에 "Firebase Admin SDK 초기화 완료 (프로덕션 모드)"가 표시되어야 함

# 5. 검증
python3 client/scripts/verify_release_readiness.py --strict 2>&1 | grep Firebase
# 기대: PASS Firebase service account
```

개발 백엔드 PC 기준 현재 확인값:

```text
Host: 100.69.69.119
Repo: /Users/ibkim/Projects/voice-to-textnote
FIREBASE_CREDENTIALS_PATH=/Users/ibkim/secure/voice-to-textnote/firebase-adminsdk-fbsvc.json
```

운영 메모:

- 서비스 계정 JSON은 repo 밖에 두고 권한은 `600`으로 유지한다.
- 원격 `.env`에 `FIREBASE_PROJECT_ID`를 추가하지 않는다. 현재 설정 모델에서 허용하지 않아 서버 시작이 실패한다.
- 로컬 `.env`를 원격으로 동기화할 때 원격의 `FIREBASE_CREDENTIALS_PATH`를 보존한다.
- 실제 개발 Push 검증은 2026-06-30에 `mock_mode False`와 Firebase message id 반환으로 완료되었다.

```text
projects/voice-to-textnote/messages/1782749586143713
```

### 1.2 APNs 인증 키

```bash
# 1. Apple Developer Console → Keys → 새 키 생성 (APNs 체크)
# 2. .p8 파일 다운로드, Key ID 기록
# 3. Firebase Console → Cloud Messaging → APNs 인증 키 업로드
# 4. 환경 변수 설정
export APNS_AUTH_KEY_PATH=/secure/path/AuthKey_XXXXXX.p8
export APNS_KEY_ID=XXXXXX
export APNS_TEAM_ID=YYYYYYYYYY

# 5. 검증
python3 client/scripts/verify_release_readiness.py --strict 2>&1 | grep APNs
# 기대: PASS APNs auth key, PASS APNs key id, PASS APNs team id
```

2026-07-01 Mac mini 기준 확인값:

```text
APNS_AUTH_KEY_PATH=/Users/ibkim/secure/voice-to-textnote/AuthKey_362893TR3Z.p8
APNS_KEY_ID=362893TR3Z
APNS_TEAM_ID=4NJ9JSQFW9
```

### 1.3 App Store Connect API 키

```bash
# 1. App Store Connect → Users and Access → Keys → API Keys 탭
# 2. 새 키 생성 (Admin 권한), Issuer ID 기록
# 3. 환경 변수 설정
export APP_STORE_CONNECT_API_KEY_PATH=/secure/path/AuthKey_XXXXXXXXXX.p8
export APP_STORE_CONNECT_KEY_ID=XXXXXXXXXX
export APP_STORE_CONNECT_ISSUER_ID=yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy

# 4. 검증
python3 client/scripts/verify_release_readiness.py --strict 2>&1 | grep "App Store"
# 기대: PASS App Store Connect API key, key id, issuer id
```

2026-07-01 Mac mini 기준 확인값:

```text
APP_STORE_CONNECT_API_KEY_PATH=/Users/ibkim/secure/voice-to-textnote/AuthKey_5WDG3L7L32.p8
APP_STORE_CONNECT_KEY_ID=5WDG3L7L32
APP_STORE_CONNECT_ISSUER_ID=3af9f2b0-aefc-4670-a821-1606fb19e086
```

App Store Connect API로 생성한 production signing 산출물:

```text
Certificate ID: 4H9K72UW92
Profile ID: 398AB7SHX6
Profile UUID: 43a2b781-c7fb-48ad-934a-821e7fdb71ca
Profile name: VoiceToTextNote App Store 20260701191236
Profile path: /Users/ibkim/secure/voice-to-textnote/apple-signing/VoiceToTextNote_AppStore_20260701191236.mobileprovision
Signing identity: Apple Distribution: KISOO KIM (4NJ9JSQFW9)
```

주의: MacBook의 Xcode automatic signing은 development signing에는 사용할 수 있지만, 2026-07-01 SSH 확인 당시 MacBook repo는 `b650ebb`였고 키체인에는 `Apple Development: KISOO KIM (PCZ7DH2Z2Q)`만 보였다. 현재 strict production entitlement 증거는 Mac mini에서 생성한 App Store distribution archive를 기준으로 한다.

### 1.4 iOS production entitlement evidence

```bash
# signed App Store/Profile release app에서 entitlement를 추출
# 예: Xcode Organizer archive/export 또는 CI 서명 산출물의 Runner.app 사용
mkdir -p docs
codesign -d --entitlements :- /path/to/signed-release/Runner.app \
  > docs/ios-release-entitlements.plist

export IOS_RELEASE_ENTITLEMENTS_PATH=docs/ios-release-entitlements.plist
shasum -a 256 "$IOS_RELEASE_ENTITLEMENTS_PATH"

# 검증 조건:
# - aps-environment = production
# - get-task-allow = false
# - application-identifier = <APNS_TEAM_ID>.com.voicetextnote.app
# - RELEASE_E2E_EVIDENCE_PATH의 release_gate.ios_entitlements_sha256과 일치
python3 client/scripts/verify_release_readiness.py --strict 2>&1 | grep "iOS release entitlements"
```

2026-07-01 production archive 기준 확인값:

```text
Archive: /Users/ibkim/secure/voice-to-textnote/apple-signing/Runner-production-final-20260701191705.xcarchive
Entitlements evidence: docs/ios-release-entitlements.plist
SHA-256: e44b8d040b5abe77085420d347e186850201db6111dd89c8819b39c664924bd3
application-identifier: 4NJ9JSQFW9.com.voicetextnote.app
aps-environment: production
get-task-allow: false
```

---

## Phase 2: 물리 기기 + E2E 증거

### 2.1 기기 연결

```bash
# Android (USB 디버깅 활성화)
adb devices
# 기대: device serial 표시
export ANDROID_DEVICE_SERIAL=<serial>

# iOS (Xcode pairing)
xcrun devicectl list devices
# 기대: device UDID 표시 (available 상태)
export IOS_DEVICE_UDID=<udid>
```

### 2.2 앱 빌드 및 설치

```bash
cd client

# Android Release APK
cat > android/key.properties <<EOF
storeFile=/secure/path/android-release.jks
storePassword=<keystore-password>
keyAlias=<key-alias>
keyPassword=<key-password>
EOF
REQUIRE_ANDROID_RELEASE_SIGNING=true ./scripts/verify_mobile.sh --native

# iOS (Xcode에서 코드사인 필요)
# iOS production release requires an explicit live HTTPS backend:
# flutter build ios --release --dart-define=API_BASE_URL=https://api.voicetextnote.com/api/v1
# Before any production install/build, run_production.sh verifies HTTPS and /health:
# API_BASE_URL=https://<live-backend>/api/v1 API_KEY="$API_KEY" ./scripts/run_production.sh

# Private staging release validation against the Tailscale backend
flutter build ios --release --dart-define=ENV=staging --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1 --dart-define=API_KEY="$API_KEY"
flutter build apk --release --dart-define=ENV=staging --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1 --dart-define=API_KEY="$API_KEY"

# App Store IPA / archive
flutter build ipa --release
```

`apksigner verify --print-certs` 출력의 certificate DN에 `CN=Android Debug`가 있으면 release APK가 아니다. `client/android/key.properties`가 `/Users/<user>/.android/debug.keystore` 또는 `androiddebugkey`를 가리키지 않는지 확인하고, 운영 upload/release keystore로 다시 빌드해야 한다.

현재 private staging 서버 기준값:

```text
API base URL: http://100.69.69.119:8000/api/v1
Health: http://100.69.69.119:8000/api/v1/health
```

주의:

- 기본 release 환경은 production이며 `https://api.voicetextnote.com/api/v1`을 사용한다.
- `api.voicetextnote.com` DNS/HTTPS 백엔드가 준비되지 않은 상태에서 기본 release 빌드를 실기기에 설치하면 Google 계정 선택 후 `/auth/google` 호출 단계에서 "서버에 연결할 수 없습니다"가 발생한다.
- 2026-07-02 현재 `https://api.voicetextnote.com/api/v1/health`는 DNS 해석이 되지 않는다. Production 배포 전에는 DNS, TLS, reverse proxy, backend `/api/v1/health` 응답을 먼저 통과시킨다.
- `client/scripts/run_production.sh`는 `API_BASE_URL`이 HTTPS가 아니거나 `${API_BASE_URL}/health`가 실패하면 `flutter run --release` 전에 중단한다. 이 검사를 우회하지 않는다.
- 로컬 strict release gate 전용 값(`APNS_*`, `APP_STORE_CONNECT_*`, `ANDROID_DEVICE_SERIAL`, `IOS_DEVICE_UDID`, `RELEASE_E2E_EVIDENCE_PATH`, `FIREBASE_TEST_DEVICE_TOKEN`)은 `.env`가 아니라 `.env.release.local`에 둔다. `.env`는 backend Settings가 직접 읽기 때문에 미등록 release-only 키를 넣으면 백엔드 시작/pytest가 실패한다. `verify_release_readiness.py --strict`는 `.env`와 `.env.release.local`을 자동 로드하되, 셸/CI에서 이미 제공한 값은 덮어쓰지 않는다.
- 현재 private staging 실기기 검증은 반드시 `--dart-define=ENV=staging`, `--dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1`, `--dart-define=API_KEY="$API_KEY"`를 함께 지정해 빌드한다.
- 기본 production placeholder release APK를 실기기에 설치하면 앱이 blank screen으로 보일 수 있다. 이 경우 코드를 고치기 전에 staging dart-define이 빠진 빌드인지 먼저 확인한다.
- iOS ATS와 Android release/profile network security의 HTTP 예외는 `100.69.69.119`에만 좁게 허용한다. 새 HTTP staging host를 쓰려면 플랫폼 보안 설정과 테스트를 함께 갱신한다.
- Mac mini private staging 서버는 `tmux` 임시 프로세스가 아니라 macOS LaunchAgent `com.voicetextnote.backend-api`로 유지한다. `./scripts/install_backend_api_launch_agent.sh`를 실행하면 로그인 시 자동 시작, 프로세스 종료 시 재시작, `logs/backend-api.launchd.*.log` 기록이 적용된다.

2026-07-02 release gate 재점검:

- `dig +short api.voicetextnote.com`가 빈 응답이고 `curl https://api.voicetextnote.com/api/v1/health`는 `Could not resolve host`로 실패했다. Production 배포 전 DNS A/AAAA 또는 CNAME, TLS 인증서, reverse proxy, `/api/v1/health` 200 응답을 먼저 복구한다.
- `http://100.69.69.119:8000/api/v1/health`는 Mac mini local backend 기동 후 200 healthy, Redis healthy, Celery active worker 1개로 확인했다. 이 주소는 private staging 검증용이며 Store production URL이 아니다.
- `docs/ios-release-entitlements.plist`는 `aps-environment=production`, `get-task-allow=false`, `application-identifier=4NJ9JSQFW9.com.voicetextnote.app`로 확인했다. Xcode 프로젝트의 개발용 `Runner.entitlements`가 `development`인 warning은 production-signed archive에서 추출한 entitlement 증거와 별도로 관리한다.
- 최신 Promise Radar staging API 증거는 `docs/promise-radar-e2e-evidence-2026-07-02-v20-summary.json`이며 `overall_pass=true`, `radar_load`, `autopilot_preview`, `review_queue`, `pre_meeting_brief`, `command_center`, `calendar_export`, `assignee_quality`, `due_push_dispatch_contract`가 모두 `ok=true`다.
- `python3 client/scripts/verify_release_readiness.py --strict`는 release secret/device는 통과하지만, 현재 git revision과 새 Android/iOS build artifact hash가 `docs/release-e2e-evidence.json`에 기록된 관측 증거와 달라 실패해야 정상이다. 이 파일은 수동으로 hash/revision만 맞추지 말고, 현재 revision과 최신 artifact로 21개 required E2E scenario를 다시 관측한 뒤 갱신한다.

2026-07-01 실기기 릴리스 설치 기준:

```bash
cd client
./scripts/run_ios_staging_release.sh
```

iOS에서 동일한 명령을 직접 실행해야 할 때:

```bash
cd client
flutter run --release --no-pub --no-resident \
  -d 00008150-000239020C08401C \
  --dart-define=ENV=staging \
  --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1 \
  --dart-define=API_KEY="$API_KEY"
```

Android에서 동일한 명령을 직접 실행해야 할 때:

```bash
cd client
flutter run --release --no-pub --no-resident \
  -d 76aadc20 \
  --dart-define=ENV=staging \
  --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1 \
  --dart-define=API_KEY="$API_KEY"
```

2026-07-01 Android `Redmi Note 9 Pro` 검증에서 오래된 설치본은 결과 화면 탭이 11개였고 `약속 레이더` 탭이 없었다. 최신 staging release 재설치 후 `adb shell dumpsys package com.voicetextnote.app`의 `lastUpdateTime=2026-07-01 19:56:54`, UIAutomator dump의 `약속 레이더\n탭 12개 중 4번째`, release APK SHA-256 `d75e70b96a30e03988a292658ef51086fbe67f19b8c084d28ff6744c6432ec2a`, release APK network-security-config의 `base-config cleartextTrafficPermitted=false` 및 `100.69.69.119` 단일 cleartext 예외를 확인했다. Promise Radar 메뉴가 보이지 않거나 앱이 blank screen이면 먼저 stale APK 또는 staging dart-define 누락 여부를 의심하고 위 명령으로 재설치한다. `verify_promise_radar_device_gate.py`가 `Promise Radar tab missing or stale tab count: None`으로 실패하면 앱 문제가 아니라 Android가 MIUI 공유 시트(`MiuiChooserActivity`, 제목 `공유`)에 머물러 있을 수 있다. 이 경우 `adb shell input keyevent HOME` 후 `adb shell monkey -p com.voicetextnote.app -c android.intent.category.LAUNCHER 1`로 앱을 다시 앞으로 가져와 결과 화면 UI dump가 복원된 뒤 gate를 재실행한다.

Archive 설치 경로를 써야 할 때:

```bash
cd client
flutter build ios --release \
  --dart-define=ENV=staging \
  --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1
xcrun devicectl list devices
xcrun devicectl device info details \
  --device C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA

xcrun devicectl device install app \
  --device C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA \
  build/ios/iphoneos/Runner.app

xcrun devicectl device process launch \
  --device C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA \
  com.voicetextnote.app
```

Flutter가 Developer Mode 오류를 표시해도 `devicectl`에서 `developerModeStatus: enabled`, `paired`, `wired`, `available`이면 archive의 서명된 앱을 직접 설치할 수 있다.

### 2.3 E2E 증거 수집

```bash
# evidence scaffold 생성
ANDROID_DEVICE_SERIAL=$ANDROID_DEVICE_SERIAL \
IOS_DEVICE_UDID=$IOS_DEVICE_UDID \
REQUIRE_ANDROID_RELEASE_SIGNING=true \
IOS_RELEASE_ENTITLEMENTS_PATH=docs/ios-release-entitlements.plist \
python3 client/scripts/create_release_e2e_evidence.py --output docs/release-e2e-evidence.json

# artifacts 값은 운영 장비 절대경로나 임의 release 파일이 아니라 아래 표준 repo-relative 경로여야 함:
# - client/build/app/outputs/flutter-apk/app-release.apk
# - client/build/ios/iphoneos/Runner.app

# 21개 required scenario 수동 실행 후 JSON 채우기:
# - 각 scenario는 `platforms` 배열을 유지해야 함:
#   - Android+iOS 공통 플로우: `["android", "ios"]`
#   - Android 전용 플로우: `["android"]`
#   - iOS 전용 플로우: `["ios"]`
# - 마이크 권한 최초 요청/거부 복구
# - iOS 백그라운드 녹음/인터럽트 재개/Bluetooth route change
# - 미완료 녹음 복구
# - STT/요약/실패 Push 수신
# - 백그라운드/콜드스타트 Push 딥링크
# - Android foreground recording notification
# - Android debug Tailscale HTTP 허용 및 Android/iOS release HTTP 차단
# - Android/iOS PDF 공유 시트

# FCM 테스트 토큰 (앱에서 등록한 토큰)
export FIREBASE_TEST_DEVICE_TOKEN=<fcm-token-from-app>

export IOS_RELEASE_ENTITLEMENTS_PATH=docs/ios-release-entitlements.plist
# release_gate.ios_entitlements_sha256은 IOS_RELEASE_ENTITLEMENTS_PATH의 SHA-256으로 갱신
export RELEASE_E2E_EVIDENCE_PATH=docs/release-e2e-evidence.json
```

### 2.4 검증

```bash
python3 client/scripts/verify_release_readiness.py --strict
# 기대: 0 errors
```

---

## Phase 3: CI 인프라 (선택, 권장)

### 3.1 Self-hosted Runner 설치

```bash
# M4 Mac Mini에서 실행
# GitHub repo → Settings → Actions → Runners → New self-hosted runner
# 안내에 따라 설치:
./config.sh --url https://github.com/kiminbean/voice-to-textnote \
  --token TOKEN \
  --labels self-hosted,macOS,mobile-release
./run.sh  # 또는 brew services로 daemon 등록
```

러너를 등록한 뒤 strict workflow를 실행하기 전에 같은 macOS 장비에서 실기기와 툴체인을 확인합니다.

```bash
ANDROID_DEVICE_SERIAL=$ANDROID_DEVICE_SERIAL \
IOS_DEVICE_UDID=$IOS_DEVICE_UDID \
python3 client/scripts/verify_mobile_release_runner.py
```

### 3.2 GitHub Environment 설정

```bash
# 환경 변수에서 secrets 일괄 설정
FIREBASE_SERVICE_ACCOUNT_JSON="$(cat $FIREBASE_CREDENTIALS_PATH)" \
ANDROID_KEYSTORE_BASE64="$(base64 < /secure/path/android-release.jks | tr -d '\n')" \
ANDROID_KEYSTORE_PASSWORD=<keystore-password> \
ANDROID_KEY_ALIAS=<key-alias> \
ANDROID_KEY_PASSWORD=<key-password> \
APNS_AUTH_KEY_P8="$(cat $APNS_AUTH_KEY_PATH)" \
APNS_KEY_ID=$APNS_KEY_ID \
APNS_TEAM_ID=$APNS_TEAM_ID \
APP_STORE_CONNECT_API_KEY_P8="$(cat $APP_STORE_CONNECT_API_KEY_PATH)" \
APP_STORE_CONNECT_KEY_ID=$APP_STORE_CONNECT_KEY_ID \
APP_STORE_CONNECT_ISSUER_ID=$APP_STORE_CONNECT_ISSUER_ID \
FIREBASE_TEST_DEVICE_TOKEN=$FIREBASE_TEST_DEVICE_TOKEN \
python3 client/scripts/configure_github_mobile_release_env.py --repo kiminbean/voice-to-textnote

python3 client/scripts/verify_github_mobile_release_env.py --repo kiminbean/voice-to-textnote
```

### 3.3 Strict Gate CI 실행

```bash
# GitHub Actions → mobile.yml → Run workflow
# evidence_path에는 체크아웃된 repo 내부 JSON 경로를 입력
gh workflow run mobile.yml \
  -f evidence_path=docs/release-e2e-evidence.json
```

---

## Phase 4: Release

Phase 4는 `python3 client/scripts/verify_release_readiness.py --strict`가 0 errors로 통과한 뒤에만 실행합니다. 현재 strict gate는 외부 secret, 물리 기기, 실제 E2E evidence가 없으면 실패해야 정상입니다.

### 4.1 README 업데이트

```markdown
**상태**: Production Ready v1.7.0 — strict release readiness 0 errors 확인 후 적용
```

### 4.2 Git Tag + GitHub Release

```bash
git tag v1.7.0 -m "Production Ready v1.7.0 — 36 SPECs completed"
git push origin v1.7.0

# GitHub Release 생성
gh release create v1.7.0 \
  --title "v1.7.0 — Production Ready" \
  --notes-file CHANGELOG.md
```

---

## 체크리스트 요약

| 단계 | 환경 변수 | 검증 방법 |
|------|-----------|-----------|
| 0.1 Android signing | `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`, `REQUIRE_ANDROID_RELEASE_SIGNING=true` | `REQUIRE_ANDROID_RELEASE_SIGNING=true ./scripts/verify_mobile.sh --native` + `--strict` signed mode PASS, `apksigner --print-certs` DN이 `CN=Android Debug`가 아님 |
| 1.1 Firebase | `FIREBASE_CREDENTIALS_PATH` | `--strict` Firebase PASS |
| 1.2 APNs | `APNS_AUTH_KEY_PATH`, `APNS_KEY_ID`, `APNS_TEAM_ID` | `--strict` APNs 3개 PASS |
| 1.3 App Store | `APP_STORE_CONNECT_API_KEY_PATH`, `KEY_ID`, `ISSUER_ID` | `--strict` App Store 3개 PASS |
| 1.4 iOS entitlement | `IOS_RELEASE_ENTITLEMENTS_PATH`, `release_gate.ios_entitlements_sha256` | signed release app entitlements plist에서 `aps-environment=production`, `get-task-allow=false`, App ID/Team ID 일치, evidence hash 일치 |
| 2.1 기기 | `ANDROID_DEVICE_SERIAL`, `IOS_DEVICE_UDID` | `verify_mobile_release_runner.py` PASS |
| 2.3 E2E | `FIREBASE_TEST_DEVICE_TOKEN`, `RELEASE_E2E_EVIDENCE_PATH` | repo 내부 evidence JSON 21개 required scenario `pass:true` + `platforms` 계약 일치 + scenario별 device id + 중복 없는 screenshot/log/video/trace/attachment 관측 산출물 단서와 scenario key를 포함한 시나리오별 고유 파일명/URL/`artifact:`/`attachment:` 식별자 |
| 3.1 Runner | (GitHub Actions) | `verify_github_mobile_release_env.py` PASS |
| 4.1 Release | (README + tag) | `git tag` + GitHub Release 확인 |

2026-07-01 Mac mini strict 상태: Android-only scenario 4개, iOS HTTP 정책 scenario 1개, Android+iOS 공통 scenario 3개는 실제 evidence로 `pass:true`이며, strict 결과는 `release_readiness: 13 errors, 1 warnings`이다. Android+iOS 공통 scenario 중 `permission_microphone_initial`, `permission_denied_recovery`, `unfinished_recording_recovery`는 Redmi Note 9 Pro `76aadc20` Android screenshot/UI dump/service log와 iPhone `00008150-000239020C08401C` Release XCUITest attachment를 모두 확보했다. iOS Release XCUITest launch smoke도 iPhone 17 Pro에서 PASS했고 screenshot/UI hierarchy attachment 경로가 확보됐다. 앱 uninstall/reinstall 뒤 `The application could not be launched because the Developer App Certificate is not trusted`가 나오면 iPhone에서 `설정 > 일반 > VPN 및 기기 관리 > Apple Development: Created via API (5WDG3L7L32) > 신뢰`를 먼저 완료한다. 남은 13개는 iOS-only 또는 Android+iOS 공통 scenario이므로 각 scenario별 실제 조작/스크린샷/푸시/딥링크 관측 증거가 채워지기 전에는 통과시키지 않는다.
