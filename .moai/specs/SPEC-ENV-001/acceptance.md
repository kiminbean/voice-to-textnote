# SPEC-ENV-001: Acceptance Criteria

## Test Scenarios

### AC-1: AppConfig 테스트 통과

**Given** Flutter 프로젝트가 빌드 가능한 상태
**When** `flutter test client/test/config/app_config_test.dart` 실행 시
**Then** 모든 테스트가 통과해야 함

**Status**: PASS

---

### AC-2: Flutter analyze 경고 없음

**Given** Flutter 프로젝트
**When** `flutter analyze client/` 실행 시
**Then** 경고 및 에러가 없어야 함

**Status**: PASS

---

### AC-3: 기존 테스트 전체 통과

**Given** 전체 Flutter 테스트 스위트
**When** `flutter test client/test/` 실행 시
**Then** 기존 테스트가 모두 통과해야 함 (회귀 없음)

**Status**: PASS

---

### AC-4: 실행 스크립트 3개 생성

**Given** 프로젝트 루트 디렉토리
**When** `client/scripts/` 디렉토리를 확인할 때
**Then** 다음 3개 스크립트가 존재해야 함:
- `run_dev.sh` (ENV=dev, localhost URL)
- `run_staging.sh` (ENV=staging, 기존 Tailscale IP)
- `run_production.sh` (ENV=production, 프로덕션 도메인)

**Status**: PASS

---

### AC-5: 컴파일 타임 환경 변수 동작 (REQ-ENV-001)

**Given** `--dart-define=API_BASE_URL=http://custom:9000/api/v1`로 빌드할 때
**When** `AppConfig.apiBaseUrl`을 조회할 때
**Then** `http://custom:9000/api/v1`을 반환해야 함

**Status**: PASS

---

### AC-6: 기본값 동작 유지 (REQ-ENV-005)

**Given** `--dart-define` 없이 빌드할 때
**When** `AppConfig.apiBaseUrl`을 조회할 때
**Then** 기존 하드코딩값 `http://100.110.255.105:8000/api/v1`을 반환해야 함

**Status**: PASS

---

### AC-7: Environment enum 동작 (REQ-ENV-002)

**Given** `--dart-define=ENV=dev`로 빌드할 때
**When** `AppConfig.environment`을 조회할 때
**Then** `Environment.dev`를 반환해야 함

**Status**: PASS

---

## Edge Cases

| Case | Expected Behavior | Status |
|------|-------------------|--------|
| 환경 변수 없이 빌드 | staging 기본값 사용 | PASS |
| 알 수 없는 ENV 값 | staging으로 fallback | PASS |
| API_BASE_URL만 지정 | ENV 무관, 지정된 URL 사용 | PASS |
| production에서 isDebugMode | false 반환 | PASS |

## Quality Gates

| Gate | Criteria | Status |
|------|----------|--------|
| Unit Tests | app_config_test.dart 통과 | PASS |
| Flutter Analyze | 0 issues | PASS |
| Regression | 기존 테스트 모두 통과 | PASS |
| Scripts | 3개 환경 스크립트 존재 | PASS |
| TRUST 5 | Tested, Readable, Unified, Secured, Trackable | PASS |

---

*Acceptance Version: 1.0.0*
*Last Updated: 2026-06-03*
