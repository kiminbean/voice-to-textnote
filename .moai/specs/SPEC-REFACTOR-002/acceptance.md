---
id: SPEC-REFACTOR-002
type: acceptance
status: completed
parent_spec: SPEC-REFACTOR-001
decisions_resolved: true
---

# SPEC-REFACTOR-002 수용 기준 (Acceptance Criteria)

> **확정된 결정 (2026-06-06)**: D-1 (action_items 분리 등록, 라우트 +9), D-2 (sentiment 통합, 라우트 +4). spec.md Section 6 참조.

## 1. Definition of Done

- [ ] flat 라우터 모듈 0건 (top-level `action_items.py` → `minutes/action_items_crud.py` 이동 완료)
- [ ] **D-1 완료**: CRUD 라우터가 `ROUTER_REGISTRY`에 등록되어 실제 서빙됨. 추출 라우터도 유지·서빙됨 (둘 다 서빙)
- [ ] **D-2 완료**: `minutes/sentiment.py`의 4개 엔드포인트가 `analytics/sentiment.py`로 병합됨. 고아 파일 삭제됨. sentiment 모듈 1개만 존재
- [ ] 잔여 flat-style 테스트 import 재지정 완료 (action_items 5건 → CRUD 모듈, sentiment 2건 → analytics 모듈)
- [ ] **기존 148개 서빙 라우트 무손실** (subset 게이트 통과) + delta(+13) 문서화 후 baseline 재생성
- [ ] registry 기존 35개 튜플 순서·인증 정책 불변 (batch→transcription 보존)
- [ ] 전체 백엔드 스위트 그린 (e2e 9건 제외), 커버리지 게이트 충족

## 2. 수용 검증 (Acceptance Checks)

### AC-R2-1: flat 라우터 0건 (REQ-R2-001)

```bash
cd /Users/ibkim/Projects/voice-to-textnote/backend
ls -1 app/api/v1/*.py | grep -v -E "^app/api/v1/(__init__|registry)\.py$" | wc -l
```

**통과 조건**: 출력 `0` (top-level `action_items.py`가 `minutes/action_items_crud.py`로 이동되어 top-level에서 사라짐).

### AC-R2-2: 라우트 baseline 무손실 + 재생성 통과 (REQ-R2-005)

```bash
cd /Users/ibkim/Projects/voice-to-textnote/backend
../venv/bin/python -m pytest tests/unit/test_route_registry_invariance.py -o addopts="" -q
```

**통과 조건**: `passed` — **delta(+13) 문서화 후 재생성된** `_route_snapshot_baseline.json` 기준으로 통과. 순수-이동의 "바이트 단위 불변"이 아니라, 기존 148개 무손실 + 신규 13개 추가가 정상 동작임에 유의.

### AC-R2-8: 기존 라우트 무손실 (subset 게이트) (REQ-R2-005)

```bash
cd /Users/ibkim/Projects/voice-to-textnote/backend
# 재생성 직전 기존 baseline을 백업(old)하고, 재생성 후 new와 비교
../venv/bin/python - <<'PY'
import json
old = json.load(open("tests/unit/_route_snapshot_baseline.json.bak"))  # 재생성 전 백업
new = json.load(open("tests/unit/_route_snapshot_baseline.json"))      # 재생성 후
def norm(d): return {(x["path"], tuple(sorted(x.get("methods", [])))) for x in (d if isinstance(d, list) else d.get("routes", d))}
o, n = norm(old), norm(new)
missing = o - n
print("missing (must be empty):", missing)
print("added (delta):", len(n - o))
assert not missing, f"REGRESSION: {len(missing)} existing routes lost"
print("PASS: 기존 라우트 무손실, delta =", len(n - o))
PY
```

**통과 조건**: `missing` 집합이 비어 있음(기존 148개 1건도 누락 없음), `added` delta가 문서화된 값(+13 또는 실측)과 일치.

### AC-R2-3: 잔여 flat-style / 고아 참조 0건 (REQ-R2-004)

```bash
cd /Users/ibkim/Projects/voice-to-textnote/backend
grep -rEn "from backend\.app\.api\.v1\.action_items import|from backend\.app\.api\.v1\.minutes\.sentiment import|from backend\.app\.api\.v1\.minutes import sentiment" tests/ | wc -l
```

**통과 조건**: 출력 `0` — top-level `action_items.py` 참조(5건)는 `minutes.action_items_crud`로, `minutes/sentiment.py` 참조(2건)는 `analytics.sentiment`로 모두 재지정됨.

### AC-R2-4: sentiment 단일 모듈 + action_items 2개 모듈 공존·등록 (REQ-R2-002, REQ-R2-003)

```bash
cd /Users/ibkim/Projects/voice-to-textnote/backend
echo "sentiment 파일 수 (1 기대):" && find app/api/v1 -name "sentiment.py" | wc -l
echo "action_items 모듈 (2 기대: 추출 + crud):" && find app/api/v1 -name "action_items.py" -o -name "action_items_crud.py" | sort
echo "registry에 CRUD 등록 확인:" && grep -c "action_items_crud" app/api/v1/registry.py
```

**통과 조건**:
- sentiment 파일 **1개** (`analytics/sentiment.py`만, `minutes/sentiment.py` 삭제됨).
- action_items 모듈 **2개** (`minutes/action_items.py` 추출 + `minutes/action_items_crud.py` CRUD), **둘 다 registry 등록·서빙**.
- registry에 `action_items_crud` 참조 **1건 이상** (CRUD 신규 등록 증명).

### AC-R2-7: 라우트 delta 검증 (REQ-R2-002, REQ-R2-003, REQ-R2-005)

```bash
cd /Users/ibkim/Projects/voice-to-textnote/backend
../venv/bin/python -c "import json; d=json.load(open('tests/unit/_route_snapshot_baseline.json')); n=len(d) if isinstance(d,list) else len(d.get('routes',d)); print('baseline entries:', n)"
```

**통과 조건**: 재생성 후 entries 수 = 148 + 13 = **161** (D-1 +9, D-2 +4), 또는 구현 실측값이 SPEC/progress에 문서화된 delta와 일치.

### AC-R2-5: 전체 스위트 그린 (글로벌 게이트)

```bash
cd /Users/ibkim/Projects/voice-to-textnote/backend
../venv/bin/python -m pytest tests/ --ignore=tests/e2e/test_pipeline_e2e.py
```

**통과 조건**: `0 failed` (skipped 허용), 프로젝트 quality 커버리지 게이트 충족. **현재 baseline**: 3130 passed, 16 skipped (2026-06-06 실측) — 재배치 후 신규 서빙 라우트로 인한 추가 테스트 포함 시 passed 수 증가 가능.

### AC-R2-6: registry 기존 튜플 순서·인증 불변 (REQ-R2-006)

```bash
cd /Users/ibkim/Projects/voice-to-textnote/backend
git diff app/api/v1/registry.py
```

**통과 조건**: 기존 35개 튜플의 순서·`requires_api_key` 값 변경 **0건** (batch→transcription 순서 보존). 허용되는 diff: D-1 CRUD 라우터 신규 등록 라인 추가, D-2 sentiment 관련 import는 이미 `analytics.sentiment`이므로 변경 없음(minutes.sentiment는 애초에 미등록).

## 3. 테스트 시나리오 (Given-When-Then)

### 시나리오 1: action_items 분리 등록 후 CRUD 서빙 (D-1)

- **Given**: top-level `action_items.py`(CRUD 9개)는 registry-고아, `minutes/action_items.py`(추출 2개)는 등록됨
- **When**: CRUD를 `minutes/action_items_crud.py`로 이동하고 `ROUTER_REGISTRY`에 신규 등록
- **Then**: `/action-items` prefix 하에 CRUD 9개 + 추출 2개가 충돌 없이 서빙되고(경로 교집합 0건), 라우트 테이블이 +9 확장됨. top-level flat 파일은 사라짐(AC-R2-1)

### 시나리오 2: sentiment 통합 후 전 기능 서빙 (D-2)

- **Given**: `analytics/sentiment.py`(분석 4개, 등록), `minutes/sentiment.py`(라이프사이클 4개, 고아)
- **When**: minutes 4개 엔드포인트를 `analytics/sentiment.py`로 병합하고 `minutes/sentiment.py` 삭제
- **Then**: `/sentiment` prefix 하에 8개 엔드포인트가 충돌 없이 서빙되고(교집합 0건), 라우트 테이블이 +4 확장됨. sentiment 모듈 1개만 존재(AC-R2-4)

### 시나리오 3: 테스트 import 재지정

- **Given**: top-level `action_items.py` 참조 5건, `minutes/sentiment.py` 참조 2건
- **When**: action_items 참조를 `minutes.action_items_crud`로, sentiment 참조를 `analytics.sentiment`로 재지정
- **Then**: 잔여 flat/고아 참조 0건(AC-R2-3)이고, 재지정된 테스트가 새 모듈에서 통과

### 시나리오 4: 기존 라우트 무손실 + delta 문서화

- **Given**: reconciliation 전 baseline 148 entries
- **When**: baseline을 백업 후 재생성
- **Then**: 기존 148개 (path,method)가 재생성 baseline의 subset으로 모두 포함(missing 0건, AC-R2-8)이고, delta = +13(AC-R2-7)

### 시나리오 5: 전체 회귀 없음

- **Given**: D-1 + D-2 + import 재지정 + baseline 재생성 완료
- **When**: `pytest tests/ --ignore=tests/e2e/test_pipeline_e2e.py` 실행
- **Then**: 0 failed, 커버리지 게이트 충족, registry 기존 튜플 diff 0건(AC-R2-6)

## 4. 품질 게이트

| 항목 | 기준 |
|------|------|
| flat 라우터 | 0건 (AC-R2-1) |
| 기존 라우트 무손실 | subset 게이트 missing 0건 (AC-R2-8) |
| 라우트 delta | +13 (또는 문서화된 실측) (AC-R2-7) |
| route invariance | 재생성 baseline 기준 passed (AC-R2-2) |
| sentiment 모듈 | 1개 (AC-R2-4) |
| action_items 모듈 | 2개, 둘 다 등록 (AC-R2-4) |
| 잔여 flat/고아 참조 | 0건 (AC-R2-3) |
| 테스트 스위트 | 0 failed (e2e 제외) (AC-R2-5) |
| 커버리지 | 프로젝트 quality 설정 충족 |
| ruff | All checks passed |
| registry SSOT | 기존 튜플 순서·인증 불변 (AC-R2-6) |

## 5. Traceability

| AC ID | Requirement IDs | 결정 |
|-------|-----------------|------|
| AC-R2-1 | REQ-R2-001 | D-1 (이동) |
| AC-R2-2 | REQ-R2-005 | D-1/D-2 (baseline 재생성) |
| AC-R2-3 | REQ-R2-004 | D-1/D-2 (import 재지정) |
| AC-R2-4 | REQ-R2-002, REQ-R2-003 | D-1 (분리 등록), D-2 (통합) |
| AC-R2-5 | REQ-R2-001 ~ REQ-R2-006 (글로벌) | — |
| AC-R2-6 | REQ-R2-006 | — |
| AC-R2-7 | REQ-R2-002, REQ-R2-003, REQ-R2-005 | D-1/D-2 (delta) |
| AC-R2-8 | REQ-R2-005 | 무손실 게이트 |
