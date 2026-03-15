---
id: SPEC-MIN-001
version: "1.0.0"
status: draft
created: 2026-03-15
updated: 2026-03-15
author: kisoo
priority: P1
issue_number: 0
---

# SPEC-MIN-001: Meeting Minutes Generator - 화자별 회의록 자동 생성

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-03-15 | 초안 작성 | kisoo |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 플랫폼 | M4 Mac Mini 24GB (Apple Silicon) |
| 런타임 | Python >= 3.11, FastAPI >= 0.135.1, uvicorn >= 0.34.0 |
| 비동기 처리 | Celery >= 5.6.2, Redis >= 7.0 |
| 데이터 검증 | Pydantic >= 2.9 |
| 입력 데이터 | SPEC-DIA-001의 DiarizationResponse (DiarizedSegmentResult[], SpeakerInfo[]) |

---

## 2. 가정 (Assumptions)

- SPEC-DIA-001의 화자 분리가 완료된 상태에서만 회의록을 생성한다. diarization_task_id로 Redis에서 결과를 조회한다.
- 회의록 생성은 순수 텍스트 후처리이므로 ML 모델이 필요 없다. CPU/메모리 부담이 거의 없다.
- 동시 처리 작업 수를 3개로 설정한다 (STT/DIA보다 가벼운 작업).
- 출력 형식은 JSON(기본)과 Markdown을 지원한다. HTML은 향후 확장.
- Redis 서버와 Celery 워커는 이미 실행 중이다.
- 화자 이름은 기본적으로 "Speaker 1", "Speaker 2" 등으로 자동 부여한다. 사용자가 커스텀 이름을 제공할 수 있다.

---

## 3. 요구사항 (Requirements)

### 모듈 1: MinutesFormatter (회의록 포맷터)

**[REQ-MIN-001] [유비쿼터스]** MinutesFormatter는 항상 DiarizedSegmentResult 목록을 입력으로 받아 화자별로 그룹화된 회의록 세그먼트 목록을 반환해야 한다. 연속된 동일 화자 세그먼트는 하나의 발화 블록으로 병합한다.

**[REQ-MIN-002] [유비쿼터스]** MinutesFormatter는 항상 각 화자의 통계를 계산해야 한다: 총 발화 시간(초), 발화 횟수, 발화 비율(%).

**[REQ-MIN-003] [이벤트 기반]** WHEN 출력 형식이 "markdown"일 때 THEN MinutesFormatter는 화자별 타임스탬프와 텍스트를 Markdown 형식으로 변환해야 한다. 형식: `**[HH:MM:SS] Speaker N**: 발화 내용`.

**[REQ-MIN-004] [이벤트 기반]** WHEN 출력 형식이 "json"일 때 THEN MinutesFormatter는 구조화된 JSON 객체를 반환해야 한다.

**[REQ-MIN-005] [원치 않는 행동]** MinutesFormatter는 speaker_id가 null인 세그먼트를 "Unknown Speaker"로 표시해야 한다. 해당 세그먼트를 무시하거나 삭제하지 않아야 한다.

### 모듈 2: Minutes Celery Task

**[REQ-MIN-006] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/minutes 요청을 보낼 때 THEN 시스템은 Celery 태스크를 생성하고 task_id를 202 Accepted 응답으로 반환해야 한다.

**[REQ-MIN-007] [유비쿼터스]** minutes_task는 항상 Redis에서 diarization 결과(task:dia:result:{diarization_task_id})를 조회하여 회의록을 생성해야 한다.

**[REQ-MIN-008] [유비쿼터스]** minutes_task는 항상 최대 3개 동시 작업 제한을 유지해야 한다. 제한 초과 시 HTTP 429 Too Many Requests를 반환해야 한다.

**[REQ-MIN-009] [이벤트 기반]** WHEN 회의록 생성 중 오류가 발생 THEN 시스템은 최대 2회 재시도(default_retry_delay=30초) 후 상태를 "failed"로 마킹해야 한다.

**[REQ-MIN-010] [원치 않는 행동]** 시스템은 diarization 결과가 존재하지 않는 diarization_task_id에 대해 404 Not Found를 반환해야 한다. 빈 회의록을 생성하지 않아야 한다.

### 모듈 3: Minutes Status & Result API

**[REQ-MIN-011] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/minutes/{task_id}/status를 요청 THEN 시스템은 처리 상태(pending/processing/completed/failed)와 진행률(0.0-1.0)을 반환해야 한다.

**[REQ-MIN-012] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/minutes/{task_id}를 요청하고 작업이 completed 상태 THEN 시스템은 화자별 회의록, 화자 통계, 메타데이터를 반환해야 한다.

**[REQ-MIN-013] [유비쿼터스]** 회의록 결과는 항상 Redis에 24시간 TTL로 캐시되어야 한다. 키 패턴: `task:min:result:{task_id}`.

**[REQ-MIN-014] [이벤트 기반]** WHEN 클라이언트가 DELETE /api/v1/minutes/{task_id}를 요청 THEN 시스템은 Redis 캐시를 삭제하고 204 No Content를 반환해야 한다.

**[REQ-MIN-015] [원치 않는 행동]** 시스템은 존재하지 않는 task_id로 조회 시 404 Not Found를 반환해야 한다.

### 모듈 4: Speaker Name Mapping

**[REQ-MIN-016] [유비쿼터스]** 시스템은 항상 기본 화자 이름을 자동 생성해야 한다. 형식: "Speaker 1", "Speaker 2" (SPEAKER_00 → Speaker 1).

**[REQ-MIN-017] [이벤트 기반]** WHEN 클라이언트가 speaker_names 매핑을 요청에 포함할 때 THEN 시스템은 해당 매핑을 사용하여 화자 이름을 대체해야 한다. 형식: {"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"}.

---

## 4. 비기능 요구사항 (Non-Functional Requirements)

### 성능 (Performance)

| 항목 | 목표값 | 비고 |
|------|--------|------|
| 회의록 생성 처리 시간 | < 3초 | 1000개 세그먼트 기준 |
| 상태 조회 응답 시간 | < 100ms | Redis 캐시 활용 |
| 동시 처리 작업 수 | 최대 3개 | 가벼운 후처리 작업 |
| API 응답 시간 (작업 제출) | < 300ms | task_id 발급 |

---

## 5. 기술 제약 조건 (Technical Constraints)

- **DIA 결과 의존**: minutes_task는 diarization_task가 completed 상태인 경우에만 실행 가능.
- **Redis 필수**: 결과 캐시 및 상태 관리에 Redis 필수.
- **ML 모델 불필요**: 순수 텍스트 후처리로 ML 엔진 없이 동작.

---

## 6. 의존성 (Dependencies)

| 라이브러리 | 버전 | 용도 |
|-----------|------|------|
| FastAPI | >= 0.135.1 | 웹 프레임워크 |
| Celery | >= 5.6.2 | 비동기 작업 큐 |
| Redis | >= 7.0 | 캐시 + 메시지 브로커 |
| Pydantic | >= 2.9 | 데이터 검증 |

추가 의존성 없음 (기존 스택으로 충분).

---

## 7. 연결된 SPEC (Related SPECs)

| SPEC ID | 관계 | 설명 |
|---------|------|------|
| SPEC-STT-001 | 간접 의존 (Upstream) | STT 결과가 DIA를 통해 Minutes에 전달 |
| SPEC-DIA-001 | 직접 의존 (Upstream) | DiarizedSegmentResult + SpeakerInfo 활용 |
| SPEC-API-001 | 소비 (Downstream, 예정) | 회의록 + AI 요약 통합 |

---

## 8. 추적성 (Traceability)

| 요구사항 ID | 모듈 | EARS 패턴 | 관련 컴포넌트 |
|-------------|------|-----------|--------------|
| REQ-MIN-001 | MinutesFormatter | 유비쿼터스 | MinutesFormatter.format() |
| REQ-MIN-002 | MinutesFormatter | 유비쿼터스 | MinutesFormatter.calculate_stats() |
| REQ-MIN-003 | MinutesFormatter | 이벤트 기반 | MinutesFormatter.to_markdown() |
| REQ-MIN-004 | MinutesFormatter | 이벤트 기반 | MinutesFormatter.to_json() |
| REQ-MIN-005 | MinutesFormatter | 원치 않는 행동 | MinutesFormatter.format() |
| REQ-MIN-006 | Celery Task | 이벤트 기반 | POST /api/v1/minutes |
| REQ-MIN-007 | Celery Task | 유비쿼터스 | minutes_task |
| REQ-MIN-008 | Celery Task | 유비쿼터스 | minutes_task |
| REQ-MIN-009 | Celery Task | 이벤트 기반 | minutes_task |
| REQ-MIN-010 | Celery Task | 원치 않는 행동 | minutes_task |
| REQ-MIN-011 | Status API | 이벤트 기반 | GET .../status |
| REQ-MIN-012 | Result API | 이벤트 기반 | GET .../{task_id} |
| REQ-MIN-013 | Result API | 유비쿼터스 | Redis 캐시 |
| REQ-MIN-014 | Result API | 이벤트 기반 | DELETE .../{task_id} |
| REQ-MIN-015 | Result API | 원치 않는 행동 | GET .../{task_id} |
| REQ-MIN-016 | Speaker Names | 유비쿼터스 | SpeakerNameMapper |
| REQ-MIN-017 | Speaker Names | 이벤트 기반 | SpeakerNameMapper |

---

*SPEC ID: SPEC-MIN-001*
*생성일: 2026-03-15*
*상태: draft*
