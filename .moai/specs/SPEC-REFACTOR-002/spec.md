---
id: SPEC-REFACTOR-002
version: 1.0.0
status: completed
created: 2026-06-06
updated: 2026-06-13
decisions_resolved: true
author: MoAI
priority: medium
title: API Router Domain Grouping Completion and Duplicate Cleanup
milestone: 0.2.0
tags: [refactoring, architecture, api-structure, router-grouping, cleanup]
parent_spec: SPEC-REFACTOR-001
related_specs:
  - SPEC-REFACTOR-001
  - SPEC-ACTION-001
---

# SPEC-REFACTOR-002: API 라우터 도메인 그룹핑 완료 및 중복 정리

## 1. Environment (현재 상황)

### 부모 SPEC와의 관계

본 SPEC은 **SPEC-REFACTOR-001 Phase 4(API 라우터 도메인 그룹핑)** 의 미완료 잔여분을 마감하는 0.2.0 마일스톤의 첫 기술 부채 SPEC이다.

SPEC-REFACTOR-001 Iteration 3(`Section 8`)은 REQ-RM-C1(도메인 그룹핑 파일 재배치)과 AC-C4(flat 라우터 0건)를 **연기(Deferred)** 하고, registry-only(Option B)만 채택한 것으로 기록되어 있다. 그 근거는 de-risker였다:

> "~40개 테스트가 27개 라우터 서브모듈을 직접 import → 파일 이동 시 import 대량 깨짐"

### 검증된 현재 상태 (2026-06-06 실측, 부모 문서와 불일치)

부모 SPEC 문서의 서술과 달리, **실제 디스크/Git 상태는 도메인 그룹핑이 이미 대부분 수행된 상태**다. 후속 커밋(`03637f1 refactor(api): SPEC-REFACTOR-001 Phase 4 — 라우터 도메인 그룹핑`)이 실제로 파일 이동을 수행했으나 부모 SPEC 문서는 갱신되지 않았다.

```
backend/app/api/v1/
├── __init__.py
├── registry.py          # ROUTER_REGISTRY (SSOT, 35개 라우터 튜플)
├── action_items.py      # ⚠️ flat 라우터 1개 잔존 (AC-C4 미충족 원인)
├── admin/               # admin, calendar, export, health, history, templates
├── analytics/           # advanced_search, dashboard, enhanced_statistics, search, sentiment, statistics, vocabulary
├── audio/               # audio, audio_analysis, audio_preprocess, enhanced_preprocess, qa, quality_assessment
├── auth/                # auth, devices
├── collaboration/       # bookmarks, meetings, speakers, teams, versions, webhooks
├── minutes/             # action_items, keywords, minutes, sentiment, summary, tags
└── transcription/       # batch, diarization, stream, transcription
```

### 발견된 문제점 (Anti-patterns)

| ID | 문제 | 심각도 | 영향 범위 | 검증 증거 |
|----|------|--------|-----------|-----------|
| AP-1 | **flat 라우터 잔존**: `action_items.py`가 top-level에 남아 AC-C4(flat 0건) 미충족 | 낮음 | `api/v1/` | `ls api/v1/*.py` → `__init__.py`, `registry.py`, `action_items.py` |
| AP-2 | **action_items 중복 (divergent)**: top-level `action_items.py`(422줄, CRUD 관리 API)와 `minutes/action_items.py`(177줄, 추출 API)가 **둘 다 `prefix="/action-items"`** 로 공존. registry는 `minutes.action_items`만 등록 → top-level은 registry-고아(orphan) | 중간 | `action_items.py` | `diff` 결과 상이, registry line 59/113은 `minutes` 버전 사용 |
| AP-3 | **sentiment 중복 (divergent)**: `analytics/sentiment.py`(256줄, registry 등록)와 `minutes/sentiment.py`(153줄, registry 미등록 고아)가 **둘 다 `prefix="/sentiment"`** | 중간 | `sentiment.py` | registry line 34/110은 `analytics` 버전 사용. `minutes.sentiment`는 main/registry 어디서도 미참조 |
| AP-4 | **테스트가 고아 라우터를 import**: top-level `action_items.py`의 CRUD 엔드포인트를 5개 테스트 위치가 직접 import. `minutes/sentiment.py`(고아)를 2개 테스트가 import | 낮음 | 7개 테스트 파일 | grep 결과 (Section 4 참조) |

### 부모 문서 de-risker 정정 (재-정정)

SPEC-REFACTOR-001 Section 8의 de-risker C-D1은 "테스트가 라우터를 import하지 않음(0건)"을 **거짓**으로 정정했고, 그 결과 Option B(registry-only)를 채택했다. **그러나 본 SPEC의 실측은 그 이후 상황을 보여준다**: 파일 이동은 이미 완료되었고, **대다수 테스트(약 145개 import 라인)는 이미 새 서브패키지 경로(`backend.app.api.v1.<domain>.<module>`)로 마이그레이션 완료**되었다. 남은 flat-style import는 **10줄 / 7개 파일**뿐이며, 그중 실제로 깨질 위험이 있는 것은 top-level `action_items.py`를 참조하는 5개 위치다.

따라서 본 SPEC의 실제 작업은 "재배치 수행"이 아니라 **"부분 완료된 재배치의 마감 + 중복 라우터 정리(divergent duplicate reconciliation) + 잔여 테스트 import 마이그레이션"** 이다.

---

## 2. Assumptions (가정)

- A-1: 기존 API 계약(URL, HTTP 메서드, 상태 코드, 응답 형식, 인증 요구사항)은 변경하지 않는다 (SPEC-REFACTOR-001 A-1 상속).
- A-2: 기존 테스트는 계속 통과해야 한다 (import 경로 변경은 허용).
- A-3: registry.py(`ROUTER_REGISTRY`)가 라우터 등록 순서와 인증 정책의 SSOT다. 등록 순서(특히 batch→transcription)는 보존한다.
- A-4: 라우트 테이블 불변(`test_route_registry_invariance.py` + `_route_snapshot_baseline.json`)이 본 SPEC의 핵심 게이트다.
- A-5: top-level `action_items.py`(CRUD)와 `minutes/action_items.py`(추출)는 **서로 다른 기능을 가진 별개의 라우터**다 (중복 복사본이 아님). **AST 분석으로 검증됨**: 두 라우터의 (METHOD, 구체 path) 집합 교집합은 **0건**이므로 동일 prefix(`/action-items`) 하에서 **충돌 없이 공존 가능**하다. 따라서 reconciliation은 "한쪽 폐기"가 아니라 "CRUD 라우터를 registry에 신규 등록(분리 등록)"으로 결정되었다 (Section 6 Resolved Decisions D-1).
- A-6: `analytics/sentiment.py`(등록)와 `minutes/sentiment.py`(고아)도 (METHOD, path) 교집합 **0건**으로 검증됨 — 기능적으로 상호 보완적(분석 조회 vs 작업 라이프사이클)이다. 따라서 reconciliation은 "통합(merge)"으로 결정되었다 (Section 6 Resolved Decisions D-2).
- A-7: e2e 9건(`tests/e2e/test_pipeline_e2e.py`)은 Python 3.14 asyncio 환경 이슈로 본 SPEC 범위 밖이다.
- A-8: **라우트 불변(invariance)의 의미가 reconciliation별로 다르다**: action_items 분리 등록과 sentiment 통합은 둘 다 **현재 미서빙(고아) 라우트를 서빙 테이블에 추가**하므로, 라우트 집합은 **의도적으로 확장(extend)** 된다. 따라서 `_route_snapshot_baseline.json`(현재 148 entries)을 **명시적·문서화된 delta와 함께 재생성**하는 것이 본 SPEC의 정상 동작이다 (순수 이동 케이스의 "바이트 단위 불변"과 구분된다).

---

## 3. Requirements (요구사항)

본 SPEC은 SPEC-REFACTOR-001의 `REQ-ROUTE-001 ~ REQ-ROUTE-003` 및 `REQ-RM-C1 ~ REQ-RM-C3`을 마감-특화 ID(`REQ-R2-*`)로 정련한다.

### Area 1: flat 라우터 제거 (Priority Medium)

#### REQ-R2-001: flat 라우터 모듈 0건

**Ubiquitous**: 시스템은 **항상** `backend/app/api/v1/` top-level에 라우터 모듈을 두지 **않아야 한다** — `registry.py`, `__init__.py`, 그리고 공유 인프라(존재 시)만 허용한다.

**Unwanted**: 시스템은 `backend/app/api/v1/*.py`(registry.py, __init__.py 제외)에 어떤 `APIRouter` 정의 파일도 남기지 **않아야 한다**.

- 대상: top-level `action_items.py` 제거(이동 또는 통합).
- 모든 라우터는 7개 도메인 서브패키지(transcription / minutes / collaboration / analytics / admin / auth / audio) 중 하나에 귀속한다.

### Area 2: 중복 라우터 정리 (Priority High)

#### REQ-R2-002: action_items 분리 등록 (CRUD 라우터 서빙 보장)

> **결정 D-1 (분리 등록)**: 두 라우터는 기능이 다르고 (METHOD, path) 충돌이 0건이므로 **둘 다 보존·서빙**한다.

**Event-Driven**: **WHEN** CRUD action_items 라우터가 존재하면, **THEN** 시스템은 이를 `ROUTER_REGISTRY`에 등록하여 **실제로 서빙**해야 한다.

**Ubiquitous**: 시스템은 **항상** CRUD 라우터(`목록/생성/조회/수정/삭제/overview/complete/meeting/batch-update`)와 추출 라우터(`/extract`, `/meeting`)를 **둘 다 등록된 상태로 유지**해야 한다.

- CRUD 라우터(top-level `action_items.py`, 422줄)를 도메인 서브패키지(`minutes/`)로 이동한 뒤 `minutes/action_items.py`(추출)와 **별개 모듈로 공존**시킨다. 두 모듈이 같은 파일명이 되지 않도록 CRUD 모듈을 `minutes/action_items_crud.py`로 명명한다(추출 모듈은 기존 `minutes/action_items.py` 유지).
- 두 라우터를 `ROUTER_REGISTRY`에 **각각** 등록한다(둘 다 `requires_api_key=True`, 기존 추출 라우터의 인증 정책 유지).
- **경로 검증(필수)**: 등록 전 두 라우터의 구체 path 집합 교집합이 0건임을 재확인한다. AST 분석 결과(2026-06-06)는 충돌 0건이나, 구현 시 재검증한다. **만약** 구현 시점에 어떤 path가 충돌하면, **THEN** CRUD 라우터의 해당 sub-path를 재할당하고 **선택한 최종 경로를 본 SPEC Section 4에 문서화**한다.
- 결과: `/action-items` prefix 하에 CRUD 9개 + 추출 2개 = 11개 라우트가 충돌 없이 서빙된다. 추출 2개는 이미 baseline에 존재하므로 **CRUD 9개가 신규 추가**되어 라우트 테이블이 확장된다 (REQ-R2-005 baseline 갱신 트리거).

**검증된 CRUD 경로(2026-06-06 AST 분석)**: `GET /action-items`, `POST /action-items`, `GET /action-items/{id}`, `PATCH /action-items/{id}`, `DELETE /action-items/{id}`, `GET /action-items/meeting/{meeting_id}`, `PATCH /action-items/{id}/complete`, `GET /action-items/overview`, `POST /action-items/batch-update`. **추출 경로**: `POST /action-items/extract`, `POST /action-items/meeting`. (교집합 0건 — `meeting/{meeting_id}` vs `meeting`는 서로 다른 경로.)

#### REQ-R2-003: sentiment 라우터 통합 (merge)

> **결정 D-2 (통합)**: 두 sentiment 라우터를 단일 canonical 라우터로 병합한다.

**Event-Driven**: **WHEN** 두 sentiment 라우터(`analytics/sentiment.py` 등록, `minutes/sentiment.py` 고아)가 존재하면, **THEN** 시스템은 두 라우터의 엔드포인트를 **단일 canonical 라우터로 병합**해야 한다.

**Ubiquitous**: 시스템은 **항상** 병합 후 단일 sentiment 라우터만 등록·서빙해야 하며, **두 원본의 모든 엔드포인트 기능을 보존**해야 한다.

- **생존 모듈**: `analytics/sentiment.py`를 생존 모듈로 채택한다. **근거**: 이미 registry에 등록되어 서빙 중이고, 4개 엔드포인트가 baseline에 존재하므로 회귀 위험이 최소이며, sentiment 분석은 analytics 도메인 의미와 정합한다. `minutes/sentiment.py`의 4개 엔드포인트(`POST /sentiment`, `GET /sentiment/{task_id}/status`, `GET /sentiment/{task_id}`, `DELETE /sentiment/{task_id}`)를 생존 모듈로 이관(병합)한다.
- **경로 충돌 검증(필수)**: 두 라우터의 (METHOD, path) 교집합은 0건임이 AST로 검증되었다(분석 4개 GET vs 작업 라이프사이클 POST/GET/DELETE). 병합 시 충돌 없이 8개 엔드포인트가 단일 `/sentiment` prefix 하에 공존한다. 구현 시 재검증한다.
- **고아 제거**: 병합 후 `minutes/sentiment.py`를 삭제한다.
- 결과: minutes 4개 엔드포인트가 **현재 고아(미서빙)** 상태에서 서빙 테이블로 추가되므로, 라우트 집합이 **4개 확장**된다 (REQ-R2-005 baseline 갱신 트리거, **net delta = +4**).

**Unwanted**: 시스템은 사용 중인 코드(라우트/테스트)가 참조하는 모듈을 사전 합의 없이 삭제 **하지 않아야 한다** — 삭제 전 참조 테스트 2건을 생존 모듈로 재지정(re-point)한다.

### Area 3: 테스트 import 마이그레이션 (Priority High)

#### REQ-R2-004: 잔여 flat-style 테스트 import 마이그레이션

**Event-Driven**: **WHEN** 테스트가 라우터 모듈을 import하면, **THEN** canonical 서브패키지 경로(`backend.app.api.v1.<domain>.<module>`)를 사용해야 한다.

- 잔여 flat-style import 10줄(7개 파일, Section 4)을 canonical 경로로 마이그레이션한다.
- top-level `action_items.py`(CRUD)를 참조하는 5개 위치는 D-1에 따라 새 CRUD 모듈 경로(`backend.app.api.v1.minutes.action_items_crud`)로 전환한다.
- `minutes/sentiment.py`를 참조하는 2개 위치는 D-2에 따라 생존 모듈(`backend.app.api.v1.analytics.sentiment`)로 재지정(re-point)한다. 병합으로 minutes 엔드포인트가 생존 모듈에 존재하므로 import 대상이 유효해진다.

### Area 4: 불변성 보존 (Priority High)

#### REQ-R2-005: 라우트 테이블 불변 + 의도적 확장 (Invariance with Documented Delta)

**Ubiquitous**: 시스템은 **항상** 기존 서빙 중인(현재 baseline 148 entries) 모든 URL 경로·HTTP 메서드·상태 코드·인증 요구사항을 **보존**해야 한다.

**Event-Driven**: **WHEN** reconciliation(D-1 분리 등록, D-2 통합)으로 현재 고아(미서빙) 라우트가 서빙 테이블에 추가되면, **THEN** 시스템은 `_route_snapshot_baseline.json`을 **명시적·문서화된 delta와 함께 재생성**해야 한다.

- **기존 148 entries는 1건도 제거·변경되지 않는다** (회귀 금지). 추가만 허용된다.
- **검증된 delta**:
  - D-1 (action_items 분리 등록): CRUD 9개 라우트 신규 추가 → **+9**.
  - D-2 (sentiment 통합): minutes 라이프사이클 4개 라우트 신규 추가 → **+4**.
  - 합산 예상: 148 → **161 entries** (구현 시 실측으로 최종 확정).
- baseline 재생성 후 `test_route_registry_invariance.py`는 새 baseline에 대해 통과해야 한다. **무단(문서화 없는) baseline 변경은 금지**한다 — 변경된 라우트 목록을 progress.md 또는 본 SPEC에 기록한다.
- **불변 보존 확인 게이트**: 재생성 전 baseline의 148개 (path, method) 엔트리가 재생성 후 baseline에 **부분집합(subset)으로 모두 포함**됨을 검증한다 (기존 라우트 무손실 증명).

#### REQ-R2-006: registry 등록 순서·인증 정책 보존

**State-Driven**: **IF** 라우터가 registry에 등록되면, **THEN** 현재 등록 순서(batch→transcription 제약 포함)와 `requires_api_key` 인증 정책을 보존해야 한다.

- registry 임포트 경로만 canonical 위치로 갱신하고, 튜플 순서와 `requires_api_key` 플래그는 변경하지 않는다.

---

## 4. Specifications (구현 명세)

### 잔여 flat-style 테스트 import (검증됨, 2026-06-06)

```
tests/unit/test_action_items_api_coverage.py:81   from backend.app.api.v1.action_items import router          (top-level CRUD, 고아)
tests/unit/test_action_items_api_coverage.py:519  from backend.app.api.v1.action_items import router          (top-level CRUD, 고아)
tests/unit/test_coverage_gaps_final.py:390         from backend.app.api.v1.action_items import get_action_items_overview
tests/unit/test_coverage_direct_calls.py:316       from backend.app.api.v1.action_items import get_action_items_overview
tests/unit/test_scattered_gaps_round2.py:1089      from backend.app.api.v1.action_items import router          (top-level CRUD, 고아)
tests/unit/test_export_api.py:97                   from backend.app.api.v1.admin import export                 (이미 서브패키지 — 정상)
tests/unit/test_export_api.py:275                  from backend.app.api.v1.admin import export                 (이미 서브패키지 — 정상)
tests/unit/test_export_api_v3.py:77                from backend.app.api.v1.admin import export                 (이미 서브패키지 — 정상)
tests/unit/test_tags_api_v5.py:90                  from backend.app.api.v1.minutes import tags as tags_mod     (이미 서브패키지 — 정상)
tests/unit/test_tags_api_v5.py:112                 from backend.app.api.v1.minutes import tags as tags_mod     (이미 서브패키지 — 정상)
```

> **주의**: `from ...admin import export`, `from ...minutes import tags`는 이미 **서브패키지 패키지 import**이므로 정상 동작한다(깨지지 않음). 실제 마이그레이션이 필요한 것은 top-level `action_items.py` 참조 5건 + (reconciliation에 따라) `minutes/sentiment.py` 참조 2건이다.

### 중복 라우터 인벤토리 (검증됨, 2026-06-06 AST 분석)

| 모듈 | 현재 등록 | 현재 고아 | prefix | (METHOD,path) 교집합 | 결정 | 결과 |
|------|-----------|-----------|--------|----------------------|------|------|
| action_items | `minutes/action_items.py` (177줄, 추출: `/extract`, `/meeting`) | `action_items.py` top-level (422줄, CRUD 9개) | `/action-items` | **0건 (충돌 없음)** | **D-1 분리 등록** | CRUD를 `minutes/action_items_crud.py`로 이동·등록. 둘 다 서빙. 라우트 **+9** |
| sentiment | `analytics/sentiment.py` (256줄, 분석 GET 4개) | `minutes/sentiment.py` (153줄, 라이프사이클 4개) | `/sentiment` | **0건 (충돌 없음)** | **D-2 통합** | minutes 4개를 `analytics/sentiment.py`로 병합. 고아 삭제. 라우트 **+4** |

### 라우트 delta 상세 (검증됨)

**D-1 신규 서빙(action_items CRUD, +9)**: `GET /action-items`, `POST /action-items`, `GET /action-items/{id}`, `PATCH /action-items/{id}`, `DELETE /action-items/{id}`, `GET /action-items/meeting/{meeting_id}`, `PATCH /action-items/{id}/complete`, `GET /action-items/overview`, `POST /action-items/batch-update`.

**D-2 신규 서빙(sentiment 라이프사이클, +4)**: `POST /sentiment`, `GET /sentiment/{task_id}/status`, `GET /sentiment/{task_id}`, `DELETE /sentiment/{task_id}`.

> 두 delta 모두 **현재 고아(미서빙)** 라우트를 서빙으로 전환하는 것이다. 기존 148개 서빙 라우트는 **1건도 제거·변경되지 않는다**.

### 호환성 보장

- 기존 서빙 중인 148개 URL 패턴은 **무손실 보존**된다 (`/api/v1/...`).
- 신규 라우트는 모두 현재 고아 라우트의 서빙 전환이며 기존 라우트와 경로 충돌이 0건이다 (AST 검증).
- registry 등록 순서(batch→transcription)·`requires_api_key` 플래그는 기존 항목에 대해 불변. 신규 2개 라우터는 `requires_api_key=True`로 추가.
- 라우트 스냅샷 baseline(`_route_snapshot_baseline.json`)을 **delta 문서화와 함께 재생성**하여 기계적 증명.

---

## 5. Acceptance Criteria 요약

상세 시나리오는 `acceptance.md` 참조.

| ID | 검증 명령 | 통과 조건 |
|----|-----------|-----------|
| AC-R2-1 | `ls backend/app/api/v1/*.py` (registry.py, __init__.py 제외) | flat 라우터 **0건** (top-level `action_items.py` 제거됨) |
| AC-R2-2 | `cd backend && ../venv/bin/python -m pytest tests/unit/test_route_registry_invariance.py -o addopts=""` | passed (delta 문서화 후 재생성된 baseline 기준). 기존 148 entries는 재생성 baseline의 **부분집합**으로 무손실 포함 |
| AC-R2-3 | `grep -rEn "from backend\.app\.api\.v1\.action_items import\|from backend\.app\.api\.v1\.minutes\.sentiment import\|from backend\.app\.api\.v1\.minutes import sentiment" tests/ \| wc -l` | **0** (top-level action_items 참조 + minutes/sentiment 고아 참조 모두 제거/재지정) |
| AC-R2-4 | sentiment 단일 모듈 + action_items 두 모듈 공존 검사 | `find app/api/v1 -name "sentiment.py"` → **1**; action_items: `minutes/action_items.py`(추출) + `minutes/action_items_crud.py`(CRUD) **2개 모듈, 둘 다 registry 등록** |
| AC-R2-5 | `cd backend && ../venv/bin/python -m pytest tests/ --ignore=tests/e2e/test_pipeline_e2e.py` | 0 failed (커버리지 게이트 충족) |
| AC-R2-6 | registry `ROUTER_REGISTRY` diff (기존 35개 튜플의 순서·`requires_api_key`) | 기존 항목 0 변경 (batch→transcription 불변). D-1 CRUD 라우터 신규 등록 + D-2 sentiment 병합으로 인한 import 경로 갱신·신규 등록만 허용 |
| AC-R2-7 | 라우트 delta 검증: 재생성 baseline entries 수 | 148 + 13 = **161** (D-1 +9, D-2 +4), 또는 구현 실측값 (delta가 SPEC/progress에 문서화됨) |
| AC-R2-8 | 기존 라우트 무손실: 재생성 전 148개 (path,method)가 재생성 후 baseline에 모두 포함 | subset 검증 통과 (0건 누락) |

---

## 6. Resolved Decisions (확정됨, 2026-06-06)

두 reconciliation 결정이 사용자 승인으로 확정되었다. 두 결정 모두 **기능 보존(preserve functionality)** 을 원칙으로 하며, AST 분석으로 경로 충돌 0건이 검증되어 안전하게 실행 가능하다.

### D-1: action_items → 분리 등록 (Co-register, 기능 보존)

- **결정**: CRUD 라우터(top-level `action_items.py`, 422줄)를 `ROUTER_REGISTRY`에 신규 등록하여 **실제로 서빙**하고, 추출 라우터(`minutes/action_items.py`)는 그대로 유지한다. **둘 다 등록·서빙**된다.
- **모듈 배치**: CRUD 라우터를 `minutes/action_items_crud.py`로 이동(파일명 충돌 회피). 추출 라우터는 `minutes/action_items.py` 유지.
- **경로 충돌**: AST 검증 결과 (METHOD, path) 교집합 **0건** → 동일 `/action-items` prefix 하에 충돌 없이 공존. 구현 시 재검증하며, 만약 충돌 발견 시 CRUD sub-path를 재할당하고 선택 경로를 Section 4에 문서화한다.
- **라우트 영향**: CRUD 9개 신규 서빙 → **+9** (baseline 확장).
- **반영**: REQ-R2-002.

### D-2: sentiment → 통합 (Merge, 기능 보존)

- **결정**: `analytics/sentiment.py`(생존)와 `minutes/sentiment.py`(고아)를 **단일 canonical 라우터로 병합**한다. 모든 엔드포인트 기능을 보존한다.
- **생존 모듈**: `analytics/sentiment.py` (근거: 이미 서빙 중이라 회귀 위험 최소, sentiment=analytics 도메인 정합). `minutes/sentiment.py`의 4개 라이프사이클 엔드포인트를 생존 모듈로 이관 후 고아 파일 삭제.
- **경로 충돌**: AST 검증 결과 (METHOD, path) 교집합 **0건** (분석 GET 4개 vs 라이프사이클 POST/GET/DELETE 4개) → 충돌 없이 8개 엔드포인트 공존.
- **테스트 재지정**: `minutes/sentiment.py` 참조 테스트 2건을 `analytics/sentiment.py`로 re-point.
- **라우트 영향**: minutes 4개 신규 서빙 → **+4** (net delta, baseline 확장).
- **반영**: REQ-R2-003.

### 라우트 스냅샷 처리 (두 결정의 공통 귀결)

- 두 결정 모두 **현재 고아(미서빙) 라우트를 서빙으로 전환**하므로, `_route_snapshot_baseline.json`(현재 148 entries)을 **delta(+9, +4 = +13 → 약 161 entries)와 함께 재생성**한다. 이는 본 SPEC의 정상 동작이며 순수-이동 케이스의 "바이트 단위 불변"과 구분된다.
- **기존 148개 서빙 라우트는 1건도 제거·변경되지 않는다** (회귀 금지, AC-R2-8 subset 게이트로 증명).

---

## 7. Out-of-Scope

- e2e 9건(`test_pipeline_e2e.py`) Python 3.14 asyncio 이벤트 루프 이슈 — 별도 처리.
- 엔드포인트 신규 **기능** 추가(새 비즈니스 로직), 응답 스키마 변경 — 범위 밖. (D-1/D-2로 인한 고아 라우트 서빙 전환·병합은 기존 코드 보존이므로 예외.)
- registry 등록 순서 최적화, 기존 라우터의 인증 정책 변경 — 범위 밖(불변 유지).

---

## 8. Traceability

| TAG | Area | Requirement IDs | 정련 출처 |
|-----|------|-----------------|-----------|
| SPEC-REFACTOR-002-FLAT | Area 1 (flat 제거) | REQ-R2-001 | REQ-RM-C1 / AC-C4 (SPEC-REFACTOR-001 §8) |
| SPEC-REFACTOR-002-DUP | Area 2 (중복 정리: D-1 분리 등록, D-2 통합) | REQ-R2-002 ~ REQ-R2-003 | 신규 (커밋 ebb127f 부작용) |
| SPEC-REFACTOR-002-TEST | Area 3 (테스트 import) | REQ-R2-004 | REQ-RM-C1 잔여분 |
| SPEC-REFACTOR-002-INV | Area 4 (불변성 + delta) | REQ-R2-005 ~ REQ-R2-006 | REQ-RM-C2 / REQ-RM-C3 (AC-C2/AC-C5) |

### Resolved Decisions → AC 매핑

| 결정 | Requirement | Acceptance |
|------|-------------|-----------|
| D-1 (action_items 분리 등록) | REQ-R2-002 | AC-R2-1, AC-R2-4, AC-R2-7 |
| D-2 (sentiment 통합) | REQ-R2-003 | AC-R2-4, AC-R2-7 |
| 라우트 baseline 재생성 (delta) | REQ-R2-005 | AC-R2-2, AC-R2-7, AC-R2-8 |

---

## 9. 구현 노트 (Implementation Notes)

### 상태 갱신 (2026-06-13)

| 항목 | SPEC (v0.2.0 draft) | 실제 구현 (2026-06-13) |
|------|---------------------|----------------------|
| 상태 | draft | **completed** |
| AC-R2-1 (flat 라우터 0건) | 미충족 | **충족** — `api/v1/*.py`에 `__init__.py`, `registry.py`만 존재 |
| AC-R2-4 (action_items 분리) | 미구현 | **충족** — `minutes/action_items.py`(추출) + `minutes/action_items_crud.py`(CRUD) 공존 |
| D-2 (sentiment 통합) | 미구현 | **충족** — `minutes/sentiment.py` 삭제됨, `analytics/sentiment.py`만 존재 |

**검증 소스**:
- `ls backend/app/api/v1/*.py` → `__init__.py`, `registry.py`만 존재 (flat 라우터 0건)
- `backend/app/api/v1/minutes/action_items_crud.py` 존재 (D-1 분리 등록 완료)
- `backend/app/api/v1/minutes/sentiment.py` 존재하지 않음 (D-2 통합으로 고아 삭제 완료)
- `backend/app/api/v1/analytics/sentiment.py` 단일 sentiment 라우터 존재
