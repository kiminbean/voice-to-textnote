---
id: SPEC-KEYWORD-001
version: "1.0.0"
status: completed
created: "2026-06-13"
updated: "2026-06-13"
author: MoAI
priority: medium
issue_number: 0
---

# SPEC-KEYWORD-001: 키워드 검색, 추천 및 통계

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

**[REQ-KEYWORD-001] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/keywords/search?q={query} 요청 THEN 시스템은 전체 문서에서 키워드 위치 및 컨텍스트를 검색하여 반환해야 한다. 다중 필터링(날짜, 화자, 문서 유형), 정렬 옵션(관련도/빈도/최신순), 페이지네이션을 지원한다.

**[REQ-KEYWORD-002] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/keywords/suggest 요청 THEN 시스템은 입력 키워드 기반으로 자동 추천 키워드 목록을 반환해야 한다.

**[REQ-KEYWORD-003] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/keywords/stats 요청 THEN 시스템은 키워드 빈도 통계를 반환해야 한다.

**[REQ-KEYWORD-004] [원치 않는 행동]** 시스템은 검색 키워드가 1글자 미만이면 422 Unprocessable Entity를 반환해야 한다.

---

## 3. 추적성 (Traceability)

| 요구사항 ID | 엔드포인트 |
|-------------|-----------|
| REQ-KEYWORD-001 | GET /api/v1/keywords/search |
| REQ-KEYWORD-002 | GET /api/v1/keywords/suggest |
| REQ-KEYWORD-003 | GET /api/v1/keywords/stats |

---

## 4. 구현 노트

- 구현 파일: `backend/app/api/v1/analytics/keyword_search.py`
- 서비스: `backend/services/keyword_service.py` (context_before/context_after 기반 검색)
- 스키마: `backend/schemas/keyword.py` (KeywordSearchFilter, SortOption)
