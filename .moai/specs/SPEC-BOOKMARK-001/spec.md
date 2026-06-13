---
id: SPEC-BOOKMARK-001
version: "1.0.0"
status: completed
created: "2026-06-13"
updated: "2026-06-13"
author: MoAI
priority: medium
issue_number: 0
---

# SPEC-BOOKMARK-001: 회의록 북마크/하이라이트 관리

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-06-13 | 기존 구현 문서화 | MoAI |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 플랫폼 | M4 Mac Mini 24GB (Apple Silicon) |
| 런타임 | Python >= 3.11, FastAPI >= 0.135.1 |
| 데이터베이스 | PostgreSQL / SQLite (SQLAlchemy async) |
| 인증 | JWT (SPEC-TEAM-001 기반) |

---

## 2. 요구사항 (Requirements)

### 모듈 1: 북마크 CRUD

**[REQ-BOOKMARK-001] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/bookmarks 요청을 보내면 THEN 시스템은 북마크를 생성하고 201 Created를 반환해야 한다.

**[REQ-BOOKMARK-002] [유비쿼터스]** 시스템은 항상 사용자 본인의 북마크만 조회할 수 있도록 해야 한다. task_id로 필터링을 지원한다.

**[REQ-BOOKMARK-003] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/bookmarks/{bookmark_id}를 요청 THEN 시스템은 북마크 단건 정보를 반환해야 한다.

**[REQ-BOOKMARK-004] [이벤트 기반]** WHEN 클라이언트가 PATCH /api/v1/bookmarks/{bookmark_id}를 요청 THEN 시스템은 북마크를 부분 수정해야 한다.

**[REQ-BOOKMARK-005] [이벤트 기반]** WHEN 클라이언트가 DELETE /api/v1/bookmarks/{bookmark_id}를 요청 THEN 시스템은 북마크를 삭제하고 204 No Content를 반환해야 한다.

### 모듈 2: 확장 기능

**[REQ-BOOKMARK-006] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/bookmarks/bulk를 요청 THEN 시스템은 대량 삭제 또는 카테고리/우선순위 업데이트를 수행해야 한다.

**[REQ-BOOKMARK-007] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/bookmarks/search를 요청 THEN 시스템은 검색어, 카테고리, 우선순위, 태그, 날짜 범위로 필터링된 결과를 반환해야 한다.

**[REQ-BOOKMARK-008] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/bookmarks/summary를 요청 THEN 시스템은 북마크 통계 및 요약 정보를 반환해야 한다.

**[REQ-BOOKMARK-009] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/bookmarks/cleanup을 요청 THEN 시스템은 중복 또는 오래된 북마크를 정리해야 한다.

**[REQ-BOOKMARK-010] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/bookmarks/export를 요청 THEN 시스템은 JSON, CSV, Markdown 형식으로 북마크를 내보내야 한다.

---

## 3. 추적성 (Traceability)

| 요구사항 ID | 엔드포인트 |
|-------------|-----------|
| REQ-BOOKMARK-001 | POST /api/v1/bookmarks |
| REQ-BOOKMARK-002 | GET /api/v1/bookmarks |
| REQ-BOOKMARK-003 | GET /api/v1/bookmarks/{id} |
| REQ-BOOKMARK-004 | PATCH /api/v1/bookmarks/{id} |
| REQ-BOOKMARK-005 | DELETE /api/v1/bookmarks/{id} |
| REQ-BOOKMARK-006 | POST /api/v1/bookmarks/bulk |
| REQ-BOOKMARK-007 | GET /api/v1/bookmarks/search |
| REQ-BOOKMARK-008 | GET /api/v1/bookmarks/summary |
| REQ-BOOKMARK-009 | POST /api/v1/bookmarks/cleanup |
| REQ-BOOKMARK-010 | POST /api/v1/bookmarks/export |

---

## 4. 구현 노트

- 구현 파일: `backend/app/api/v1/collaboration/bookmarks.py`, `backend/services/bookmark_service.py`
- 스키마: `backend/schemas/bookmark.py`
- 모든 엔드포인트 JWT 인증 필요
- 페이지네이션: page/page_size 파라미터 사용
