---
id: SPEC-WEBHOOK-001
version: "1.0.0"
status: completed
created: "2026-06-13"
updated: "2026-06-13"
author: MoAI
priority: medium
issue_number: 0
---

# SPEC-WEBHOOK-001: 웹훅 엔드포인트 관리

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
| 인증 | JWT |

---

## 2. 요구사항 (Requirements)

**[REQ-WEBHOOK-001] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/webhooks 요청 THEN 시스템은 웹훅 엔드포인트를 등록하고 201을 반환해야 한다. URL, 이벤트 타입, secret을 포함한다.

**[REQ-WEBHOOK-002] [유비쿼터스]** 시스템은 항상 사용자 본인의 웹훅 목록을 반환해야 한다. 페이지네이션을 지원한다. secret은 마스킹하여 반환한다.

**[REQ-WEBHOOK-003] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/webhooks/{id} THEN 시스템은 웹훅 단건을 반환해야 한다.

**[REQ-WEBHOOK-004] [이벤트 기반]** WHEN 클라이언트가 PATCH /api/v1/webhooks/{id} THEN 시스템은 웹훅을 부분 수정해야 한다.

**[REQ-WEBHOOK-005] [이벤트 기반]** WHEN 클라이언트가 DELETE /api/v1/webhooks/{id} THEN 시스템은 웹훅을 삭제하고 204를 반환해야 한다.

**[REQ-WEBHOOK-006] [원치 않는 행동]** 시스템은 웹훅 secret을 응답에서 마스킹해야 한다. 원본 secret은 DB에 암호화되어 저장된다.

**[REQ-WEBHOOK-007] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/webhooks/{id}/ping THEN 시스템은 등록된 URL로 테스트 페이로드를 전송하고 응답 코드, 성공 여부, 메시지를 반환해야 한다.

---

## 3. 추적성 (Traceability)

| 요구사항 ID | 엔드포인트 |
|-------------|-----------|
| REQ-WEBHOOK-001 | POST /api/v1/webhooks |
| REQ-WEBHOOK-002 | GET /api/v1/webhooks |
| REQ-WEBHOOK-003 | GET /api/v1/webhooks/{id} |
| REQ-WEBHOOK-004 | PATCH /api/v1/webhooks/{id} |
| REQ-WEBHOOK-005 | DELETE /api/v1/webhooks/{id} |
| REQ-WEBHOOK-007 | POST /api/v1/webhooks/{id}/ping |

---

## 4. 구현 노트

- 구현 파일: `backend/app/api/v1/collaboration/webhooks.py`
- 서비스: `backend/services/webhook_service.py`
- `from_orm_masked()` 메서드로 secret 마스킹 처리
- ping은 비동기 HTTP 전송으로 실제 웹훅 URL에 테스트 이벤트 전달
