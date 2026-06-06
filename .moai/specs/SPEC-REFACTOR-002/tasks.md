---
id: SPEC-REFACTOR-002
type: tasks
status: draft
parent_spec: SPEC-REFACTOR-001
decisions_resolved: true
---

# SPEC-REFACTOR-002 작업 체크리스트

> **결정 확정됨 (2026-06-06)**: D-1 (action_items 분리 등록), D-2 (sentiment 통합). 선행 OQ 게이트 없음 — 즉시 착수 가능.

## T1: action_items 분리 등록 (D-1, REQ-R2-002)

- [ ] **T1.1** 등록 직전 (METHOD, path) 교집합 0건 런타임 재검증 (CRUD 9개 vs 추출 2개)
- [ ] **T1.2** top-level `app/api/v1/action_items.py`(CRUD 422줄) → `app/api/v1/minutes/action_items_crud.py`로 이동
- [ ] **T1.3** `minutes/__init__.py`에서 `action_items_crud`의 `router` re-export (필요 시)
- [ ] **T1.4** `ROUTER_REGISTRY`에 `(action_items_crud.router, True)` 신규 등록 (추출 라우터 항목·기존 35개 튜플 순서 불변)
- [ ] **T1.5** 만약 path 충돌 발견 시: CRUD sub-path 재할당 + 선택 경로를 spec.md Section 4에 문서화

## T2: sentiment 통합 (D-2, REQ-R2-003)

- [ ] **T2.1** 병합 전 두 라우터 (METHOD, path) 교집합 0건 재검증 (분석 4개 vs 라이프사이클 4개)
- [ ] **T2.2** `minutes/sentiment.py`의 4개 엔드포인트(`POST /sentiment`, `GET /{task_id}/status`, `GET /{task_id}`, `DELETE /{task_id}`)를 `analytics/sentiment.py`로 이관(병합)
- [ ] **T2.3** 병합 후 `analytics/sentiment.py`의 (METHOD, path) 집합이 두 원본 합집합(8개)과 정확히 일치하는지 검증
- [ ] **T2.4** `minutes/sentiment.py` 삭제
- [ ] **T2.5** registry는 `analytics.sentiment`만 등록(이미 등록, 변경 없음) — minutes.sentiment는 애초 미등록이므로 튜플 불변 확인

## T3: 테스트 import 재지정 (Secondary, REQ-R2-004)

- [ ] **T3.1** top-level `action_items.py` 참조 5건 → `backend.app.api.v1.minutes.action_items_crud`:
  - `tests/unit/test_action_items_api_coverage.py:81, :519`
  - `tests/unit/test_coverage_gaps_final.py:390`
  - `tests/unit/test_coverage_direct_calls.py:316`
  - `tests/unit/test_scattered_gaps_round2.py:1089`
- [ ] **T3.2** `minutes/sentiment.py` 참조 2건 → `backend.app.api.v1.analytics.sentiment`:
  - `tests/unit/test_sentiment_additional.py:14`
  - `tests/unit/test_minutes_sentiment_coverage.py:27`
- [ ] **T3.3** grep으로 잔여 flat/고아 import 0건 확인 (AC-R2-3)

## T4: flat 라우터 잔존 검증 (Tertiary, REQ-R2-001)

- [ ] **T4.1** top-level `action_items.py`가 이동(T1.2)으로 사라졌는지 확인
- [ ] **T4.2** `ls app/api/v1/*.py` (registry.py, __init__.py 제외) → 0건 검증 (AC-R2-1)

## T5: baseline 재생성 + 무손실 게이트 (Final, REQ-R2-005, REQ-R2-006)

- [ ] **T5.1** 기존 `_route_snapshot_baseline.json`을 `.bak`으로 백업 (무손실 비교용)
- [ ] **T5.2** 라우트 baseline 재생성 (D-1 +9, D-2 +4 반영)
- [ ] **T5.3** 무손실 subset 게이트(AC-R2-8): 기존 148개 (path,method)가 재생성 baseline에 모두 포함, missing 0건
- [ ] **T5.4** delta 검증(AC-R2-7): entries 148 → 161(또는 실측), delta를 progress.md/spec.md에 문서화
- [ ] **T5.5** `pytest tests/unit/test_route_registry_invariance.py -o addopts=""` 통과(AC-R2-2)
- [ ] **T5.6** registry 기존 35개 튜플 순서·인증 diff 0건 확인 (AC-R2-6)
- [ ] **T5.7** 전체 스위트 그린: `pytest tests/ --ignore=tests/e2e/test_pipeline_e2e.py` → 0 failed (AC-R2-5)
  - **현재 baseline**: 3130 passed, 16 skipped, 0 failed (2026-06-06 실측)
- [ ] **T5.8** ruff check 통과
- [ ] **T5.9** sentiment 1개 모듈 + action_items 2개 모듈 등록 확인 (AC-R2-4)

## 의존 관계

```
T1 (action_items 분리 등록)  ─┐
T2 (sentiment 통합)          ─┴─> T3 (import 재지정) ─> T4 (flat 잔존 검증) ─> T5 (baseline 재생성 + 게이트)
```

> T1, T2는 서로 독립적이므로 병렬 가능. T3는 T1/T2의 새 모듈 경로 확정에 의존. T5는 전 작업 완료 후.

## Traceability

| 작업 그룹 | Requirement IDs | AC IDs |
|-----------|-----------------|--------|
| T1 (D-1) | REQ-R2-002 | AC-R2-1, AC-R2-4, AC-R2-7 |
| T2 (D-2) | REQ-R2-003 | AC-R2-4, AC-R2-7 |
| T3 | REQ-R2-004 | AC-R2-3 |
| T4 | REQ-R2-001 | AC-R2-1 |
| T5 | REQ-R2-005, REQ-R2-006 | AC-R2-2, AC-R2-5, AC-R2-6, AC-R2-7, AC-R2-8 |
