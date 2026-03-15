---
id: SPEC-E2E-001
version: "1.0.0"
status: draft
created: 2026-03-15
updated: 2026-03-15
author: kisoo
priority: P1
issue_number: 0
---

# SPEC-E2E-001: E2E 통합 테스트 - 전체 파이프라인 검증 (STT → DIA → MIN → SUM)

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-03-15 | 초안 작성 | kisoo |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 테스트 프레임워크 | pytest 8.0+ / pytest-asyncio |
| HTTP 테스트 | FastAPI TestClient |
| Mock | unittest.mock (AsyncMock) |
| 대상 | 백엔드 전체 파이프라인: STT → DIA → MIN → SUM |

---

## 2. 가정 (Assumptions)

- 모든 E2E 테스트는 mock 기반으로 실행된다. 실제 ML 모델, Redis 서버, Celery 워커를 사용하지 않는다.
- 각 파이프라인 단계의 Celery 태스크는 즉시 완료로 mock 처리한다.
- Redis는 AsyncMock으로 대체하되, 키-값 저장/조회 동작을 시뮬레이션한다.
- 기존 conftest.py의 픽스처를 최대한 재사용한다.

---

## 3. 요구사항 (Requirements)

### 모듈 1: E2E 테스트 픽스처

**[REQ-E2E-001] [유비쿼터스]** E2E 테스트용 포괄적 Redis mock 픽스처를 제공해야 한다. 키-값 저장/조회/삭제, Set 연산(scard/sadd/srem)을 시뮬레이션한다.

**[REQ-E2E-002] [유비쿼터스]** 각 파이프라인 단계의 완료 결과 mock 데이터를 제공해야 한다: STT 결과(segments, metadata), DIA 결과(speaker_id 포함 segments, speakers), MIN 결과(병합 segments, stats), SUM 결과(summary_text, action_items).

**[REQ-E2E-003] [유비쿼터스]** 모든 Celery 태스크(transcription_task, diarization_celery_task, minutes_celery_task, summary_celery_task)를 delay() mock으로 대체해야 한다.

### 모듈 2: 단계별 파이프라인 E2E 테스트

**[REQ-E2E-004] [유비쿼터스]** STT → DIA 연결 테스트: STT task_id를 사용하여 DIA 요청이 성공하고, DIA 결과에 speaker_id가 포함되는지 검증해야 한다.

**[REQ-E2E-005] [유비쿼터스]** DIA → MIN 연결 테스트: DIA task_id를 사용하여 MIN 요청이 성공하고, MIN 결과에 speaker_name과 통계가 포함되는지 검증해야 한다.

**[REQ-E2E-006] [유비쿼터스]** MIN → SUM 연결 테스트: MIN task_id를 사용하여 SUM 요청이 성공하고, SUM 결과에 summary_text와 action_items가 포함되는지 검증해야 한다.

### 모듈 3: 전체 파이프라인 E2E 테스트

**[REQ-E2E-007] [유비쿼터스]** 전체 파이프라인 테스트: STT 업로드 → DIA 요청 → MIN 요청 → SUM 요청을 순차 실행하고, 각 단계의 task_id가 다음 단계 입력으로 올바르게 전달되는지 검증해야 한다.

**[REQ-E2E-008] [이벤트 기반]** WHEN 이전 단계 결과가 Redis에 존재하지 않을 때 THEN 다음 단계 API는 404를 반환해야 한다 (DIA: stt 미존재, MIN: dia 미존재, SUM: min 미존재).

**[REQ-E2E-009] [유비쿼터스]** 각 단계의 상태 조회(GET /status) 엔드포인트가 올바른 상태(pending/processing/completed)를 반환하는지 검증해야 한다.

**[REQ-E2E-010] [유비쿼터스]** 각 단계의 삭제(DELETE) 엔드포인트가 204를 반환하고 Redis에서 해당 키를 제거하는지 검증해야 한다.

### 모듈 4: 에러 전파 테스트

**[REQ-E2E-011] [이벤트 기반]** WHEN 파이프라인 중간 단계가 실패(failed) THEN 후속 단계에서 해당 task_id로 조회 시 결과가 없거나 실패 상태를 반환해야 한다.

**[REQ-E2E-012] [유비쿼터스]** 각 단계의 동시 작업 제한(STT:3, DIA:2, MIN:3, SUM:2) 초과 시 429를 반환하는지 검증해야 한다.

---

## 4. 비기능 요구사항

| 항목 | 목표값 |
|------|--------|
| E2E 테스트 실행 시간 | < 5초 (mock 기반) |
| 기존 테스트 회귀 | 0건 |

---

## 5. 의존성

기존 의존성만 사용. 추가 패키지 없음.

---

## 6. 연결된 SPEC

| SPEC ID | 관계 | 설명 |
|---------|------|------|
| SPEC-STT-001 | 검증 대상 | POST /transcriptions API |
| SPEC-DIA-001 | 검증 대상 | POST /diarizations API |
| SPEC-MIN-001 | 검증 대상 | POST /minutes API |
| SPEC-SUM-001 | 검증 대상 | POST /summaries API |

---

*SPEC ID: SPEC-E2E-001*
*생성일: 2026-03-15*
*상태: draft*
