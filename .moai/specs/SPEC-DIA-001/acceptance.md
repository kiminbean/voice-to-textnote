---
spec_id: SPEC-DIA-001
type: acceptance
version: "1.0.0"
created: 2026-03-15
updated: 2026-03-15
author: kisoo
---

# SPEC-DIA-001 인수 기준: pyannote.audio 3.1 화자 분리 파이프라인

---

## 테스트 시나리오

### Scenario 1: Happy path - 2화자 회의 화자 분리

**관련 요구사항**: REQ-DIA-003, REQ-DIA-005, REQ-DIA-006, REQ-DIA-010, REQ-DIA-011, REQ-DIA-015

```gherkin
Given STT 처리가 완료된 task_id "stt_abc123"이 존재하고
  And 해당 STT 결과에 10개의 SegmentResult가 Redis에 캐시되어 있고
  And 전처리된 WAV 파일 "stt_abc123_normalized.wav"이 temp_dir에 존재하고
  And DiarizationEngine 모델이 로드된 상태이다
When 클라이언트가 POST /api/v1/diarizations를 {stt_task_id: "stt_abc123"} 로 요청한다
  And 화자 분리 처리가 완료된다
  And 클라이언트가 GET /api/v1/diarizations/{task_id}를 요청한다
Then 응답 status는 "completed"이다
  And segments 목록의 각 항목에 speaker_id가 "SPEAKER_00" 또는 "SPEAKER_01"로 할당되어 있다
  And 각 세그먼트의 speaker_confidence는 0.0 이상 1.0 이하이다
  And speakers 목록에 2명의 화자 정보(speaker_id, total_duration, segment_count)가 포함되어 있다
  And num_speakers는 2이다
```

---

### Scenario 2: HuggingFace 토큰 미설정 시 서버 시작 거부

**관련 요구사항**: REQ-DIA-002

```gherkin
Given HUGGINGFACE_TOKEN 환경 변수가 설정되지 않았다
When FastAPI 서버를 시작한다
Then 서버는 시작을 거부한다
  And 에러 메시지에 "HUGGINGFACE_TOKEN is not set or invalid"가 포함된다
  And 에러 메시지에 모델 라이선스 URL "https://huggingface.co/pyannote/speaker-diarization-3.1"이 포함된다
```

---

### Scenario 3: 상태 폴링 (pending -> processing -> completed)

**관련 요구사항**: REQ-DIA-005, REQ-DIA-014

```gherkin
Given DiarizationEngine이 로드된 상태이다
When 클라이언트가 POST /api/v1/diarizations를 유효한 stt_task_id로 요청한다
Then 응답 상태 코드는 202 Accepted이다
  And 응답에 task_id와 status_url이 포함된다

When 클라이언트가 즉시 GET /api/v1/diarizations/{task_id}/status를 요청한다
Then status는 "pending" 또는 "processing"이다
  And progress는 0.0 이상이다

When 화자 분리 처리가 완료된 후 GET /api/v1/diarizations/{task_id}/status를 요청한다
Then status는 "completed"이다
  And progress는 1.0이다
```

---

### Scenario 4: 화자 수 자동 감지 (num_speakers=None)

**관련 요구사항**: REQ-DIA-022

```gherkin
Given 3명의 화자가 참여한 회의 오디오의 STT가 완료된 상태이다
When 클라이언트가 POST /api/v1/diarizations를 {stt_task_id: "...", num_speakers: null}로 요청한다
  And 화자 분리 처리가 완료된다
Then 응답의 num_speakers는 자동 감지된 화자 수이다
  And speakers 목록에 감지된 수만큼의 화자 정보가 포함된다
```

---

### Scenario 5: 최대 동시 작업 초과 (3번째 요청 -> 429)

**관련 요구사항**: REQ-DIA-007

```gherkin
Given 2개의 화자 분리 작업이 processing 상태로 실행 중이다
When 클라이언트가 3번째 POST /api/v1/diarizations 요청을 보낸다
Then 응답 상태 코드는 429 Too Many Requests이다
  And 응답 메시지에 "Maximum concurrent diarization tasks exceeded"가 포함된다
  And 기존 2개 작업은 정상적으로 계속 처리된다
```

---

### Scenario 6: STT 결과와 화자 타임스탬프 매칭 정확도

**관련 요구사항**: REQ-DIA-010, REQ-DIA-011

```gherkin
Given STT 세그먼트 [0.5s, 3.2s]가 존재하고
  And 화자 세그먼트 [0.4s, 2.0s] SPEAKER_00 (겹침 1.5s)이 있고
  And 화자 세그먼트 [2.0s, 3.5s] SPEAKER_01 (겹침 1.2s)이 있다
When SpeakerMatcher.match()를 실행한다
Then 해당 STT 세그먼트의 speaker_id는 "SPEAKER_00"이다 (1.5s > 1.2s)
  And speaker_confidence는 약 0.556이다 (1.5 / 2.7)
```

---

### Scenario 7: 단독 화자 구간 - speaker_confidence 높은 값

**관련 요구사항**: REQ-DIA-011

```gherkin
Given STT 세그먼트 [10.0s, 15.0s] (5초 길이)가 존재하고
  And 화자 세그먼트 [9.5s, 16.0s] SPEAKER_00만 겹친다 (겹침 5.0s, 전체 구간)
When SpeakerMatcher.match()를 실행한다
Then 해당 STT 세그먼트의 speaker_id는 "SPEAKER_00"이다
  And speaker_confidence는 1.0이다 (5.0 / 5.0 = 완전 겹침)
```

---

### Scenario 8: 화자 없는 구간 (무음) - speaker_id=null

**관련 요구사항**: REQ-DIA-012

```gherkin
Given STT 세그먼트 [20.0s, 22.0s]가 존재하고
  And 해당 시간 구간에 겹치는 화자 세그먼트가 없다
When SpeakerMatcher.match()를 실행한다
Then 해당 STT 세그먼트의 speaker_id는 null이다
  And speaker_confidence는 0.0이다
```

---

### Scenario 9: 오래된 화자 분리 결과 삭제 (DELETE -> 204)

**관련 요구사항**: REQ-DIA-017

```gherkin
Given 화자 분리 결과가 존재하는 task_id "dia_xyz789"가 있다
  And Redis에 task:dia:status:dia_xyz789와 task:dia:result:dia_xyz789 키가 존재한다
When 클라이언트가 DELETE /api/v1/diarizations/dia_xyz789를 요청한다
Then 응답 상태 코드는 204 No Content이다
  And Redis에서 task:dia:status:dia_xyz789 키가 삭제되었다
  And Redis에서 task:dia:result:dia_xyz789 키가 삭제되었다
```

---

### Scenario 10: 헬스 체크 엔드포인트

**관련 요구사항**: REQ-DIA-019

```gherkin
Given DiarizationEngine 모델이 로드된 상태이다
When 클라이언트가 GET /api/v1/health/diarization을 요청한다
Then 응답 상태 코드는 200 OK이다
  And 응답에 "status": "loaded"가 포함된다
  And 응답에 "memory_usage_bytes"가 양수 값으로 포함된다
```

```gherkin
Given DiarizationEngine 모델이 아직 로드되지 않은 상태이다
When 클라이언트가 GET /api/v1/health/diarization을 요청한다
Then 응답 상태 코드는 200 OK이다
  And 응답에 "status": "not_loaded"가 포함된다
```

---

### Scenario 11: 메모리 임계값 초과 시 503 반환

**관련 요구사항**: REQ-DIA-021

```gherkin
Given 현재 시스템 메모리 사용량이 24GB의 80%(19.2GB)를 초과한 상태이다
When 클라이언트가 POST /api/v1/diarizations 요청을 보낸다
Then 응답 상태 코드는 503 Service Unavailable이다
  And 응답 메시지에 "Memory usage exceeds threshold"가 포함된다
  And 기존 진행 중인 작업에는 영향이 없다
```

---

### Scenario 12: 잘못된 task_id - 404 반환

**관련 요구사항**: REQ-DIA-018

```gherkin
Given "nonexistent_task_id"라는 task_id는 존재하지 않는다
When 클라이언트가 GET /api/v1/diarizations/nonexistent_task_id를 요청한다
Then 응답 상태 코드는 404 Not Found이다
  And 응답에 "Task not found" 메시지가 포함된다

When 클라이언트가 GET /api/v1/diarizations/nonexistent_task_id/status를 요청한다
Then 응답 상태 코드는 404 Not Found이다

When 클라이언트가 DELETE /api/v1/diarizations/nonexistent_task_id를 요청한다
Then 응답 상태 코드는 404 Not Found이다
```

---

### Scenario 13: 동점 화자 처리 (동일 겹침 시간 -> 시작 빠른 화자 선택)

**관련 요구사항**: REQ-DIA-013

```gherkin
Given STT 세그먼트 [5.0s, 7.0s] (2초 길이)가 존재하고
  And 화자 세그먼트 [4.5s, 6.0s] SPEAKER_00 (겹침 1.0s)이 있고
  And 화자 세그먼트 [6.0s, 7.5s] SPEAKER_01 (겹침 1.0s)이 있다
When SpeakerMatcher.match()를 실행한다
Then 해당 STT 세그먼트의 speaker_id는 "SPEAKER_00"이다 (시작 시간 4.5s < 6.0s)
  And 경고 로그에 "Tie-breaking for segment"가 기록된다
  And 로그에 "SPEAKER_00, SPEAKER_01" 화자 정보가 포함된다
  And 로그에 겹침 시간 "1.0s"가 포함된다
```

---

### Scenario 14: 중복 작업 방지

**관련 요구사항**: REQ-DIA-009

```gherkin
Given stt_task_id "stt_abc123"에 대한 화자 분리 작업이 이미 processing 중이다
When 클라이언트가 동일한 stt_task_id로 POST /api/v1/diarizations를 다시 요청한다
Then 시스템은 중복 작업을 거부한다
  And 기존 작업의 task_id를 반환하거나 적절한 에러 응답을 반환한다
```

---

### Scenario 15: 처리 실패 시 지수 백오프 재시도

**관련 요구사항**: REQ-DIA-008

```gherkin
Given DiarizationEngine.diarize()가 처리 중 RuntimeError를 발생시킨다
When diarization_task가 실행된다
Then 시스템은 60초 간격으로 지수 백오프 재시도를 수행한다
  And 최대 3회까지 재시도한다
  And 3회 재시도 후에도 실패하면 상태를 "failed"로 마킹한다
  And 실패 원인이 에러 메시지에 기록된다
```

---

## Quality Gates

### 테스트 커버리지

| 모듈 | 목표 커버리지 | 비고 |
|------|-------------|------|
| speaker_matcher.py | 100% | 핵심 알고리즘, 모든 경계값 테스트 필수 |
| diarization_engine.py | 85%+ | mock Pipeline 기반 단위 테스트 |
| diarization_task.py | 85%+ | mock Engine + mock Redis |
| diarization.py (API) | 85%+ | TestClient 기반 통합 테스트 |
| diarization.py (Schema) | 90%+ | Pydantic 모델 검증 |
| **전체 SPEC-DIA-001** | **85%+** | TRUST 5 기준 |

### 통합 테스트 전략

- pyannote.audio Pipeline은 **mock 처리**: 실제 모델 로드 없이 테스트 가능
- Redis는 **fakeredis** 또는 테스트용 Redis 인스턴스 사용
- Celery 태스크는 `task_always_eager=True`로 동기 실행 테스트
- FastAPI TestClient로 엔드포인트 통합 테스트

### 성능 검증

- 처리 시간 로깅: 각 diarization_task 실행 시 처리 시간(초)을 INFO 레벨로 기록
- 메모리 사용량 로깅: 모델 로드 전/후 메모리 변화량 기록
- 타임스탬프 매칭 성능: 1000개 세그먼트 기준 1초 이내 완료 확인

### Definition of Done

- [ ] 모든 22개 요구사항(REQ-DIA-001 ~ REQ-DIA-022)에 대한 테스트 존재
- [ ] 전체 테스트 커버리지 85% 이상
- [ ] speaker_matcher.py 커버리지 100%
- [ ] 모든 15개 인수 시나리오 통과
- [ ] 통합 테스트에서 전체 API 흐름(생성 -> 폴링 -> 결과 조회 -> 삭제) 검증
- [ ] HUGGINGFACE_TOKEN 미설정 시 서버 시작 거부 확인
- [ ] 동시 작업 제한(2개) 동작 확인
- [ ] 헬스 체크 엔드포인트 정상 응답 확인
- [ ] ruff/black 포맷팅 통과
- [ ] 보안 취약점 스캔 통과

---

*Acceptance ID: SPEC-DIA-001*
*생성일: 2026-03-15*
*상태: completed*
