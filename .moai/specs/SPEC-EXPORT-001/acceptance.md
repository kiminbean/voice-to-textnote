---
id: SPEC-EXPORT-001
type: acceptance
created: "2026-03-22"
updated: "2026-03-22"
author: kisoo
---

# SPEC-EXPORT-001: 수락 기준 (Acceptance Criteria)

---

## AC-EXPORT-001: PDF 생성 시 유효한 PDF와 한국어 텍스트 반환

### Scenario 1: 정상적인 회의록 데이터로 PDF 생성

```gherkin
Given 완전한 회의록 데이터가 Redis에 저장되어 있고
  And 데이터에 한국어 텍스트가 포함되어 있을 때
When MinutesPDFGenerator.generate()를 호출하면
Then bytes 타입의 PDF 데이터가 반환되고
  And 반환된 데이터는 PDF 매직 바이트(%PDF-)로 시작하며
  And 한국어 텍스트가 깨지지 않고 정상 렌더링된다
```

### Scenario 2: NotoSansKR 폰트 등록

```gherkin
Given MinutesPDFGenerator가 초기화될 때
When fpdf2 인스턴스가 생성되면
Then NotoSansKR-Regular.ttf가 유니코드 폰트로 등록되고
  And NotoSansKR-Bold.ttf가 유니코드 폰트로 등록된다
```

---

## AC-EXPORT-002: PDF에 모든 섹션 포함 (헤더, 회의록, 요약, 액션 아이템)

### Scenario 1: PDF 헤더 섹션

```gherkin
Given 회의 제목이 "주간 팀 미팅"이고 생성 시간이 "2026-03-22 14:00"일 때
When PDF를 생성하면
Then PDF 첫 페이지에 "주간 팀 미팅" 제목이 포함되고
  And 생성 날짜/시간이 표시되며
  And 총 발화 시간이 표시된다
```

### Scenario 2: 발화자 통계 섹션

```gherkin
Given 3명의 발화자(김철수: 15회, 이영희: 12회, 박민수: 8회)가 있을 때
When PDF를 생성하면
Then 발화자별 발화 횟수와 총 발화 시간이 테이블로 표시된다
```

### Scenario 3: 회의록 본문 섹션

```gherkin
Given segments 배열에 발화 데이터가 포함되어 있을 때
When PDF를 생성하면
Then 각 발화가 "[시작시간~종료시간] 발화자: 발화내용" 형식으로 표시된다
```

### Scenario 4: 요약 및 주요 결정사항 섹션

```gherkin
Given summary_text와 key_decisions 데이터가 있을 때
When PDF를 생성하면
Then 요약 전문이 별도 섹션으로 표시되고
  And 주요 결정사항이 번호 매김 목록으로 표시된다
```

### Scenario 5: 액션 아이템 섹션

```gherkin
Given action_items 배열에 [{assignee, task, deadline, priority}] 데이터가 있을 때
When PDF를 생성하면
Then 담당자, 작업, 기한, 우선순위가 테이블 형식으로 표시된다
```

---

## AC-EXPORT-003: Export API가 PDF StreamingResponse 반환

### Scenario 1: 정상 PDF 내보내기

```gherkin
Given 유효한 minutes_task_id "abc-123"에 대한 회의록 데이터가 존재할 때
When GET /api/v1/export/pdf/abc-123 요청을 보내면
Then HTTP 200 응답이 반환되고
  And Content-Type 헤더가 "application/pdf"이며
  And Content-Disposition 헤더가 'attachment; filename="minutes_abc-123.pdf"'이고
  And 응답 본문은 유효한 PDF 바이너리 데이터이다
```

### Scenario 2: Redis TTL 만료 시 SQLite fallback

```gherkin
Given minutes_task_id "abc-123"의 Redis 데이터가 TTL 만료로 삭제되었고
  And SQLite에 해당 데이터가 저장되어 있을 때
When GET /api/v1/export/pdf/abc-123 요청을 보내면
Then SQLite에서 데이터를 조회하여 PDF를 정상 생성하고
  And HTTP 200 응답을 반환한다
```

---

## AC-EXPORT-004: Flutter 내보내기 버튼 + 다운로드 + 공유

### Scenario 1: 내보내기 버튼 표시

```gherkin
Given 사용자가 ResultScreen에 진입했을 때
When 화면이 로드되면
Then AppBar 우측에 내보내기 아이콘 버튼이 표시된다
```

### Scenario 2: PDF 다운로드 및 공유

```gherkin
Given 사용자가 ResultScreen에서 내보내기 버튼을 탭했을 때
When 버튼을 탭하면
Then 로딩 인디케이터가 표시되고
  And Export API를 호출하여 PDF를 다운로드하며
  And 다운로드 완료 후 iOS Share Sheet가 표시되고
  And 로딩 인디케이터가 사라진다
```

### Scenario 3: 다운로드 중 재요청 방지

```gherkin
Given PDF 다운로드가 진행 중일 때
When 사용자가 내보내기 버튼을 다시 탭하면
Then 중복 요청이 발생하지 않고
  And 기존 다운로드가 계속 진행된다
```

---

## AC-EXPORT-005: 누락/불완전 데이터 오류 처리

### Scenario 1: 존재하지 않는 task_id

```gherkin
Given 존재하지 않는 minutes_task_id "invalid-id"로 요청할 때
When GET /api/v1/export/pdf/invalid-id 요청을 보내면
Then HTTP 404 응답이 반환되고
  And 응답 본문에 {"detail": "Minutes not found"} 메시지가 포함된다
```

### Scenario 2: 불완전한 회의록 데이터

```gherkin
Given minutes_task_id "abc-123"의 segments 배열이 비어있을 때
When GET /api/v1/export/pdf/abc-123 요청을 보내면
Then HTTP 422 응답이 반환되고
  And 응답 본문에 {"detail": "Incomplete minutes data"} 메시지가 포함된다
```

### Scenario 3: Flutter 다운로드 실패 처리

```gherkin
Given 네트워크 오류로 PDF 다운로드가 실패했을 때
When Export API 호출이 실패하면
Then 로딩 인디케이터가 사라지고
  And SnackBar로 "PDF 내보내기에 실패했습니다" 오류 메시지가 표시되며
  And 사용자는 다시 내보내기를 시도할 수 있다
```

---

## 품질 게이트 (Quality Gates)

### 테스트 커버리지

| 대상                            | 최소 커버리지 | 테스트 유형            |
| ------------------------------- | ------------- | ---------------------- |
| `pdf_generator.py`              | 85%           | 단위 테스트            |
| `api/v1/export.py`              | 85%           | 통합 테스트 (TestClient)|
| `export_api.dart`               | 80%           | 단위 테스트 (Mockito)  |
| `result_screen.dart` (변경분)   | 80%           | 위젯 테스트            |

### TRUST 5 체크리스트

- [x] **Tested**: 모든 요구사항에 대한 테스트 존재 (REQ-EXPORT-001 ~ 005)
- [x] **Readable**: 코드 주석은 'Why' 중심, Google 스타일 docstring
- [x] **Unified**: ruff/formatting 통과, Flutter analyze 통과
- [x] **Secured**: 입력값 검증 (task_id 형식), 에러 메시지에 내부 정보 미노출
- [x] **Trackable**: SPEC-EXPORT-001 참조 이력 유지

### 2026-06-14 재검증

- Backend 전체 회귀: `venv/bin/python -m pytest backend -q` -> `3323 passed, 16 skipped`, coverage `98.62%`
- Backend lint/format: `venv/bin/python -m ruff check backend` -> `All checks passed!`; `venv/bin/python -m ruff format --check backend` -> `394 files already formatted`
- Backend type check: `venv/bin/python -m mypy backend` -> `Success: no issues found in 394 source files`
- Flutter export client tests are included in `cd client && flutter test` -> `324 passed`
- Flutter analyze: `cd client && flutter analyze` -> `No issues found!`
- 실기기 공유 시트 UX는 시뮬레이터/자동화로 완전 증명할 수 없으므로 수동 E2E 체크리스트에 유지한다.

### 검증 명령어

```bash
# Backend 테스트
pytest tests/test_pdf_generator.py tests/test_export_api.py -v --cov=backend/pipeline/pdf_generator --cov=backend/app/api/v1/export

# Backend 수동 검증
curl -o test.pdf http://localhost:8000/api/v1/export/pdf/{task_id}
file test.pdf  # "PDF document" 출력 확인

# Flutter 테스트
cd client && flutter test test/services/export_api_test.dart
cd client && flutter analyze
```

---

## 추적성 태그 (Traceability)

| 수락 기준      | 관련 요구사항               | 검증 방법              |
| -------------- | --------------------------- | ---------------------- |
| AC-EXPORT-001  | REQ-EXPORT-002, REQ-EXPORT-003 | 단위 테스트, PDF 검사  |
| AC-EXPORT-002  | REQ-EXPORT-002              | 단위 테스트, 육안 확인 |
| AC-EXPORT-003  | REQ-EXPORT-001              | 통합 테스트, curl      |
| AC-EXPORT-004  | REQ-EXPORT-004              | 위젯 테스트, 실기기    |
| AC-EXPORT-005  | REQ-EXPORT-005              | 통합/위젯 테스트       |
