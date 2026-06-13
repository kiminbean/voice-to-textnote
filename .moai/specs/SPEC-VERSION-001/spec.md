---
id: SPEC-VERSION-001
version: "1.0.0"
status: completed
created: "2026-06-13"
updated: "2026-06-13"
author: MoAI
priority: medium
issue_number: 0
---

# SPEC-VERSION-001: 회의록 버전 관리

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

**[REQ-VERSION-001] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/minutes/{task_id}/versions 요청 THEN 시스템은 회의록 현재 내용을 버전 스냅샷으로 저장하고 201을 반환해야 한다.

**[REQ-VERSION-002] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/minutes/{task_id}/versions 요청 THEN 시스템은 버전 목록을 최신순으로 반환해야 한다. 페이지네이션(limit, offset)을 지원한다.

**[REQ-VERSION-003] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/minutes/{task_id}/versions/{version_id} THEN 시스템은 특정 버전 단건을 반환해야 한다.

**[REQ-VERSION-004] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/minutes/{task_id}/versions/{from}/diff/{to} THEN 시스템은 두 버전 간 텍스트 unified diff를 반환해야 한다. 추가/삭제 라인 수를 포함한다.

**[REQ-VERSION-005] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/minutes/{task_id}/versions/{from}/structured-diff/{to} THEN 시스템은 JSON 구조 기반 diff를 반환해야 한다. summary_text, sections, action_items를 added/removed/modified로 분류한다.

**[REQ-VERSION-006] [이벤트 기반]** WHEN 클라이언트가 DELETE /api/v1/minutes/{task_id}/versions/{version_id} THEN 시스템은 버전을 삭제하고 204를 반환해야 한다.

---

## 3. 추적성 (Traceability)

| 요구사항 ID | 엔드포인트 |
|-------------|-----------|
| REQ-VERSION-001 | POST /api/v1/minutes/{task_id}/versions |
| REQ-VERSION-002 | GET /api/v1/minutes/{task_id}/versions |
| REQ-VERSION-003 | GET /api/v1/minutes/{task_id}/versions/{id} |
| REQ-VERSION-004 | GET .../versions/{from}/diff/{to} |
| REQ-VERSION-005 | GET .../versions/{from}/structured-diff/{to} |
| REQ-VERSION-006 | DELETE .../versions/{id} |

---

## 4. 구현 노트

- 구현 파일: `backend/app/api/v1/collaboration/versions.py`
- 서비스: `backend/services/version_service.py` (compute_diff, compute_structured_diff)
- 모델: `backend/db/version_models.py` (MinutesVersion)
- structured-diff는 클라이언트가 필드 단위 UI 렌더링을 할 수 있도록 섹션/액션아이템별 분류 제공
