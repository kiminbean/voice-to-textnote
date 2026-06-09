## Task Decomposition
SPEC: SPEC-ERR-002

| Task ID | Description | Requirement | Dependencies | Planned Files | Status |
|---------|-------------|-------------|--------------|---------------|--------|
| T-001 | Transcription Redis → ServiceUnavailableError | REQ-ERR2-002 | - | backend/app/api/v1/transcription/transcription.py, backend/tests/unit/test_error_handling_transcription.py | pending |
| T-002 | Worker DB 저장 실패 → 에러 로깅 | REQ-ERR2-003 | - | backend/workers/tasks/transcription_task.py, backend/workers/tasks/minutes_task.py, backend/workers/tasks/summary_task.py, backend/workers/tasks/diarization_task.py, backend/tests/unit/test_error_handling_workers.py | pending |
| T-003 | auth.py HTTPException → 커스텀 예외 (11건) | REQ-ERR2-004 | - | backend/app/middleware/auth.py, backend/tests/unit/test_error_handling_middleware.py | pending |
| T-004 | dependencies.py HTTPException → 커스텀 예외 (4건) | REQ-ERR2-004 | - | backend/app/dependencies.py, backend/tests/unit/test_error_handling_middleware.py | pending |
| T-005 | Event Publisher 에러 전파 강화 | REQ-ERR2-006 | T-001~004 | backend/events/publisher.py, backend/tests/unit/test_error_handling_publisher.py | pending |
| T-006 | Lifecycle Degraded 상태 추적 | REQ-ERR2-008 | T-001~004 | backend/app/lifecycle.py, backend/app/api/v1/admin/health.py, backend/tests/unit/test_error_handling_lifecycle.py | pending |
| T-007 | PDF JSON 파싱 → 안전한 fallback | REQ-ERR2-007 | T-001~004 | backend/pipeline/pdf_generator.py, backend/tests/unit/test_error_handling_workers.py | pending |
| T-008 | 통일 에러 포맷 검증 | REQ-ERR2-005 | T-003, T-004 | (테스트만) | pending |
