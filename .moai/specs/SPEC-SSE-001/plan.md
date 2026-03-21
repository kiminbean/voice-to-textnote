# SPEC-SSE-001 구현 계획

## Task 1: 의존성 (pyproject.toml)
- sse-starlette>=2.0

## Task 2: 이벤트 발행 (backend/events/publisher.py)
- publish_task_event(task_id, event_type, data)
- Redis Pub/Sub 채널: task:{task_id}:status

## Task 3: 이벤트 구독 (backend/events/subscriber.py)
- subscribe_task_events(task_id) async generator
- Redis Pub/Sub 구독

## Task 4: SSE 엔드포인트 (backend/app/api/v1/stream.py)
- GET /api/v1/tasks/{task_id}/stream
- EventSourceResponse
- 15초 하트비트
- completed/failed 시 종료

## Task 5: main.py 라우터 등록

## 리스크
- Redis Pub/Sub 연결 끊김 → 재연결 로직 필요
- 다수 동시 SSE 연결 → 메모리 관리
