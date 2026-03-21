# SPEC-LOG-001 구현 계획

## Task 1: 감사 로깅 미들웨어 (audit_log.py)
- Starlette BaseHTTPMiddleware 기반
- 타이머로 duration_ms 측정
- 헬스체크/메트릭 경로 제외
- 민감 헤더 필터링

## Task 2: Slow request 경고
- 5초 초과 시 WARNING 로그

## Task 3: main.py 통합
- 미들웨어 등록 (request_id 다음)

## 의존성
- 추가 의존성 없음 (기존 structlog 활용)
