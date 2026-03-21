# SPEC-LIFECYCLE-001 인수 조건

## AC-1: 시작 검증 로그
- 서버 시작 → redis/db/model 상태 로그

## AC-2: DB 테이블 생성
- DATABASE_URL 미설정 → SQLite 테이블 자동 생성

## AC-3: Graceful Shutdown
- 종료 → DB dispose + 로그

## AC-4: 버전 정보
- GET /api/v1/health → version, started_at, uptime_seconds
