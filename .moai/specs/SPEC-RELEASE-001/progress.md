# SPEC-RELEASE-001 Progress

## 상태: PARTIAL — 코드 작업 완료, 외부 계정/기기 의존 단계는 사용자 실행 대기

## 완료 증거 (코드 작업)

### 문서
- `CHANGELOG.md` — v1.6.0 섹션 추가 (SPEC-BUGFIX-001/002, TECHDEBT-001, UX-002, RELEASE-001)
- `docs/release-procedure.md` — 4단계 실행 가이드 (Firebase, APNs, App Store Connect, 물리 기기 E2E, self-hosted runner, Release)
- `.moai/specs/SPEC-RELEASE-001/spec.md` — 5개 REQ EARS 포맷
- `.moai/specs/SPEC-RELEASE-001/plan.md` — 4단계 의존성 그래프

### 현재 상태
- Default readiness: 0 errors, 2 warnings ✅
- Strict readiness: 11 errors (전부 외부 secret/물리 기기 — 사용자 실행 필요)

## 남은 단계 (사용자 실행)

| 단계 | REQ | 환경 변수 | 상태 |
|------|-----|-----------|------|
| 1.1 | REL-001 | `FIREBASE_CREDENTIALS_PATH` | 대기 |
| 1.2 | REL-002 | `APNS_AUTH_KEY_PATH`, `APNS_KEY_ID`, `APNS_TEAM_ID` | 대기 |
| 1.3 | REL-003 | `APP_STORE_CONNECT_*` 3개 | 대기 |
| 2.1 | REL-004 | `ANDROID_DEVICE_SERIAL`, `IOS_DEVICE_UDID` | 대기 |
| 2.3 | REL-004 | `FIREBASE_TEST_DEVICE_TOKEN`, `RELEASE_E2E_EVIDENCE_PATH` | 대기 |
| 3.1 | REL-005 | Self-hosted runner | 대기 |
| 4.1 | 전체 | README + Git tag | 대기 |

## phase log
- Plan: completed
- Implementation (코드): completed
- Implementation (외부): 사용자 실행 대기
