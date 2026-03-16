# SPEC-OPS-001 인수 조건

## AC-1: 메트릭 엔드포인트
- **Given** 서버 실행 중
- **When** GET /metrics
- **Then** text/plain Prometheus 메트릭

## AC-2: HTTP 메트릭
- **Given** POST /api/v1/transcriptions 요청 후
- **When** GET /metrics
- **Then** http_requests_total{method="POST", handler="/api/v1/transcriptions"} 포함

## AC-3: 요청 ID 생성
- **Given** 요청에 X-Request-ID 미포함
- **When** 응답 수신
- **Then** X-Request-ID 헤더에 UUID 포함

## AC-4: 요청 ID 전파
- **Given** X-Request-ID: test-123 헤더 포함
- **When** 응답 수신
- **Then** 동일 ID 반환

## AC-5: Readiness
- **Given** Redis 정상 연결
- **When** GET /api/v1/health/ready
- **Then** 200 OK
