---
id: SPEC-TYPING-001
version: 1.0.0
status: draft
created: 2026-06-08
author: MoAI
---

# 구현 계획: SPEC-TYPING-001 Mypy Static Type Error Resolution

## 접근 전략

### 원칙
1. **무력화 금지**: `disable_error_code`, 관대한 설정, blanket `# type: ignore` 사용 금지. 실제 타입 정확성으로만 해소한다.
2. **원천 우선 수정**: Pydantic 모델 / SQLAlchemy 모델 속성 / 서비스 시그니처에서 수정하고, 불가피할 때만 호출 지점에서 좁힌다.
3. **런타임 불변**: 매 변경 후 `pytest backend/`로 3174 passed / 16 skipped 유지를 확인한다.
4. **에러 집중도 기반 순서**: hotspot 우선, 프로덕션(170) → 테스트(24).
5. **Phase별 검증 관문**: 각 Phase 종료 시 해당 파일의 mypy 에러를 0으로 만든다.

### 전제 조건
- **[HARD]** PR #14 (`chore/mypy-config-consolidation`) 병합 완료. 미병합 시 baseline 무효.
- 착수 검증: `./venv/bin/python -m mypy backend/ 2>&1 | tail -1` → 약 194개 에러 확인.
- Phase 착수 전 대상 파일에 대해 mypy 재실행하여 현행 행 번호/에러 목록 확정 (A-6).

---

## Phase 1: services/ Hotspots (Priority High)

대상: 83개 에러 (4 파일). 서비스 시그니처 변경이 호출 지점에 파급되므로 가장 먼저, 가장 신중하게 처리한다.

### Primary Goal: 서비스 반환/시그니처 타입 정합

#### Step 1-1: `services/advanced_search.py` (28)
- DP-4 중심: `type[TaskResult]`에 인스턴스 속성 접근하는 코드를 인스턴스 참조로 정정.
- 검색 결과 dict 반환을 명시 타입(Pydantic 또는 `TypedDict`)으로 정정.

#### Step 1-2: `services/quality_service.py` (27)
- DP-4 중심: `operator` 에러(`str * float` 등) 피연산자 타입 정정.
- 점수 계산 변수의 `var-annotated` 에러에 명시 어노테이션 부여.

#### Step 1-3: `services/action_item_service.py` (19)
- DP-3 중심: `str` ↔ `datetime` 할당(`:242`) 정정 — 모델 필드 타입 또는 파싱 로직 수정.
- `Sequence` ↔ `list` 반환(`:188`) — 반환 타입 어노테이션을 실제 타입에 맞춤.

#### Step 1-4: `services/enhanced_statistics.py` (9)
- 집계 결과 타입 어노테이션 및 `union-attr` 좁히기.

**검증**: `./venv/bin/python -m mypy backend/services/advanced_search.py backend/services/quality_service.py backend/services/action_item_service.py backend/services/enhanced_statistics.py` → 0 에러. 이후 `pytest backend/` 전체 통과 확인.

---

## Phase 2: API 계층 (Priority High)

대상: 44개 에러 (5 파일). Phase 1에서 정정된 서비스 시그니처를 소비하는 계층이므로 Phase 1 완료 후 진행한다.

### Primary Goal: dict → Pydantic 응답 모델 변환 정합

#### Step 2-1: `app/api/v1/minutes/action_items_crud.py` (19)
- DP-1: `Incompatible return value type (got "ActionItem", expected "ActionItemResponse")`(`:313`) — `ActionItemResponse.model_validate(...)` 명시 변환.
- DP-2: `**dict` 언패킹(`:105`) — 명시적 키워드 인자 또는 `TypedDict` 필터로 전환.

#### Step 2-2: `app/api/v1/analytics/sentiment.py` (10)
- DP-1: `"dict[Any, Any]" has no attribute "overall_score"` — 서비스 반환을 타입드 모델로 정정 후 속성 접근.

#### Step 2-3: `app/api/v1/transcription/transcription.py` (5)
#### Step 2-4: `app/api/v1/collaboration/bookmarks.py` (5)
#### Step 2-5: `app/api/v1/audio/enhanced_preprocess.py` (5)
- 각 라우터의 응답 모델 변환 및 인자 타입 정합.

**검증**: 대상 5개 파일 mypy 0 에러 + `pytest backend/` 전체 통과.

---

## Phase 3: 나머지 프로덕션 파일 (Priority Medium)

대상: 43개 에러 (약 28 파일, 각 1~3개). 포함 예: `pipeline/summary_generator.py` (4).

### Primary Goal: 잔여 프로덕션 타입 에러 제거

- 파일당 에러 수가 적어 위험이 낮음. 패턴(DP-1~DP-4)별로 일괄 처리.
- `var-annotated`, `assignment`, `arg-type` 다수 — 명시 어노테이션과 형변환 중심.

**검증**: `./venv/bin/python -m mypy backend/` 실행 시 프로덕션 코드(170건) 전부 0. 잔여는 테스트 파일 24건만 남아야 함.

---

## Phase 4: 테스트 파일 (Priority Low)

대상: 24개 에러. 포함: `tests/unit/test_speaker_voice_service.py` (12), `tests/unit/test_template_parser.py` (4) 외.

### Primary Goal: 테스트 코드 타입 에러 제거

- 테스트의 mock/fixture 타입 어노테이션 정정.
- 테스트는 격리되어 위험이 가장 낮으므로 마지막에 처리.

**검증**: `./venv/bin/python -m mypy backend/` → **0 에러** (전체 달성).

---

## 최종 검증 (Definition of Done)

```bash
./venv/bin/python -m mypy backend/                 # 0 errors
./venv/bin/python -m pytest backend/               # 3174 passed, 16 skipped, cov ≥ 85%
./venv/bin/python -m ruff check backend/           # clean
./venv/bin/python -m ruff format --check backend/  # clean
grep -rn "disable_error_code" mypy.ini pyproject.toml  # 결과 없음
grep -rn "# type: ignore" backend/ | grep -v "\[" # 코드 미지정 ignore 없음
```

## 위험 및 대응

| 위험 | 확률 | 대응 |
|------|------|------|
| 서비스 시그니처 변경이 다수 호출 지점을 깨뜨림 | 중간 | Phase 1에서 호출 지점 동시 업데이트 + 즉시 `pytest` 회귀 확인 |
| 형변환 추가가 런타임 동작을 바꿈 | 낮음 | `model_validate`는 검증 단계 추가일 뿐 데이터 불변. 테스트로 보증 |
| 서드파티 한계로 정상 수정 불가 | 낮음 | `# type: ignore[code]` + 사유 주석 (REQ-NOSUP-002 예외 조항) |
| baseline 행 번호 이동 | 중간 | Phase 착수 전 mypy 재실행으로 현행 목록 확정 (A-6) |
