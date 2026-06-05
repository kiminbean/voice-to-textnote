# Research Artifact — SPEC-REFACTOR-001 Iteration 3 (Phase 4)

조사 일자: 2026-06-05
대상 범위: Phase 4 — API 라우터 도메인 그룹핑 (REQ-ROUTE-001~003 → REQ-RM-C*)
조사 방법: deep Explore (Glob/Grep 기반 정적 분석)

---

## 1. 라우터 인벤토리 (35개)

`backend/app/api/v1/`에 35개의 `APIRouter` 파일이 존재한다. (파일, prefix, 인증) 전수:

| 파일 | prefix | 인증 |
|------|--------|------|
| batch.py | `/transcriptions/batch` | api_key |
| transcription.py | `/transcriptions` | api_key |
| diarization.py | `/diarizations` | api_key |
| audio_preprocess.py | `/audio` | api_key |
| audio_analysis.py | `/audio-analysis` | api_key |
| audio.py | (no prefix) `/meetings/{task_id}/audio` | **public** |
| minutes.py | `/minutes` | api_key |
| summary.py | `/summaries` | api_key |
| sentiment.py | `/sentiment` | api_key |
| tags.py | `/tags` | JWT |
| keywords.py | `/keywords` | api_key |
| action_items.py | `/action-items` | api_key |
| quality_assessment.py | `/quality` | api_key |
| versions.py | `/minutes` (subpath `/{task_id}/versions`) | JWT |
| teams.py | `/teams` | JWT |
| meetings.py | `/meetings` | JWT |
| bookmarks.py | `/bookmarks` | JWT |
| webhooks.py | `/webhooks` | JWT |
| speakers.py | `/speakers` | JWT (엔드포인트 레벨) |
| statistics.py | `/statistics` | api_key |
| dashboard.py | `/statistics` (subpath `/{task_id}`) | api_key |
| enhanced_statistics.py | `/enhanced-statistics` | api_key |
| advanced_search.py | `/advanced-search` | api_key |
| admin.py | `/admin` | api_key |
| health.py | `/health` | **public** |
| history.py | (no prefix) `/history...` | api_key |
| export.py | (no prefix) `/export/...` | api_key |
| templates.py | `/templates` | api_key |
| auth.py | `/auth` | JWT |
| devices.py | `/devices` | JWT |
| calendar.py | `/calendar` | api_key |
| vocabulary.py | `/vocabulary` | api_key |
| qa.py | `/qa` | api_key |
| search.py | (no prefix) `/search` | api_key |
| stream.py | `/tasks` | api_key |

---

## 2. 등록 구조 (main.py)

- 위치: `backend/app/main.py` 라인 192-275, `create_app()` 내부.
- 35개의 정적 `include_router` 호출.
- 모두 `prefix=api_prefix` 사용 (`api_prefix="/api/v1"`, 라인 195).
- 공유 `_auth = [Depends(verify_api_key)]` (라인 196).
- 24개 라우터는 등록 시 `dependencies=_auth` 부여 (라우터 레벨 api_key).
- 9개 라우터(auth, bookmarks, devices, meetings, speakers, tags, teams, versions, webhooks)는 `_auth` 미부여 → 엔드포인트 레벨 `Depends(get_current_user)` 사용.
- 2개 라우터(audio, health)는 public.

---

## 3. 핵심 De-risker (검증됨)

| ID | 사실 | 영향 |
|----|------|------|
| C-D1 | `grep -r "from backend.app.api.v1" tests/` → **0건** 클레임은 거짓. 실제: ~40개 테스트 파일이 27개 라우터 서브모듈을 직접 import (`from backend.app.api.v1.<module> import router/service`, 예: quality_assessment ×14, export ×9, stream ×7). grep 경로 오류(repo-root `tests/` 미존재 → 실제 `backend/tests/`) 때문에 거짓 0건 초래. **Refuted during implementation.** 파일 이동은 이들 import를 깨뜨림. 따라서 AC-C4(flat routers 0건)는 호환성 shim으로 불가능(shim 자체가 flat .py). **Option B(registry-only, 파일 이동 없음) 채택 사유.** |
| C-D2 | 조건부/동적 라우터 등록 없음 (35개 정적 호출) | 등록 로직 단순·예측 가능 |
| C-D3 | Phase 1-3 완료 (싱글톤 0건, 2475 passed per progress.md) | 안정 기반 위 순수 구조 변경 |
| C-D4 | `backend/app/api/v1/__init__.py`는 최소(docstring만, import 없음) | 신규 도메인 `__init__.py` 충돌 없음 |

---

## 4. 핵심 제약 / 정련 (낙관적 스케치 supersede)

REQ-ROUTE-001의 스케치(~24개 명명)는 실제 35개 인벤토리와 불일치한다. 다음 제약이 스케치를 보완·정정한다.

- **35개 전체를 그룹에 매핑**해야 한다. 미분류 라우터(calendar, vocabulary, qa, search, stream, action_items, templates, sentiment, speakers) 포함.
- 권고 그룹: transcription / minutes / collaboration / analytics / admin / auth / core(misc).
- **`/statistics` 공유(statistics.py + dashboard.py)는 실제 충돌 아님** — subpath 분리로 공존, 2475 테스트 통과 중. 파일별 `prefix=`와 등록 `prefix="/api/v1"`가 불변이면 URL 동일. **병합 금지, 위치 이동만** → 제약 A-1 보존.
- **registry.py는 신규 패턴** (현존 없음). 순환 import 회피 설계: registry → routers, main.py → registry (단방향).
- **prefix 없는 라우터(audio, history, export, search)**: 데코레이터에 전체 경로 정의 → 이동만으로 URL 불변. 단, 도메인 `__init__.py`에서 `router` re-export 보장 필요.

---

## 5. 정련된 EARS 요구사항 (Section 8에 작성됨)

- **REQ-RM-C1** (도메인 그룹핑): 35개 라우터를 도메인 서브패키지로 재배치, `router` 변수명 보존, 각 도메인 `__init__.py`가 router re-export. Unwanted: 라우터 병합 금지.
- **REQ-RM-C2** (registry 도입): `ROUTER_GROUPS` 매핑 도입, main.py 등록 블록을 registry 순회 루프로 축소. 인증 전략(api_key 라우터 레벨 vs JWT/public 엔드포인트 레벨)을 라우터별로 정확히 보존.
- **REQ-RM-C3** (URL/인증 불변): 모든 URL 경로·HTTP 메서드·상태 코드·인증 요구사항을 바이트 단위 동일 유지.

---

## 6. 수용 기준 핵심

- AC-C1: `pytest tests/ --ignore=tests/e2e/test_pipeline_e2e.py` → 0 failed. ✅ **충족 (2478 passed, 4 skipped)**.
- AC-C2: **라우트 테이블 스냅샷** — 재배치 전후 `app.routes`의 (path, methods) 집합 동일 (A-1 기계적 증명). ✅ **충족 (135 routes invariant, _route_snapshot_baseline.json)**.
- AC-C3: main.py `include_router` 호출 개수 대폭 감소 (루프 1개소 집약). ✅ **충족 (35→1)**.
- AC-C4: `ls backend/app/api/v1/*.py` (registry.py, __init__.py 제외) → flat 라우터 0건. ❌ **Deferred (범위 축소: registry-only, 파일 이동 없음)** — REQ-RM-C1(도메인 그룹핑 파일 재배치) 미수행, 라우터는 flat 구조 유지. 대신 registry.py 도입으로 main.py 보일러플레이트 축소(AC-C3)·라우트 불변(AC-C2) 달성.
- AC-C5: 인증 전략 보존 (api_key 라우터 레벨 78개, no-router-dep 57개). ✅ **충족** (AC-C1 통과로 간접 증명).

---

## 7. Out-of-Scope / 미해소 모호성

- **그룹 경계 2건** (Plan Review gate 확정): `core` 그룹 유지 여부, `speakers.py` 귀속(transcription vs collaboration).
- **e2e 9건** (`test_pipeline_e2e.py`): Python 3.14 asyncio 이벤트 루프 환경 이슈, 리팩토링 무관. 제외.
- **엔드포인트 동작 변경**(URL 이름·메서드·인증 전략 변경): 범위 밖. 순수 구조 변경만 수행.

---

## 8. 검증 환경 (Iteration 2 재사용)

- venv python: `backend/../venv/bin/python`
- import 접두사: `backend.`
- 커버리지 게이트 비활성화(실패 격리 시): `-o addopts=""`
