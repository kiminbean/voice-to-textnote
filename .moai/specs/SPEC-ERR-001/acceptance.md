# SPEC-ERR-001 인수 조건

## AC-1: 커스텀 예외 에러 응답
- **Given** AudioProcessingError("INVALID_FORMAT", "지원하지 않는 형식", 422) 발생
- **When** 전역 핸들러 처리
- **Then** 422 + {"error_code": "INVALID_FORMAT", "message": "지원하지 않는 형식", "request_id": "uuid"}

## AC-2: 미처리 예외 안전 처리
- **Given** RuntimeError("unexpected") 발생
- **When** 전역 핸들러 처리
- **Then** 500 + {"error_code": "INTERNAL_ERROR", "message": "서버 내부 오류가 발생했습니다"} + 로그에 스택트레이스

## AC-3: 검증 에러 상세
- **Given** RequestValidationError 발생
- **When** 전역 핸들러 처리
- **Then** 422 + 필드별 에러 목록

## AC-4: 설정 검증
- **Given** MAX_CONCURRENT_JOBS=0
- **When** Settings() 생성
- **Then** ValidationError
