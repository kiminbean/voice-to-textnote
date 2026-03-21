# SPEC-PERSIST-001 구현 계획

## Task 1: 동기 DB 엔진 (sync_engine.py)
- create_engine (동기)
- sessionmaker
- get_sync_session context manager

## Task 2: 동기 ResultService (sync_service.py)
- persist_task_result(task_id, task_type, status, result_data, error_message)
- 내부에서 try-except + 로깅 (실패 안전)

## Task 3: API 결과 폴백 (result_fallback.py)
- get_result_with_fallback(redis, task_id, task_type, db_session)
- Redis 우선 → DB 폴백 → Redis 캐시 복원

## Task 4: 태스크 워커 연동
- 각 task 파일에 persist 호출 추가 (완료/실패 시)

## 리스크
- Celery 동기 + SQLAlchemy 동기 연결 안정성 → 커넥션 풀 관리
