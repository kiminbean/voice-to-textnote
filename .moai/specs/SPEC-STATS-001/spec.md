---
id: SPEC-STATS-001
version: "1.0.0"
status: completed
created: "2026-06-13"
updated: "2026-06-13"
author: MoAI
priority: medium
issue_number: 0
---

# SPEC-STATS-001: 회의 통계 대시보드

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

**[REQ-STATS-001] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/statistics/{task_id} 요청 THEN 시스템은 해당 회의록의 통계를 반환해야 한다: 화자별 발화 시간/비율, 세그먼트 수, 단어 수, 키워드 빈도.

**[REQ-STATS-002] [유비쿼터스]** 시스템은 항상 읽기 전용으로 동작해야 하며, 저장소 구조를 변경하지 않아야 한다.

**[REQ-STATS-003] [유비쿼터스]** 시스템은 항상 top_n(상위 키워드 수) 및 min_length(키워드 최소 글자 수) 파라미터를 지원해야 한다.

---

## 3. 추적성 (Traceability)

| 요구사항 ID | 엔드포인트 |
|-------------|-----------|
| REQ-STATS-001 | GET /api/v1/statistics/{task_id} |
| REQ-STATS-002 | (읽기 전용 제약) |
| REQ-STATS-003 | GET /api/v1/statistics/{task_id}?top_n=&min_length= |

---

## 4. 구현 노트

- 구현 파일: `backend/app/api/v1/analytics/statistics.py`
- 서비스: `backend/services/statistics.py` (StatisticsService.compute)
- Redis에서 minutes 결과를 조회하여 통계 계산
