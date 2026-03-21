# SPEC-ERR-001 구현 계획

## Task 1: 커스텀 예외 클래스 (exceptions.py)
- VoiceNoteError 기본 클래스
- AudioProcessingError, StorageError, PipelineError 하위 클래스
- error_code, message, status_code 속성

## Task 2: 전역 예외 핸들러 (error_handlers.py)
- VoiceNoteError 핸들러 → 커스텀 JSON 응답
- RequestValidationError 핸들러 → 422 상세 응답
- 일반 Exception 핸들러 → 500 안전 응답
- 모든 응답에 request_id 포함

## Task 3: 설정 검증 (config.py)
- max_concurrent_jobs 범위 (1~10)
- max_file_size_mb 범위 (1~2000)
- rate_limit_per_minute 범위 (1~1000)

## Task 4: main.py 통합
- 핸들러 등록
