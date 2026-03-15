---
id: SPEC-SUM-001
version: "1.0.0"
status: draft
created: 2026-03-15
updated: 2026-03-15
author: kisoo
priority: P1
issue_number: 0
---

# SPEC-SUM-001: AI Meeting Summary - Claude API 기반 회의 요약 및 액션 아이템 추출

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
| AI API | Anthropic Claude API (anthropic >= 0.28.0) |
| 모델 | claude-sonnet-4-20250514 (기본값, 설정 변경 가능) |
| 비동기 처리 | Celery >= 5.6.2, Redis >= 7.0 |
| 입력 데이터 | SPEC-MIN-001의 MinutesResponse (MinutesSegment[], SpeakerStats[]) |

---

## 2. 가정 (Assumptions)

- SPEC-MIN-001의 회의록 생성이 완료된 상태에서만 요약을 생성한다. minutes_task_id로 Redis에서 결과를 조회한다.
- ANTHROPIC_API_KEY 환경 변수가 설정되어 있다. 미설정 시 요약 기능을 비활성화하되 서버는 정상 시작한다.
- Claude API 호출은 Celery 워커에서 동기적으로 실행한다 (sync Anthropic client).
- 동시 요약 작업 수를 2개로 제한한다 (API 비용 및 rate limit 관리).
- 요약 결과는 구조화된 JSON으로 반환한다: summary_text, action_items[], key_decisions[], next_steps[].
- 한 번의 API 호출로 요약 + 액션 아이템 + 결정사항을 모두 추출한다.

---

## 3. 요구사항 (Requirements)

### 모듈 1: SummaryGenerator (요약 생성기)

**[REQ-SUM-001] [유비쿼터스]** SummaryGenerator는 항상 MinutesResponse의 segments와 speakers를 입력으로 받아 Claude API에 전송할 프롬프트를 구성해야 한다. 프롬프트에는 화자별 발화 내용과 화자 통계가 포함된다.

**[REQ-SUM-002] [유비쿼터스]** SummaryGenerator는 항상 Claude API 응답을 파싱하여 구조화된 결과를 반환해야 한다: summary_text(요약문), action_items(list[ActionItem]), key_decisions(list[str]), next_steps(list[str]).

**[REQ-SUM-003] [이벤트 기반]** WHEN Claude API 호출이 실패할 때(네트워크 오류, 타임아웃) THEN SummaryGenerator는 예외를 발생시키고 Celery 재시도 메커니즘에 위임해야 한다.

**[REQ-SUM-004] [원치 않는 행동]** SummaryGenerator는 Claude API 응답이 예상 JSON 형식이 아닐 때 원본 텍스트를 summary_text로 저장하고 action_items/key_decisions/next_steps를 빈 리스트로 반환해야 한다. 오류를 발생시키지 않아야 한다.

### 모듈 2: Summary Schema

**[REQ-SUM-005] [유비쿼터스]** ActionItem 스키마는 항상 다음 필드를 포함해야 한다: assignee(str|None), task(str), deadline(str|None), priority(str="medium").

### 모듈 3: Summary Celery Task

**[REQ-SUM-006] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/summaries 요청을 보낼 때 THEN 시스템은 Celery 태스크를 생성하고 task_id를 202 Accepted 응답으로 반환해야 한다.

**[REQ-SUM-007] [유비쿼터스]** summary_task는 항상 Redis에서 minutes 결과(task:min:result:{minutes_task_id})를 조회하여 요약을 생성해야 한다.

**[REQ-SUM-008] [유비쿼터스]** summary_task는 항상 최대 2개 동시 작업 제한을 유지해야 한다. 제한 초과 시 HTTP 429 Too Many Requests를 반환해야 한다.

**[REQ-SUM-009] [이벤트 기반]** WHEN 요약 생성 중 오류가 발생 THEN 시스템은 최대 2회 재시도(default_retry_delay=30초) 후 상태를 "failed"로 마킹해야 한다.

**[REQ-SUM-010] [원치 않는 행동]** 시스템은 minutes 결과가 존재하지 않는 minutes_task_id에 대해 404 Not Found를 반환해야 한다.

**[REQ-SUM-011] [이벤트 기반]** WHEN ANTHROPIC_API_KEY가 설정되지 않았을 때 THEN summary_task는 즉시 실패하고 "ANTHROPIC_API_KEY is not configured" 에러 메시지를 반환해야 한다. 재시도하지 않아야 한다.

### 모듈 4: Summary Status & Result API

**[REQ-SUM-012] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/summaries/{task_id}/status를 요청 THEN 시스템은 처리 상태와 진행률을 반환해야 한다.

**[REQ-SUM-013] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/summaries/{task_id}를 요청하고 작업이 completed 상태 THEN 시스템은 요약문, 액션 아이템, 결정사항, 다음 단계를 반환해야 한다.

**[REQ-SUM-014] [유비쿼터스]** 요약 결과는 항상 Redis에 24시간 TTL로 캐시되어야 한다. 키 패턴: `task:sum:result:{task_id}`.

**[REQ-SUM-015] [이벤트 기반]** WHEN 클라이언트가 DELETE /api/v1/summaries/{task_id}를 요청 THEN 시스템은 Redis 캐시를 삭제하고 204 No Content를 반환해야 한다.

**[REQ-SUM-016] [원치 않는 행동]** 시스템은 존재하지 않는 task_id로 조회 시 404 Not Found를 반환해야 한다.

---

## 4. 비기능 요구사항 (Non-Functional Requirements)

| 항목 | 목표값 | 비고 |
|------|--------|------|
| 요약 생성 처리 시간 | < 15초 | Claude API 응답 시간 포함 |
| 상태 조회 응답 시간 | < 100ms | Redis 캐시 활용 |
| 동시 처리 작업 수 | 최대 2개 | API 비용/rate limit 관리 |
| API 응답 시간 (작업 제출) | < 300ms | task_id 발급 |

---

## 5. 기술 제약 조건 (Technical Constraints)

- **MIN 결과 의존**: summary_task는 minutes_task가 completed 상태인 경우에만 실행 가능.
- **API 키 필수**: ANTHROPIC_API_KEY 환경 변수 미설정 시 요약 기능 비활성화.
- **Sync API 호출**: Celery 워커에서 동기 Anthropic client 사용 (비동기 Celery 미지원).

---

## 6. 의존성 (Dependencies)

| 라이브러리 | 버전 | 용도 |
|-----------|------|------|
| anthropic | >= 0.28.0 | Claude API SDK |
| FastAPI | >= 0.135.1 | 웹 프레임워크 |
| Celery | >= 5.6.2 | 비동기 작업 큐 |
| Redis | >= 7.0 | 캐시 + 메시지 브로커 |
| Pydantic | >= 2.9 | 데이터 검증 |

**신규 의존성**: anthropic >= 0.28.0

---

## 7. 연결된 SPEC (Related SPECs)

| SPEC ID | 관계 | 설명 |
|---------|------|------|
| SPEC-MIN-001 | 직접 의존 (Upstream) | MinutesResponse를 입력으로 사용 |
| SPEC-DIA-001 | 간접 의존 | DIA → MIN → SUM 파이프라인 |
| SPEC-STT-001 | 간접 의존 | STT → DIA → MIN → SUM 파이프라인 |

---

## 8. 추적성 (Traceability)

| 요구사항 ID | 모듈 | EARS 패턴 | 관련 컴포넌트 |
|-------------|------|-----------|--------------|
| REQ-SUM-001 | SummaryGenerator | 유비쿼터스 | build_prompt() |
| REQ-SUM-002 | SummaryGenerator | 유비쿼터스 | parse_response() |
| REQ-SUM-003 | SummaryGenerator | 이벤트 기반 | generate_summary() |
| REQ-SUM-004 | SummaryGenerator | 원치 않는 행동 | parse_response() |
| REQ-SUM-005 | Schema | 유비쿼터스 | ActionItem |
| REQ-SUM-006 | Celery Task | 이벤트 기반 | POST /api/v1/summaries |
| REQ-SUM-007 | Celery Task | 유비쿼터스 | summary_task |
| REQ-SUM-008 | Celery Task | 유비쿼터스 | summary_task |
| REQ-SUM-009 | Celery Task | 이벤트 기반 | summary_task |
| REQ-SUM-010 | Celery Task | 원치 않는 행동 | summary_task |
| REQ-SUM-011 | Celery Task | 이벤트 기반 | summary_task |
| REQ-SUM-012 | Status API | 이벤트 기반 | GET .../status |
| REQ-SUM-013 | Result API | 이벤트 기반 | GET .../{task_id} |
| REQ-SUM-014 | Result API | 유비쿼터스 | Redis 캐시 |
| REQ-SUM-015 | Result API | 이벤트 기반 | DELETE .../{task_id} |
| REQ-SUM-016 | Result API | 원치 않는 행동 | GET .../{task_id} |

---

*SPEC ID: SPEC-SUM-001*
*생성일: 2026-03-15*
*상태: draft*
