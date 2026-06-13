---
id: SPEC-VOCAB-001
version: "1.0.0"
status: completed
created: "2026-06-13"
updated: "2026-06-13"
author: MoAI
priority: medium
issue_number: 0
---

# SPEC-VOCAB-001: 커스텀 어휘 관리

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

---

## 2. 요구사항 (Requirements)

**[REQ-VOCAB-001] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/vocabulary 요청 THEN 시스템은 커스텀 어휘 리스트를 생성하고 201을 반환해야 한다.

**[REQ-VOCAB-002] [유비쿼터스]** 시스템은 항상 어휘 리스트 목록을 반환해야 한다. 페이지네이션을 지원한다.

**[REQ-VOCAB-003] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/vocabulary/{id} THEN 시스템은 어휘 리스트 단건을 반환해야 한다.

**[REQ-VOCAB-004] [이벤트 기반]** WHEN 클라이언트가 PUT /api/v1/vocabulary/{id} THEN 시스템은 어휘 리스트를 수정해야 한다.

**[REQ-VOCAB-005] [이벤트 기반]** WHEN 클라이언트가 DELETE /api/v1/vocabulary/{id} THEN 시스템은 어휘 리스트를 삭제하고 204를 반환해야 한다.

---

## 3. 추적성 (Traceability)

| 요구사항 ID | 엔드포인트 |
|-------------|-----------|
| REQ-VOCAB-001 | POST /api/v1/vocabulary |
| REQ-VOCAB-002 | GET /api/v1/vocabulary |
| REQ-VOCAB-003 | GET /api/v1/vocabulary/{id} |
| REQ-VOCAB-004 | PUT /api/v1/vocabulary/{id} |
| REQ-VOCAB-005 | DELETE /api/v1/vocabulary/{id} |

---

## 4. 구현 노트

- 구현 파일: `backend/app/api/v1/analytics/vocabulary.py`
- 서비스: `backend/services/vocabulary_service.py`
- 어휘 리스트는 STT 정확도 향상을 위한 도메인 특화 용어 사전으로 사용됨
- JWT 인증 불필요 (API Key 기반 접근)
