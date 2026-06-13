---
id: SPEC-ACTION-001
version: "1.0.0"
status: completed
created: "2026-06-13"
updated: "2026-06-13"
author: MoAI
priority: medium
issue_number: 0
---

# SPEC-ACTION-001: 액션 아이템 추출 및 관리

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

### 모듈 1: 액션 아이템 추출

**[REQ-ACTION-001] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/action-items/extract 요청 THEN 시스템은 입력 텍스트에서 액션 아이템(할 일, 담당자, 기한, 우선순위)을 추출하여 반환해야 한다.

**[REQ-ACTION-002] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/action-items/meeting 요청 THEN 시스템은 기존 회의록에서 액션 아이템을 추출하여 반환해야 한다.

### 모듈 2: 액션 아이템 CRUD 및 관리

**[REQ-ACTION-003] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/action-items 요청 THEN 시스템은 사용자의 액션 아이템 목록을 반환해야 한다. 필터(status, priority, assignee_id, meeting_id, due_from, due_to)와 페이지네이션을 지원한다.

**[REQ-ACTION-004] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/action-items 요청 THEN 시스템은 새 액션 아이템을 생성하고 201을 반환해야 한다.

**[REQ-ACTION-005] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/action-items/{id} 요청 THEN 시스템은 단건 액션 아이템을 반환해야 한다.

**[REQ-ACTION-006] [이벤트 기반]** WHEN 클라이언트가 PATCH /api/v1/action-items/{id} 요청 THEN 시스템은 액션 아이템을 수정해야 한다.

**[REQ-ACTION-007] [이벤트 기반]** WHEN 클라이언트가 DELETE /api/v1/action-items/{id} 요청 THEN 시스템은 액션 아이템을 삭제하고 204를 반환해야 한다.

**[REQ-ACTION-008] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/action-items/meeting/{meeting_id} 요청 THEN 시스템은 특정 회의의 액션 아이템 목록을 반환해야 한다.

**[REQ-ACTION-009] [이벤트 기반]** WHEN 클라이언트가 PATCH /api/v1/action-items/{id}/complete 요청 THEN 시스템은 액션 아이템을 완료 처리해야 한다.

**[REQ-ACTION-010] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/action-items/overview 요청 THEN 시스템은 액션 아이템 대시보드(상태별/우선순위별 통계)를 반환해야 한다.

**[REQ-ACTION-011] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/action-items/batch-update 요청 THEN 시스템은 여러 액션 아이템을 일괄 수정하고 성공/실패 결과를 반환해야 한다.

---

## 3. 추적성 (Traceability)

| 요구사항 ID | 엔드포인트 |
|-------------|-----------|
| REQ-ACTION-001 | POST /api/v1/action-items/extract |
| REQ-ACTION-002 | POST /api/v1/action-items/meeting |
| REQ-ACTION-003 | GET /api/v1/action-items |
| REQ-ACTION-004 | POST /api/v1/action-items |
| REQ-ACTION-005 | GET /api/v1/action-items/{id} |
| REQ-ACTION-006 | PATCH /api/v1/action-items/{id} |
| REQ-ACTION-007 | DELETE /api/v1/action-items/{id} |
| REQ-ACTION-008 | GET /api/v1/action-items/meeting/{meeting_id} |
| REQ-ACTION-009 | PATCH /api/v1/action-items/{id}/complete |
| REQ-ACTION-010 | GET /api/v1/action-items/overview |
| REQ-ACTION-011 | POST /api/v1/action-items/batch-update |

---

## 4. 구현 노트

- 추출 엔드포인트: `backend/app/api/v1/minutes/action_items.py`
- CRUD 엔드포인트: `backend/app/api/v1/minutes/action_items_crud.py`
- 추출 엔진: `backend/ml/action_items_engine.py`
- 서비스: `backend/services/action_item_service.py`
- 스키마: `backend/app/schemas/action_item.py`, `backend/schemas/action_items.py`
