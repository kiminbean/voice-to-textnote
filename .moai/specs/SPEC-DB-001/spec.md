---
id: SPEC-DB-001
version: "1.0.0"
status: completed
created: 2026-03-21
updated: 2026-03-21
author: kisoo
priority: P0
issue_number: 0
---

# SPEC-DB-001: PostgreSQL 데이터베이스 연동 - 결과 영속 저장 기반

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-03-21 | 초안 작성 | kisoo |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 런타임 | Python >= 3.11, FastAPI >= 0.135.1 |
| ORM | SQLAlchemy >= 2.0 (async), asyncpg |
| 마이그레이션 | Alembic >= 1.13 |
| 데이터베이스 | PostgreSQL 16 (docker-compose.prod.yml에 이미 정의) |
| 테스트 DB | SQLite in-memory (aiosqlite) |

---

## 2. 가정 (Assumptions)

- 기존 Redis 캐시 계층은 유지한다 (빠른 조회용). DB는 영속 저장소로 병행 사용.
- PostgreSQL URL은 환경 변수(DATABASE_URL)로 설정하며, 미설정 시 SQLite 폴백 (개발).
- 테스트는 aiosqlite in-memory DB를 사용하여 PostgreSQL 미설치 환경에서도 실행 가능.
- 이 SPEC에서는 DB 기반만 구축하고, 기존 엔드포인트 마이그레이션은 최소한으로 한다.
- 작업 결과 저장은 Celery task 완료 콜백에서 비동기적으로 수행한다.

---

## 3. 요구사항 (Requirements)

### 모듈 1: 데이터베이스 연결 관리

**[REQ-DB-001] [유비쿼터스]** 시스템은 async SQLAlchemy 세션 팩토리를 통해 PostgreSQL 연결을 관리해야 한다.

**[REQ-DB-002] [상태 기반]** IF DATABASE_URL이 미설정 THEN SQLite 파일 기반 폴백으로 동작해야 한다 (개발/테스트 환경).

**[REQ-DB-003] [유비쿼터스]** 커넥션 풀은 최소 5개, 최대 20개 커넥션을 유지해야 한다.

### 모듈 2: 데이터베이스 모델

**[REQ-DB-004] [유비쿼터스]** TaskResult 모델은 task_id, task_type(stt/diarization/minutes/summary), status, input_metadata, result_data(JSON), error_message, created_at, updated_at, completed_at 필드를 포함해야 한다.

**[REQ-DB-005] [유비쿼터스]** AuditLog 모델은 request_id, method, path, status_code, client_ip, duration_ms, timestamp 필드를 포함해야 한다.

**[REQ-DB-006] [유비쿼터스]** 모든 모델은 UUID 기반 primary key와 생성/수정 시각 필드를 포함해야 한다.

### 모듈 3: 마이그레이션

**[REQ-DB-007] [유비쿼터스]** Alembic으로 데이터베이스 스키마 버전을 관리해야 한다.

**[REQ-DB-008] [이벤트 기반]** WHEN alembic upgrade head 실행 THEN 모든 테이블이 올바르게 생성되어야 한다.

### 모듈 4: 결과 영속 저장 서비스

**[REQ-DB-009] [이벤트 기반]** WHEN Celery 작업이 완료 THEN 결과를 DB에 비동기적으로 저장해야 한다 (Redis 캐시와 병행).

**[REQ-DB-010] [이벤트 기반]** WHEN API가 결과 조회 요청을 받고 Redis에 캐시가 없을 때 THEN DB에서 결과를 조회하여 반환해야 한다.

**[REQ-DB-011] [유비쿼터스]** 결과 영속 서비스는 save_result(), get_result(), list_results() 메서드를 제공해야 한다.

### 모듈 5: FastAPI 의존성

**[REQ-DB-012] [유비쿼터스]** FastAPI 의존성 주입을 통해 DB 세션을 엔드포인트에 제공해야 한다.

---

## 4. 인수 조건 (Acceptance Criteria)

### AC-1: DB 연결
- **Given** DATABASE_URL 설정
- **When** get_db_session() 호출
- **Then** async SQLAlchemy 세션 반환

### AC-2: SQLite 폴백
- **Given** DATABASE_URL 미설정
- **When** DB 세션 요청
- **Then** SQLite 폴백 동작

### AC-3: 모델 생성
- **Given** 마이그레이션 실행
- **When** alembic upgrade head
- **Then** task_results, audit_logs 테이블 생성

### AC-4: 결과 저장
- **Given** TaskResult 데이터
- **When** save_result() 호출
- **Then** DB에 저장 + 조회 가능

### AC-5: 결과 조회
- **Given** DB에 결과 존재
- **When** get_result(task_id) 호출
- **Then** 저장된 결과 반환

### AC-6: 결과 목록
- **Given** 여러 결과 저장
- **When** list_results(task_type="stt") 호출
- **Then** 해당 타입 결과 목록 반환

---

## 5. 기술 접근 방식

### 파일 구조

```
backend/
├── db/
│   ├── __init__.py
│   ├── engine.py              # async SQLAlchemy 엔진/세션 관리
│   ├── models.py              # TaskResult, AuditLog 모델
│   └── service.py             # 결과 영속 저장 서비스
├── app/
│   ├── dependencies.py        # get_db_session 의존성 추가
│   └── main.py                # lifespan에 DB 초기화 추가
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial.py
├── alembic.ini
```
