---
id: SPEC-TECHDEBT-001
version: "1.0.0"
status: planned
created: "2026-06-15"
updated: "2026-06-15"
author: MoAI
priority: medium
issue_number: 0
---

# SPEC-TECHDEBT-001: 기술 부채 정리 — Python 3.14 호환성, Pydantic v2 완전 마이그레이션

## HISTORY

| Date | Version | Change | Author |
|------|---------|--------|--------|
| 2026-06-15 | 1.0.0 | Initial SPEC — 4개 기술 부채 카테고리 정의 | MoAI |

## 개요

SPEC-BUGFIX-001/002에서 런타임 버그와 회귀 방지를 해결한 후, 남은 기술 부채를 정리한다. 현재 3374개 테스트가 통과하지만 Python 3.14에서 약 38개의 `datetime.utcnow()` deprecation warning과 5개의 Pydantic v2 class-based `Config` deprecation이 발생한다. 또한 `asyncio.get_event_loop()` 3곳이 Python 3.16에서 제거 예정이다.

본 SPEC은 이러한 기술 부채를 해소하여:
1. Python 3.16 이상으로의 마이그레이션 경로 확보
2. Deprecation warning을 0으로 감소 (운영 로그 노이즈 제거)
3. Pydantic v3 마이그레이션 기반 마련

## 요구사항 (EARS Format)

### REQ-TD-001: datetime.utcnow() → datetime.now(UTC) 전환

- **When** Python 3.14 이상에서 `datetime.utcnow()`를 호출할 때
- **Then** DeprecationWarning이 발생한다
- **Rationale**: Python 3.16에서 완전 제거 예정. 38곳(프로덕션 16곳 + 테스트 22곳)에서 사용 중.

**검증 방법**:
- 모든 `datetime.utcnow()` → `datetime.now(UTC)` (또는 `datetime.now(timezone.utc)`)로 전환
- `grep -rn "datetime.utcnow()" backend/` 결과 0건
- `pytest -W error::DeprecationWarning` 실행 시 `datetime.utcnow` 관련 에러 0건

**대상 파일**:
- 프로덕션 (16곳): `services/action_item_service.py` (7곳), `services/advanced_search.py` (1), `app/api/v1/analytics/advanced_search.py` (7), `app/api/v1/analytics/sentiment.py` (2), `app/api/v1/minutes/action_items_crud.py` (3), `app/api/v1/collaboration/meetings.py` (1)
- 테스트 (22곳): `tests/test_device_token_models.py` (1), `tests/unit/test_action_item_service_coverage.py` (7), `tests/unit/test_coverage_to_100.py` (6), `tests/unit/test_action_items_api_coverage.py` (3), 그 외

### REQ-TD-002: Pydantic class-based Config → ConfigDict 전환

- **When** Pydantic v2에서 class-based `Config` 내부 클래스를 사용할 때
- **Then** `PydanticDeprecatedSince20` warning이 발생한다
- **Rationale**: Pydantic v3에서 class-based Config 제거 예정. `backend/app/schemas/action_item.py`의 5개 클래스에서 사용 중.

**검증 방법**:
- `ActionItemResponse`, `ActionItemComment`, `ActionItemCommentResponse`, `ActionItemHistory`, `ActionItemReminder`의 class-based `Config`를 `model_config = ConfigDict(...)`로 전환
- `pytest` 실행 시 `PydanticDeprecatedSince20` warning 0건

### REQ-TD-003: asyncio.get_event_loop() → 대체 패턴

- **When** Python 3.14+에서 `asyncio.get_event_loop()`를 호출할 때
- **Then** DeprecationWarning이 발생한다 (3.16에서 제거 예정)
- **Rationale**: 3곳에서 사용 중: `conftest.py:350`, `enhanced_audio_processor.py:164,211`

**검증 방법**:
- `conftest.py`: `asyncio.get_event_loop()` → `asyncio.new_event_loop()` 또는 fixture 기반으로 전환
- `enhanced_audio_processor.py:164,211`: `asyncio.get_event_loop().time()` → `time.perf_counter()` 또는 `asyncio.get_running_loop().time()` (이미 running loop 안에서 호출되므로)
- `grep -rn "get_event_loop" backend/` 결과 0건 (또는 모두 `get_running_loop`)

### REQ-TD-004: pytest-asyncio fixture loop scope 설정

- **When** pytest-asyncio가 `asyncio_default_fixture_loop_scope` 설정 없이 실행될 때
- **Then** `PytestDeprecationWarning`이 발생한다
- **Rationale**: `pyproject.toml`의 `[tool.pytest.ini_options]`에 `asyncio_default_fixture_loop_scope = "function"` 명시 필요

**검증 방법**:
- `pyproject.toml`에 `asyncio_default_fixture_loop_scope = "function"` 추가
- `pytest` 실행 시 해당 deprecation warning 0건

## 인수 기준 (Acceptance Criteria)

### AC-001: datetime.utcnow 제거
- `grep -rn "datetime\.utcnow\(\)" backend/ --include="*.py"` 결과 0건
- 전체 테스트 스위트 실행 시 datetime 관련 DeprecationWarning 0건

### AC-002: Pydantic Config 마이그레이션
- `grep -rn "class Config:" backend/ --include="*.py"` 결과 0건 (테스트 파일 제외)
- `ActionItemResponse` 등 5개 클래스가 `model_config = ConfigDict(...)` 사용
- pytest 실행 시 `PydanticDeprecatedSince20` warning 0건

### AC-003: asyncio.get_event_loop 제거
- `grep -rn "get_event_loop" backend/ --include="*.py"` 결과 0건
- 또는 모두 `get_running_loop`로 전환

### AC-004: pytest-asyncio 설정
- `pyproject.toml`에 `asyncio_default_fixture_loop_scope` 명시
- pytest 실행 시 해당 warning 0건

### AC-005: 전체 게이트 유지
- ruff check: 0 errors
- mypy: 0 errors
- pytest: 3374+ passed (기존 테스트 + 신규 호환성 테스트)
- pytest -W error::DeprecationWarning: 대상 카테고리 0건

## 기술 접근법

### datetime.utcnow() 전환 패턴

```python
# Before
from datetime import datetime
now = datetime.utcnow()

# After
from datetime import UTC, datetime
now = datetime.now(UTC)
```

주의: ORM 모델의 `default=datetime.utcnow` (함수 참조)는 `default=lambda: datetime.now(UTC).replace(tzinfo=None)`로 전환 — 기존 DB 컬럼이 tzinfo 없는 datetime을 기대하므로. `backend/db/models.py`의 `_utcnow()` 헬퍼가 이미 이 패턴을 사용 중이므로 참고.

### Pydantic ConfigDict 전환 패턴

```python
# Before
from pydantic import BaseModel

class MyResponse(BaseModel):
    class Config:
        from_attributes = True
        populate_by_name = True

# After
from pydantic import BaseModel, ConfigDict

class MyResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )
```

### asyncio.get_event_loop() 전환 패턴

```python
# Before (enhanced_audio_processor.py)
start_time = asyncio.get_event_loop().time()
processing_time = asyncio.get_event_loop().time() - start_time

# After (이미 async 함수 내부이므로 running loop 사용)
start_time = asyncio.get_running_loop().time()
# 또는 time.perf_counter() (loop과 무관한 고해상도 타이머)

# Before (conftest.py:350)
loop = asyncio.get_event_loop()

# After (테스트 fixture로 대체)
@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
```

## 영향 범위

### 수정 대상 파일

**프로덕션 코드**:
- `backend/services/action_item_service.py` — utcnow 7곳
- `backend/services/advanced_search.py` — utcnow 1곳
- `backend/app/api/v1/analytics/advanced_search.py` — utcnow 7곳
- `backend/app/api/v1/analytics/sentiment.py` — utcnow 2곳
- `backend/app/api/v1/minutes/action_items_crud.py` — utcnow 3곳
- `backend/app/api/v1/collaboration/meetings.py` — utcnow 1곳
- `backend/app/schemas/action_item.py` — class Config 5곳
- `backend/pipeline/enhanced_audio_processor.py` — get_event_loop 2곳
- `backend/conftest.py` — get_event_loop 1곳

**테스트 코드**:
- `backend/tests/test_device_token_models.py` — utcnow 1곳
- `backend/tests/unit/test_action_item_service_coverage.py` — utcnow 7곳
- `backend/tests/unit/test_coverage_to_100.py` — utcnow 6곳
- `backend/tests/unit/test_action_items_api_coverage.py` — utcnow 3곳
- 기타 utcnow 5곳

**설정**:
- `pyproject.toml` — `asyncio_default_fixture_loop_scope` 추가

### 의존성 변경
- 없음 (표준 라이브러리 및 이미 설치된 패키지만 사용)

## 리스크

| 리스크 | 확률 | 영향 | 완화책 |
|--------|------|------|--------|
| datetime.now(UTC) 전환 시 tzinfo 불일치 | 중간 | DB 쿼리 결과 차이 | `_utcnow()` 패턴(tzinfo 제거) 준수, 기존 DB 데이터와 비교 테스트 |
| Pydantic ConfigDict 전환 시 필드 검증 동작 변경 | 낮음 | API 응답 스키마 차이 | 전환 후 스키마 동일성 단위 테스트 |
| asyncio fixture 전환 시 테스트 실행 순서 변경 | 낮음 | 간헐적 테스트 실패 | `pytest-asyncio` `auto` 모드 유지, fixture scope 명시 |

## 우선순위

| REQ | 우선순위 | 이유 |
|-----|---------|------|
| REQ-TD-001 | P1 | Python 3.16 마이그레이션 선행 조건, 38곳 대량 |
| REQ-TD-003 | P1 | Python 3.16 마이그레이션 선행 조건 |
| REQ-TD-002 | P2 | Pydantic v3 대비 (시간적 여유 있음) |
| REQ-TD-004 | P2 | 노이즈 감소 (기능 영향 없음) |

## 제약사항

- DB 모델의 `default=datetime.utcnow` (함수 참조)는 tzinfo 없는 datetime을 반환해야 함 — 기존 DB 컬럼 타입과 호환성 유지
- 테스트 코드의 `datetime.utcnow()`는 tzinfo 있는 `datetime.now(UTC)`로 전환해도 무방 (메모리 객체 비교만 수행)
- `conftest.py`의 `get_event_loop()`는 테스트 환경에서만 사용되므로 `new_event_loop`로 안전하게 전환 가능
