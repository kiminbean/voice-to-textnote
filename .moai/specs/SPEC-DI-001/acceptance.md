---
id: SPEC-DI-001
version: 1.0.0
---

# Acceptance Criteria: SPEC-DI-001

## Area 1: Lifespan-Managed Resources

### AC-DI-001: DB engine created in lifespan

**Given** the FastAPI application is starting up
**When** the lifespan context manager enters the startup phase
**Then** an `AsyncEngine` instance shall be created and stored in `app.state.db_engine`
**And** an `async_sessionmaker` shall be created from that engine and stored in `app.state.session_factory`

### AC-DI-002: DB session injected via Depends

**Given** a route handler uses `Depends(get_db_session)`
**When** a request is received by that handler
**Then** an `AsyncSession` shall be yielded from `request.app.state.session_factory`
**And** the session shall be automatically closed after the request completes

### AC-DI-003: DB engine disposed on shutdown

**Given** the FastAPI application is running
**When** the lifespan context manager enters the shutdown phase
**Then** `app.state.db_engine.dispose()` shall be called
**And** all pooled connections shall be released

### AC-DI-004: No module-level DB engine variable

**Given** the refactored `backend/app/dependencies.py`
**When** the module is inspected
**Then** there shall be no `_db_engine` or `_session_factory` module-level mutable variables
**And** all engine creation shall occur within the lifespan context manager

### AC-DI-005: Redis client created in lifespan

**Given** the FastAPI application is starting up
**When** the lifespan context manager enters the startup phase
**Then** an `aioredis.Redis` client shall be created and stored in `app.state.redis`

### AC-DI-006: Redis client closed on shutdown

**Given** the FastAPI application is running
**When** the lifespan context manager enters the shutdown phase
**Then** `app.state.redis.aclose()` shall be called
**And** the Redis connection shall be released

### AC-DI-007: App started_at stored in app.state

**Given** the FastAPI application is starting up
**When** the lifespan context manager enters the startup phase
**Then** `app.state.started_at` shall be set to the current UTC datetime
**And** `get_app_started_at()` shall return that value when called with a valid request

### AC-DI-008: get_app_started_at returns None outside lifespan

**Given** no FastAPI application context is available
**When** `get_app_started_at()` is called without a request parameter
**Then** it shall return `None`

---

## Area 2: ML Engine Factory Pattern

### AC-DI-009: WhisperEngine created in lifespan

**Given** the FastAPI application is starting up
**When** the lifespan context manager enters the startup phase
**Then** a `WhisperEngine` instance shall be created and stored in `app.state.whisper_engine`
**And** the engine's `load()` method may be called for warm-up if configured

### AC-DI-010: WhisperEngine injected via Depends

**Given** a route handler uses `Depends(get_whisper_engine)`
**When** a request is received by that handler
**Then** the `WhisperEngine` instance from `request.app.state.whisper_engine` shall be returned
**And** the engine shall be thread-safe for concurrent transcribe calls

### AC-DI-011: WhisperEngine lazy load preserved

**Given** a `WhisperEngine` instance stored in `app.state.whisper_engine`
**When** `transcribe()` is called without prior `load()`
**Then** the engine shall automatically call `load()` (lazy load behavior preserved)

### AC-DI-012: DiarizationEngine created in lifespan

**Given** the FastAPI application is starting up
**When** the lifespan context manager enters the startup phase
**Then** a `DiarizationEngine` instance shall be created and stored in `app.state.diarization_engine`

### AC-DI-013: DiarizationEngine injected via Depends

**Given** a route handler uses `Depends(get_diarization_engine)`
**When** a request is received by that handler
**Then** the `DiarizationEngine` instance from `request.app.state.diarization_engine` shall be returned

### AC-DI-014: No class-level singleton for engines

**Given** the refactored `backend/ml/stt_engine.py` and `backend/ml/diarization_engine.py`
**When** the classes are inspected
**Then** there shall be no `_instance` class variable
**And** there shall be no `get_instance()` class method
**And** `WhisperEngine()` / `DiarizationEngine()` constructors shall be usable without singleton enforcement

---

## Area 3: Client Pool Pattern

### AC-DI-015: OpenAI client created in lifespan

**Given** the FastAPI application is starting up
**When** the lifespan context manager enters the startup phase
**Then** an `AsyncOpenAI` client shall be created and stored in `app.state.openai_client`
**And** if `OPENAI_API_KEY` is not set, a dummy-key client shall be created with a warning log

### AC-DI-016: OpenAI client injected via Depends

**Given** a service uses `Depends(get_openai_client)`
**When** a request requires OpenAI functionality
**Then** the `AsyncOpenAI` client from `request.app.state.openai_client` shall be returned

### AC-DI-017: No module-level OpenAI client global

**Given** the refactored `backend/ml/openai_client.py`
**When** the module is inspected
**Then** there shall be no `_openai_client` module-level variable
**And** `get_cached_openai_client()` shall either be removed or delegate to the DI provider

### AC-DI-018: HTTP client created in lifespan

**Given** the FastAPI application is starting up
**When** the lifespan context manager enters the startup phase
**Then** an `httpx.AsyncClient(timeout=30.0)` shall be created and stored in `app.state.http_client`

### AC-DI-019: HTTP client closed on shutdown

**Given** the FastAPI application is running
**When** the lifespan context manager enters the shutdown phase
**Then** `app.state.http_client.aclose()` shall be called

### AC-DI-020: No module-level HTTP client global

**Given** the refactored `backend/ml/tagging_engine.py`
**When** the module is inspected
**Then** there shall be no `_http_client` module-level variable
**And** `close_http_client()` shall be removed (cleanup handled by lifespan)

---

## Area 4: Sync Engine (Celery)

### AC-DI-021: Sync engine explicit initialization

**Given** a Celery worker is starting
**When** the `worker_init` signal fires
**Then** `init_sync_engine()` shall be called
**And** the sync `Engine` and `sessionmaker` shall be stored for worker use

### AC-DI-022: No module-level sync engine globals

**Given** the refactored `backend/db/sync_engine.py`
**When** the module is inspected
**Then** there shall be no `_sync_engine` or `_SessionLocal` module-level mutable variables

### AC-DI-023: get_sync_session works after init

**Given** `init_sync_engine()` has been called
**When** a Celery task calls `get_sync_session()`
**Then** a valid synchronous `Session` shall be yielded
**And** the session shall be automatically closed after use

### AC-DI-024: get_sync_session fails gracefully before init

**Given** `init_sync_engine()` has NOT been called
**When** `get_sync_session()` is invoked
**Then** a clear error shall be raised indicating the engine must be initialized first
**And** the error shall NOT be a `NameError` or `AttributeError` (use a descriptive exception)

---

## Area 5: Test Infrastructure

### AC-DI-025: dependency_overrides replaces all singleton resets

**Given** the test suite after migration
**When** `grep -rn "_instance = None" backend/tests/` is executed
**Then** the result shall be empty (zero matches)

### AC-DI-026: dependency_overrides replaces all global patches

**Given** the test suite after migration
**When** `grep -rn "patch.*_db_engine\|patch.*_sync_engine\|patch.*_openai_client\|patch.*_http_client" backend/tests/` is executed
**Then** the result shall be empty (zero matches)

### AC-DI-027: Centralized test fixtures in conftest.py

**Given** the refactored `backend/tests/conftest.py`
**When** the file is inspected
**Then** fixtures shall exist for `override_db_session`, `override_redis_client`,
`override_whisper_engine`, `override_diarization_engine`, `override_openai_client`,
and `override_http_client`
**And** each fixture shall use `app.dependency_overrides` to inject mock dependencies

### AC-DI-028: Tests pass with pytest-xdist

**Given** the refactored test suite
**When** `pytest backend/tests/ -n auto --tb=short` is executed
**Then** all tests shall pass
**And** no test shall fail due to shared global state contamination

### AC-DI-029: Existing API contracts unchanged

**Given** the existing API test suite
**When** all tests are executed after the migration
**Then** every existing test shall pass without modification to test assertions
**And** API endpoint URLs, HTTP status codes, and response formats shall remain identical

---

## Edge Cases

### AC-DI-030: Lifespan handles partial initialization failure

**Given** the lifespan startup is in progress
**When** one resource fails to initialize (e.g., Redis connection refused)
**Then** previously initialized resources shall be cleaned up
**And** a structured error log shall be emitted
**And** the application shall not start in a degraded state without explicit configuration

### AC-DI-031: Concurrent request access to app.state

**Given** the FastAPI application is handling multiple concurrent requests
**When** two requests simultaneously call `Depends(get_db_session)`
**Then** each request shall receive an independent `AsyncSession`
**And** no session shall leak between requests

### AC-DI-032: Engine load during high concurrency

**Given** `WhisperEngine.load()` has not been called yet
**When** multiple requests trigger lazy load simultaneously
**Then** the engine shall load exactly once (thread-safe double-checked locking)
**And** all subsequent requests shall use the loaded model

---

## Regression Gates

### AC-DI-033: Full test suite passes

**Given** all phases are complete
**When** `pytest backend/tests/ --tb=short -q` is executed
**Then** all existing tests shall pass
**And** test count shall not decrease
**And** no new test skips shall be introduced

### AC-DI-034: No performance regression

**Given** the refactored DI system
**When** a standard request flow is benchmarked
**Then** request latency shall not increase by more than 5% compared to pre-migration baseline
**And** the DI overhead (attribute lookup on `app.state`) shall be negligible (< 1ms per request)

### AC-DI-035: Celery tasks continue to work

**Given** a running Celery worker with `init_sync_engine()` called
**When** a task that requires DB access is executed
**Then** the task shall complete successfully with the same behavior as before migration

---

## Definition of Done

- [ ] All 35 acceptance criteria pass
- [ ] Zero module-level mutable globals for managed resources (verified by grep)
- [ ] Zero `module._instance = None` patterns in test files (verified by grep)
- [ ] All existing tests pass without assertion changes
- [ ] `pytest-xdist` parallel execution passes
- [ ] `ruff check backend/` passes with no new warnings
- [ ] TRUST 5 quality gates passed (Tested, Readable, Unified, Secured, Trackable)
