---
id: SPEC-TECHDEBT-001
phase: plan
version: "1.0.0"
created: "2026-06-15"
updated: "2026-06-15"
---

# SPEC-TECHDEBT-001 Implementation Plan

## 개요

SPEC-TECHDEBT-001은 4개 기술 부채 카테고리(REQ-TD-001~004)를 해결하여 Python 3.16 마이그레이션 경로를 확보하고 deprecation warning을 0으로 감소시킨다.

## 개발 방법론

- **TDD (RED-GREEN-REFACTOR)**: 기존 코드가 풍부하고 테스트 커버리지가 97% 이상이므로 TDD 적용
- 각 REQ별로 기존 동작을 검증하는 테스트 확인(RED) → 전환(GREEN) → 정리(REFACTOR)

## 태스크 분해

### Phase 1: P1 (Python 3.16 선행 조건)

#### Task 1: REQ-TD-001 — datetime.utcnow() 전환

**사전 분석**:
- 38곳 (프로덕션 16곳 + 테스트 22곳)
- DB 모델 default의 경우 tzinfo 없는 datetime 필요 → `_utcnow()` 패턴 준수

**단계**:
1. `backend/db/models.py`의 `_utcnow()` 헬퍼 확인 (이미 `datetime.now(UTC).replace(tzinfo=None)` 패턴)
2. 프로덕션 코드 16곳 전환:
   - `services/action_item_service.py` (7곳): 모두 `datetime.utcnow()` → `datetime.now(UTC)` (tzinfo 있어도 Pydantic이 직렬화 처리)
   - `services/advanced_search.py` (1곳): 동일
   - `app/api/v1/analytics/advanced_search.py` (7곳): 동일
   - `app/api/v1/analytics/sentiment.py` (2곳): 동일
   - `app/api/v1/minutes/action_items_crud.py` (3곳): 동일
   - `app/api/v1/collaboration/meetings.py` (1곳): 동일
3. 테스트 코드 22곳 전환 (동일 패턴)
4. `from datetime import UTC` import 추가

**검증**:
- `grep -rn "datetime\.utcnow\(\)" backend/` → 0건
- pytest 실행 시 `DeprecationWarning` 중 `utcnow` 관련 0건

#### Task 2: REQ-TD-003 — asyncio.get_event_loop() 전환

**단계**:
1. `backend/pipeline/enhanced_audio_processor.py:164,211`:
   - `asyncio.get_event_loop().time()` → `asyncio.get_running_loop().time()` (이미 async 함수 내부)
   - 또는 `time.perf_counter()`로 전환 (더 단순, loop 무관)
2. `backend/conftest.py:350`:
   - 테스트 환경이므로 `asyncio.new_event_loop()`로 전환
   - 또는 pytest-asyncio의 기본 fixture를 사용하도록 제거

**검증**:
- `grep -rn "get_event_loop" backend/` → 0건 (또는 `get_running_loop`만 남음)
- pytest 실행 시 `get_event_loop` 관련 DeprecationWarning 0건

### Phase 2: P2 (노이즈 감소, 미래 대비)

#### Task 3: REQ-TD-002 — Pydantic ConfigDict 전환

**단계**:
1. `backend/app/schemas/action_item.py`의 5개 클래스 확인:
   - `ActionItemResponse` (line ~98)
   - `ActionItemComment` (line ~186)
   - `ActionItemCommentResponse` (line ~209)
   - `ActionItemHistory` (line ~225)
   - `ActionItemReminder` (line ~242)
2. 각 클래스의 `class Config:` 내용 추출
3. `model_config = ConfigDict(...)`로 전환
4. `from pydantic import ConfigDict` import 추가

**검증**:
- `grep -rn "class Config:" backend/app/schemas/` → 0건
- pytest 실행 시 `PydanticDeprecatedSince20` warning 0건

#### Task 4: REQ-TD-004 — pytest-asyncio 설정

**단계**:
1. `pyproject.toml`의 `[tool.pytest.ini_options]`에 추가:
   ```toml
   asyncio_default_fixture_loop_scope = "function"
   ```
2. pytest 실행으로 warning 감소 확인

**검증**:
- pytest 실행 시 `asyncio_default_fixture_loop_scope` warning 0건

### Phase 3: 통합 검증

#### Task 5: 전체 게이트 + DeprecationWarning 에러 모드

**단계**:
1. `ruff check backend/` — 0 errors
2. `mypy backend/` — 0 errors
3. `pytest backend -q` — 3374+ passed
4. `pytest backend -W error::DeprecationWarning -q` — datetime/asyncio/pydantic 관련 0건 (외부 라이브러리 warning은 제외)
5. 커버리지 97%+ 유지

## 병렬 실행 가능성

| Task Group | 병렬 가능 | 이유 |
|-----------|----------|------|
| Task 1 + Task 2 | ✓ | 독립 파일 (services/api vs pipeline/conftest) |
| Task 3 + Task 4 | ✓ | 독립 파일 (schemas vs pyproject.toml) |
| Task 1 → Task 3 | 순차 | 스키마 파일이 action_item_service와 연관 |

## 파일 변경 예상 목록

### 수정
- `backend/services/action_item_service.py` — utcnow 7곳
- `backend/services/advanced_search.py` — utcnow 1곳
- `backend/app/api/v1/analytics/advanced_search.py` — utcnow 7곳
- `backend/app/api/v1/analytics/sentiment.py` — utcnow 2곳
- `backend/app/api/v1/minutes/action_items_crud.py` — utcnow 3곳
- `backend/app/api/v1/collaboration/meetings.py` — utcnow 1곳
- `backend/app/schemas/action_item.py` — ConfigDict 전환 5곳
- `backend/pipeline/enhanced_audio_processor.py` — get_event_loop 2곳
- `backend/conftest.py` — get_event_loop 1곳
- `backend/tests/test_device_token_models.py` — utcnow 1곳
- `backend/tests/unit/test_action_item_service_coverage.py` — utcnow 7곳
- `backend/tests/unit/test_coverage_to_100.py` — utcnow 6곳
- `backend/tests/unit/test_action_items_api_coverage.py` — utcnow 3곳
- 기타 테스트 파일 utcnow 5곳
- `pyproject.toml` — asyncio_default_fixture_loop_scope 추가

### 신규
- 없음 (기존 코드 수정만)

## 리스크 완화

| 리스크 | 완화책 |
|--------|--------|
| datetime.now(UTC) tzinfo 불일치 | Pydantic이 ISO 직렬화 시 tzinfo 처리. DB 모델 default는 `_utcnow()` 패턴 유지 |
| Pydantic ConfigDict 동작 변경 | 5개 클래스 각각에 대해 스키마 동일성 단위 테스트 실행 |
| conftest.py fixture 전환 부작용 | pytest-asyncio `auto` 모드 유지로 기존 동작 보존 |

## 완료 기준

- [ ] AC-001~004 전부 통과
- [ ] ruff check: 0 errors
- [ ] mypy: 0 errors
- [ ] pytest: 3374+ passed
- [ ] `grep -rn "datetime\.utcnow\(\)" backend/` → 0건
- [ ] `grep -rn "class Config:" backend/app/schemas/` → 0건
- [ ] `grep -rn "get_event_loop" backend/` → 0건 (또는 get_running_loop만)
- [ ] pytest DeprecationWarning 중 대상 카테고리 0건
