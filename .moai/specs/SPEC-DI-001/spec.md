---
id: SPEC-DI-001
version: 1.0.0
status: completed
created: 2026-06-09
updated: 2026-06-10
author: MoAI
priority: high
title: "Dependency Injection 패턴 전환 — Global State 제거"
tags: [refactoring, architecture, dependency-injection, testing, fastapi]
related_specs:
  - SPEC-REFACTOR-001
  - SPEC-ERR-001
  - SPEC-LIFECYCLE-001
depends_on:
  - SPEC-REFACTOR-001
lifecycle_level: spec-anchored
---

# SPEC-DI-001: Dependency Injection 패턴 전환 — Global State 제거

## 1. Environment (현재 상황)

### 기술 스택
- FastAPI 0.115+ (lifespan context manager 지원)
- SQLAlchemy 2.0 (async engine + async_sessionmaker)
- Celery 5.x (동기 워커 — 별도 sync engine)
- Redis (aioredis 비동기 클라이언트)
- OpenAI AsyncOpenAI (LLM 호출)
- httpx.AsyncClient (태깅 HTTP 클라이언트)

### 현재 아키텍처의 문제점

SPEC-REFACTOR-001(AP-8)에서 식별된 "DB 엔진 모듈레벨 생성" 문제를 포함하여,
9개의 핵심 글로벌 상태 변수가 모듈 import 시점에 생성되거나 런타임에 싱글톤으로 관리되고 있다.

| ID | 파일 | 변수 | 타입 | 소비자 수 |
|----|------|------|------|-----------|
| GS-1 | `app/lifecycle.py` | `_app_started_at` | `datetime \| None` | get_app_started_at(), logging |
| GS-2 | `app/dependencies.py` | `_db_engine` | `AsyncEngine` | 15+ 서비스 |
| GS-3 | `app/dependencies.py` | `_session_factory` | `async_sessionmaker` | 모든 DB 의존 서비스 |
| GS-4 | `ml/stt_engine.py` | `_instance` | `WhisperEngine \| None` | 20+ API 엔드포인트 |
| GS-5 | `ml/diarization_engine.py` | `_instance` | `DiarizationEngine \| None` | 8+ API 엔드포인트 |
| GS-6 | `ml/openai_client.py` | `_openai_client` | `AsyncOpenAI \| None` | OpenAI 의존 서비스 |
| GS-7 | `ml/tagging_engine.py` | `_http_client` | `httpx.AsyncClient \| None` | 태깅 서비스 |
| GS-8 | `db/sync_engine.py` | `_sync_engine` | `Engine \| None` | Celery 워커 |
| GS-9 | `db/sync_engine.py` | `_SessionLocal` | `sessionmaker \| None` | Celery 워커 |

### 파생 문제

1. **테스트 격이 어려움**: 23+ 테스트 파일이 `module._instance = None`, `patch("backend.app.dependencies._db_engine")` 패턴으로 글로벌 상태를 수동 초기화
2. **수명주기 관리 불일치**: 일부 리소스는 `lifecycle.py`에서 정리하고, 일부는 모듈 수준에서 방치됨
3. **종료 순서 의존성**: `cleanup_shutdown()`이 여러 모듈에서 개별적으로 import하여 정리 — 누락 위험
4. **병렬 테스트 불가**: 글로벌 싱글톤을 공유하므로 pytest-xdist 실행 시 상태 오염

### 이미 확립된 DI 패턴 (SPEC-REFACTOR-001 이후)
- 서비스 팩토리 함수: `get_<service_name>()` 패턴 (149개 사용)
- FastAPI `Depends()` 주입 — 라우트 핸들러에서 사용
- `app.dependency_overrides` — 테스트에서 mock 교체
- 약 70%의 서비스가 이미 적절한 DI를 사용 중

---

## 2. Assumptions (가정)

| ID | 가정 | 신뢰도 | 검증 상태 |
|----|------|--------|-----------|
| A-1 | FastAPI `lifespan` context manager로 모든 리소스 생명주기를 관리할 수 있다 | 높음 (95%) | FastAPI 공식 문서 확인 |
| A-2 | `app.dependency_overrides`는 테스트에서 기존처럼 계속 작동한다 | 높음 (99%) | 현재 conftest.py에서 이미 사용 중 |
| A-3 | Celery 워커는 FastAPI lifespan 외부에서 동작하므로 별도 초기화 패턴이 필요하다 | 높음 (100%) | Celery 아키텍처상 확인 |
| A-4 | WhisperEngine/DiarizationEngine의 스레드 안전 싱글톤은 유지하되, 인스턴스 생성은 DI를 통해 제어한다 | 높음 (90%) | 현재 double-checked locking 코드 분석 |
| A-5 | 기존 API 계약(URL, HTTP 상태 코드, 응답 형식)은 변경하지 않는다 | 높음 (100%) | SPEC-REFACTOR-001 A-1과 동일 |
| A-6 | 모든 기존 테스트는 계속 통과해야 한다 (import 경로 변경은 허용) | 높음 (100%) | 회귀 방지 원칙 |

---

## 3. Requirements (요구사항)

### Area 1: Lifespan-Managed Resources (Priority High)

#### REQ-DI-001: DB 엔진 Lifespan 관리

**Event-Driven**: **WHEN** FastAPI 앱이 시작되면, 시스템은 **SHALL** `lifespan` context manager 내에서 `AsyncEngine`과 `async_sessionmaker`를 생성하고 `app.state`에 저장해야 한다.

**State-Driven**: **WHILE** 앱이 실행 중일 때, `get_db_session()` 의존성은 **SHALL** `app.state`에서 세션 팩토리를 조회하여 DB 세션을 주입해야 한다.

**Event-Driven**: **WHEN** FastAPI 앱이 종료되면, 시스템은 **SHALL** lifespan의 cleanup 단계에서 `AsyncEngine.dispose()`를 호출하여 커넥션 풀을 정리해야 한다.

#### REQ-DI-002: Redis 클라이언트 Lifespan 관리

**Event-Driven**: **WHEN** FastAPI 앱이 시작되면, 시스템은 **SHALL** `aioredis.Redis` 클라이언트를 생성하고 `app.state`에 저장해야 한다.

**Event-Driven**: **WHEN** FastAPI 앱이 종료되면, 시스템은 **SHALL** `redis.aclose()`를 호출하여 연결을 정리해야 한다.

#### REQ-DI-003: 앱 시작 시각 Lifespan 관리

**Event-Driven**: **WHEN** FastAPI 앱이 시작되면, 시스템은 **SHALL** `_app_started_at`을 `app.state`에 기록해야 한다.

**Ubiquitous**: `get_app_started_at()` 함수는 **SHALL** 항상 `app.state.started_at`을 반환하거나, lifespan 외부 호출 시 `None`을 반환해야 한다.

### Area 2: ML Engine Factory Pattern (Priority High)

#### REQ-DI-004: WhisperEngine DI 제어

**Event-Driven**: **WHEN** `get_whisper_engine()` 의존성이 호출되면, 시스템은 **SHALL** `WhisperEngine` 인스턴스를 반환하되, 인스턴스 생성 시점은 `lifespan` warm-up 또는 첫 요청(lazy load) 중 하나여야 한다.

**State-Driven**: **IF** 테스트 환경에서 `app.dependency_overrides`가 설정되어 있으면, 시스템은 **SHALL** 오버라이드된 엔진을 주입해야 한다.

#### REQ-DI-005: DiarizationEngine DI 제어

**Event-Driven**: **WHEN** `get_diarization_engine()` 의존성이 호출되면, 시스템은 **SHALL** `DiarizationEngine` 인스턴스를 반환해야 한다. 인스턴스 생명주기는 REQ-DI-004와 동일하다.

### Area 3: Client Pool Pattern (Priority Medium)

#### REQ-DI-006: OpenAI 클라이언트 Lifespan 관리

**Event-Driven**: **WHEN** OpenAI 클라이언트가 필요한 서비스가 요청되면, 시스템은 **SHALL** `app.state`에서 `AsyncOpenAI` 클라이언트를 조회하여 반환해야 한다.

**State-Driven**: **IF** `OPENAI_API_KEY`가 설정되지 않았으면, 시스템은 **SHALL** dummy-key 클라이언트를 반환하고 warning 로그를 출력해야 한다 (기존 동작 보존).

#### REQ-DI-007: HTTP 클라이언트 Lifespan 관리

**Event-Driven**: **WHEN** 태깅 서비스가 요청되면, 시스템은 **SHALL** `app.state`에서 공유 `httpx.AsyncClient`를 조회하여 반환해야 한다.

**Event-Driven**: **WHEN** FastAPI 앱이 종료되면, 시스템은 **SHALL** `httpx.AsyncClient.aclose()`를 호출해야 한다.

### Area 4: Sync Engine (Celery) (Priority Medium)

#### REQ-DI-008: 동기 엔진 명시적 초기화

**Ubiquitous**: Celery 워커는 **SHALL** 모듈 import 시점이 아닌 명시적 초기화 함수 호출 시에만 동기 DB 엔진을 생성해야 한다.

**Event-Driven**: **WHEN** Celery 워커가 시작되면, 시스템은 **SHALL** `init_sync_engine()`을 호출하여 동기 엔진과 세션 팩토리를 초기화해야 한다.

**Unwanted**: 시스템은 **SHALL NOT** `_sync_engine`과 `_SessionLocal`을 모듈 수준 전역 변수로 유지해야 한다. 대신 팩토리 함수의 클로저 또는 명시적 상태 객체를 사용해야 한다.

### Area 5: Test Infrastructure (Priority High)

#### REQ-DI-009: 테스트 의존성 오버라이드

**Event-Driven**: **WHEN** 테스트가 `app.dependency_overrides`를 설정하면, 시스템은 **SHALL** 모든 DI 의존성을 mock으로 교체할 수 있어야 한다.

**Unwanted**: 테스트는 **SHALL NOT** `module._instance = None` 또는 `patch("module._global_var")` 패턴으로 글로벌 상태를 직접 조작해야 한다.

#### REQ-DI-010: 테스트 격리 보장

**Ubiquitous**: 각 테스트는 **SHALL** 독립적인 의존성 인스턴스를 사용해야 하며, 이전 테스트의 상태가 영향을 주지 않아야 한다.

---

## 4. Non-Goals (명시적 제외)

| 항목 | 제외 사유 |
|------|-----------|
| 새로운 DI 프레임워크 도입 (wire, injector 등) | FastAPI 내장 `Depends()` + `app.state`로 충분 |
| Celery를 비동기로 전환 | 이 SPEC의 범위를 벗어남 — 별도 아키텍처 결정 |
| 기존 API 엔드포인트 URL/응답 변경 | API 계약 불변 원칙 |
| ML 엔진 내부 로직 변경 | 엔진 추론 로직은 DI와 무관 |
| 프론트엔드(Flutter) 코드 변경 | 백엔드 내부 리팩토링 |
| `get_current_user()` 의존성 재설계 | 이미 적절한 DI 패턴 사용 중 |

---

## 5. Technical Specification

### 5.1 Lifespan Context Manager 도입

FastAPI의 `asynccontextmanager` 기반 `lifespan`을 `app/main.py`에 도입한다.
모든 리소스(AsyncEngine, Redis, OpenAI, httpx)는 lifespan의 startup에서 생성되어
`request.app.state`에 저장되고, shutdown에서 정리된다.

### 5.2 DI Provider 함수 패턴

각 글로벌 상태는 FastAPI 의존성 함수로 전환한다:

```
# Before: 모듈 수준 전역 변수
_db_engine = create_engine(...)
_session_factory = get_session_factory(_db_engine)

# After: app.state 기반 DI
async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    factory = request.app.state.session_factory
    async with factory() as session:
        yield session
```

### 5.3 ML Engine Factory

WhisperEngine, DiarizationEngine은 싱글톤 패턴을 유지하되,
인스턴스를 `app.state`에 저장하고 의존성 함수로 조회한다.
엔진의 `load()` 메서드와 double-checked locking은 내부적으로 유지된다.

### 5.4 Celery 동기 엔진

Celery 워커는 `init_sync_engine()` 명시적 호출 패턴으로 전환한다.
모듈 수준 `_sync_engine` 전역 변수 대신, 함수 클로저나 `celery_app.user_options`를 활용한다.

### 5.5 테스트 인프라

기존 `conftest.py`의 `app.dependency_overrides` 패턴을 확장한다.
`module._instance = None` 패턴을 제거하고, 대신 `dependency_overrides`로 mock을 주입한다.

### 5.6 마이그레이션 전략

| Phase | 대상 | 전환 패턴 | 영향 파일 수 |
|-------|------|-----------|-------------|
| Phase 1 | DB Engine + Redis + 시작시각 | Lifespan-managed | 5-8 |
| Phase 2 | WhisperEngine + DiarizationEngine | Engine factory | 8-12 |
| Phase 3 | OpenAI + httpx 클라이언트 | Client pool | 4-6 |
| Phase 4 | 동기 엔진 (Celery) | 명시적 초기화 | 3-5 |
| Phase 5 | 테스트 인프라 정리 | dependency_overrides 통일 | 23+ |
