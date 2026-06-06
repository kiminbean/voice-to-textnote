---
id: SPEC-REFACTOR-002
type: plan
status: draft
parent_spec: SPEC-REFACTOR-001
---

# SPEC-REFACTOR-002 구현 계획

## 1. 개요

SPEC-REFACTOR-001 Phase 4(라우터 도메인 그룹핑)의 마감 SPEC. 실측 결과 파일 재배치는 이미 대부분 완료되었고, 본 SPEC은 **잔여 flat 라우터 제거 + 중복 라우터 정리 + 잔여 테스트 import 마이그레이션 + 라우트 baseline 확장(delta)**을 수행한다.

> **결정 확정됨 (2026-06-06)**: spec.md Section 6 Resolved Decisions에서 두 reconciliation이 확정되었다.
> - **D-1 (action_items)**: 분리 등록(co-register) — CRUD 라우터를 신규 등록하여 서빙, 추출 라우터 유지. 라우트 **+9**.
> - **D-2 (sentiment)**: 통합(merge) — minutes 엔드포인트를 `analytics/sentiment.py`로 병합, 고아 삭제. 라우트 **+4**.
> AST 분석으로 두 케이스 모두 경로 충돌 0건이 검증되어 안전하게 실행 가능하다.

## 2. 검증 환경 (SPEC-REFACTOR-001 상속)

- venv Python 경로: `backend/../venv/bin/python` (예: `cd backend && ../venv/bin/python -m pytest ...`)
- import 접두사: `backend.` (예: `from backend.app.api.v1.minutes.action_items import router`)
- 커버리지 게이트가 실패 식별을 방해하면 `-o addopts=""`로 비활성화하여 실패 목록만 확인.
- 전체 게이트는 `--ignore=tests/e2e/test_pipeline_e2e.py`로 실행(e2e 9건 환경 이슈 제외).

## 3. 기술 접근

### 3.1 핵심 원칙

1. **기존 무손실 + 의도적 확장**: 기존 서빙 중인 148개 라우트는 **1건도 제거·변경하지 않는다**(subset 게이트로 증명). reconciliation으로 추가되는 고아→서빙 전환 라우트(+13)는 **delta를 문서화한 뒤 `_route_snapshot_baseline.json`을 재생성**한다. `test_route_registry_invariance.py`는 재생성 baseline 기준으로 통과한다.
2. **SSOT 보존**: registry.py(`ROUTER_REGISTRY`)의 **기존 35개 튜플**의 순서·`requires_api_key` 플래그는 변경하지 않는다(batch→transcription 불변). D-1으로 CRUD 라우터 1개 신규 등록, D-2로 sentiment import 경로 갱신만 수행한다.
3. **기능 보존(preserve functionality)**: D-1/D-2 모두 엔드포인트를 삭제·축소하지 않는다. CRUD는 신규 서빙, sentiment는 두 원본의 합집합을 단일 모듈로 병합한다.
4. **소비자 추적**: 라우터 모듈을 import하는 모든 테스트를 grep으로 추적 후 일괄 재지정한다.

### 3.2 확정된 reconciliation 실행 명세

**D-1 (action_items 분리 등록)**:
- `app/api/v1/action_items.py`(CRUD 422줄)를 `app/api/v1/minutes/action_items_crud.py`로 이동(파일명 충돌 회피).
- `ROUTER_REGISTRY`에 CRUD 라우터를 `(action_items_crud.router, True)`로 신규 등록(추출 라우터 항목은 그대로 유지).
- 등록 전 두 라우터 (METHOD, path) 교집합 0건 재검증.
- 결과: `/action-items` prefix 하 CRUD 9개 + 추출 2개 공존, 라우트 **+9**.

**D-2 (sentiment 통합)**:
- `app/api/v1/minutes/sentiment.py`의 4개 엔드포인트(`POST /sentiment`, `GET /{task_id}/status`, `GET /{task_id}`, `DELETE /{task_id}`)를 생존 모듈 `app/api/v1/analytics/sentiment.py`로 이관(병합).
- 병합 후 `minutes/sentiment.py` 삭제.
- registry는 `analytics.sentiment`만 등록(이미 등록됨, 변경 없음). minutes/sentiment는 애초에 미등록이었으므로 registry 튜플은 불변.
- 결과: `/sentiment` prefix 하 분석 4개 + 라이프사이클 4개 공존, 라우트 **+4**.

## 4. 마일스톤 (Priority 기반)

### Primary Goal (Priority High): reconciliation 실행 (D-1 + D-2)

- **D-1 (REQ-R2-002)**: CRUD 라우터를 `minutes/action_items_crud.py`로 이동 + `ROUTER_REGISTRY` 신규 등록. 경로 충돌 0건 재검증.
- **D-2 (REQ-R2-003)**: `minutes/sentiment.py` 4개 엔드포인트를 `analytics/sentiment.py`로 병합 + 고아 파일 삭제.
- 의존: 결정 확정됨 → 즉시 착수 가능.

### Secondary Goal (Priority High): 테스트 import 재지정

- 잔여 flat-style import 재지정(REQ-R2-004):
  - top-level `action_items.py` 참조 5건 → `backend.app.api.v1.minutes.action_items_crud`.
  - `minutes/sentiment.py` 참조 2건 → `backend.app.api.v1.analytics.sentiment`(병합 후 엔드포인트 존재).
- 의존: Primary Goal 완료(새 모듈 경로·병합 확정) 후 착수.

### Tertiary Goal (Priority Medium): flat 라우터 제거

- top-level `action_items.py`는 D-1에서 `minutes/action_items_crud.py`로 이동되므로 top-level에서 사라진다(REQ-R2-001) → AC-R2-1(flat 0건) 충족.
- 의존: Primary(이동) + Secondary(참조 재지정) 완료 후 잔존 검증.

### Final Goal (Priority High): baseline 재생성 + 무손실 게이트

- **baseline 재생성(REQ-R2-005)**: delta(+9 CRUD, +4 sentiment lifecycle)를 문서화하고 `_route_snapshot_baseline.json`을 재생성. 재생성 전 148개 (path,method)가 재생성 후 baseline의 subset임을 검증(AC-R2-8 무손실 게이트).
- `test_route_registry_invariance.py`가 새 baseline 기준 통과(AC-R2-2).
- registry 기존 튜플 순서·인증 불변 확인(REQ-R2-006, AC-R2-6).
- 전체 스위트 그린(AC-R2-5).
- 의존: 전 마일스톤 완료 후 최종 게이트.

## 5. 아키텍처 설계 방향

### Before (현재)

```
api/v1/
├── action_items.py          # flat, CRUD(422줄), registry-고아
├── registry.py              # minutes.action_items, analytics.sentiment 등록
├── analytics/sentiment.py   # registry 등록(256줄)
├── minutes/action_items.py  # registry 등록, 추출(177줄)
└── minutes/sentiment.py     # registry-고아(153줄)
```

### After (목표, D-1/D-2 적용 후)

```
api/v1/
├── registry.py                    # 기존 35개 튜플 불변 + CRUD 라우터 1개 신규 등록
├── __init__.py
├── minutes/
│   ├── action_items.py            # 추출 API 유지 (registry 등록)
│   └── action_items_crud.py       # CRUD API 이동·신규 등록 (NEW, D-1)
├── analytics/
│   └── sentiment.py               # 분석 4개 + 병합된 라이프사이클 4개 (D-2 merge)
├── <other domains>/               # 7개 서브패키지만 — flat 라우터 0건
   (minutes/sentiment.py 삭제됨, top-level action_items.py 이동됨)
```

## 6. 리스크 및 대응

| 리스크 | 확률 | 대응 |
|--------|------|------|
| baseline 재생성이 기존 148개 라우트를 실수로 변경/삭제 | 중간 | AC-R2-8 subset 게이트: 재생성 전 148개 (path,method)가 재생성 후 baseline에 모두 포함됨을 기계 검증. 위반 시 실패 처리 |
| D-1 CRUD와 추출 라우터 경로가 실제로 충돌(AST 분석 오류 가능성) | 낮음 | 등록 직전 두 라우터 (METHOD, path) 교집합을 런타임 재검증. 충돌 시 CRUD sub-path 재할당 후 Section 4 문서화 |
| D-2 병합 시 sentiment 엔드포인트 누락/중복 | 중간 | 병합 전후 `analytics/sentiment.py`의 (METHOD, path) 집합이 두 원본의 합집합(8개)과 정확히 일치하는지 검증 |
| 고아/이동 라우터 참조 테스트 깨짐 | 높음(미처리 시) | 삭제·이동 전 grep으로 모든 참조 추적(5+2건), 참조 테스트를 새 모듈로 선재지정 |
| baseline entries 수 불일치 (부모 문서 "135" vs 실측 148) | 낮음 | 실측 baseline(148 entries)을 권위로 사용. 재생성 후 예상 161(=148+13)을 실측으로 최종 확정 |

## 7. Traceability

| 마일스톤 | Requirement IDs |
|----------|-----------------|
| Primary (중복 정리) | REQ-R2-002, REQ-R2-003 |
| Secondary (테스트 import) | REQ-R2-004 |
| Tertiary (flat 제거) | REQ-R2-001 |
| Final (불변성) | REQ-R2-005, REQ-R2-006 |
