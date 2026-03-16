# SPEC-SEC-001 인수 조건

## AC-1: API Key 인증 작동
- **Given** API_KEYS="test-key-1,test-key-2" 환경 변수 설정
- **When** X-API-Key: test-key-1 헤더로 POST /api/v1/transcriptions 요청
- **Then** 정상 응답 (HTTP 200/202)

## AC-2: 미인증 접근 차단
- **Given** API_KEYS="test-key-1" 환경 변수 설정
- **When** X-API-Key 헤더 없이 POST /api/v1/transcriptions 요청
- **Then** HTTP 401 Unauthorized

## AC-3: 헬스체크 공개 접근
- **Given** API_KEYS="test-key-1" 환경 변수 설정
- **When** X-API-Key 없이 GET /api/v1/health 요청
- **Then** HTTP 200 OK

## AC-4: 레이트 리미팅 작동
- **Given** RATE_LIMIT_PER_MINUTE=5 설정
- **When** 1분 내 동일 IP에서 6번째 요청
- **Then** HTTP 429 + Retry-After 헤더

## AC-5: 개발 모드
- **Given** API_KEYS 환경 변수 미설정
- **When** 인증 없이 요청
- **Then** 정상 처리

## AC-6: 보안 헤더
- **Given** 서버 실행 중
- **When** 임의의 요청
- **Then** X-Content-Type-Options: nosniff, X-Frame-Options: DENY 포함

## 엣지 케이스

- 잘못된 API Key → 401
- 빈 문자열 API Key → 401
- Redis 다운 시 레이트 리미팅 → 인메모리 폴백으로 계속 작동
- 쿼리 파라미터로 API Key 전달 → 정상 인증
