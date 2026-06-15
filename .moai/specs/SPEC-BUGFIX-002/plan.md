---
id: SPEC-BUGFIX-002
phase: plan
version: "1.0.0"
created: "2026-06-15"
updated: "2026-06-15"
---

# SPEC-BUGFIX-002 Implementation Plan

## 개요

SPEC-BUGFIX-002는 loop 워크플로우에서 fix한 18건 버그의 후속 작업으로, 6개 요구사항(REQ-BF2-001~006)을 구현한다. 본 plan은 각 REQ에 대한 구현 전략, 파일 변경 목록, 태스크 분해를 정의한다.

## 개발 방법론

- **DDD (ANALYZE-PRESERVE-IMPROVE)**: 기존 코드가 풍부한 brownfield 프로젝트이므로 DDD 적용
- 각 REQ별로 ANALYZE → PRESERVE (characterization test) → IMPROVE 순서로 진행

## 태스크 분해

### Phase 1: P0 (즉시 필요)

#### Task 1: REQ-BF2-003 — push_service FCM to_thread wrap
- **ANALYZE**: `backend/services/push_service.py` 라인 ~108-130 (MOCK 모드) 및 ~152-175 (실제 전송 경로) 읽기
- **PRESERVE**: 현재 MOCK 모드 테스트가 PASS하는지 확인
- **IMPROVE**:
  - `messaging.send(message)` → `await asyncio.to_thread(messaging.send, message)`
  - `import asyncio` 추가
  - `# FCM-TIMEBOMB` 주석 제거 (있는 경우)
- **검증**: `pytest backend/tests/unit -k push` 통과

#### Task 2: REQ-BF2-005 — version_service Alembic migration
- **ANALYZE**: `backend/alembic/versions/` 기존 migration 패턴 확인, `backend/db/version_models.py` UniqueConstraint 확인
- **PRESERVE**: 기존 `version_service` 테스트가 PASS하는지 확인
- **IMPROVE**:
  - `alembic revision --autogenerate -m "add unique constraint on minutes_versions (task_id, version_number)"` 실행
  - 생성된 migration script 검증 (SQLite + PostgreSQL 호환성)
  - 기존 데이터 중복 확인 쿼리 작성 (사전 검증)
- **검증**: `alembic upgrade head` 성공 + `pytest backend/tests -k version` 통과

### Phase 2: P1 (근본 해결)

#### Task 3: REQ-BF2-002 — collab_service Lua script
- **ANALYZE**: `backend/services/collab_service.py` `add_presence`, `apply_edit` 현재 구조 + 테스트 환경의 AsyncMock 사용 패턴
- **PRESERVE**: 기존 `test_collab_service.py` 33개 테스트 PASS 확인
- **IMPROVE**:
  - `fakeredis >= 2.20` (Lua 지원) 의존성 추가 (`pyproject.toml [dev]`)
  - `_ADD_PRESENCE_LUA` 상수 정의 (atomic check-and-set)
  - `_APPLY_EDIT_LUA` 상수 정의 (atomic LWW compare-and-set)
  - `add_presence`를 Lua script 기반으로 재작성
  - `apply_edit`을 Lua script 기반으로 재작성
  - 테스트 fixture를 AsyncMock → fakeredis로 교체
- **검증**:
  - 기존 33개 테스트 전부 PASS (fakeredis 호환)
  - 신규 동시성 테스트: 10개 동시 add_presence → MAX_PARTICIPANTS=5 위반 없음

#### Task 4: REQ-BF2-001 — asyncio.to_thread 회귀 테스트
- **ANALYZE**: 7곳의 `asyncio.to_thread` 호출 패턴 수집 (transcription.py, batch.py, audio_analysis.py, export.py ×2, templates.py)
- **PRESERVE**: 현재 게이트 green 상태 기록
- **IMPROVE**:
  - `backend/tests/unit/test_async_blocking_regression.py` (신규) 작성
  - 각 엔드포인트의 소스를 읽어 `asyncio.to_thread` 또는 `run_in_executor` 호출 포함 여부 확인하는 정적 테스트
  - 또는 AST 기반 검사 (`ast.walk`로 Call 노드 순회)
- **검증**: 7개 회귀 테스트 PASS + 의도적으로 to_thread 제거 시 FAIL 확인

### Phase 3: P2 (재발 방지)

#### Task 5: REQ-BF2-004 — temp file leak AST-grep gate
- **ANALYZE**: 기존 7곳 `mkdtemp`/`mkstemp` 사용 패턴 수집, cleanup 페어 확인
- **PRESERVE**: 현재 코드가 AST-grep 규칙을 통과하는지 사전 검증
- **IMPROVE**:
  - `.sgconfig.yml` 또는 `pyproject.toml`에 custom ruff/ast-grep 규칙 추가
  - `tempfile.mkdtemp` 호출 시 같은 함수 범위 내 `shutil.rmtree` 존재 확인
  - CI workflow에 AST-grep 실행 step 추가
- **검증**: 기존 코드 PASS + 의도적 leak 코드 FAIL

#### Task 6: REQ-BF2-006 — 운영 로그 검증
- **ANALYZE**: 14곳 `logger.warning("DB 결과 저장 실패...")` 패턴 수집
- **PRESERVE**: 현재 로그 출력 확인
- **IMPROVE**:
  - `logger.warning(..., extra={"category": "db_fallback"})` 구조화된 필드 추가
  - 단위 테스트에서 `caplog`로 로그 카테고리 검증
  - Prometheus 메트릭 정의 문서화 (`.moai/docs/monitoring.md` 또는 기존 문서)
- **검증**: 로그 카테고리 필드 포함 테스트 PASS

## 병렬 실행 가능성

| Task Group | 병렬 가능 | 이유 |
|-----------|----------|------|
| Task 1 + Task 2 | ✓ | 독립 파일 (push_service vs alembic) |
| Task 3 + Task 4 | ✓ | collab_service vs 신규 테스트 파일 |
| Task 5 + Task 6 | ✓ | CI config vs 로깅 |
| Task 3 → Task 4 | 순차 | Task 4가 collab 변경 후 회귀 테스트 추가 |

## 파일 변경 예상 목록

### 수정
- `backend/services/push_service.py` — FCM to_thread wrap (Task 1)
- `backend/services/collab_service.py` — Lua script 통합 (Task 3)
- `backend/services/version_service.py` — migration 대비 (Task 2)
- `backend/workers/tasks/*.py` — 로그 카테고리 필드 (Task 6, 14곳)
- `pyproject.toml` — fakeredis 의존성 (Task 3)

### 신규
- `backend/alembic/versions/0XX_add_unique_constraint_minutes_versions.py` (Task 2)
- `backend/tests/unit/test_async_blocking_regression.py` (Task 4)
- `backend/tests/unit/test_collab_concurrency.py` (Task 3)
- `.sgconfig.yml` 또는 `pyproject.toml` AST-grep 규칙 (Task 5)

## 리스크

| 리스크 | 확률 | 영향 | 완화책 |
|--------|------|------|--------|
| fakeredis Lua 호환성 문제 | 중간 | Task 3 지연 | Redis test container로 폴백 |
| Alembic autogenerate 불일치 | 낮음 | Task 2 지연 | 수동 migration script 작성 |
| AST-grep false positive | 중간 | Task 5 채택 어려움 | 기존 패턴 기반 규칙 세밀화 |
| collab_service 재작성 시 기존 테스트 깨짐 | 중간 | Task 3 지연 | PRESERVE 단계에서 characterization test 확보

## 완료 기준

- [ ] 모든 AC-001~006 통과
- [ ] ruff check: 0 errors
- [ ] mypy: 0 errors
- [ ] pytest: 기존 3353 + 신규 회귀 테스트 전부 PASS
- [ ] coverage: 97%+ 유지
- [ ] Alembic migration: upgrade/downgrade 정상 동작
