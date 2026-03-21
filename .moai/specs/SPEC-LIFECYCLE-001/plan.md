# SPEC-LIFECYCLE-001 구현 계획

## Task 1: 수명주기 헬퍼 (lifecycle.py)
- validate_startup() - Redis, DB, 모델 상태 검증
- cleanup_shutdown() - DB dispose, 로깅

## Task 2: lifespan 업데이트 (main.py)
- startup: validate_startup() + DB 테이블 생성
- shutdown: cleanup_shutdown()

## Task 3: health 업데이트 (health.py)
- version, started_at, uptime_seconds 추가

## 리스크
- DB 초기화가 모델 로드보다 먼저 → 순서 관리
