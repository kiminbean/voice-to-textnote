## SPEC-REFACTOR-001 Progress (Iteration 2)

- Started: 2026-06-04 (Scope A 회귀수정 → Scope B DI완료, Phase 4 deferred)
- Completed: 2026-06-04
- Mode: sub-agent (expert-backend, foreground)
- Pre-run verified: progress 없음(fresh), 싱글톤 21건, Scope A 회귀 3종 재현(NameError 등), venv=Python 3.14.3

### Phase A — 테스트 회귀 수정
- [x] TASK-A1 audio_preprocess 413 전파
- [x] TASK-A2 transcription VoiceNoteError import
- [x] TASK-A3 batch audio read error
- [x] TASK-A4 summary 픽스처 핸들러 등록
- [x] TASK-A5 sentiment/rate_limit 404·429 재확인
- [x] TASK-A6 전체 스위트 그린 (과거 e2e 9건 제외 기록은 후속 재검증으로 해소)

### Phase B — DI 완료 (21 싱글톤 → Depends)
- [x] TASK-B1~B14 파일별 provider 전환 (18개 파일, 21개 싱글톤)
- [x] TASK-B15 글로벌 게이트: grep 0건 + 전체 2475 passed, 0 failed

### Results
- **Test suite**: 2475 passed, 4 skipped, 73 warnings (181.28s)
- **Singletons remaining**: 0 (`grep "_service = .*Service()" → 0`)
- **Phase 4 (라우터 그룹핑)**: 이번 반복 제외

---

## SPEC-REFACTOR-001 Progress (Iteration 3 — Phase 4: registry-only)

- Started/Completed: 2026-06-05
- Mode: sub-agent (expert-backend, foreground) / development_mode=tdd (behavior-preserving characterization 규율 적용)
- **범위 결정 변경**: research-iter3.md의 핵심 de-risker C-D1("테스트가 라우터 모듈 import 0건")이 **거짓**으로 판명. 원인: research grep이 repo-root `tests/`(미존재)를 대상 → 실제 테스트는 `backend/tests/`에 있고 ~40개 파일이 27개 라우터 서브모듈을 직접 import. 파일 이동 시 import 전부 깨짐 → 사용자 결정으로 **Option B(registry만 도입, 파일 이동 X)** 선택.

### 구현
- [x] `backend/app/api/v1/registry.py` 신규 — `ROUTER_REGISTRY: list[tuple[APIRouter, bool]]` (35개, 25 True/10 False), 등록 순서·인증 정책 SSOT, @MX:ANCHOR
- [x] `backend/app/main.py` — 35개 정적 `include_router`(198-275) → 단일 순회 루프, 35-module import 블록 제거, registry import 추가
- [x] `backend/tests/unit/test_route_registry_invariance.py` + `_route_snapshot_baseline.json` — AC-C2/C5 기계 증명(135 라우트 golden snapshot)

### 게이트 결과
- **AC-C1**: `pytest tests/ --ignore=tests/e2e/test_pipeline_e2e.py` → **2478 passed, 4 skipped, 0 failed** (185.8s, cov 97.35%)
- **AC-C2**: 라우트 테이블 스냅샷 — invariance test 3/3 PASS (count·full table·auth policy 모두 baseline 동일)
- **AC-C3**: main.py `include_router` 직접 호출 35 → 1 (루프)
- **AC-C5**: 라우터별 인증 정책(api_key 78 routes / no-router-dep 57 routes) 불변 증명
- **AC-C4**: **충족 (2026-06-14 재검증)** — SPEC-REFACTOR-002 후속 완료로 flat 라우터 0건. `backend/app/api/v1` top-level에는 `__init__.py`, `registry.py`만 남음.
- **Route 중복 정리**: `enhanced_preprocess` 중복 등록 제거 후 live route method entries 161 / unique 161 / duplicates 0.
- **전체 회귀**: `venv/bin/python -m pytest backend -q` → **3323 passed, 16 skipped**, coverage **98.62%**.
- **E2E 후속 재검증**: `venv/bin/python -m pytest -o addopts="" backend/tests/e2e/test_pipeline_e2e.py -q` → **16 passed, 6 warnings in 1.73s** (2026-06-15). 과거 Python 3.14 event loop 제외 조건은 현재 재현되지 않음.

### 후속 (sync 단계 완료)
- spec.md Section 8: AC-C4/REQ-RM-C1 deferred 상태를 후속 완료 상태로 정정
- research-iter3.md C-D1 정정 기록은 이력으로 유지하되 현재 상태는 SPEC-REFACTOR-002 및 본 progress.md를 기준으로 삼음
- 잔여 cruft: `backend/fake.wav`(0바이트), `.omc/state/*.json`(런타임) — 커밋 제외
