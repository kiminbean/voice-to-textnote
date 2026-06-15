# SPEC-BUGFIX-002 Progress

## 상태: COMPLETED

## 완료 증거

### 코드
- `backend/services/push_service.py` — FCM 전송 경로 asyncio.to_thread wrap (send_push, send_multicast)
- `backend/services/collab_service.py` — `_ADD_PRESENCE_LUA`, `_APPLY_EDIT_LUA` Lua script + `_is_real_redis` 폴백
- `backend/services/version_service.py` — IntegrityError catch-and-retry (3회)
- `backend/db/version_models.py` — UniqueConstraint("task_id", "version_number") 추가
- `alembic/versions/004_unique_minutes_versions_task_version.py` — batch_alter_table migration
- `backend/workers/tasks/*.py` (5개) — `category="db_fallback"` structured logging 필드 (12곳)
- `backend/app/api/v1/transcription/transcription.py` — `category="redis_fallback"` 필드

### 테스트 (신규 21개)
- `backend/tests/unit/test_async_blocking_regression.py` — 8개 (AST 기반 asyncio.to_thread 회귀 검사)
- `backend/tests/unit/test_collab_concurrency.py` — 5개 (동시성 + LWW 검증)
- `backend/tests/unit/test_tempfile_leak_gate.py` — 2개 (tempfile cleanup 정적 분석 게이트)
- `backend/tests/unit/test_log_category_gate.py` — 6개 (로그 category 필드 검증)

### 게이트
- ruff check: All checks passed! (0 errors)
- mypy: Success: no issues found in 407 source files
- pytest: **3374 passed**, 16 skipped (이전 3353 + 21 신규)
- alembic upgrade head + downgrade -1: 정상 동작

## phase log
- Plan: completed (spec.md + plan.md 작성)
- Implementation: completed (Task 1-6 전부)
- Verification: completed (전체 게이트 green)

## 비고
- collab_service Lua script는 프로덕션 Redis에서만 활성화 (test double은 _is_real_redis 폴백)
- fakeredis가 Lua eval을 지원하지 않아 AsyncMock 기반 테스트 유지, 프로덕션에서만 atomic 보장
- migration 004는 minutes_versions 테이블이 없는 DB에서 안전하게 스킵 (initial_schema에 테이블 없음)
