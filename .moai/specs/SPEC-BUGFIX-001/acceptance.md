# SPEC-BUGFIX-001: Acceptance Criteria

## Test Scenarios

### AC-1: 백엔드 테스트 전체 통과

**Given** backend 가상환경이 활성화된 상태
**When** `venv/bin/python -m pytest backend/tests/` 실행 시
**Then** 모든 테스트가 통과해야 함 (0 failures)

**Status**: PASS (393 passed, 0 failures)

---

### AC-2: Flutter 테스트 전체 통과

**Given** Flutter 프로젝트가 빌드 가능한 상태
**When** `flutter test client/test/` 실행 시
**Then** 모든 테스트가 통과해야 함 (0 failures)

**Status**: PASS (37 passed, 0 failures)

---

### AC-3: Ruff lint 오류 없음

**Given** backend 코드베이스
**When** `ruff check backend/` 실행 시
**Then** 0개의 오류가 발생해야 함

**Status**: PASS (0 errors)

---

### AC-4: Flutter analyze 오류 없음

**Given** Flutter 프로젝트
**When** `flutter analyze client/` 실행 시
**Then** 0개의 이슈가 발생해야 함

**Status**: PASS (0 issues)

---

### AC-5: 커버리지 유지

**Given** 백엔드 테스트가 모두 통과한 상태
**When** 커버리지를 측정할 때
**Then** 94% 이상의 커버리지를 유지해야 함

**Status**: PASS (97.76% 달성)

---

### AC-6: Summary Schema 기본값 동기화 (REQ-BF-001)

**Given** `SummaryCreateRequest`가 `max_tokens` 없이 생성될 때
**When** 기본값을 확인할 때
**Then** 4096이어야 함

**Status**: PASS

---

### AC-7: Redis 캐시 TTL 동기화 (REQ-BF-002)

**Given** DB에서 Redis 캐시를 복원할 때
**When** TTL 값을 확인할 때
**Then** `settings.cache_ttl_seconds` (604800, 7일)을 사용해야 함

**Status**: PASS

---

## Quality Gates

| Gate | Criteria | Status |
|------|----------|--------|
| Backend Tests | 0 failures | PASS |
| Flutter Tests | 0 failures | PASS |
| Python Lint | ruff check 0 errors | PASS |
| Flutter Analyze | 0 issues | PASS |
| Coverage | 94%+ | PASS (97.76%) |
| TRUST 5 | Tested, Readable, Unified, Secured, Trackable | PASS |

---

*Acceptance Version: 1.0.0*
*Last Updated: 2026-06-03*
