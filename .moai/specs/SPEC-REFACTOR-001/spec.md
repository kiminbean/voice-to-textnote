---
id: SPEC-REFACTOR-001
version: 1.0.0
status: in-progress
created: 2026-06-03
author: MoAI
priority: medium
title: Backend Structure Refactoring
tags: [refactoring, architecture, error-handling, service-layer, api-structure]
related_specs:
  - SPEC-ERR-001
  - SPEC-DB-001
---

# SPEC-REFACTOR-001: Backend Structure Refactoring

## 1. Environment (현재 상황)

### 기술 스택
- FastAPI + SQLAlchemy (async) + SQLite/PostgreSQL
- Celery + Redis (비동기 작업 처리)
- Pydantic v2 (스키마 검증)
- structlog (구조화된 로깅)

### 현재 아키텍처
```
backend/
├── app/
│   ├── api/v1/          # 30+ 라우터 파일 (flat 구조)
│   ├── middleware/       # 인증, 감사로깅, 보안헤더, Rate Limit
│   ├── dependencies.py  # FastAPI 의존성 (DB, Redis, JWT)
│   ├── exceptions.py    # VoiceNoteError 계층 (3개 서브클래스)
│   ├── error_handlers.py # 전역 예외 핸들러
│   ├── config.py        # 설정
│   └── main.py          # 앱 생성 (80+줄 라우터 등록)
├── db/                  # 모델 + 서비스 혼재 (13개 서비스 파일)
├── services/            # 일부 서비스 (7개)
├── schemas/             # Pydantic 스키마 (20+)
├── pipeline/            # 처리 파이프라인
├── workers/tasks/       # Celery 태스크
└── utils/               # 유틸리티
```

### 발견된 문제점 (Anti-patterns)

| ID | 문제 | 심각도 | 영향 범위 |
|----|------|--------|-----------|
| AP-1 | **HTTPException 남용**: VoiceNoteError 계층이 존재하나 158건의 raw HTTPException 사용 | 높음 | 30+ 라우터 |
| AP-2 | **응답 형식 불일치**: 99개 response_model vs 11개 bare dict 반환 혼재 | 중간 | 20+ 엔드포인트 |
| AP-3 | **비즈니스 로직 누수**: 53개 인라인 try/except가 라우터에 존재 | 높음 | 15+ 라우터 |
| AP-4 | **서비스 위치 혼재**: `db/`에 13개, `services/`에 7개 서비스 분산 | 중간 | 전체 |
| AP-5 | **모듈레벨 서비스 인스턴스**: 21개 `_service = XxxService()` (의존성 주입 미사용) | 중간 | 15+ 라우터 |
| AP-6 | **라우터 flat 구조**: 30+ 라우터가 도메인 그룹핑 없이 단일 디렉토리에 존재 | 낮음 | main.py, 라우터 |
| AP-7 | **main.py 비대**: 라우터 등록이 80+줄로 반복적 | 낮음 | main.py |
| AP-8 | **DB 엔진 모듈레벨 생성**: `_db_engine`이 import 시점에 생성됨 | 낮음 | dependencies.py |

---

## 2. Assumptions (가정)

- A-1: 기존 API 계약(URL, HTTP 상태 코드, 응답 형식)은 변경하지 않는다
- A-2: 기존 테스트는 계속 통과해야 한다 (import 경로 변경은 허용)
- A-3: 각 Phase는 독립적으로 배포 가능하다
- A-4: Phase 간 의존성은 순서대로 처리한다 (Phase 1 → 2 → 3 → 4)
- A-5: 현재 VoiceNoteError 계층과 error_handlers.py는 잘 설계되어 있어 확장한다

---

## 3. Requirements (요구사항)

### Area 1: 공통 에러/응답 패턴 (Priority High)

#### REQ-ERR-001: 도메인 예외 확장

**Ubiquitous**: 시스템은 **항상** 모든 도메인 에러를 `VoiceNoteError` 계층으로 처리해야 한다.

```
기존 VoiceNoteError 계층에 다음 서브클래스를 추가한다:
- NotFoundError (404)
- UnauthorizedError (401)
- ForbiddenError (403)
- ValidationError (400)
- ConflictError (409)
- RateLimitError (429)
```

#### REQ-ERR-002: 에러 헬퍼 함수

**Event-Driven**: **WHEN** 라우터에서 에러가 발생하면, **THEN** `backend/app/errors.py`의 헬퍼 함수를 사용해야 한다.

```python
# backend/app/errors.py
def not_found(message: str = "리소스를 찾을 수 없습니다") -> NoReturn: ...
def unauthorized(message: str = "인증이 필요합니다") -> NoReturn: ...
def forbidden(message: str = "접근 권한이 없습니다") -> NoReturn: ...
def bad_request(message: str) -> NoReturn: ...
def conflict(message: str) -> NoReturn: ...
```

#### REQ-ERR-003: HTTPException 제거

**Unwanted**: 시스템은 라우터에서 **직접** `HTTPException`을 raise **하지 않아야 한다**.

- 기존 158건의 `HTTPException`을 `VoiceNoteError` 서브클래스로 교체
- `HTTPException`은 FastAPI 내부용(middleware 등)에만 허용

#### REQ-ERR-004: 응답 형식 통일

**Ubiquitous**: 시스템은 **항상** 모든 엔드포인트에서 `response_model`을 사용하여 응답해야 한다.

**Unwanted**: 시스템은 라우터에서 **직접** `dict`를 반환 **하지 않아야 한다**.

- 11건의 bare dict 반환을 Pydantic 스키마로 교체
- 비동기 작업 응답도 `TaskCreatedResponse` 같은 공통 스키마 사용

---

### Area 2: DB/의존성 구조 (Priority High)

#### REQ-DEP-001: 서비스 의존성 주입

**Ubiquitous**: 시스템은 **항상** 서비스를 FastAPI `Depends()`로 주입해야 한다.

**Unwanted**: 시스템은 모듈 레벨에서 서비스를 직접 인스턴스화 **하지 않아야 한다**.

```
Before: _service = BookmarkService()
After:  def get_bookmark_service() -> BookmarkService: ...
        async def create(db, user, svc=Depends(get_bookmark_service)): ...
```

#### REQ-DEP-002: DB 세션 관리 일관성

**State-Driven**: **IF** 서비스가 DB 접근이 필요하면, **THEN** `AsyncSession`을 메서드 파라미터로 받아야 한다.

- 현재 패턴 유지 (서비스 메서드에 session 파라미터 전달)
- 서비스 내부에서 세션을 생성하지 않음

#### REQ-DEP-003: DB 엔진 생명주기 관리

**Event-Driven**: **WHEN** 애플리케이션이 시작되면, **THEN** DB 엔진을 lifespan에서 생성해야 한다.

**Unwanted**: 시스템은 모듈 import 시점에 DB 엔진을 생성 **하지 않아야 한다**.

- `_db_engine` 생성을 `lifespan`으로 이동
- `dependencies.py`에서 엔진 생성 코드 제거

---

### Area 3: 서비스 계층 분리 (Priority Medium)

#### REQ-SVC-001: 모델/서비스 분리

**Ubiquitous**: 시스템은 **항상** 모델 파일과 서비스 파일을 분리된 위치에 유지해야 한다.

- `backend/db/`에는 모델(`*_models.py`)만 유지
- `backend/db/`의 서비스 파일(`*_service.py`)을 `backend/services/`로 이동
- 이동 대상: auth_service, bookmark_service, meeting_share_service, search_service, speaker_service, speaker_voice_service, tag_service, team_service, version_service, vocabulary_service, webhook_service

#### REQ-SVC-002: 서비스 인터페이스 일관성

**State-Driven**: **IF** 서비스가 존재하면, **THEN** 일관된 메서드 시그니처를 가져야 한다.

- 모든 서비스 메서드: 첫 번째 파라미터로 `session: AsyncSession`
- 반환 타입 명시 (type hints)
- 에러 발생 시 `VoiceNoteError` 서브클래스 raise

#### REQ-SVC-003: 라우터 비즈니스 로직 제거

**Unwanted**: 라우터는 **비즈니스 로직을 포함하지 않아야 한다**.

- 라우터 역할: 요청 파싱, 의존성 주입, 서비스 호출, 응답 변환
- 비즈니스 로직(데이터 변환, 검증, 계산)은 서비스로 이동
- 53개 인라인 try/except를 서비스 레이어로 이동

---

### Area 4: API 라우터 구조 (Priority Low)

#### REQ-ROUTE-001: 도메인별 라우터 그룹핑

**Ubiquitous**: 시스템은 **항상** 라우터를 도메인 그룹으로 구성해야 한다.

```
backend/app/api/v1/
├── transcription/     # STT, Diarization, Batch
├── minutes/           # Minutes, Summary, Sentiment, Tags, Keywords
├── collaboration/     # Teams, Meetings, Bookmarks, Webhooks
├── analytics/         # Statistics, Dashboard, EnhancedStats, AdvancedSearch
├── audio/             # AudioAnalysis, AudioPreprocess, Quality
├── admin/             # Admin, Health, History, Export
├── auth/              # Auth, Devices
└── registry.py        # 라우터 그룹 등록 헬퍼
```

#### REQ-ROUTE-002: 라우터 등록 간소화

**Event-Driven**: **WHEN** 새 라우터가 추가되면, **THEN** `registry.py`에 그룹 등록만으로 반영되어야 한다.

```python
# backend/app/api/v1/registry.py
ROUTER_GROUPS = {
    "transcription": {
        "prefix": "/api/v1",
        "routers": [batch.router, transcription.router, diarization.router],
        "auth": "api_key",
    },
    ...
}
```

#### REQ-ROUTE-003: 인증 전략 명확화

**State-Driven**: **IF** 라우터가 보호 대상이면, **THEN** 라우터 레벨에서 인증 전략을 명시해야 한다.

- API Key 인증: `dependencies=[Depends(verify_api_key)]` (라우터 레벨)
- JWT 인증: `Depends(get_current_user)` (엔드포인트 레벨)
- 공개 엔드포인트: 인증 의존성 없음
- 각 라우터 파일에 인증 전략을 주석으로 명시

---

## 4. Specifications (구현 명세)

### 파일 수정 영향도

| Phase | New Files | Modified Files | Moved Files | Risk |
|-------|-----------|----------------|-------------|------|
| Phase 1 | `app/errors.py` | `app/exceptions.py`, 30 라우터 | 0 | 낮음 |
| Phase 2 | 0 | Import 경로 전체 | 11 서비스 파일 | 중간 |
| Phase 3 | `app/service_deps.py` | 15+ 라우터, 서비스 | 0 | 중간 |
| Phase 4 | `api/v1/registry.py`, 도메인 `__init__.py` | `main.py` | 30 라우터 | 낮음 |

### 호환성 보장

- 모든 기존 URL 패턴 유지 (`/api/v1/...`)
- HTTP 상태 코드 유지
- 응답 JSON 구조 유지 (error_code, message, request_id)
- 기존 테스트 통과 보장 (import 경로 변경은 업데이트 필요)

---

## 5. Traceability

| TAG | Source | Requirement IDs |
|-----|--------|-----------------|
| SPEC-REFACTOR-001-ERR | Area 1 | REQ-ERR-001 ~ REQ-ERR-004 |
| SPEC-REFACTOR-001-DEP | Area 2 | REQ-DEP-001 ~ REQ-DEP-003 |
| SPEC-REFACTOR-001-SVC | Area 3 | REQ-SVC-001 ~ REQ-SVC-003 |
| SPEC-REFACTOR-001-ROUTE | Area 4 | REQ-ROUTE-001 ~ REQ-ROUTE-003 |

---

## 6. Implementation Status (2026-06-04 Sync)

### Phase Progress

| Phase | Status | Details |
|-------|--------|---------|
| Phase 1 (에러/예외) | ✅ 구현 완료 | `errors.py` 신규 (에러 헬퍼 5종), `exceptions.py` 확장 (서브클래스 6종), 23개 라우트 전환, raw `HTTPException` 0건 |
| Phase 2 (서비스 이동) | ✅ 구현 완료 | `backend/db/`에서 11개 서비스 파일 삭제, `backend/services/`에 26개 서비스 집중, `db/`는 모델만 유지 |
| Phase 3 (의존성 주입) | 🔶 부분 진행 | 31개 라우트에서 `Depends()` 사용, 20개 모듈레벨 `_service = XxxService()` 잔존 |
| Phase 4 (라우터 그룹핑) | ❌ 미시작 | flat 구조 유지 (35개 라우터), main.py에 35개 `include_router` |

### Test Status

- **Total**: 2416 passed / 14 failed / 4 skipped
- **Failure Rate**: 0.57% (14/2434)

### Known Regressions (14건)

| Category | Count | Test Cases | Root Cause | Fix |
|----------|-------|------------|------------|-----|
| 잘못된 헬퍼 사용 | 1 | `test_file_too_large_returns_413` | `audio_preprocess.py:110`에서 empty file size 케이스에 `bad_request()`(400) 사용. `request_entity_too_large()`(413)는 line 136 다른 경로에만 사용 | 조건 분기 수정: size=0은 `bad_request`, size>max는 `request_entity_too_large` |
| 응답 형식 불일치 | 11 | summary API 5건(404/409/429), sentiment 1건(404) | 테스트가 `response.json()["message"]` 참조 → `KeyError`. VoiceNoteError 핸들러는 `{"error_code", "message", "request_id"}` 반환하나, 테스트 클라이언트에 핸들러 미등록 시 FastAPI 기본 `{"detail": "..."}` 반환 | 테스트 클라이언트에 `register_exception_handlers()` 호출 추가 |
| import 누락 | 2 | `test_upload_corrupted_audio`, `test_corrupted_file_upload_returns_422` | `transcription.py:150`에서 `except VoiceNoteError:` 참조하나 import 없음 → `NameError` | `from backend.app.exceptions import VoiceNoteError` 추가 |

### Architecture Changes (Phase 1-2)

```
Before:                              After:
backend/                             backend/
├── app/                             ├── app/
│   ├── api/v1/ (30+ routers)        │   ├── api/v1/ (35 routers, error helpers)
│   ├── exceptions.py (3 classes)    │   ├── errors.py (10 helper functions) ← NEW
│   └── ...                          │   ├── exceptions.py (14 classes) ← EXPANDED
├── db/                              │   └── ...
│   ├── *_service.py (11 files)      ├── db/
│   └── *_models.py                  │   ├── *_models.py (모델만 유지)
├── services/ (7 files)              │   ├── engine.py, service.py, sync_engine.py
│   └── ...                          │   └── ...
                                     ├── services/ (26 files) ← CONSOLIDATED
                                     │   ├── auth_service.py
                                     │   ├── search_service.py
                                     │   ├── ... (db/에서 이동)
                                     │   └── ... (기존 유지)
                                     └── ...
```

### Affected Files (Uncommitted)

- Modified: 32 backend app files, 50 test files
- Deleted: 11 backend db service files
- Total: 103 files, +981 / -3577 lines
