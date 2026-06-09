---
id: SPEC-DI-001
version: 1.0.0
---

# Implementation Plan: SPEC-DI-001

## Migration Strategy

Incremental phase-based migration where each phase is independently deployable.
Each phase ends with all existing tests passing (zero regression).

### Phase Ordering Rationale

1. **Phase 1 (DB + Redis)** first because they are the highest-impact singletons
   (consumed by 15+ services). All downstream phases depend on DB session injection.
2. **Phase 2 (ML Engines)** after DB because engines use DB for metadata and their
   consumers (API endpoints) already use `get_db_session`.
3. **Phase 3 (HTTP Clients)** after engines because tagging/OpenAI services depend
   on the established DI pattern from Phases 1-2.
4. **Phase 4 (Sync Engine)** is isolated to Celery workers and can proceed in parallel
   with Phase 3 if needed.
5. **Phase 5 (Test Cleanup)** must be last because it removes the old global-state
   patterns that earlier phases maintain as backward-compatible shims.

---

## Phase 1: DB Engine + Redis + App State (Priority High)

### Primary Goal
Move `_db_engine`, `_session_factory`, `get_redis_client()`, and `_app_started_at`
from module-level globals to FastAPI `app.state` via lifespan context manager.

### Milestone 1.1: Lifespan Context Manager

**Files to modify:**
- `backend/app/main.py` — Add `lifespan` async context manager, attach to `FastAPI(lifespan=...)`
- `backend/app/dependencies.py` — Remove `_db_engine` and `_session_factory` module-level variables; update `get_db_session()` to use `request.app.state`
- `backend/app/lifecycle.py` — Move `_app_started_at` to `app.state.started_at`; refactor `validate_startup()` and `cleanup_shutdown()` to use `app.state`

**Approach:**
1. Create `lifespan()` in `main.py` using `@asynccontextmanager`
2. Inside lifespan startup: create `AsyncEngine`, `async_sessionmaker`, `aioredis.Redis`, set `started_at`
3. Inside lifespan shutdown: call `engine.dispose()`, `redis.aclose()`, clear `started_at`
4. Update `get_db_session()` to accept `Request` and read from `request.app.state.session_factory`
5. Update `get_redis_client()` similarly
6. Update `get_app_started_at()` to accept optional `Request` parameter

### Milestone 1.2: Lifecycle Module Refactor

**Files to modify:**
- `backend/app/lifecycle.py` — Remove `_app_started_at` global; `validate_startup()` receives `app` parameter
- `backend/app/dependencies.py` — `close_redis_client()` reads from `app.state` instead of `lru_cache`

**Approach:**
1. `validate_startup(app)` reads `app.state.redis`, `app.state.db_engine` instead of importing dependencies
2. `cleanup_shutdown(app)` disposes resources from `app.state`
3. `_app_started_at` replaced by `app.state.started_at`

### Milestone 1.3: Backward-Compatibility Shim

**Files to modify:**
- `backend/app/dependencies.py` — Keep `get_db_session()` and `get_redis_client()` signatures unchanged for existing `Depends()` usage

**Approach:**
1. `get_db_session(request: Request)` — `Request` added as parameter, consumed via `Depends()`
2. Existing route handlers continue using `Depends(get_db_session)` without changes
3. `lru_cache` removed from `get_redis_client`; replaced with `request.app.state.redis`

### Validation
- All existing tests pass
- `pytest backend/tests/ -x --tb=short`
- Verify no module-level `_db_engine` or `_session_factory` references remain in `dependencies.py`

---

## Phase 2: ML Engine Factory Pattern (Priority High)

### Primary Goal
Move `WhisperEngine._instance` and `DiarizationEngine._instance` from class-level
singletons to `app.state` managed instances, while preserving thread-safe lazy loading.

### Milestone 2.1: WhisperEngine DI

**Files to modify:**
- `backend/ml/stt_engine.py` — Remove `_instance` class variable; add `create_engine()` factory function; keep `load()` and thread safety
- `backend/app/dependencies.py` — Update `get_whisper_engine()` to use `request.app.state.whisper_engine`

**Approach:**
1. Add `WhisperEngine.create()` class method that returns a new instance (no singleton)
2. In lifespan startup: create `WhisperEngine` instance, store in `app.state.whisper_engine`
3. Optional warm-up: call `engine.load()` in lifespan if configured
4. `get_whisper_engine(request)` reads from `app.state.whisper_engine`
5. Thread-safe `load()` with double-checked locking preserved inside the instance
6. Remove `_instance` and `_lock` class variables from `WhisperEngine`

### Milestone 2.2: DiarizationEngine DI

**Files to modify:**
- `backend/ml/diarization_engine.py` — Same pattern as WhisperEngine
- `backend/app/dependencies.py` — Update `get_diarization_engine()` to use `request.app.state.diarization_engine`

**Approach:**
1. Identical pattern to Milestone 2.1
2. `DiarizationEngine.create()` factory, stored in `app.state.diarization_engine`

### Milestone 2.3: Route Handler Updates

**Files to modify:**
- Any route handler that imports `WhisperEngine.get_instance()` or `DiarizationEngine.get_instance()` directly
- Update to use `Depends(get_whisper_engine)` or `Depends(get_diarization_engine)`

**Approach:**
1. Grep for `get_instance()` calls across all route files
2. Replace direct calls with `Depends()` injection
3. Keep `get_instance()` as deprecated shim during migration (log warning)

### Validation
- All existing tests pass
- `WhisperEngine._instance` and `DiarizationEngine._instance` no longer accessed outside engine classes
- `pytest backend/tests/ -x --tb=short`

---

## Phase 3: Client Pool Pattern (Priority Medium)

### Primary Goal
Move `_openai_client` and `_http_client` from module-level globals to
`app.state` managed client pool.

### Milestone 3.1: OpenAI Client DI

**Files to modify:**
- `backend/ml/openai_client.py` — Remove `_openai_client` global; `get_cached_openai_client()` reads from `request.app.state`
- `backend/app/dependencies.py` — Add `get_openai_client()` FastAPI dependency
- `backend/app/main.py` — Create `AsyncOpenAI` in lifespan, store in `app.state.openai_client`

**Approach:**
1. In lifespan: create `AsyncOpenAI` with settings, store in `app.state.openai_client`
2. `get_openai_client(request: Request)` reads from `app.state.openai_client`
3. Services that import `get_cached_openai_client()` switch to `Depends(get_openai_client)`
4. Preserve dummy-key fallback behavior when `OPENAI_API_KEY` is unset

### Milestone 3.2: HTTP Client DI

**Files to modify:**
- `backend/ml/tagging_engine.py` — Remove `_http_client` global; functions receive client via DI
- `backend/app/dependencies.py` — Add `get_http_client()` FastAPI dependency
- `backend/app/main.py` — Create `httpx.AsyncClient` in lifespan, store in `app.state.http_client`

**Approach:**
1. In lifespan: create `httpx.AsyncClient(timeout=30.0)`, store in `app.state.http_client`
2. In lifespan shutdown: call `http_client.aclose()`
3. `get_http_client(request: Request)` reads from `app.state.http_client`
4. `close_http_client()` removed — lifespan handles cleanup

### Validation
- All existing tests pass
- No `_openai_client` or `_http_client` module-level globals remain
- `pytest backend/tests/ -x --tb=short`

---

## Phase 4: Sync Engine Explicit Init (Priority Medium)

### Primary Goal
Remove `_sync_engine` and `_SessionLocal` module-level globals from
`db/sync_engine.py`, replacing with explicit initialization function.

### Milestone 4.1: Sync Engine Factory

**Files to modify:**
- `backend/db/sync_engine.py` — Remove globals; add `init_sync_engine()` returning `(Engine, sessionmaker)`; add `get_sync_session()` that uses stored state
- `backend/workers/` — Call `init_sync_engine()` on worker startup (Celery `worker_init` signal)

**Approach:**
1. Create `SyncEngineState` dataclass holding `engine` and `session_factory`
2. `init_sync_engine() -> SyncEngineState` creates and returns state
3. Celery `worker_init` signal calls `init_sync_engine()` and stores result
4. `get_sync_session()` reads from stored state
5. Remove `_sync_engine` and `_SessionLocal` module-level globals

### Validation
- Celery worker starts and processes tasks
- All sync-engine-dependent tests pass
- `pytest backend/tests/ -x --tb=short`

---

## Phase 5: Test Infrastructure Cleanup (Priority High)

### Primary Goal
Remove all `module._instance = None`, `patch("module._global_var")` patterns
from tests, replacing with `app.dependency_overrides`.

### Milestone 5.1: Test Fixture Consolidation

**Files to modify:**
- `backend/tests/conftest.py` — Add centralized DI override fixtures
- 23+ test files — Remove manual singleton reset patterns

**Approach:**
1. Create `override_db_session`, `override_redis_client`, `override_whisper_engine`,
   `override_diarization_engine`, `override_openai_client`, `override_http_client` fixtures
2. Each fixture uses `app.dependency_overrides[dependency_func] = mock_func`
3. Grep all test files for `_instance = None`, `_sync_engine`, `_db_engine` patch patterns
4. Replace with `conftest.py` fixture usage
5. Run full test suite to verify zero regressions

### Milestone 5.2: Global State Audit

**Files to modify:**
- None (verification only)

**Approach:**
1. Run `grep -rn "^[a-z_]* = " backend/ --include="*.py" | grep -v "__" | grep -v "test_"`
2. Verify no new module-level mutable globals introduced
3. Confirm all state is managed via `app.state` or explicit initialization

### Validation
- Zero `module._instance = None` patterns in test files
- Zero `patch("backend.app.dependencies._db_engine")` patterns
- All tests pass: `pytest backend/tests/ --tb=short`
- Test suite supports `pytest-xdist` parallel execution: `pytest -n auto`

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Circular import from lifespan importing dependencies | Medium | High | Keep lifespan in `main.py` with local imports; dependency functions remain in `dependencies.py` |
| Celery worker init order | Low | High | Use Celery `worker_init` signal with explicit `init_sync_engine()` |
| Test regression from fixture changes | Medium | Medium | Phase 5 is last; phases 1-4 maintain backward-compatible shims |
| Request-scoped DI unavailable in background tasks | Low | Medium | Background tasks receive dependencies as arguments, not via `Request` |

## Expert Consultation Recommended

- **expert-backend**: API design review for lifespan-managed resource initialization order
- **expert-testing**: Test fixture architecture for parallel test isolation
