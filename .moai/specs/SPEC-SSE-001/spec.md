---
id: SPEC-SSE-001
version: "1.0.0"
status: completed
created: 2026-03-21
updated: 2026-03-21
author: kisoo
priority: P2
issue_number: 0
---

# SPEC-SSE-001: Server-Sent Events 실시간 작업 상태 스트리밍

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-03-21 | 초안 작성 | kisoo |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 런타임 | Python >= 3.11, FastAPI >= 0.135.1 |
| SSE | sse-starlette >= 2.0 |
| 이벤트 소스 | Redis Pub/Sub (기존 Redis 활용) |

---

## 2. 가정 (Assumptions)

- 기존 폴링 방식 API(/status)는 유지하고 SSE 엔드포인트를 추가한다.
- Redis Pub/Sub을 이벤트 채널로 사용하여 Celery worker와 API 서버 간 통신한다.
- 각 task_id에 대해 별도 SSE 스트림을 제공한다.
- 작업 완료 또는 실패 시 SSE 스트림을 자동 종료한다.

---

## 3. 요구사항 (Requirements)

### 모듈 1: SSE 엔드포인트

**[REQ-SSE-001] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/tasks/{task_id}/stream 요청 THEN text/event-stream 형식으로 실시간 상태 업데이트를 스트리밍해야 한다.

**[REQ-SSE-002] [유비쿼터스]** SSE 이벤트는 event(status_update/completed/failed), data(JSON: status, progress, message), id(이벤트 시퀀스) 필드를 포함해야 한다.

**[REQ-SSE-003] [이벤트 기반]** WHEN 작업 상태가 completed 또는 failed THEN SSE 스트림을 자동 종료해야 한다.

**[REQ-SSE-004] [이벤트 기반]** WHEN 클라이언트가 연결 끊기 THEN 서버 리소스를 즉시 해제해야 한다.

### 모듈 2: 이벤트 발행

**[REQ-SSE-005] [이벤트 기반]** WHEN Celery 작업 상태가 변경 THEN Redis Pub/Sub 채널(task:{task_id}:status)에 이벤트를 발행해야 한다.

**[REQ-SSE-006] [유비쿼터스]** 이벤트 발행 유틸리티는 publish_task_event(task_id, event_type, data) 인터페이스를 제공해야 한다.

### 모듈 3: 하트비트

**[REQ-SSE-007] [유비쿼터스]** SSE 스트림은 15초마다 하트비트(:ping) 이벤트를 전송하여 연결 유지를 확인해야 한다.

---

## 4. 인수 조건 (Acceptance Criteria)

### AC-1: SSE 스트림 연결
- **Given** 서버 실행 중
- **When** GET /api/v1/tasks/{task_id}/stream
- **Then** Content-Type: text/event-stream 응답

### AC-2: 상태 업데이트 수신
- **Given** SSE 스트림 연결 상태
- **When** 작업 상태 변경 이벤트 발행
- **Then** 클라이언트가 이벤트 수신

### AC-3: 작업 완료 시 종료
- **Given** SSE 스트림 연결 상태
- **When** completed 이벤트 수신
- **Then** 스트림 자동 종료

### AC-4: 잘못된 task_id
- **Given** 존재하지 않는 task_id
- **When** 스트림 연결
- **Then** 즉시 404 에러 이벤트 + 종료

---

## 5. 기술 접근 방식

### 파일 구조

```
backend/
├── app/
│   ├── api/v1/
│   │   └── stream.py             # SSE 엔드포인트
│   └── main.py                    # 라우터 등록
├── events/
│   ├── __init__.py
│   ├── publisher.py              # Redis Pub/Sub 이벤트 발행
│   └── subscriber.py            # Redis Pub/Sub 이벤트 구독
├── tests/unit/
│   ├── test_sse_stream.py
│   └── test_event_publisher.py
```
