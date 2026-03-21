# SPEC-DB-001 구현 계획

## Task 1: 의존성 추가 (pyproject.toml)
- sqlalchemy[asyncio]>=2.0
- asyncpg>=0.29 (PostgreSQL async driver)
- aiosqlite>=0.20 (SQLite async for tests)
- alembic>=1.13

## Task 2: DB 엔진/세션 (backend/db/engine.py)
- create_async_engine with DATABASE_URL
- SQLite 폴백 (DATABASE_URL 미설정 시)
- async_sessionmaker
- get_db_session async generator

## Task 3: 모델 (backend/db/models.py)
- Base = declarative_base()
- TaskResult: task_id, task_type, status, input_metadata, result_data, error_message, timestamps
- AuditLog: request_id, method, path, status_code, client_ip, duration_ms, timestamp

## Task 4: 결과 영속 서비스 (backend/db/service.py)
- ResultService class
- save_result(), get_result(), list_results()

## Task 5: Alembic 설정
- alembic.ini
- alembic/env.py (async 지원)
- 초기 마이그레이션

## Task 6: FastAPI 통합
- config.py에 DATABASE_URL 추가
- dependencies.py에 get_db_session 추가
- main.py lifespan에 테이블 자동 생성

## Task 7: config.py 업데이트
- database_url 필드 추가
- db_pool_size, db_max_overflow 필드

## 리스크
- asyncpg vs aiosqlite 호환성 → SQLAlchemy async 추상화로 해결
- 기존 테스트 영향 → 새 테스트에서만 DB 사용, 기존 테스트 불변
