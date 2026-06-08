---
id: SPEC-TYPING-001
version: 1.0.0
status: draft
created: 2026-06-08
author: MoAI
priority: medium
title: Mypy Static Type Error Resolution
tags: [typing, mypy, static-analysis, quality-gate, type-safety]
related_specs:
  - SPEC-REFACTOR-001
  - SPEC-REFACTOR-002
---

# SPEC-TYPING-001: Mypy Static Type Error Resolution

## 1. Environment (현재 상황)

### 기술 스택
- Python 3.14 + FastAPI + SQLAlchemy (async)
- Pydantic v2 (스키마 검증)
- mypy (정적 타입 검사, 최근 품질 게이트에 편입)
- pytest (테스트), ruff (lint/format)

### 검증 명령
- 타입 검사: `./venv/bin/python -m mypy backend/`
- 테스트: `./venv/bin/python -m pytest backend/`
- Lint: `./venv/bin/python -m ruff check backend/`
- Format: `./venv/bin/python -m ruff format --check backend/`

### 현재 측정 결과 (Baseline)

mypy를 품질 게이트에 추가한 직후 측정한 baseline은 **40개 파일에 걸친 194개 타입 에러**이다.
이 에러들은 누적된 타입 어노테이션 불일치이며, **런타임 버그가 아니다** — 현재 3174개 테스트가 모두 통과하고 커버리지는 99.91%다.

| 분류 | 에러 수 |
|------|---------|
| 전체 | 194 (40 파일) |
| 프로덕션 코드 | 170 |
| 테스트 파일 | 24 |

### 에러 코드 분포

| 에러 코드 | 개수 | 에러 코드 | 개수 |
|-----------|------|-----------|------|
| `arg-type` | 69 | `union-attr` | 8 |
| `attr-defined` | 44 | `call-arg` | 5 |
| `operator` | 23 | `misc` | 4 |
| `assignment` | 17 | `dict-item` | 2 |
| `return-value` | 9 | `str-bytes-safe` | 1 |
| `var-annotated` | 8 | `no-redef` / `method-assign` / `index` / `call-overload` | 각 1 |

> 참고: `annotation-unchecked` note 6건은 비차단(non-blocking) 항목이며 에러 카운트에 포함되지 않는다.

### 에러 집중 파일 (Hotspots)

| 파일 | 에러 수 | 계층 |
|------|---------|------|
| `backend/services/advanced_search.py` | 28 | 서비스 |
| `backend/services/quality_service.py` | 27 | 서비스 |
| `backend/services/action_item_service.py` | 19 | 서비스 |
| `backend/app/api/v1/minutes/action_items_crud.py` | 19 | API |
| `backend/tests/unit/test_speaker_voice_service.py` | 12 | 테스트 |
| `backend/app/api/v1/analytics/sentiment.py` | 10 | API |
| `backend/services/enhanced_statistics.py` | 9 | 서비스 |
| `backend/app/api/v1/transcription/transcription.py` | 5 | API |
| `backend/app/api/v1/collaboration/bookmarks.py` | 5 | API |
| `backend/app/api/v1/audio/enhanced_preprocess.py` | 5 | API |
| `backend/tests/unit/test_template_parser.py` | 4 | 테스트 |
| `backend/pipeline/summary_generator.py` | 4 | 파이프라인 |
| 나머지 약 28개 파일 | 1~3 (각) | 혼재 |

### 발견된 지배적 패턴 (Dominant Patterns)

| ID | 패턴 | 대표 사례 | 주요 에러 코드 |
|----|------|-----------|----------------|
| DP-1 | **dict ↔ Pydantic 스키마 불일치**: 서비스는 plain `dict`를 반환하나 API 계층은 타입드 Pydantic 응답 모델을 기대 | `action_items_crud.py:313` `Incompatible return value type (got "ActionItem", expected "ActionItemResponse")`; `sentiment.py` `"dict[Any, Any]" has no attribute "overall_score"` | `return-value`, `attr-defined` |
| DP-2 | **`**kwargs` dict 언패킹 시 구체 타입 소실** | `action_items_crud.py:105` `Argument 3 to "list_items" has incompatible type "**dict[str, UUID\|str\|datetime\|bool\|None]"; expected "ActionItemStatus \| None"` | `arg-type` |
| DP-3 | **str ↔ datetime / Sequence ↔ list 불일치** | `action_item_service.py:242` `Incompatible types in assignment (expression has type "str", target has type "datetime")`; `:188` `got "tuple[Sequence[ActionItem], int]", expected "tuple[list[ActionItem], int]"` | `assignment`, `return-value` |
| DP-4 | **선언되지 않은 속성/연산자 접근** | `advanced_search.py:48` `"type[TaskResult]" has no attribute "content"`; `quality_service.py:329` `Unsupported operand types for * ("str" and "float")` | `attr-defined`, `operator` |

---

## 2. Assumptions (가정)

- A-1: **[전제 조건]** PR #14 (브랜치 `chore/mypy-config-consolidation`)가 main에 병합된 상태를 기준으로 194 baseline이 측정되었다. 자세한 내용은 Section 6 (Dependency) 참조.
- A-2: 194개 에러는 어노테이션 불일치이며 **런타임 동작에 영향을 주지 않는다** (전체 테스트 통과로 증명됨).
- A-3: 모든 수정은 **런타임 동작을 보존**해야 한다. 테스트 통과 수(3174 passed / 16 skipped)와 커버리지(≥ 85%, 현재 99.91%)는 변하지 않아야 한다.
- A-4: 각 Phase는 독립적으로 검증/배포 가능하다. Phase 순서는 에러 집중도와 위험도에 따라 정해진다.
- A-5: 진실의 원천(source of truth) — Pydantic 모델, SQLAlchemy 모델 속성, 서비스 시그니처 — 에서 수정하는 것이 호출 지점(call site)에서 우회하는 것보다 우선한다.
- A-6 **[가정/문서화]**: baseline에 포함된 정확한 에러 행 번호는 PR #14 병합 시점의 코드를 기준으로 한다. Phase 착수 시점에 행 번호가 이동했을 수 있으므로, 각 Phase는 착수 전 해당 파일에 대해 `mypy`를 재실행하여 현행 에러 목록을 확정한다.

---

## 3. Requirements (요구사항)

### Area 0: 전제 조건 검증 (Priority High)

#### REQ-PRE-001: mypy 설정 전제 검증

**State-Driven**: **IF** SPEC 구현을 시작하면, **THEN** `mypy.ini`에 `ignore_missing_imports = True`가 적용되어 있고 `pyproject.toml`에 dead `[tool.mypy]` 블록이 없는 상태(PR #14 병합 상태)여야 한다.

- 전제 미충족 시(`./venv/bin/python -m mypy backend/` 에러 수가 194와 크게 다를 경우) 구현을 중단하고 PR #14 병합 여부를 확인한다.

---

### Area 1: 타입 정확성 원칙 (Priority High)

#### REQ-TYPE-001: 에러 0 달성

**Ubiquitous**: 시스템은 **항상** `./venv/bin/python -m mypy backend/` 실행 시 0개의 타입 에러를 보고해야 한다.

- 194개 에러를 0으로 줄이는 것이 본 SPEC의 최종 목표다.

#### REQ-TYPE-002: 진실의 원천에서 수정

**State-Driven**: **IF** 타입 불일치의 원인이 모델/서비스 시그니처에 있으면, **THEN** 호출 지점이 아닌 원천(Pydantic 모델, SQLAlchemy 모델 속성, 서비스 시그니처)에서 수정해야 한다.

- DP-1: 서비스 반환 타입을 Pydantic 스키마와 일치시키거나, API 계층에서 명시적 모델 변환(`Model.model_validate(...)`)을 수행한다.
- DP-3: `str` ↔ `datetime` 불일치는 모델 필드 타입 또는 할당 로직을 정정한다. `Sequence` ↔ `list` 불일치는 반환 타입 어노테이션을 실제 타입에 맞춘다.

#### REQ-TYPE-003: kwargs 타입 보존

**Event-Driven**: **WHEN** dict를 `**kwargs`로 언패킹하여 타입드 시그니처에 전달하면, **THEN** 구체 타입이 소실되지 않도록 명시적 인자 전달 또는 `TypedDict`를 사용해야 한다.

- DP-2: `**filters` 같은 dict 언패킹을 명시적 키워드 인자로 전환하거나, 필터 dict를 `TypedDict`로 정의한다.

#### REQ-TYPE-004: 속성/연산자 정합성

**State-Driven**: **IF** 객체의 속성 또는 연산자가 정적으로 미선언이면, **THEN** 해당 타입에 속성을 선언하거나 올바른 타입으로 좁혀(narrow) 접근해야 한다.

- DP-4: `type[TaskResult]` 같은 클래스 객체에 인스턴스 속성을 접근하는 코드는 인스턴스 참조로 정정한다. `str * float` 같은 잘못된 연산자는 피연산자 타입을 정정한다.

---

### Area 2: 타입 검사기 무력화 금지 (Priority High)

#### REQ-NOSUP-001: error code 비활성화 금지

**Unwanted**: 시스템은 `disable_error_code` 또는 관대한 `[tool.mypy]` 블록을 **추가하거나 재도입하지 않아야 한다**.

- 수정은 실제 타입 정확성을 통해 이루어져야 하며, 검사 약화로 달성해서는 안 된다.

#### REQ-NOSUP-002: blanket ignore 금지

**Unwanted**: 시스템은 무차별(`# type: ignore`) 무시 주석을 **사용하지 않아야 한다**.

- 진짜 서드파티 라이브러리 한계로 정상 수정이 불가능한 경우에만, 행 단위 코드 지정 형태(`# type: ignore[specific-code]`)와 인라인 사유 주석을 함께 사용할 수 있다.
- 각 `# type: ignore[code]` 사용은 사유가 문서화되어야 한다.

---

### Area 3: 런타임 동작 보존 (Priority High)

#### REQ-RT-001: 테스트 결과 불변

**Ubiquitous**: 시스템은 **항상** `./venv/bin/python -m pytest backend/` 실행 시 3174 passed / 16 skipped를 유지해야 한다.

#### REQ-RT-002: 커버리지 유지

**State-Driven**: **IF** 수정이 완료되면, **THEN** 커버리지는 85% 이상(현재 99.91%)을 유지해야 한다.

#### REQ-RT-003: Lint/Format 통과

**Ubiquitous**: 시스템은 **항상** `ruff check`와 `ruff format --check`를 통과해야 한다.

---

### Area 4: 단계적 해소 (Priority Medium)

#### REQ-PHASE-001: 에러 집중도 기반 Phase 진행

**Event-Driven**: **WHEN** 한 Phase가 완료되면, **THEN** 해당 Phase 대상 파일들의 mypy 에러 수가 0에 도달해야 한다.

- Phase 1: `services/` hotspots (advanced_search 28, quality_service 27, action_item_service 19, enhanced_statistics 9)
- Phase 2: API 계층 (action_items_crud 19, sentiment 10, transcription 5, bookmarks 5, enhanced_preprocess 5)
- Phase 3: 나머지 프로덕션 파일 (각 1~3개)
- Phase 4: 테스트 파일 (24개)

#### REQ-PHASE-002: 프로덕션 우선

**State-Driven**: **IF** Phase 순서를 정하면, **THEN** 프로덕션 코드(170개)를 테스트 파일(24개)보다 먼저 처리해야 한다.

---

## 4. Specifications (구현 명세)

### 파일 영향도 (Phase별)

| Phase | 대상 | 에러 수 | 위험 |
|-------|------|---------|------|
| Phase 1 | services/ hotspots (4 파일) | 83 | 중간 (서비스 시그니처 변경이 호출 지점에 파급) |
| Phase 2 | API 계층 (5 파일) | 44 | 중간 (응답 모델 변환 필요) |
| Phase 3 | 나머지 프로덕션 (약 28 파일) | 43 | 낮음 (파일당 1~3개) |
| Phase 4 | 테스트 파일 (2+ 파일) | 24 | 낮음 (테스트 격리) |
| 합계 | 40 파일 | 194 | — |

> Phase별 에러 합(83 + 44 + 43 + 24 = 194)은 baseline 총합과 일치한다.

### 호환성 보장

- 모든 기존 API 계약(URL, HTTP 상태 코드, 응답 JSON 구조) 불변
- 서비스 public 시그니처 변경 시 모든 호출 지점을 동시 업데이트
- mypy 수정은 어노테이션/형변환 중심이며, 비즈니스 로직은 변경하지 않음

---

## 5. Non-Goals (범위 밖)

- 타입 검사기 약화(`disable_error_code`, 관대한 설정, blanket ignore)를 통한 에러 카운트 감소
- 비즈니스 로직 변경 또는 기능 추가/제거
- mypy strict 모드 추가 도입(예: `disallow_any_generics`, `strict_optional` 강화) — 본 SPEC은 현행 설정에서 194 → 0만 목표로 한다
- PR #14가 다루는 `mypy.ini` / `pyproject.toml` 설정 변경(이미 전제 조건으로 병합됨)
- 테스트 추가/리팩토링(테스트 파일의 타입 에러 수정은 포함하되, 새 테스트 작성은 비목표)

---

## 6. Dependency (전제 조건)

### [HARD] PR #14 병합 전제

본 SPEC의 194 baseline은 **PR #14 (브랜치 `chore/mypy-config-consolidation`)가 main에 병합된 상태**를 가정한다.

PR #14의 변경 사항:
- `mypy.ini`에 `ignore_missing_imports = True` 추가 → 타입 미제공 서드파티 라이브러리(pydub, celery, whisper 등)의 import 노이즈 에러 29건 제거
- `pyproject.toml`의 dead `[tool.mypy]` 블록 제거

**PR #14가 병합되지 않은 상태에서는 mypy 에러 수가 194와 다르며(약 223), 본 SPEC의 Phase 계획이 무효가 된다.** 구현 착수 전 REQ-PRE-001로 전제를 검증한다.

---

## 7. Traceability

| TAG | Source | Requirement IDs |
|-----|--------|-----------------|
| SPEC-TYPING-001-PRE | Area 0 | REQ-PRE-001 |
| SPEC-TYPING-001-TYPE | Area 1 | REQ-TYPE-001 ~ REQ-TYPE-004 |
| SPEC-TYPING-001-NOSUP | Area 2 | REQ-NOSUP-001 ~ REQ-NOSUP-002 |
| SPEC-TYPING-001-RT | Area 3 | REQ-RT-001 ~ REQ-RT-003 |
| SPEC-TYPING-001-PHASE | Area 4 | REQ-PHASE-001 ~ REQ-PHASE-002 |
