# SPEC-SENTIMENT-001 검수 기준

## 1. 개요

본 문서는 텍스트 감정 분석 통합 완료의 수락 기준을 Given/When/Then 형식으로 정의한다. 검수는 기존 구현을 보존하면서 Celery 실행, SSE 진행률, Flutter 전용 UI, 하위 호환성이 충족되는지 확인한다.

---

## 2. 검수 시나리오

### AC-SEN-001: Celery 등록 버그 수정 검증

**관련 요구사항**: REQ-SEN-001, REQ-SEN-002

**Given**
- Redis가 실행 중이다.
- Celery 워커가 `backend.workers.celery_app` 설정으로 시작되어 있다.
- 유효한 `minutes_task_id`에 대한 minutes 결과가 Redis 또는 `TaskResult`에 존재한다.

**When**
- 클라이언트가 `POST /api/v1/sentiment`에 `minutes_task_id`를 포함해 요청한다.

**Then**
- API는 감정 분석 `task_id`를 반환한다.
- Celery 워커는 `sentiment_celery_task`를 실제로 실행한다.
- 해당 작업 상태는 pending에 영구 대기하지 않고 processing 또는 completed/failed 상태로 전이된다.
- 성공 시 `task:sentiment:result:{task_id}` 또는 동등한 결과 저장소에서 감정 분석 결과를 조회할 수 있다.

**통과 조건**
- Celery registered task 목록 또는 worker 로그에서 감정 분석 태스크 실행이 확인된다.
- 이전 결함처럼 큐 메시지만 생성되고 실행되지 않는 상태가 재현되지 않는다.

---

### AC-SEN-002: SSE 진행률 스트리밍

**관련 요구사항**: REQ-SEN-005, REQ-SEN-006

**Given**
- 감정 분석 태스크가 생성되어 `task:sentiment:status:{task_id}` Redis 키가 존재한다.
- 태스크 상태 업데이트가 `publish_task_event_sync`를 통해 발행된다.

**When**
- 클라이언트가 `GET /api/v1/transcription/{task_id}/stream`을 호출한다.

**Then**
- stream 엔드포인트는 감정 분석 task_id를 존재하는 태스크로 인식한다.
- 응답은 `text/event-stream`으로 유지된다.
- 클라이언트는 감정 분석 진행률, 메시지, 완료/실패 이벤트를 수신한다.

**통과 조건**
- `task:sentiment:status:` prefix만 존재하는 task_id에 대해 404가 반환되지 않는다.
- 진행률 이벤트가 최소 1회 이상 수신된다.

---

### AC-SEN-003: Flutter 감정 분석 탭 렌더링

**관련 요구사항**: REQ-SEN-007, REQ-SEN-008, REQ-SEN-009

**Given**
- 회의 결과 화면을 열 수 있는 completed meeting/task가 있다.
- `GET /api/v1/sentiment/meeting/{meeting_id}` 응답에 `segments`, `speakers`, `emotional_timeline`, `overall_sentiment`, `overall_emotion`이 포함되어 있다.

**When**
- 사용자가 회의 결과 화면에서 감정 분석 탭을 클릭한다.

**Then**
- 전용 감정 분석 탭이 표시된다.
- 전체 감정 분포가 positive/neutral/negative 비율로 표시된다.
- `emotional_timeline`이 시간 순서의 시계열 시각화로 표시된다.
- 화자별 감정 분포는 클라이언트 재계산보다 백엔드 `SpeakerSentiment` precomputed 데이터를 우선 사용해 표시된다.

**통과 조건**
- 기존 통계 탭 하단에만 감정 카드가 묻혀 있지 않고 별도 탭에서 접근 가능하다.
- 응답의 `emotional_timeline` 데이터가 UI에서 누락되지 않는다.

---

### AC-SEN-004: 기존 SentimentResponse 하위 호환성

**관련 요구사항**: REQ-SEN-011, REQ-SEN-012, REQ-SEN-013

**Given**
- 기존 클라이언트 또는 테스트가 `GET /api/v1/sentiment/{task_id}`를 호출한다.
- 기존 파서는 `task_id`, `status`, `minutes_task_id`, `overall_sentiment`, `overall_emotion`, `segments`, `speakers`, `emotional_timeline`, `generation_time_seconds`, `error_message` 필드를 기대한다.

**When**
- 감정 분석 결과 응답을 수신한다.

**Then**
- 기존 `SentimentResponse` 필드 의미와 타입이 유지된다.
- 새 필드가 추가된 경우 optional로만 제공된다.
- 기존 segments-only Flutter 메서드인 `getResult()` 및 `getByMeeting()`은 계속 `List<SentimentSegment>`를 반환한다.

**통과 조건**
- 기존 sentiment API 테스트가 수정 없이 통과한다.
- 새 필드가 required로 추가되어 기존 JSON 파서가 실패하는 일이 없다.

---

### AC-SEN-005: 오류 복구 UI

**관련 요구사항**: REQ-SEN-010

**Given**
- 감정 분석 API가 네트워크 오류, 500 응답, 또는 인증 오류를 반환한다.
- Flutter 결과 화면이 감정 분석 탭을 표시한다.

**When**
- 감정 분석 데이터를 로드한다.

**Then**
- UI는 빈 공간으로 실패를 숨기지 않는다.
- 사용자에게 오류 메시지와 재시도 액션을 제공한다.
- 재시도 시 동일 provider/API 호출이 다시 수행된다.

**통과 조건**
- `SizedBox.shrink()` 기반 silent failure가 제거된다.
- 위젯 테스트에서 오류 상태와 retry 콜백이 검증된다.

---

### AC-SEN-006: README 정확성 검증

**관련 요구사항**: REQ-SEN-014, REQ-SEN-015

**Given**
- SPEC-SENTIMENT-001 구현이 완료되었다.
- README에는 주요 기능, 모델 설명, 다음 단계가 문서화되어 있다.

**When**
- README의 AI 분석 관련 섹션을 검토한다.

**Then**
- 텍스트 감정 분석은 완료된 기능으로 설명된다.
- 모델 설명은 ZAI `glm-5.2`와 일치한다.
- 부정확한 Claude 모델 표기가 감정 분석 기능 설명에 남아 있지 않다.

**통과 조건**
- README의 기능 목록과 실제 구현 상태가 충돌하지 않는다.
- 운영자가 잘못된 API 키 또는 모델 공급자를 설정하도록 유도하는 문구가 없다.

---

### AC-SEN-007: 감정 분석 동시성 제한 설정

**관련 요구사항**: REQ-SEN-004

**Given**
- 설정의 감정 분석 동시 실행 기본값이 3이다.
- 이미 3개의 감정 분석 작업이 active 상태로 등록되어 있다.

**When**
- 네 번째 감정 분석 작업을 시작하려고 한다.

**Then**
- 시스템은 기존 동시성 제한 의미를 유지한다.
- 제한 초과 상태는 명확한 에러 또는 재시도 가능한 상태로 표현된다.
- 제한 값은 코드 상수 직접 수정 없이 설정으로 조정 가능하다.

**통과 조건**
- 기본 동작은 기존 `MAX_CONCURRENT_SENTIMENT=3`과 동일하다.
- 설정 변경 시 태스크 로직이 변경된 값을 사용한다.

---

## 3. 최종 완료 체크리스트

- [ ] `backend/workers/celery_app.py`에 `backend.workers.tasks.sentiment_task`가 등록되어 있다.
- [ ] `stream.py`가 `task:sentiment:status:` prefix를 인식한다.
- [ ] Flutter 결과 화면에 감정 분석 전용 탭이 있다.
- [ ] `emotional_timeline`이 UI에서 시간 순서로 표시된다.
- [ ] `SpeakerSentiment` precomputed 데이터가 렌더링에 사용된다.
- [ ] 감정 분석 API 오류가 재시도 UI로 표시된다.
- [ ] 기존 `/api/v1/sentiment/*` 응답 스키마가 하위 호환성을 유지한다.
- [ ] README의 기능 상태와 모델명이 실제 구현과 일치한다.
