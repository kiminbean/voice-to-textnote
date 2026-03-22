---
id: SPEC-SEARCH-001
type: acceptance
version: "1.0.0"
created: "2026-03-22"
updated: "2026-03-22"
author: kisoo
---

# SPEC-SEARCH-001: 수락 기준

---

## AC-SEARCH-001: 키워드 검색 시 관련 결과 반환

**관련 요구사항**: REQ-SEARCH-001, REQ-SEARCH-002

```gherkin
Scenario: 키워드로 회의록 검색
  Given 검색 인덱스에 "프로젝트 일정 보고서" 텍스트를 포함하는 minutes 작업 결과가 존재한다
  And 검색 인덱스에 "예산 검토 회의" 텍스트를 포함하는 summary 작업 결과가 존재한다
  When 사용자가 GET /api/v1/search?q=보고서 요청을 보낸다
  Then 응답 상태 코드는 200이다
  And 응답 body의 items에 "보고서"를 포함하는 결과가 1건 이상 존재한다
  And 각 item에 task_id, task_type, snippet, created_at 필드가 존재한다
  And 응답 body에 total, page, page_size, query 필드가 존재한다

Scenario: 검색어 미입력 시 에러 반환
  When 사용자가 GET /api/v1/search 요청을 보낸다 (q 파라미터 없음)
  Then 응답 상태 코드는 422이다

Scenario: 검색어 1자 미만 시 에러 반환
  When 사용자가 GET /api/v1/search?q=가 요청을 보낸다
  Then 응답 상태 코드는 422이다

Scenario: 매칭 결과 없는 검색
  Given 검색 인덱스에 "프로젝트" 관련 데이터가 존재하지 않는다
  When 사용자가 GET /api/v1/search?q=존재하지않는키워드 요청을 보낸다
  Then 응답 상태 코드는 200이다
  And 응답 body의 items는 빈 배열이다
  And 응답 body의 total은 0이다
```

---

## AC-SEARCH-002: 검색 타입 필터링

**관련 요구사항**: REQ-SEARCH-004

```gherkin
Scenario: summary 타입 필터
  Given 검색 인덱스에 "예산" 텍스트를 포함하는 summary 작업 결과가 존재한다
  And 검색 인덱스에 "예산" 텍스트를 포함하는 minutes 작업 결과가 존재한다
  When 사용자가 GET /api/v1/search?q=예산&task_type=summary 요청을 보낸다
  Then 응답의 모든 items의 task_type은 "summary"이다

Scenario: minutes 타입 필터
  Given 검색 인덱스에 "예산" 텍스트를 포함하는 minutes 작업 결과가 존재한다
  When 사용자가 GET /api/v1/search?q=예산&task_type=minutes 요청을 보낸다
  Then 응답의 모든 items의 task_type은 "minutes"이다

Scenario: all 타입 (기본값)
  Given 검색 인덱스에 summary와 minutes 타입 결과가 모두 존재한다
  When 사용자가 GET /api/v1/search?q=예산 요청을 보낸다 (task_type 미지정)
  Then 응답의 items에 summary와 minutes 타입이 모두 포함된다

Scenario: 유효하지 않은 타입
  When 사용자가 GET /api/v1/search?q=예산&task_type=invalid 요청을 보낸다
  Then 응답 상태 코드는 422이다
```

---

## AC-SEARCH-003: 빈 검색어 처리

**관련 요구사항**: REQ-SEARCH-001

```gherkin
Scenario: 빈 문자열 검색어
  When 사용자가 GET /api/v1/search?q= 요청을 보낸다
  Then 응답 상태 코드는 422이다

Scenario: 공백만 있는 검색어
  When 사용자가 GET /api/v1/search?q=%20%20 요청을 보낸다
  Then 응답 상태 코드는 422이다
```

---

## AC-SEARCH-004: 페이지네이션 동작

**관련 요구사항**: REQ-SEARCH-003

```gherkin
Scenario: 기본 페이지네이션
  Given 검색 인덱스에 "회의"를 포함하는 결과가 25건 존재한다
  When 사용자가 GET /api/v1/search?q=회의 요청을 보낸다
  Then 응답의 items 길이는 20이다 (기본 page_size)
  And 응답의 total은 25이다
  And 응답의 page는 1이다
  And 응답의 page_size는 20이다

Scenario: 2페이지 조회
  Given 검색 인덱스에 "회의"를 포함하는 결과가 25건 존재한다
  When 사용자가 GET /api/v1/search?q=회의&page=2 요청을 보낸다
  Then 응답의 items 길이는 5이다
  And 응답의 page는 2이다

Scenario: 커스텀 page_size
  Given 검색 인덱스에 "회의"를 포함하는 결과가 15건 존재한다
  When 사용자가 GET /api/v1/search?q=회의&page_size=5 요청을 보낸다
  Then 응답의 items 길이는 5이다
  And 응답의 page_size는 5이다

Scenario: page_size 최대값 초과
  When 사용자가 GET /api/v1/search?q=회의&page_size=100 요청을 보낸다
  Then 응답 상태 코드는 422이다 (최대 50 초과)

Scenario: 정렬 확인 (최신 우선)
  Given 검색 인덱스에 서로 다른 날짜의 결과가 존재한다
  When 사용자가 GET /api/v1/search?q=회의 요청을 보낸다
  Then 응답의 items는 created_at 기준 내림차순으로 정렬되어 있다
```

---

## AC-SEARCH-005: Flutter 검색 UI 동작

**관련 요구사항**: REQ-SEARCH-005

```gherkin
Scenario: 검색 진입
  Given 사용자가 홈 화면에 있다
  When 사용자가 AppBar의 검색 아이콘을 탭한다
  Then 검색 화면이 표시된다
  And 검색 텍스트 필드에 포커스가 있다

Scenario: 검색 실행 및 결과 표시
  Given 사용자가 검색 화면에 있다
  When 사용자가 "프로젝트"를 입력하고 300ms가 경과한다
  Then API 검색 요청이 1회 발생한다
  And 검색 결과 리스트가 표시된다
  And 각 결과에 작업 유형 아이콘, 스니펫, 날짜가 표시된다

Scenario: 디바운스 동작
  Given 사용자가 검색 화면에 있다
  When 사용자가 빠르게 "프", "프로", "프로젝", "프로젝트"를 입력한다
  Then API 검색 요청은 최종 입력 후 300ms에 1회만 발생한다

Scenario: 검색 결과 없음
  Given 사용자가 검색 화면에 있다
  When 사용자가 매칭되지 않는 키워드를 입력한다
  Then "검색 결과가 없습니다" 메시지가 표시된다

Scenario: 로딩 상태
  Given 사용자가 검색 화면에 있다
  When 검색 API 요청이 진행 중이다
  Then 로딩 인디케이터가 표시된다

Scenario: 에러 상태
  Given 사용자가 검색 화면에 있다
  When 검색 API 요청이 실패한다
  Then 에러 메시지와 재시도 버튼이 표시된다

Scenario: 결과 탭 시 상세 이동
  Given 검색 결과 리스트에 항목이 표시되어 있다
  When 사용자가 검색 결과 항목을 탭한다
  Then 해당 회의의 상세 화면으로 이동한다
```

---

## AC-SEARCH-006: 자동 인덱싱

**관련 요구사항**: REQ-SEARCH-002

```gherkin
Scenario: 회의록 작업 완료 시 자동 인덱싱
  Given Celery minutes 작업이 완료되었다
  When persist_task_result()가 호출된다
  Then search_index 테이블에 해당 task_id로 레코드가 생성된다
  And content 필드에 segments의 text가 결합되어 저장된다
  And speaker_names 필드에 화자 이름이 저장된다

Scenario: 요약 작업 완료 시 자동 인덱싱
  Given Celery summary 작업이 완료되었다
  When persist_task_result()가 호출된다
  Then search_index 테이블에 해당 task_id로 레코드가 생성된다
  And summary_text 필드에 요약 텍스트가 저장된다
  And action_items_text 필드에 액션 아이템과 결정사항이 결합되어 저장된다

Scenario: transcription 작업은 인덱싱 제외
  Given Celery transcription 작업이 완료되었다
  When persist_task_result()가 호출된다
  Then search_index 테이블에 해당 task_id로 레코드가 생성되지 않는다

Scenario: 인덱싱 실패 시 작업 저장에 영향 없음
  Given 검색 인덱스 테이블에 문제가 있다
  When persist_task_result()가 호출된다
  Then task_results 테이블에는 정상적으로 저장된다
  And 인덱싱 실패 로그가 기록된다
```

---

## AC-SEARCH-007: 기존 기능 회귀 없음

**관련 요구사항**: 전체

```gherkin
Scenario: 기존 API 엔드포인트 정상 동작
  Given SPEC-SEARCH-001 변경이 적용되었다
  When 기존 API 엔드포인트들을 호출한다 (health, history, upload 등)
  Then 모든 기존 API가 이전과 동일하게 동작한다

Scenario: 기존 Celery 작업 정상 동작
  Given SPEC-SEARCH-001 변경이 적용되었다
  When 전체 파이프라인 (STT -> DIA -> MIN -> SUM)을 실행한다
  Then 모든 작업이 이전과 동일하게 완료된다
  And 새로 추가된 인덱싱으로 인해 작업 완료가 지연되거나 실패하지 않는다

Scenario: 기존 테스트 스위트 통과
  Given SPEC-SEARCH-001 변경이 적용되었다
  When 전체 백엔드 테스트 스위트를 실행한다
  Then 기존 테스트가 모두 통과한다 (0 failures, 0 errors)
```

---

## Quality Gates

### Backend

- [ ] 신규 코드 테스트 커버리지 >= 85%
- [ ] 기존 테스트 전체 통과 (0 failures)
- [ ] API 응답 시간 < 200ms (100건 이하)
- [ ] FTS5 인덱싱 실패가 기존 기능에 영향 없음
- [ ] Pydantic 스키마 유효성 검증 통과
- [ ] structlog 로깅 표준 준수

### Flutter

- [ ] 위젯 테스트 통과
- [ ] 디바운스 동작 확인 (300ms)
- [ ] 빈 상태 / 로딩 상태 / 에러 상태 UI 확인
- [ ] 스니펫 하이라이트 렌더링 확인
- [ ] 기존 홈 화면 기능 회귀 없음

### Definition of Done

1. 모든 AC (AC-SEARCH-001 ~ AC-SEARCH-007) 시나리오 통과
2. Backend 신규 테스트 + 기존 테스트 전체 통과
3. Flutter 위젯 테스트 통과
4. 코드 리뷰 완료
5. API 문서 (OpenAPI/Swagger) 자동 생성 확인
6. 검색 기능 수동 E2E 검증 (키워드 입력 -> 결과 확인 -> 상세 이동)
