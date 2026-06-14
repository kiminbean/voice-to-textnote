---
id: SPEC-TYPING-001
version: 1.0.0
status: completed
created: 2026-06-08
updated: 2026-06-14
author: MoAI
---

# 인수 기준: SPEC-TYPING-001 Mypy Static Type Error Resolution

## 품질 게이트 (Quality Gates)

### TRUST 5 검증

| 항목 | 기준 | 측정 방법 |
|------|------|-----------|
| Tested | 3174 passed / 16 skipped 유지, 커버리지 ≥ 85% | `./venv/bin/python -m pytest backend/` |
| Readable | ruff lint 0 errors | `./venv/bin/python -m ruff check backend/` |
| Unified | ruff format 일치 | `./venv/bin/python -m ruff format --check backend/` |
| Secured | 기존 보안 테스트 통과 (회귀 없음) | `./venv/bin/python -m pytest backend/ -k security` |
| Trackable | Conventional commit 메시지 | `git log --oneline` 확인 |

---

## 전제 조건 인수 기준

### AC-PRE-001: PR #14 병합 전제 검증

**Given** 작업 디렉토리가 main 기준이고 PR #14가 병합됨
**When** `./venv/bin/python -m mypy backend/`를 실행함
**Then** 에러 수가 약 194개여야 하며, `mypy.ini`에 `ignore_missing_imports = True`가 존재해야 함

```gherkin
Scenario: mypy 설정 전제 확인
  Given mypy.ini가 존재함
  When grep "ignore_missing_imports = True" mypy.ini 실행
  Then 매치가 1건 이상이어야 함
  And pyproject.toml에 [tool.mypy] 블록이 없어야 함
```

---

## 최종 인수 기준 (Overall)

### AC-FINAL-001: mypy 에러 0 달성

**Given** 모든 Phase가 완료됨
**When** `./venv/bin/python -m mypy backend/`를 실행함
**Then** "Success: no issues found" 또는 에러 0개를 보고해야 함

```gherkin
Scenario: 전체 타입 에러 제거
  Given 194개 baseline 에러가 수정됨
  When ./venv/bin/python -m mypy backend/ 실행
  Then 종료 코드는 0이어야 함
  And 출력에 "error:"가 0건이어야 함
```

### AC-FINAL-002: 런타임 동작 보존

**Given** 타입 수정이 완료됨
**When** `./venv/bin/python -m pytest backend/`를 실행함
**Then** 3174 passed / 16 skipped이어야 하고 커버리지는 85% 이상이어야 함

```gherkin
Scenario: 테스트 회귀 없음
  Given 모든 타입 수정이 적용됨
  When pytest backend/ 실행
  Then 통과 수는 3174, skip 수는 16이어야 함
  And 실패(failed) 수는 0이어야 함
  And 커버리지는 85% 이상이어야 함
```

### AC-FINAL-003: Lint/Format 통과

**Given** 타입 수정이 완료됨
**When** ruff 검사를 실행함
**Then** check와 format --check 모두 통과해야 함

```gherkin
Scenario: 코드 스타일 유지
  When ./venv/bin/python -m ruff check backend/ 실행
  Then 에러가 0건이어야 함
  When ./venv/bin/python -m ruff format --check backend/ 실행
  Then 재포맷 대상이 0건이어야 함
```

### AC-FINAL-004: 타입 검사기 무력화 금지

**Given** 수정이 완료됨
**When** 설정 파일과 코드를 검사함
**Then** `disable_error_code`가 없고, blanket `# type: ignore`가 없어야 함

```gherkin
Scenario: 검사 약화 금지 검증
  When grep -rn "disable_error_code" mypy.ini pyproject.toml 실행
  Then 매치가 0건이어야 함
  When grep "# type: ignore" 중 코드 미지정(blanket) 항목을 검사
  Then blanket ignore가 0건이어야 함
  And 모든 "# type: ignore[code]"는 인라인 사유 주석을 동반해야 함
```

---

## Phase별 인수 기준 (Exit Criteria)

### AC-PHASE-1: services/ Hotspots

**Given** Phase 1 대상 4개 파일이 수정됨
**When** 해당 파일에 대해 mypy를 실행함
**Then** 4개 파일의 에러 합이 0이어야 함 (83 → 0)

```gherkin
Scenario: Phase 1 종료 검증
  When ./venv/bin/python -m mypy \
    backend/services/advanced_search.py \
    backend/services/quality_service.py \
    backend/services/action_item_service.py \
    backend/services/enhanced_statistics.py 실행
  Then 에러가 0건이어야 함
  And pytest backend/ 가 3174 passed로 유지되어야 함
```

### AC-PHASE-2: API 계층

**Given** Phase 2 대상 5개 파일이 수정됨
**When** 해당 파일에 대해 mypy를 실행함
**Then** 5개 파일의 에러 합이 0이어야 함 (44 → 0)

```gherkin
Scenario: Phase 2 종료 검증
  When ./venv/bin/python -m mypy \
    backend/app/api/v1/minutes/action_items_crud.py \
    backend/app/api/v1/analytics/sentiment.py \
    backend/app/api/v1/transcription/transcription.py \
    backend/app/api/v1/collaboration/bookmarks.py \
    backend/app/api/v1/audio/enhanced_preprocess.py 실행
  Then 에러가 0건이어야 함
  And pytest backend/ 가 3174 passed로 유지되어야 함
```

### AC-PHASE-3: 나머지 프로덕션 파일

**Given** Phase 3 대상 약 28개 파일이 수정됨
**When** mypy를 전체 실행함
**Then** 프로덕션 코드 에러가 0이어야 하고 잔여는 테스트 파일 24건만 남아야 함 (43 → 0)

```gherkin
Scenario: Phase 3 종료 검증
  Given Phase 1~2가 완료됨
  When ./venv/bin/python -m mypy backend/ 실행
  Then 프로덕션 코드(170건) 에러가 0이어야 함
  And 잔여 에러는 테스트 파일에만 존재해야 함 (약 24건)
```

### AC-PHASE-4: 테스트 파일

**Given** Phase 4 대상 테스트 파일이 수정됨
**When** mypy를 전체 실행함
**Then** 전체 에러가 0이어야 함 (24 → 0, 누적 194 → 0)

```gherkin
Scenario: Phase 4 종료 검증 (최종)
  Given Phase 1~3이 완료됨
  When ./venv/bin/python -m mypy backend/ 실행
  Then 전체 에러가 0이어야 함
  And pytest backend/ 가 3174 passed / 16 skipped로 유지되어야 함
```

---

## Definition of Done

- [ ] AC-PRE-001: PR #14 병합 전제 확인 (baseline ≈ 194)
- [ ] AC-PHASE-1: services/ hotspots 4파일 mypy 0
- [ ] AC-PHASE-2: API 계층 5파일 mypy 0
- [ ] AC-PHASE-3: 나머지 프로덕션 파일 mypy 0 (테스트만 잔여)
- [ ] AC-PHASE-4: 테스트 파일 mypy 0 (전체 194 → 0)
- [ ] AC-FINAL-001: `mypy backend/` 0 에러
- [ ] AC-FINAL-002: 3174 passed / 16 skipped, 커버리지 ≥ 85%
- [ ] AC-FINAL-003: ruff check + format --check 통과
- [ ] AC-FINAL-004: `disable_error_code` 없음, blanket `# type: ignore` 없음, 모든 `# type: ignore[code]`에 사유 주석
