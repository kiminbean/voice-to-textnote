# Release Readiness 실행 절차

**SPEC-RELEASE-001 | 작성일: 2026-06-15**

이 문서는 Release Candidate를 Production Ready로 전환하기 위한 단계별 실행 가이드입니다.

## 사전 조건

- [x] 36개 SPEC 전부 완료
- [x] `verify_release_readiness.py` (default) — 0 errors
- [x] CI: Test & Lint PASS, Flutter Android PASS, Flutter iOS PASS
- [x] 백엔드: 3772 passed, Flutter: 379 passed, backend coverage 100.00%
- [ ] `verify_release_readiness.py --strict` — **11 errors (이 문서의 목표)**

---

## Phase 1: 외부 계정 설정 (병렬 가능)

### 1.1 Firebase 서비스 계정

```bash
# 1. Firebase Console → 프로젝트 설정 → 서비스 계정 → Python → 새 비공개 키 생성
# 2. 다운로드한 JSON을 안전한 위치에 저장
# 3. 환경 변수 설정
export FIREBASE_CREDENTIALS_PATH=/secure/path/service-account.json

# 4. 백엔드 재시작 후 MOCK 모드 해제 확인
# 로그에 "Firebase Admin SDK 초기화 완료 (프로덕션 모드)"가 표시되어야 함

# 5. 검증
python3 client/scripts/verify_release_readiness.py --strict 2>&1 | grep Firebase
# 기대: PASS Firebase service account
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
flutter build apk --release

# iOS (Xcode에서 코드사인 필요)
flutter build ios --release
```

### 2.3 E2E 증거 수집

```bash
# evidence scaffold 생성
ANDROID_DEVICE_SERIAL=$ANDROID_DEVICE_SERIAL \
IOS_DEVICE_UDID=$IOS_DEVICE_UDID \
python3 client/scripts/create_release_e2e_evidence.py --output docs/release-e2e-evidence.json

# 17개 required scenario 수동 실행 후 JSON 채우기:
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

### 3.2 GitHub Environment 설정

```bash
# 환경 변수에서 secrets 일괄 설정
FIREBASE_SERVICE_ACCOUNT_JSON="$(cat $FIREBASE_CREDENTIALS_PATH)" \
APNS_AUTH_KEY_P8="$(cat $APNS_AUTH_KEY_PATH)" \
APNS_KEY_ID=$APNS_KEY_ID \
APNS_TEAM_ID=$APNS_TEAM_ID \
APP_STORE_CONNECT_API_KEY_P8="$(cat $APP_STORE_CONNECT_API_KEY_PATH)" \
APP_STORE_CONNECT_KEY_ID=$APP_STORE_CONNECT_KEY_ID \
APP_STORE_CONNECT_ISSUER_ID=$APP_STORE_CONNECT_ISSUER_ID \
FIREBASE_TEST_DEVICE_TOKEN=$FIREBASE_TEST_DEVICE_TOKEN \
python3 client/scripts/configure_github_mobile_release_env.py --repo kiminbean/voice-to-textnote
```

### 3.3 Strict Gate CI 실행

```bash
# GitHub Actions → mobile.yml → Run workflow
# evidence_path에 docs/release-e2e-evidence.json 입력
gh workflow run mobile.yml \
  -f evidence_path=docs/release-e2e-evidence.json
```

---

## Phase 4: Release

Phase 4는 `python3 client/scripts/verify_release_readiness.py --strict`가 0 errors로 통과한 뒤에만 실행합니다. 현재 strict gate는 외부 secret, 물리 기기, 실제 E2E evidence가 없으면 실패해야 정상입니다.

### 4.1 README 업데이트

```markdown
**상태**: Production Ready v1.6.0 — strict release readiness 0 errors 확인 후 적용
```

### 4.2 Git Tag + GitHub Release

```bash
git tag v1.6.0 -m "Production Ready v1.6.0 — 36 SPECs completed"
git push origin v1.6.0

# GitHub Release 생성
gh release create v1.6.0 \
  --title "v1.6.0 — Production Ready" \
  --notes-file CHANGELOG.md
```

---

## 체크리스트 요약

| 단계 | 환경 변수 | 검증 방법 |
|------|-----------|-----------|
| 1.1 Firebase | `FIREBASE_CREDENTIALS_PATH` | `--strict` Firebase PASS |
| 1.2 APNs | `APNS_AUTH_KEY_PATH`, `APNS_KEY_ID`, `APNS_TEAM_ID` | `--strict` APNs 3개 PASS |
| 1.3 App Store | `APP_STORE_CONNECT_API_KEY_PATH`, `KEY_ID`, `ISSUER_ID` | `--strict` App Store 3개 PASS |
| 2.1 기기 | `ANDROID_DEVICE_SERIAL`, `IOS_DEVICE_UDID` | `adb`/`devicectl` 인식 |
| 2.3 E2E | `FIREBASE_TEST_DEVICE_TOKEN`, `RELEASE_E2E_EVIDENCE_PATH` | evidence JSON 17개 required scenario pass:true |
| 3.1 Runner | (GitHub Actions) | `verify_github_mobile_release_env.py` PASS |
| 4.1 Release | (README + tag) | `git tag` + GitHub Release 확인 |
