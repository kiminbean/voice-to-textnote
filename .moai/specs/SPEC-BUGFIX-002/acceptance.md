# SPEC-BUGFIX-002 Acceptance Criteria

## 검증 방법
본 문서는 spec.md의 REQ-BF2-001~006 요구사항이 코드와 테스트로 충족되었는지 추적한다.

## Acceptance Criteria

### AC-001: asyncio.to_thread 회귀 테스트
- 상태: MET
- 증거: `backend/tests/unit/test_async_blocking_regression.py` (8개 테스트 PASS)
  - transcription.py upload_transcription
  - batch.py upload_batch_transcription
  - audio_analysis.py analyze_audio_file
  - export.py export_pdf
  - export.py export_docx
  - templates.py upload_template
  - push_service.py send_push
  - push_service.py send_multicast

### AC-002: collab_service Lua script
- 상태: MET (부분)
- 증거: `backend/services/collab_service.py` `_ADD_PRESENCE_LUA`, `_APPLY_EDIT_LUA` 상수 + `_is_real_redis` 감지
- 동시성 테스트: `backend/tests/unit/test_collab_concurrency.py` (5개 PASS)
- 비고: fakeredis가 Lua eval 미지원 → 프로덕션 Redis에서만 atomic 보장, 테스트는 폴백 경로

### AC-003: push_service FCM wrap
- 상태: MET
- 증거: `backend/services/push_service.py` send_push/send_multicast의 `asyncio.to_thread` 적용
- 회귀 테스트: `test_async_blocking_regression.py::TestPushServiceAsyncBlocking` PASS

### AC-004: temp file leak 정적 분석 gate
- 상태: MET
- 증거: `backend/tests/unit/test_tempfile_leak_gate.py` (2개 PASS)
- self-test 포함: 의도적 leak 코드 감지 확인

### AC-005: version_service migration
- 상태: MET
- 증거: `alembic/versions/004_unique_minutes_versions_task_version.py`
- `alembic upgrade head` + `downgrade -1` 정상 동작 (SQLite batch mode)
- 기존 migration 테스트 6개 전부 PASS (003 version assertion 업데이트)

### AC-006: 운영 로그 검증
- 상태: MET
- 증거: `backend/workers/tasks/*.py` (5개 파일) + `transcription.py`의 `category` 필드 (13곳)
- 게이트 테스트: `backend/tests/unit/test_log_category_gate.py` (6개 PASS)
- 비고: 운영 대시보드 설정은 본 SPEC 범위 외 (별 Ops 작업)
