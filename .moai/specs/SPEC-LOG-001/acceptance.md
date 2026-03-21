# SPEC-LOG-001 인수 조건

## AC-1: 감사 로그 생성
- **Given** POST /api/v1/transcriptions 요청
- **When** 응답 완료
- **Then** structlog 출력에 method, path, status_code, duration_ms, client_ip 포함

## AC-2: 민감 정보 필터링
- **Given** X-API-Key: secret-key 헤더 요청
- **When** 감사 로그 생성
- **Then** "secret-key" 문자열 미포함

## AC-3: 헬스체크 제외
- **Given** GET /api/v1/health
- **When** 미들웨어 통과
- **Then** audit 로그 미생성

## AC-4: Slow request
- **Given** 5초 초과 요청
- **When** 응답 완료
- **Then** WARNING slow_request 로그
