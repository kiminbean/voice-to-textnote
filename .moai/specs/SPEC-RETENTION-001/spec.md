---
id: SPEC-RETENTION-001
version: "1.0.0"
status: completed
created: 2026-03-21
updated: 2026-03-21
author: kisoo
priority: P2
issue_number: 0
---

# SPEC-RETENTION-001: 데이터 보존 정책 - 자동 정리 및 저장소 관리

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-03-21 | 초안 작성 | kisoo |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 런타임 | Python >= 3.11, Celery >= 5.6.2 |
| DB | SQLAlchemy 2.0 (SPEC-DB-001 기반) |
| 스케줄러 | Celery Beat |

---

## 2. 가정 (Assumptions)

- 기본 데이터 보존 기간은 30일이며 환경 변수로 설정 가능하다.
- 임시 오디오 파일은 처리 완료 후 24시간 뒤 자동 삭제한다.
- Celery Beat으로 일일 정리 작업을 스케줄링한다.
- DB 결과와 임시 파일을 함께 정리한다.

---

## 3. 요구사항 (Requirements)

### 모듈 1: 보존 정책 설정

**[REQ-RET-001] [유비쿼터스]** 데이터 보존 기간은 환경 변수(DATA_RETENTION_DAYS, 기본 30일)로 설정 가능해야 한다.

**[REQ-RET-002] [유비쿼터스]** 임시 파일 보존 기간은 환경 변수(TEMP_FILE_RETENTION_HOURS, 기본 24시간)로 설정 가능해야 한다.

### 모듈 2: 자동 정리 서비스

**[REQ-RET-003] [이벤트 기반]** WHEN 정리 작업 실행 THEN 보존 기간 초과한 DB 결과를 삭제해야 한다.

**[REQ-RET-004] [이벤트 기반]** WHEN 정리 작업 실행 THEN 보존 기간 초과한 임시 오디오 파일을 삭제해야 한다.

**[REQ-RET-005] [유비쿼터스]** 정리 작업은 삭제된 항목 수와 해제된 공간을 로그에 기록해야 한다.

### 모듈 3: 스케줄링

**[REQ-RET-006] [유비쿼터스]** Celery Beat으로 매일 03:00에 정리 작업을 자동 실행해야 한다.

### 모듈 4: 수동 정리 API

**[REQ-RET-007] [이벤트 기반]** WHEN POST /api/v1/admin/cleanup 요청 THEN 즉시 정리 작업을 실행하고 결과를 반환해야 한다.

---

## 4. 인수 조건 (Acceptance Criteria)

### AC-1: 만료 결과 삭제
- 30일 이상 된 TaskResult → 삭제

### AC-2: 임시 파일 정리
- 24시간 초과 임시 파일 → 삭제

### AC-3: 정리 결과 로그
- 정리 후 삭제 수 + 해제 공간 로그

### AC-4: 수동 정리
- POST /api/v1/admin/cleanup → 즉시 실행 + 결과 반환

---

## 5. 기술 접근 방식

```
backend/
├── services/
│   ├── __init__.py
│   └── retention.py              # 데이터 보존 정리 서비스
├── workers/tasks/
│   └── cleanup_task.py           # Celery 정리 태스크
├── app/api/v1/admin.py           # 관리자 API
├── app/config.py                 # 보존 설정 추가
├── tests/unit/
│   ├── test_retention.py
│   └── test_cleanup_task.py
```
