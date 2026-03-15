---
spec_id: SPEC-SUM-001
type: acceptance
version: "1.0.0"
created: 2026-03-15
updated: 2026-03-15
author: kisoo
---

# SPEC-SUM-001 인수 기준: Claude API 기반 회의 요약

---

## 테스트 시나리오

### Scenario 1: Happy path - 회의 요약 생성

**관련 요구사항**: REQ-SUM-001, REQ-SUM-002, REQ-SUM-006, REQ-SUM-007, REQ-SUM-013

```gherkin
Given 회의록 생성이 완료된 minutes_task_id가 존재하고
  And ANTHROPIC_API_KEY가 설정되어 있다
When 클라이언트가 POST /api/v1/summaries를 {minutes_task_id: "min_abc123"} 로 요청한다
  And 요약 생성이 완료된다
  And 클라이언트가 GET /api/v1/summaries/{task_id}를 요청한다
Then 응답 status는 "completed"이다
  And summary_text에 회의 요약문이 포함되어 있다
  And action_items는 리스트 형태이다
  And key_decisions는 리스트 형태이다
  And next_steps는 리스트 형태이다
```

### Scenario 2: Claude API 응답이 JSON이 아닌 경우 graceful 처리

**관련 요구사항**: REQ-SUM-004

```gherkin
Given Claude API가 순수 텍스트(비-JSON)를 반환한다
When SummaryGenerator.parse_response()를 실행한다
Then summary_text에 원본 텍스트가 저장된다
  And action_items는 빈 리스트이다
  And key_decisions는 빈 리스트이다
  And next_steps는 빈 리스트이다
  And 오류가 발생하지 않는다
```

### Scenario 3: ANTHROPIC_API_KEY 미설정

**관련 요구사항**: REQ-SUM-011

```gherkin
Given ANTHROPIC_API_KEY 환경 변수가 설정되지 않았다 (빈 문자열)
When summary_task가 실행된다
Then 태스크는 즉시 실패한다
  And 에러 메시지에 "ANTHROPIC_API_KEY is not configured"가 포함된다
  And 재시도하지 않는다
```

### Scenario 4: Minutes 결과 미존재

**관련 요구사항**: REQ-SUM-010

```gherkin
Given "nonexistent_min_id"라는 minutes_task_id는 Redis에 존재하지 않는다
When 클라이언트가 POST /api/v1/summaries를 요청한다
Then 응답 상태 코드는 404 Not Found이다
```

### Scenario 5: 동시 작업 초과 (3번째 요청 → 429)

**관련 요구사항**: REQ-SUM-008

```gherkin
Given 2개의 요약 생성 작업이 processing 상태이다
When 클라이언트가 3번째 POST /api/v1/summaries 요청을 보낸다
Then 응답 상태 코드는 429 Too Many Requests이다
```

### Scenario 6: 상태 폴링

**관련 요구사항**: REQ-SUM-006, REQ-SUM-012

```gherkin
When 클라이언트가 POST /api/v1/summaries를 요청한다
Then 응답 상태 코드는 202 Accepted이다
When GET /api/v1/summaries/{task_id}/status를 요청한다
Then status는 "pending" 또는 "processing"이다
When 생성 완료 후 GET /status를 요청한다
Then status는 "completed"이고 progress는 1.0이다
```

### Scenario 7: 결과 삭제

**관련 요구사항**: REQ-SUM-015

```gherkin
Given 요약 결과가 존재하는 task_id가 있다
When DELETE /api/v1/summaries/{task_id}를 요청한다
Then 응답 상태 코드는 204 No Content이다
```

### Scenario 8: ActionItem 구조 검증

**관련 요구사항**: REQ-SUM-005

```gherkin
Given Claude API가 액션 아이템을 포함한 응답을 반환한다
When 응답을 파싱한다
Then 각 ActionItem에 task(str)가 존재한다
  And assignee는 str|None이다
  And priority 기본값은 "medium"이다
```

---

## Quality Gates

| 모듈 | 목표 커버리지 |
|------|-------------|
| summary_generator.py | 100% |
| summary.py (Schema) | 90%+ |
| summary_task.py | 85%+ |
| summary.py (API) | 85%+ |
| 전체 | 85%+ |

### Definition of Done

- [ ] 모든 16개 요구사항 테스트 존재
- [ ] 전체 커버리지 85%+
- [ ] summary_generator.py 100%
- [ ] Claude API mock으로 전체 테스트 통과
- [ ] ruff/black 포맷팅 통과
- [ ] anthropic 의존성 추가

---

*Acceptance ID: SPEC-SUM-001*
*생성일: 2026-03-15*
*상태: draft*
