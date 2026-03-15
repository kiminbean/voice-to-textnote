---
spec_id: SPEC-E2E-001
type: acceptance
version: "1.0.0"
created: 2026-03-15
updated: 2026-03-15
author: kisoo
---

# SPEC-E2E-001 인수 기준

---

## 테스트 시나리오

### Scenario 1: STT → DIA 연결
```gherkin
Given STT 결과가 Redis에 완료 상태로 존재한다
When DIA 요청에 stt_task_id를 전달한다
Then 202 응답을 받고 DIA 결과에 speaker_id가 포함된다
```

### Scenario 2: DIA → MIN 연결
```gherkin
Given DIA 결과가 Redis에 완료 상태로 존재한다
When MIN 요청에 diarization_task_id를 전달한다
Then 202 응답을 받고 MIN 결과에 speaker_name과 통계가 포함된다
```

### Scenario 3: MIN → SUM 연결
```gherkin
Given MIN 결과가 Redis에 완료 상태로 존재한다
When SUM 요청에 minutes_task_id를 전달한다
Then 202 응답을 받고 SUM 결과에 summary_text가 포함된다
```

### Scenario 4: 전체 파이프라인
```gherkin
When STT 업로드 → DIA 요청 → MIN 요청 → SUM 요청을 순차 실행한다
Then 각 단계의 task_id가 다음 단계 입력으로 올바르게 전달된다
  And 최종 SUM 결과에 요약과 액션 아이템이 포함된다
```

### Scenario 5: 이전 단계 미존재 → 404
```gherkin
Given 존재하지 않는 stt_task_id로 DIA를 요청한다
Then 404 응답을 받는다
```

### Scenario 6: 동시 제한 초과 → 429
```gherkin
Given DIA 활성 작업이 2개인 상태에서
When 3번째 DIA 요청을 보낸다
Then 429 응답을 받는다
```

---

## Quality Gates

- [ ] E2E 테스트 전체 통과
- [ ] 기존 377개 테스트 회귀 0건
- [ ] 전체 커버리지 유지 (85%+)

---

*Acceptance ID: SPEC-E2E-001*
*생성일: 2026-03-15*
*상태: completed*
