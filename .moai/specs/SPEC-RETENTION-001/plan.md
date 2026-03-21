# SPEC-RETENTION-001 구현 계획

## Task 1: 설정 추가 (config.py)
- data_retention_days (기본 30)
- temp_file_retention_hours (기본 24)

## Task 2: 보존 서비스 (services/retention.py)
- cleanup_expired_results(session, retention_days)
- cleanup_temp_files(temp_dir, retention_hours)

## Task 3: Celery 태스크 (workers/tasks/cleanup_task.py)
- cleanup_task - 매일 실행

## Task 4: Celery Beat 스케줄 (celery_app.py)
- beat_schedule 추가

## Task 5: 관리자 API (app/api/v1/admin.py)
- POST /admin/cleanup → 즉시 정리
