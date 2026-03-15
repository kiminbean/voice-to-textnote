---
spec_id: SPEC-MIN-001
type: acceptance
version: "1.0.0"
created: 2026-03-15
updated: 2026-03-15
author: kisoo
---

# SPEC-MIN-001 인수 기준: 화자별 회의록 자동 생성

---

## 테스트 시나리오

### Scenario 1: Happy path - 2화자 회의록 생성

**관련 요구사항**: REQ-MIN-001, REQ-MIN-002, REQ-MIN-006, REQ-MIN-007, REQ-MIN-012

```gherkin
Given 화자 분리가 완료된 diarization_task_id "dia_abc123"이 존재하고
  And 해당 DIA 결과에 10개의 DiarizedSegmentResult와 2명의 SpeakerInfo가 Redis에 캐시되어 있다
When 클라이언트가 POST /api/v1/minutes를 {diarization_task_id: "dia_abc123"} 로 요청한다
  And 회의록 생성이 완료된다
  And 클라이언트가 GET /api/v1/minutes/{task_id}를 요청한다
Then 응답 status는 "completed"이다
  And segments 목록에 화자별로 병합된 회의록 세그먼트가 포함되어 있다
  And speakers 목록에 2명의 화자 통계(speaker_name, total_speaking_time, segment_count, speaking_ratio)가 포함되어 있다
  And total_speakers는 2이다
```

### Scenario 2: 연속 동일 화자 세그먼트 병합

**관련 요구사항**: REQ-MIN-001

```gherkin
Given DIA 결과에 연속 3개의 SPEAKER_00 세그먼트가 있다
  And [0.0s-2.0s "안녕하세요"], [2.0s-4.0s "오늘 회의"], [4.0s-6.0s "시작하겠습니다"]
When MinutesFormatter.format_minutes()를 실행한다
Then 3개의 세그먼트가 1개로 병합된다
  And 병합된 세그먼트의 text는 "안녕하세요 오늘 회의 시작하겠습니다"이다
  And start는 0.0, end는 6.0이다
```

### Scenario 3: Markdown 형식 출력

**관련 요구사항**: REQ-MIN-003

```gherkin
Given 회의록 생성이 완료된 task_id가 존재하고
  And 출력 형식이 "markdown"으로 요청되었다
When 클라이언트가 GET /api/v1/minutes/{task_id}를 요청한다
Then 응답의 markdown 필드에 포맷된 회의록이 포함된다
  And 각 발화는 "**[00:00:00] Speaker 1**: 발화 내용" 형식이다
```

### Scenario 4: speaker_id=null 처리

**관련 요구사항**: REQ-MIN-005

```gherkin
Given DIA 결과에 speaker_id가 null인 세그먼트가 존재한다
When MinutesFormatter.format_minutes()를 실행한다
Then 해당 세그먼트의 speaker_name은 "Unknown Speaker"이다
  And 세그먼트가 무시되지 않고 회의록에 포함된다
```

### Scenario 5: 동시 작업 초과 (4번째 요청 → 429)

**관련 요구사항**: REQ-MIN-008

```gherkin
Given 3개의 회의록 생성 작업이 processing 상태로 실행 중이다
When 클라이언트가 4번째 POST /api/v1/minutes 요청을 보낸다
Then 응답 상태 코드는 429 Too Many Requests이다
  And 기존 3개 작업은 정상적으로 계속 처리된다
```

### Scenario 6: DIA 결과 미존재 → 404

**관련 요구사항**: REQ-MIN-010

```gherkin
Given "nonexistent_dia_id"라는 diarization_task_id는 Redis에 존재하지 않는다
When 클라이언트가 POST /api/v1/minutes를 {diarization_task_id: "nonexistent_dia_id"} 로 요청한다
Then 응답 상태 코드는 404 Not Found이다
  And 응답 메시지에 "Diarization result not found"가 포함된다
```

### Scenario 7: 커스텀 화자 이름 매핑

**관련 요구사항**: REQ-MIN-016, REQ-MIN-017

```gherkin
Given DIA 결과에 SPEAKER_00과 SPEAKER_01이 존재한다
When 클라이언트가 speaker_names={"SPEAKER_00": "김팀장", "SPEAKER_01": "이대리"}를 포함하여 요청한다
  And 회의록 생성이 완료된다
Then segments의 speaker_name은 "김팀장" 또는 "이대리"이다
  And speakers 통계의 speaker_name도 동일하게 매핑된다
```

### Scenario 8: 상태 폴링 (pending → processing → completed)

**관련 요구사항**: REQ-MIN-006, REQ-MIN-011

```gherkin
When 클라이언트가 POST /api/v1/minutes를 유효한 diarization_task_id로 요청한다
Then 응답 상태 코드는 202 Accepted이다
When 클라이언트가 GET /api/v1/minutes/{task_id}/status를 요청한다
Then status는 "pending" 또는 "processing"이다
When 회의록 생성이 완료된 후 GET /api/v1/minutes/{task_id}/status를 요청한다
Then status는 "completed"이고 progress는 1.0이다
```

### Scenario 9: 결과 삭제

**관련 요구사항**: REQ-MIN-014

```gherkin
Given 회의록 결과가 존재하는 task_id가 있다
When 클라이언트가 DELETE /api/v1/minutes/{task_id}를 요청한다
Then 응답 상태 코드는 204 No Content이다
  And Redis에서 관련 키가 삭제되었다
```

### Scenario 10: 잘못된 task_id → 404

**관련 요구사항**: REQ-MIN-015

```gherkin
Given "nonexistent_id"라는 task_id는 존재하지 않는다
When 클라이언트가 GET /api/v1/minutes/nonexistent_id를 요청한다
Then 응답 상태 코드는 404 Not Found이다
```

---

## Quality Gates

### 테스트 커버리지

| 모듈 | 목표 커버리지 |
|------|-------------|
| minutes_formatter.py | 100% |
| minutes.py (Schema) | 90%+ |
| minutes_task.py | 85%+ |
| minutes.py (API) | 85%+ |
| 전체 SPEC-MIN-001 | 85%+ |

### Definition of Done

- [ ] 모든 17개 요구사항(REQ-MIN-001 ~ REQ-MIN-017)에 대한 테스트 존재
- [ ] 전체 테스트 커버리지 85% 이상
- [ ] minutes_formatter.py 커버리지 100%
- [ ] 모든 10개 인수 시나리오 통과
- [ ] ruff/black 포맷팅 통과

---

*Acceptance ID: SPEC-MIN-001*
*생성일: 2026-03-15*
*상태: draft*
