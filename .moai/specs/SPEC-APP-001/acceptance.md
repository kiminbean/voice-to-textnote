---
spec_id: SPEC-APP-001
type: acceptance
version: "1.0.0"
created: 2026-03-15
updated: 2026-03-15
author: kisoo
---

# SPEC-APP-001 인수 기준: Flutter 클라이언트 MVP

---

## 테스트 시나리오

### Scenario 1: API 서비스 - 서버 연결 확인

```gherkin
Given 백엔드 서버가 localhost:8000에서 실행 중이다
When HealthApiService.check()를 호출한다
Then 서버 상태가 "ok"로 반환된다
```

### Scenario 2: API 서비스 - 파일 업로드

```gherkin
Given 녹음된 WAV 파일이 존재한다
When TranscriptionApiService.upload(file)를 호출한다
Then task_id가 반환된다
  And status_url이 포함된 응답을 받는다
```

### Scenario 3: 파이프라인 자동 진행

```gherkin
Given 녹음이 완료되었다
When PipelineNotifier가 파이프라인을 시작한다
Then 업로드 → STT → 화자분리 → 회의록 → AI요약 순서로 자동 진행된다
  And 각 단계의 진행률이 업데이트된다
```

### Scenario 4: 파이프라인 실패 처리

```gherkin
Given STT 단계가 processing 중이다
When STT 작업이 failed 상태가 된다
Then PipelineNotifier는 STT 단계에서 멈춘다
  And 에러 메시지가 표시된다
  And 후속 단계(화자분리/회의록/요약)는 실행되지 않는다
```

### Scenario 5: 홈 화면 - 빈 상태

```gherkin
Given 저장된 회의가 없다
When HomeScreen이 표시된다
Then "회의 기록이 없습니다" 메시지가 표시된다
  And 녹음 시작 버튼이 중앙에 표시된다
```

### Scenario 6: 녹음 화면 - 상태 전이

```gherkin
Given RecordingScreen이 표시된다
When 녹음 시작 버튼을 탭한다
Then 녹음 상태가 recording으로 변경된다
  And 타이머가 0:00부터 증가한다
When 중지 버튼을 탭한다
Then 녹음 상태가 stopped으로 변경된다
  And 파이프라인 처리가 자동 시작된다
```

### Scenario 7: 결과 화면 - 회의록 표시

```gherkin
Given 파이프라인이 모두 완료된 회의가 있다
When ResultScreen이 표시된다
Then 화자별 회의록 세그먼트가 표시된다
  And AI 요약문이 표시된다
  And 액션 아이템 목록이 표시된다
```

### Scenario 8: 서버 연결 실패 처리

```gherkin
Given 백엔드 서버가 응답하지 않는다
When 앱이 API 호출을 시도한다
Then 앱이 중단되지 않는다
  And "서버에 연결할 수 없습니다" 메시지가 표시된다
  And 재시도 버튼이 제공된다
```

---

## Quality Gates

- [ ] Flutter 프로젝트 빌드 성공 (web + macOS)
- [ ] 모든 위젯/단위 테스트 통과
- [ ] API 서비스 레이어 mock 테스트 통과
- [ ] 파이프라인 상태 관리 테스트 통과
- [ ] flutter analyze 경고 0개

---

*Acceptance ID: SPEC-APP-001*
*생성일: 2026-03-15*
*상태: draft*
