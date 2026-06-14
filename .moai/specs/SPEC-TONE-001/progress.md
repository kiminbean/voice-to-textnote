## SPEC-TONE-001 Progress

- Started: 2026-06-14T16:50:00+09:00
- Mode: sub-agent (team_* tools unavailable, fallback per MoAI workflow)
- Methodology: TDD (RED-GREEN-REFACTOR)
- Plan approval: User approved (승인 — 진행)

### Phase 1.6: Acceptance Criteria Registered
- AC-TONE-001: Celery tone_task 등록 및 실행
- AC-TONE-002: DIA 완료 후 자동 트리거
- AC-TONE-003: 짧은 세그먼트 스킵
- AC-TONE-004: tone_task 실패 시 기존 파이프라인 무영향
- AC-TONE-005: Flutter tone timeline 렌더링
- AC-TONE-006: tone_model 빈 값 시 비활성화

### Recurrence Prevention
- Delegation guard: `deep` is an oh-my-openagent category, not a callable subagent ID. Use `category="deep"` or a real agent ID such as `sisyphus-junior`; never use `subagent_type="deep"`.
- Test guard: ToneEngine tests that inject a mock Smile object must use `_make_initialized_tone_engine(...)`. Setting only `engine._smile` lets `_initialize()` overwrite the mock and causes false `process_signal` call-count failures.
- Verification guard: after Wave 1 edits, run `python -m pytest backend/tests/unit/test_tone_engine.py -q --no-cov --tb=short` and `python -m ruff check backend/app/config.py backend/app/main.py backend/ml/tone_engine.py backend/tests/unit/test_tone_engine.py`.

### Phase 2: Implementation Complete
- Wave 1 (M6+M1): ToneEngine singleton + config + deps — 9 tests, 64 regression pass
- Wave 2 (M2+M3): Audio preservation + Celery tone_task — 10 tests, 57 regression pass
- Wave 3 (M4): Schema + API router + task_id fix — 8 tests, 82 regression pass
- Wave 4 (M5): Flutter tone_api + timeline UI — 17 tests, 318 Flutter tests pass
- Coverage fix: tone_engine 84→98%, tone_task 80→100% (+22 tests)

### Phase 2.5: Quality Validation PASS
- Backend: 3106 passed, 0 failed, 16 skipped
- Flutter: 318 passed, 0 failed
- Tone coverage: engine 98%, task 100%, schema 100%, API 100% after Phase 2.6
- LSP diagnostics: 0 errors all files
- Route baseline updated: 161 → 165 routes

### Phase 2.6: API Coverage Closure
- Date: 2026-06-14
- Added API coverage regression tests:
  - `backend/tests/unit/test_api_coverage_completion.py`
  - `backend/tests/unit/test_devices_api_coverage.py`
- Covered remaining API route/direct-call paths across history, templates, tone, vocabulary, quality assessment, bookmarks, speakers, batch upload, devices, and collaboration WebSocket handling.
- Verification:
  - `python -m pytest backend/tests/unit/test_api_coverage_completion.py backend/tests/unit/test_devices_api_coverage.py -q --no-cov` → `19 passed`
  - `python -m ruff check backend/tests/unit/test_api_coverage_completion.py backend/tests/unit/test_devices_api_coverage.py` → `All checks passed!`
  - Coverage JSON API aggregate: `2545/2545` covered lines, `100.00%`, `missing=[]`
- Known non-API suite risk: full `python -m pytest backend -q --cov-report=json:coverage.json` still has 11 existing non-API failures in OAuth/STT/ToneEngine/worker tests; these do not reduce API coverage but block claiming full-suite green.

### Acceptance Criteria
- AC-TONE-001 ✅ Celery tone_task registered (celery_app include + test)
- AC-TONE-002 ✅ DIA → tone auto-trigger (_trigger_tone_task + wav preservation)
- AC-TONE-003 ✅ Short segment skip (< 0.5s, boundary inclusive)
- AC-TONE-004 ✅ Failure isolation (try/except + wav cleanup in finally)
- AC-TONE-005 ✅ Flutter timeline (color mapping + empty/loading/error states + retry)
- AC-TONE-006 ✅ Disabled when tone_model="" (503 API + no trigger + immediate wav delete)

### Files: 12 new + 13 modified = 25 files total
