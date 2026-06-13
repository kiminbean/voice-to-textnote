---
id: SPEC-ADVANCED-SEARCH-001
version: "1.0.0"
status: completed
created: "2026-06-13"
updated: "2026-06-13"
author: MoAI
priority: medium
issue_number: 0
---

# SPEC-ADVANCED-SEARCH-001: 고급 검색 (필터/정렬/히스토리)

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

**[REQ-ASEARCH-001] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/advanced-search/search 요청 THEN 시스템은 다양한 필터(날짜 범위, 화자 ID, 콘텐츠 유형, 태그, 단어 수 범위)와 정렬 옵션을 적용한 검색 결과를 반환해야 한다. 결과에는 pagination과 analytics 통계가 포함된다.

**[REQ-ASEARCH-002] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/advanced-search/history 요청 THEN 시스템은 검색 히스토리를 반환해야 한다.

**[REQ-ASEARCH-003] [이벤트 기반]** WHEN 클라이언트가 DELETE /api/v1/advanced-search/history 요청 THEN 시스템은 검색 히스토리를 삭제해야 한다.

**[REQ-ASEARCH-004] [유비쿼터스]** 시스템은 항상 검색 결과에 query_info(적용된 필터, 정렬 정보)를 포함해야 한다.

---

## 3. 추적성 (Traceability)

| 요구사항 ID | 엔드포인트 |
|-------------|-----------|
| REQ-ASEARCH-001 | POST /api/v1/advanced-search/search |
| REQ-ASEARCH-002 | GET /api/v1/advanced-search/history |
| REQ-ASEARCH-003 | DELETE /api/v1/advanced-search/history |

---

## 4. 구현 노트

- 구현 파일: `backend/app/api/v1/analytics/advanced_search.py`
- 서비스: `backend/services/advanced_search.py` (AdvancedSearchService)
- 검색 결과는 Redis 기반 인덱스 사용
- AdvancedSearchRequest에 필터/정렬/페이지네이션 정보 포함
