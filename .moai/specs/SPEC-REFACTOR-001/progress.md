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
- [x] TASK-A6 전체 스위트 그린 (e2e 9건 제외)

### Phase B — DI 완료 (21 싱글톤 → Depends)
- [x] TASK-B1~B14 파일별 provider 전환 (18개 파일, 21개 싱글톤)
- [x] TASK-B15 글로벌 게이트: grep 0건 + 전체 2475 passed, 0 failed

### Results
- **Test suite**: 2475 passed, 4 skipped, 73 warnings (181.28s)
- **Singletons remaining**: 0 (`grep "_service = .*Service()" → 0`)
- **Phase 4 (라우터 그룹핑)**: 이번 반복 제외
