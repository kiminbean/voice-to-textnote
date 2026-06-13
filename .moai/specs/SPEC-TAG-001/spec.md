---
id: SPEC-TAG-001
version: "1.0.0"
status: completed
created: "2026-06-13"
updated: "2026-06-13"
author: MoAI
priority: medium
issue_number: 0
---

# SPEC-TAG-001: 회의록 태그 관리 (수동 + AI 자동 태깅)

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
| AI 태깅 | `backend/ml/tagging_engine.py` (generate_auto_tags) |

---

## 2. 요구사항 (Requirements)

**[REQ-TAG-001] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/tags/auto 요청 THEN 시스템은 회의록 내용을 AI로 분석하여 자동 태그를 생성하고 DB에 저장한 후 201을 반환해야 한다. 최대 태그 수(max_tags)를 지원한다.

**[REQ-TAG-002] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/tags 요청 THEN 시스템은 수동 태그를 생성하고 201을 반환해야 한다.

**[REQ-TAG-003] [유비쿼터스]** 시스템은 항상 회의록의 태그 목록을 반환해야 한다. task_id는 필수이며, tag_type 및 source(auto/manual) 필터를 지원한다.

**[REQ-TAG-004] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/tags/{id} THEN 시스템은 태그 단건을 반환해야 한다.

**[REQ-TAG-005] [이벤트 기반]** WHEN 클라이언트가 PATCH /api/v1/tags/{id} THEN 시스템은 태그를 수정해야 한다.

**[REQ-TAG-006] [이벤트 기반]** WHEN 클라이언트가 DELETE /api/v1/tags/{id} THEN 시스템은 태그를 삭제하고 204를 반환해야 한다.

**[REQ-TAG-007] [이벤트 기반]** WHEN 클라이언트가 DELETE /api/v1/tags/bulk/delete THEN 시스템은 회의록의 태그를 일괄 삭제해야 한다. source 필터로 auto/manual 중 선택적 삭제를 지원한다.

---

## 3. 추적성 (Traceability)

| 요구사항 ID | 엔드포인트 |
|-------------|-----------|
| REQ-TAG-001 | POST /api/v1/tags/auto |
| REQ-TAG-002 | POST /api/v1/tags |
| REQ-TAG-003 | GET /api/v1/tags |
| REQ-TAG-004 | GET /api/v1/tags/{id} |
| REQ-TAG-005 | PATCH /api/v1/tags/{id} |
| REQ-TAG-006 | DELETE /api/v1/tags/{id} |
| REQ-TAG-007 | DELETE /api/v1/tags/bulk/delete |

---

## 4. 구현 노트

- 구현 파일: `backend/app/api/v1/minutes/tags.py`
- 서비스: `backend/services/tag_service.py`
- AI 태깅: `backend/ml/tagging_engine.py` (회의록 내용 분석 → 태그 추출)
- 태그 속성: tag_type(topic/person/action 등), tag_value, source(auto/manual), confidence
