# SPEC-SSE-001 인수 조건

## AC-1: SSE 연결
- **Given** 서버 실행 중
- **When** GET /api/v1/tasks/test-id/stream
- **Then** Content-Type: text/event-stream

## AC-2: 이벤트 수신
- **Given** SSE 연결 상태
- **When** publish_task_event("test-id", "status_update", {"status": "processing"})
- **Then** 클라이언트 이벤트 수신

## AC-3: 완료 시 종료
- **Given** SSE 연결 상태
- **When** "completed" 이벤트
- **Then** 스트림 종료

## AC-4: 잘못된 ID
- **Given** task_id 미존재
- **When** 스트림 연결
- **Then** 에러 이벤트 + 종료
