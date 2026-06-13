---
id: SPEC-CAL-001
version: "1.0.0"
status: completed
created: "2026-06-13"
updated: "2026-06-13"
author: MoAI
priority: medium
issue_number: 0
---

# SPEC-CAL-001: 캘린더 통합 (이벤트 생성/조회/삭제)

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-06-13 | 기존 구현 문서화 | MoAI |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 런타임 | Python >= 3.11, FastAPI >= 0.135.1 |
| 데이터베이스 | PostgreSQL / SQLite (SQLAlchemy async) |
| 캐시 | Redis |

---

## 2. 요구사항 (Requirements)

**[REQ-CAL-001] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/calendar/events/{task_id} 요청 THEN 시스템은 회의록 데이터에서 캘린더 이벤트를 생성(미팅 일정, 참가자, 액션 아이템 포함)하여 201을 반환해야 한다. calendar_type 쿼리 파라미터로 캘린더 서비스(google, outlook, ical)를 선택할 수 있다.

**[REQ-CAL-002] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/calendar/events/{task_id} 요청 THEN 시스템은 생성된 캘린더 이벤트를 반환해야 한다.

**[REQ-CAL-003] [이벤트 기반]** WHEN 클라이언트가 DELETE /api/v1/calendar/events/{task_id} 요청 THEN 시스템은 캘린더 이벤트를 삭제하고 204를 반환해야 한다.

**[REQ-CAL-004] [원치 않는 행동]** 시스템은 회의록 데이터를 찾을 수 없으면 404를, 회의록 데이터가 불완전하면 422를 반환해야 한다.

**[REQ-CAL-005] [유비쿼터스]** 시스템은 CalendarService.SUPPORTED_CALENDARS에 정의된 캘린더 타입만 허용해야 한다.

---

## 3. 추적성 (Traceability)

| 요구사항 ID | 엔드포인트 |
|-------------|-----------|
| REQ-CAL-001 | POST /api/v1/calendar/events/{task_id} |
| REQ-CAL-002 | GET /api/v1/calendar/events/{task_id} |
| REQ-CAL-003 | DELETE /api/v1/calendar/events/{task_id} |

---

## 4. 구현 노트

- 구현 파일: `backend/app/api/v1/admin/calendar.py`
- 서비스: `backend/services/calendar_service.py`
- 스키마: `backend/schemas/calendar.py`
- 연관: SPEC-REFACTOR-001 (서비스 계층 분리 + 에러 헬퍼 마이그레이션)
