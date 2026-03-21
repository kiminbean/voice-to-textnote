---
id: SPEC-PERSIST-001
version: "1.0.0"
status: completed
created: 2026-03-21
updated: 2026-03-21
author: kisoo
priority: P0
issue_number: 0
---

# SPEC-PERSIST-001: DB 영속 저장 연동 - Celery 태스크 결과 자동 저장 및 API 폴백

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-03-21 | 초안 작성 | kisoo |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 런타임 | Python >= 3.11, Celery >= 5.6.2 |
| DB | SQLAlchemy 2.0 (async + sync), SPEC-DB-001 기반 |
| 캐시 | Redis (기존 유지) |

---

## 2. 가정 (Assumptions)

- Celery 워커는 동기 환경이므로 DB 접근은 동기 SQLAlchemy를 사용한다.
- Redis 캐시는 기존대로 유지하며, DB는 영속 백업 저장소로 병행 동작한다.
- API 엔드포인트의 결과 조회는 기존 Redis 우선, Redis miss 시 DB 폴백 패턴을 사용한다.
- DB 저장 실패는 작업 자체의 실패로 이어지지 않는다 (best-effort 저장).

---

## 3. 요구사항 (Requirements)

### 모듈 1: 동기 DB 서비스 (Celery 워커용)

**[REQ-PERSIST-001] [유비쿼터스]** 시스템은 Celery 동기 환경에서 사용 가능한 동기 DB 세션 팩토리를 제공해야 한다.

**[REQ-PERSIST-002] [유비쿼터스]** 동기 ResultService는 save_result_sync(task_id, task_type, status, result_data, error_message) 메서드를 제공해야 한다.

**[REQ-PERSIST-003] [원치 않는 행동]** DB 저장 실패가 Celery 작업 자체를 실패시키지 않아야 한다 (try-except + 로깅).

### 모듈 2: 태스크 결과 자동 저장

**[REQ-PERSIST-004] [이벤트 기반]** WHEN Celery 전사 작업(transcription_task)이 완료 THEN 결과를 DB에 자동 저장해야 한다.

**[REQ-PERSIST-005] [이벤트 기반]** WHEN Celery 화자분리 작업(diarization_task)이 완료 THEN 결과를 DB에 자동 저장해야 한다.

**[REQ-PERSIST-006] [이벤트 기반]** WHEN Celery 회의록 작업(minutes_task)이 완료 THEN 결과를 DB에 자동 저장해야 한다.

**[REQ-PERSIST-007] [이벤트 기반]** WHEN Celery 요약 작업(summary_task)이 완료 THEN 결과를 DB에 자동 저장해야 한다.

**[REQ-PERSIST-008] [이벤트 기반]** WHEN Celery 작업이 실패 THEN 실패 상태와 에러 메시지를 DB에 저장해야 한다.

### 모듈 3: API 결과 조회 DB 폴백

**[REQ-PERSIST-009] [이벤트 기반]** WHEN API가 결과 조회 요청을 받고 Redis에 캐시가 없을 때 THEN DB에서 결과를 조회하여 반환해야 한다.

**[REQ-PERSIST-010] [이벤트 기반]** WHEN DB에서 결과를 찾았을 때 THEN Redis 캐시에 복원하여 후속 조회를 가속해야 한다.

---

## 4. 인수 조건 (Acceptance Criteria)

### AC-1: 동기 세션 생성
- **Given** DATABASE_URL 설정
- **When** get_sync_session() 호출
- **Then** 동기 SQLAlchemy 세션 반환

### AC-2: 결과 자동 저장
- **Given** 전사 작업 완료
- **When** persist_task_result 호출
- **Then** DB에 결과 저장

### AC-3: 저장 실패 안전 처리
- **Given** DB 연결 실패
- **When** persist_task_result 호출
- **Then** 예외 로깅 후 정상 반환 (작업 미실패)

### AC-4: DB 폴백 조회
- **Given** Redis에 캐시 없음 + DB에 결과 존재
- **When** get_result_with_fallback 호출
- **Then** DB에서 결과 반환 + Redis 캐시 복원

---

## 5. 기술 접근 방식

### 파일 구조

```
backend/
├── db/
│   ├── sync_engine.py           # 동기 SQLAlchemy 엔진/세션
│   └── sync_service.py          # 동기 ResultService (Celery용)
├── app/
│   └── result_fallback.py       # Redis→DB 폴백 조회 유틸리티
├── tests/unit/
│   ├── test_sync_service.py
│   └── test_result_fallback.py
```
