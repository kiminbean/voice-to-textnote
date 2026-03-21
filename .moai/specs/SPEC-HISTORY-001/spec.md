---
id: SPEC-HISTORY-001
version: "1.0.0"
status: completed
created: 2026-03-21
updated: 2026-03-21
author: kisoo
priority: P2
issue_number: 0
---

# SPEC-HISTORY-001: 작업 이력 조회 API

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-03-21 | 초안 작성 | kisoo |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 런타임 | Python >= 3.11, FastAPI >= 0.135.1 |
| DB | SQLAlchemy 2.0 async (SPEC-DB-001 기반) |

---

## 2. 가정 (Assumptions)

- SPEC-PERSIST-001에서 Celery 작업 결과가 자동으로 DB에 저장된다.
- 이력 API는 DB에서 직접 조회하며, Redis 캐시를 사용하지 않는다.
- 페이지네이션, 필터링, 정렬 기능을 제공한다.

---

## 3. 요구사항 (Requirements)

### 모듈 1: 이력 목록 API

**[REQ-HIST-001] [이벤트 기반]** WHEN GET /api/v1/history 요청 THEN DB에서 전체 작업 이력을 페이지네이션하여 반환해야 한다.

**[REQ-HIST-002] [이벤트 기반]** WHEN task_type 쿼리 파라미터 제공 THEN 해당 유형(stt, diarization, minutes, summary)만 필터링해야 한다.

**[REQ-HIST-003] [이벤트 기반]** WHEN status 쿼리 파라미터 제공 THEN 해당 상태(completed, failed, processing)만 필터링해야 한다.

**[REQ-HIST-004] [유비쿼터스]** 응답은 items(결과 목록), total(전체 수), page, page_size를 포함해야 한다.

### 모듈 2: 이력 상세 API

**[REQ-HIST-005] [이벤트 기반]** WHEN GET /api/v1/history/{task_id} 요청 THEN DB에서 해당 작업의 상세 결과를 반환해야 한다.

**[REQ-HIST-006] [이벤트 기반]** WHEN 존재하지 않는 task_id 요청 THEN 404 응답을 반환해야 한다.

### 모듈 3: 이력 삭제 API

**[REQ-HIST-007] [이벤트 기반]** WHEN DELETE /api/v1/history/{task_id} 요청 THEN DB에서 해당 결과를 삭제해야 한다.

---

## 4. 인수 조건 (Acceptance Criteria)

### AC-1: 이력 목록
- GET /api/v1/history → 200 + {items, total, page, page_size}

### AC-2: 필터링
- GET /api/v1/history?task_type=stt → stt만 반환

### AC-3: 상세 조회
- GET /api/v1/history/{task_id} → 200 + 상세 결과

### AC-4: 404 처리
- GET /api/v1/history/nonexistent → 404

### AC-5: 삭제
- DELETE /api/v1/history/{task_id} → 204

---

## 5. 기술 접근 방식

```
backend/
├── app/api/v1/history.py         # 이력 API 엔드포인트
├── schemas/history.py            # 이력 Pydantic 스키마
├── tests/unit/test_history_api.py
```
