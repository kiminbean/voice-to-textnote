---
id: SPEC-RELEASE-001
version: "1.0.0"
status: planned
created: "2026-06-15"
updated: "2026-06-15"
author: MoAI
priority: high
issue_number: 0
---

# SPEC-RELEASE-001: Release Readiness 절차 — Release Candidate → Production Ready 전환

## HISTORY

| Date | Version | Change | Author |
|------|---------|--------|--------|
| 2026-06-15 | 1.0.0 | Initial SPEC — 5단계 release readiness 절차 정의 | MoAI |

## 개요

Voice to TextNote는 34개 SPEC 완료, 3374 백엔드 테스트 + 328 Flutter 테스트 통과, CI 전부 green 상태의 **Release Candidate**입니다. 하지만 `verify_release_readiness.py --strict`는 11개 외부 의존성 미해결로 실패합니다.

본 SPEC은 Release Candidate를 Production Ready로 전환하기 위한 **실행 가능한 순차 절차**를 정의합니다. 각 단계는 명확한 입력, 출력, 검증 방법을 가집니다.

**현재 상태**:
- Default readiness: 0 errors, 2 warnings ✅
- Strict readiness: 11 errors ❌ (전부 외부 secret/물리 기기)
- Open PRs: 0
- CI: Test & Lint PASS, Flutter Android PASS, Flutter iOS PASS

## 요구사항 (EARS Format)

### REQ-REL-001: Firebase 프로젝트 설정 및 서비스 계정 연동

- **When** 백엔드가 Firebase Admin SDK를 초기화할 때
- **Then** 유효한 서비스 계정 JSON 파일이 존재하고 Push 전송이 가능해야 한다
- **Rationale**: `FIREBASE_CREDENTIALS_PATH` 미설정으로 strict 실패.

**절차**:
1. Firebase Console에서 프로젝트 생성 (이미 있는 경우 생략)
2. 서비스 계정 JSON 다운로드: Firebase Console → 프로젝트 설정 → 서비스 계정 → Python → 새 비공개 키 생성
3. `.env.local`에 `FIREBASE_CREDENTIALS_PATH=/path/to/service-account.json` 설정
4. 백엔드 재시작 후 `push_service._is_mock_mode == False` 확인
5. 테스트 기기에 앱 설치 후 FCM 토큰 등록 확인
6. 테스트 Push 전송: `POST /api/v1/devices/push-test`

**검증**:
- `FIREBASE_CREDENTIALS_PATH` 설정 시 `verify_release_readiness.py --strict`에서 해당 항목 PASS
- Push 전송 성공 로그 확인

### REQ-REL-002: APNs 인증 키 설정

- **When** iOS 기기에서 Push 알림을 수신할 때
- **Then** APNs `.p8` 인증 키가 Firebase Console에 업로드되고 환경 변수가 설정되어야 한다
- **Rationale**: `APNS_AUTH_KEY_PATH`, `APNS_KEY_ID`, `APNS_TEAM_ID` 미설정.

**절차**:
1. Apple Developer Console → Keys → 새 키 생성 (APNs 체크)
2. `.p8` 파일 다운로드, Key ID 기록
3. Firebase Console → Cloud Messaging → APNs 인증 키 업로드
4. 환경 변수 설정:
   - `APNS_AUTH_KEY_PATH=/path/to/AuthKey_XXXXXX.p8`
   - `APNS_KEY_ID=XXXXXX`
   - `APNS_TEAM_ID=YYYYYYYYYY`

**검증**:
- `verify_release_readiness.py --strict`에서 APNs 3개 항목 PASS
- iOS 실기기에서 Push 수신 확인

### REQ-REL-003: App Store Connect API 키 설정

- **When** App Store에 앱을 업로드하거나 메타데이터를 관리할 때
- **Then** App Store Connect API 키가 설정되어 있어야 한다
- **Rationale**: `APP_STORE_CONNECT_API_KEY_PATH`, `APP_STORE_CONNECT_KEY_ID`, `APP_STORE_CONNECT_ISSUER_ID` 미설정.

**절차**:
1. App Store Connect → Users and Access → Keys → API Keys 탭
2. 새 키 생성 (Admin 권권), Issuer ID 기록
3. `.p8` 파일 다운로드, Key ID 기록
4. 환경 변수 설정:
   - `APP_STORE_CONNECT_API_KEY_PATH=/path/to/AuthKey_XXXXXXXXXX.p8`
   - `APP_STORE_CONNECT_KEY_ID=XXXXXXXXXX`
   - `APP_STORE_CONNECT_ISSUER_ID=yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy`

**검증**:
- `verify_release_readiness.py --strict`에서 App Store Connect 3개 항목 PASS

### REQ-REL-004: 물리 기기 확보 및 E2E 증거 수집

- **When** Strict release readiness를 통과할 때
- **Then** Android 1대 + iOS 1대가 연결되어 있고 6개 E2E 시나리오의 pass 증거가 수집되어야 한다
- **Rationale**: `ANDROID_DEVICE_SERIAL`, `IOS_DEVICE_UDID`, `FIREBASE_TEST_DEVICE_TOKEN`, `RELEASE_E2E_EVIDENCE_PATH` 미설정.

**필수 기기**:
- Android: USB 디버깅 활성화, `adb devices`에 표시
- iOS: Xcode pairing, `xcrun devicectl list devices`에 표시

**6개 E2E 시나리오** (`docs/e2e-device-checklist.md` 참조):
1. **Push 알림**: 백엔드에서 Push 전송 → 기기에서 수신 확인
2. **딥링크**: Push 알림 탭 → 앱이 해당 회의 결과 화면으로 이동
3. **백그라운드 녹음**: 녹음 중 앱 백그라운드 전환 → 녹음 계속 → 복귀 후 정상
4. **HTTP 정책**: Release APK가 HTTP 평문 차단 (Tailscale만 허용)
5. **Foreground service**: Android 녹음 중 알림 표시
6. **PDF 공유**: 회의록 PDF 내보내기 → 시스템 공유 시트 동작

**절차**:
1. `ANDROID_DEVICE_SERIAL=<serial> IOS_DEVICE_UDID=<udid> python3 client/scripts/create_release_e2e_evidence.py --output docs/release-e2e-evidence.json`
2. 각 시나리오를 실기기에서 수동 실행하며 JSON 채우기
3. `FIREBASE_TEST_DEVICE_TOKEN` 설정 (앱에서 등록한 FCM 토큰)
4. `RELEASE_E2E_EVIDENCE_PATH=docs/release-e2e-evidence.json` 설정

**검증**:
- `verify_release_readiness.py --strict`에서 4개 항목 PASS
- evidence JSON의 모든 시나리오 `pass: true`

### REQ-REL-005: Self-hosted Runner 및 GitHub Environment 구성

- **When** GitHub Actions에서 strict release gate를 실행할 때
- **Then** `self-hosted`, `macOS`, `mobile-release` 라벨을 가진 runner가 온라인 상태여야 한다
- **Rationale**: `gh api repos/.../actions/runners` → runners=0.

**절차**:
1. macOS 기기 (M4 Mac Mini 사용 가능)에 GitHub Actions Runner 설치:
   ```bash
   gh actions-runner create-token --repo kiminbean/voice-to-textnote
   # 안내에 따라 runner 설치
   ./config.sh --url https://github.com/kiminbean/voice-to-textnote --token TOKEN --labels self-hosted,macOS,mobile-release
   ./run.sh
   ```
2. `mobile-release` GitHub Environment에 secrets/vars 설정:
   ```bash
   # 환경 변수에서 secrets 설정
   FIREBASE_SERVICE_ACCOUNT_JSON="$(cat service-account.json)" \
   APNS_AUTH_KEY_P8="$(cat AuthKey.p8)" \
   APNS_KEY_ID=... APNS_TEAM_ID=... \
   APP_STORE_CONNECT_API_KEY_P8="$(cat AuthKey.p8)" \
   APP_STORE_CONNECT_KEY_ID=... APP_STORE_CONNECT_ISSUER_ID=... \
   FIREBASE_TEST_DEVICE_TOKEN=... \
   python3 client/scripts/configure_github_mobile_release_env.py --repo kiminbean/voice-to-textnote
   ```
3. GitHub Actions workflow_dispatch로 strict gate 실행

**검증**:
- `python3 client/scripts/verify_github_mobile_release_env.py --repo kiminbean/voice-to-textnote` PASS
- `python3 client/scripts/verify_mobile_release_runner.py` PASS
- GitHub Actions strict release gate 통과

## 인수 기준 (Acceptance Criteria)

### AC-001: verify_release_readiness.py --strict 통과
- `python3 client/scripts/verify_release_readiness.py --strict` 실행 시 `0 errors`

### AC-002: GitHub Actions strict gate 통과
- `.github/workflows/mobile.yml`의 `workflow_dispatch` strict release job이 `self-hosted` runner에서 PASS

### AC-003: README 상태 업데이트
- README.md `**상태**:` 라인이 `Production Ready` (또는 `Released vX.X.X`)로 변경
- 현재 `Release Candidate` 텍스트 제거

### AC-004: Git tag 생성
- `git tag v1.X.0 -m "Production Ready"` 태그 생성 및 push
- GitHub Release 생성 (CHANGELOG 포함)

### AC-005: 전체 게이트 유지
- ruff check: 0 errors
- mypy: 0 errors
- pytest: 3374+ passed
- flutter analyze: No issues found!
- flutter test: 328+ passed

## 기술 접근법

### 절차 실행 순서 (의존성 그래프)

```
Phase 1: 외부 계정 설정 (병렬 가능)
├── Firebase 프로젝트 + 서비스 계정 (REQ-REL-001)
├── Apple Developer APNs 키 (REQ-REL-002)
└── App Store Connect API 키 (REQ-REL-003)

Phase 2: 물리 기기 + E2E 증거 (Phase 1 완료 후)
├── 기기 연결 + 앱 빌드 (REQ-REL-004)
└── 6개 시나리오 수동 실행 + evidence JSON 작성

Phase 3: CI 인프라 구축 (Phase 1+2 완료 후)
├── Self-hosted runner 설치 (REQ-REL-005)
├── GitHub Environment secrets 설정
└── Strict release gate CI 실행

Phase 4: Release (Phase 3 통과 후)
├── README 상태 업데이트
├── Git tag 생성
└── GitHub Release 게시
```

### 제약사항

- **외부 계정 필요**: Firebase, Apple Developer ($99/년), App Store Connect — 본 SPEC은 절차만 정의, 계정 생성은 사용자가 수행
- **물리 기기 필요**: Android 1대 + iOS 1대 — 에뮬레이터/시뮬레이터로 대체 불가
- **본 SPEC은 코드 변경 최소**: 대부분 설정/실행/검증 절차이므로 코드 수정보다 문서/실행 위주

## 우선순위

| REQ | 우선순위 | 이유 |
|-----|---------|------|
| REQ-REL-001 | P0 | 모든 Push 기능의 기반 |
| REQ-REL-002 | P0 | iOS Push 필수 |
| REQ-REL-003 | P0 | App Store 업로드 필수 |
| REQ-REL-004 | P0 | Strict gate 통과의 핵심 |
| REQ-REL-005 | P1 | CI 자동화 (수동 실행으로 대체 가능) |

## 제약사항

- 본 SPEC의 대부분은 외부 계정 설정 및 수동 기기 테스트이므로, 코드 기반 SPEC과 달리 **사용자 직접 실행**이 필요한 단계가 많음
- 코드 변경 최소: `verify_release_readiness.py` 개선, README 업데이트, CHANGELOG 생성 정도
- Apple Developer Program 연회비 ($99) 필요
- Firebase 프로젝트는 무료 할당량 내에서 운영 가능
