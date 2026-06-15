---
id: SPEC-RELEASE-001
phase: plan
version: "1.0.0"
created: "2026-06-15"
updated: "2026-06-15"
---

# SPEC-RELEASE-001 Implementation Plan

## 개요

SPEC-RELEASE-001은 Release Candidate를 Production Ready로 전환하기 위한 5단계 절차를 정의한다. 대부분 외부 계정 설정 및 수동 기기 테스트이므로, 코드 기반 SPEC과 달리 **사용자 실행**이 필요한 단계가 많다.

## 개발 방법론

- **문서/절차 중심**: 코드 변경보다 설정/실행/검증 절차 위주
- 각 단계는 사용자가 수행하고, 코드/스크립트로 검증

## 태스크 분해

### Phase 1: 외부 계정 설정 (사용자 실행, 병렬 가능)

#### Task 1: REQ-REL-001 — Firebase 서비스 계정 연동

**사용자 수행**:
1. Firebase Console에서 프로젝트 생성/확인
2. 서비스 계정 JSON 다운로드
3. `.env.local`에 `FIREBASE_CREDENTIALS_PATH` 설정
4. 백엔드 재시작

**코드 작업**:
- 없음 (이미 `push_service.py`가 `settings.firebase_credentials_path` 확인)

**검증**:
```bash
FIREBASE_CREDENTIALS_PATH=/path/to/service-account.json \
python3 client/scripts/verify_release_readiness.py --strict 2>&1 | grep Firebase
```

#### Task 2: REQ-REL-002 — APNs 인증 키 설정

**사용자 수행**:
1. Apple Developer Console에서 APNs 키 생성
2. Firebase Console에 업로드
3. 환경 변수 설정

**검증**:
```bash
APNS_AUTH_KEY_PATH=... APNS_KEY_ID=... APNS_TEAM_ID=... \
python3 client/scripts/verify_release_readiness.py --strict 2>&1 | grep APNs
```

#### Task 3: REQ-REL-003 — App Store Connect API 키 설정

**사용자 수행**:
1. App Store Connect에서 API 키 생성
2. 환경 변수 설정

**검증**:
```bash
APP_STORE_CONNECT_API_KEY_PATH=... APP_STORE_CONNECT_KEY_ID=... APP_STORE_CONNECT_ISSUER_ID=... \
python3 client/scripts/verify_release_readiness.py --strict 2>&1 | grep "App Store"
```

### Phase 2: 물리 기기 + E2E 증거 (사용자 실행)

#### Task 4: REQ-REL-004 — 물리 기기 E2E 테스트

**사용자 수행**:
1. Android/iOS 기기 연결
2. 앱 Release 빌드 설치
3. evidence scaffold 생성:
   ```bash
   ANDROID_DEVICE_SERIAL=... IOS_DEVICE_UDID=... \
   python3 client/scripts/create_release_e2e_evidence.py --output docs/release-e2e-evidence.json
   ```
4. 6개 시나리오 수동 실행 및 JSON 작성
5. `FIREBASE_TEST_DEVICE_TOKEN` 설정

**검증**:
```bash
RELEASE_E2E_EVIDENCE_PATH=docs/release-e2e-evidence.json \
ANDROID_DEVICE_SERIAL=... IOS_DEVICE_UDID=... \
FIREBASE_TEST_DEVICE_TOKEN=... \
python3 client/scripts/verify_release_readiness.py --strict
```

### Phase 3: CI 인프라 (사용자 실행)

#### Task 5: REQ-REL-005 — Self-hosted Runner + GitHub Environment

**사용자 수행**:
1. M4 Mac Mini에 GitHub Actions runner 설치
2. `mobile-release` Environment secrets 설정:
   ```bash
   python3 client/scripts/configure_github_mobile_release_env.py --repo kiminbean/voice-to-textnote
   ```
3. GitHub Actions `workflow_dispatch`로 strict gate 실행

**검증**:
```bash
python3 client/scripts/verify_github_mobile_release_env.py --repo kiminbean/voice-to-textnote
```

### Phase 4: Release (코드 작업 + 사용자 실행)

#### Task 6: README 업데이트 + Git tag

**코드 작업**:
- README.md `**상태**:` → `Production Ready vX.X.0`
- CHANGELOG.md 생성
- `git tag v1.X.0`

**사용자 수행**:
- GitHub Release 게시

**검증**:
- `git tag` 확인
- GitHub Release URL 확인

## 병렬 실행 가능성

| Task Group | 병렬 가능 | 이유 |
|-----------|----------|------|
| Task 1 + 2 + 3 | ✓ | 독립 외부 계정 |
| Task 4 | 순차 | Phase 1 완료 후 |
| Task 5 | 순차 | Phase 1+2 완료 후 |
| Task 6 | 순차 | Phase 3 통과 후 |

## 파일 변경 예상 목록

### 수정 (최소)
- `README.md` — 상태 라인 `Production Ready`로 변경
- `CHANGELOG.md` (신규 또는 업데이트)

### 신규
- `docs/release-e2e-evidence.json` (scaffold에서 채운 버전)
- `.moai/specs/SPEC-RELEASE-001/{progress,acceptance}.md`

## 완료 기준

- [ ] AC-001: `verify_release_readiness.py --strict` 0 errors
- [ ] AC-002: GitHub Actions strict gate PASS
- [ ] AC-003: README `Production Ready`로 업데이트
- [ ] AC-004: Git tag 생성 + GitHub Release 게시
- [ ] AC-005: 전체 게이트 유지 (ruff/mypy/pytest/flutter)
