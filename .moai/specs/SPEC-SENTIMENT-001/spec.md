---
id: SPEC-SENTIMENT-001
version: "1.0.0"
status: completed
created: "2026-06-13"
updated: "2026-06-13"
author: MoAI
priority: medium
issue_number: 0
---

# SPEC-SENTIMENT-001: 회의 감성 분석

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
| AI | OpenAI 호환 API (settings.summary_model) |

---

## 2. 요구사항 (Requirements)

### 모듈 1: 감성 분석 조회 (동기)

**[REQ-SENTIMENT-001] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/sentiment/meeting/{meeting_id} 요청 THEN 시스템은 특정 회의의 감성 분석 결과를 반환해야 한다.

**[REQ-SENTIMENT-002] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/sentiment/trends 요청 THEN 시스템은 시간별 감성 추이 분석을 반환해야 한다.

**[REQ-SENTIMENT-003] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/sentiment/speaker/{speaker_id} 요청 THEN 시스템은 화자별 감성 분석을 반환해야 한다.

**[REQ-SENTIMENT-004] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/sentiment/dashboard/summary 요청 THEN 시스템은 감성 대시보드 요약을 반환해야 한다.

### 모듈 2: 감성 분석 작업 (비동기)

**[REQ-SENTIMENT-005] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/sentiment 요청 THEN 시스템은 감정 분석 작업을 생성하고 202 Accepted를 반환해야 한다.

**[REQ-SENTIMENT-006] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/sentiment/{task_id}/status 요청 THEN 시스템은 작업 상태를 반환해야 한다.

**[REQ-SENTIMENT-007] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/sentiment/{task_id} 요청 (completed 상태) THEN 시스템은 전체 감성 분석 결과를 반환해야 한다.

**[REQ-SENTIMENT-008] [이벤트 기반]** WHEN 클라이언트가 DELETE /api/v1/sentiment/{task_id} 요청 THEN 시스템은 작업을 삭제하고 204를 반환해야 한다.

---

## 3. 감성 점수 스키마

| 필드 | 타입 | 설명 |
|------|------|------|
| positive | float (0.0~1.0) | 긍정적 감성 비율 |
| neutral | float (0.0~1.0) | 중립적 감성 비율 |
| negative | float (0.0~1.0) | 부정적 감성 비율 |
| dominant | SentimentLabel | 주요 감성 (positive/neutral/negative) |
| overall_score | float (-1.0~1.0) | 종합 감성 점수 |
| trend_direction | improving/declining/stable | 추이 방향 |

---

## 4. 추적성 (Traceability)

| 요구사항 ID | 엔드포인트 |
|-------------|-----------|
| REQ-SENTIMENT-001 | GET /api/v1/sentiment/meeting/{meeting_id} |
| REQ-SENTIMENT-002 | GET /api/v1/sentiment/trends |
| REQ-SENTIMENT-003 | GET /api/v1/sentiment/speaker/{speaker_id} |
| REQ-SENTIMENT-004 | GET /api/v1/sentiment/dashboard/summary |
| REQ-SENTIMENT-005 | POST /api/v1/sentiment |
| REQ-SENTIMENT-006 | GET /api/v1/sentiment/{task_id}/status |
| REQ-SENTIMENT-007 | GET /api/v1/sentiment/{task_id} |
| REQ-SENTIMENT-008 | DELETE /api/v1/sentiment/{task_id} |

---

## 5. 구현 노트

- 구현 파일: `backend/app/api/v1/analytics/sentiment.py`
- 서비스: `backend/services/sentiment_service.py`
- Celery 태스크: `backend/workers/tasks/sentiment_task.py`
- 비동기 작업은 Celery + Redis 기반, 동기 조회는 DB/Redis 직접 조회
