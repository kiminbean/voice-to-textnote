---
id: SPEC-ENHANCED-STATS-001
version: "1.0.0"
status: completed
created: "2026-06-13"
updated: "2026-06-13"
author: MoAI
priority: medium
issue_number: 0
---

# SPEC-ENHANCED-STATS-001: 고급 통계 대시보드

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

**[REQ-ESTATS-001] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/enhanced-statistics/{task_id} 요청 THEN 시스템은 고급 통계를 반환해야 한다: 시계열 데이터, 화자 참여도 패턴, 키워드 빈도 추이, 회의 효율성 지표.

**[REQ-ESTATS-002] [유비쿼터스]** 시스템은 항상 time_range(1d/7d/30d/90d), top_n_keywords, include_speaker_analysis, include_efficiency_metrics 파라미터를 지원해야 한다.

**[REQ-ESTATS-003] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/enhanced-statistics/overview 요청 THEN 시스템은 전체 프로젝트 통계 개요를 반환해야 한다.

---

## 3. 추적성 (Traceability)

| 요구사항 ID | 엔드포인트 |
|-------------|-----------|
| REQ-ESTATS-001 | GET /api/v1/enhanced-statistics/{task_id} |
| REQ-ESTATS-002 | (파라미터 지원) |
| REQ-ESTATS-003 | GET /api/v1/enhanced-statistics/overview |

---

## 4. 구현 노트

- 구현 파일: `backend/app/api/v1/analytics/enhanced_statistics.py`
- 서비스: `backend/services/enhanced_statistics.py`
- 회의 효율성 지표: 발화 밀도, 발언 균형도, 키워드 다양성 등
