---
id: SPEC-SEARCH-002
version: "1.0.0"
status: completed
created: "2026-06-03"
author: MoAI
priority: medium
completed: "2026-06-14"
verification:
  - "./venv/bin/python -m mypy backend/ -> Success: no issues found in 394 source files"
  - "./venv/bin/python -m pytest backend/tests/unit/test_api_coverage_completion.py -q -o addopts='' -> included in 177 passed"
---

# SPEC-SEARCH-002: 수락 기준 (Acceptance Criteria)

## AC-SEARCH-008: 날짜 범위 필터 수락 기준 (REQ-SEARCH-007)

### 시나리오 1: date_from만 지정

```gherkin
Given 검색 인덱스에 2026-01월, 2026-03월, 2026-05월 데이터가 존재한다
When GET /api/v1/search?q=회의&date_from=2026-03-01 요청을 보낸다
Then 2026-03월 이후 결과만 반환된다
And response.items의 모든 created_at >= 2026-03-01 이다
And response.total은 전체 결과 중 조건에 맞는 건수이다
```

### 시나리오 2: date_to만 지정

```gherkin
Given 검색 인덱스에 여러 날짜의 데이터가 존재한다
When GET /api/v1/search?q=회의&date_to=2026-03-31 요청을 보낸다
Then 2026-03-31 이전 결과만 반환된다
And response.items의 모든 created_at <= 2026-03-31 이다
```

### 시나리오 3: 날짜 범위 모두 지정

```gherkin
Given 검색 인덱스에 2026-01월 ~ 2026-06월 데이터가 존재한다
When GET /api/v1/search?q=회의&date_from=2026-02-01&date_to=2026-04-30 요청을 보낸다
Then 2026-02-01 ~ 2026-04-30 범위 내 결과만 반환된다
And response.total은 범위 내 매칭 건수이다
```

### 시나리오 4: 유효하지 않은 날짜 형식

```gherkin
When GET /api/v1/search?q=회의&date_from=invalid-date 요청을 보낸다
Then 422 Validation Error가 반환된다
And error detail에 올바른 날짜 형식 안내가 포함된다
```

### 시나리오 5: 날짜 미지정 (하위 호환)

```gherkin
When GET /api/v1/search?q=회의 요청을 보낸다 (date_from, date_to 없음)
Then 기존과 동일하게 전체 날짜 범위의 결과가 반환된다
And 응답 형식은 SPEC-SEARCH-001과 동일하다
```

---

## AC-SEARCH-009: 정렬 옵션 수락 기준 (REQ-SEARCH-008)

### 시나리오 1: relevance 정렬

```gherkin
Given 검색 인덱스에 "회의록" 키워드가 여러 문서에 다른 빈도로 포함되어 있다
When GET /api/v1/search?q=회의록&sort=relevance 요청을 보낸다
Then 결과가 bm25 관련성 점수 순으로 정렬된다 (rank 값 오름차순)
And response에 sort="relevance" 필드가 포함된다
```

### 시나리오 2: newest 정렬

```gherkin
Given 검색 인덱스에 여러 날짜의 데이터가 존재한다
When GET /api/v1/search?q=회의&sort=newest 요청을 보낸다
Then 결과가 created_at 내림차순으로 정렬된다
And 가장 최근 결과가 첫 번째에 위치한다
```

### 시나리오 3: oldest 정렬

```gherkin
Given 검색 인덱스에 여러 날짜의 데이터가 존재한다
When GET /api/v1/search?q=회의&sort=oldest 요청을 보낸다
Then 결과가 created_at 오름차순으로 정렬된다
And 가장 오래된 결과가 첫 번째에 위치한다
```

### 시나리오 4: sort 미지정 (하위 호환)

```gherkin
When GET /api/v1/search?q=회의 요청을 보낸다 (sort 파라미터 없음)
Then 결과가 created_at DESC로 정렬된다 (기존 동작 유지)
And response에 sort 필드가 포함되지 않거나 null이다
```

### 시나리오 5: 유효하지 않은 sort 값

```gherkin
When GET /api/v1/search?q=회의&sort=invalid 요청을 보낸다
Then 422 Validation Error가 반환된다
And error detail에 허용 값(relevance, newest, oldest)이 안내된다
```

---

## AC-SEARCH-010: 검색 자동완성 수락 기준 (REQ-SEARCH-009)

### 시나리오 1: 정상 제안

```gherkin
Given 검색 인덱스에 "프로젝트 회의록", "주간 회의", "프로젝트 리뷰" 데이터가 존재한다
When GET /api/v1/search/suggestions?q=프로 요청을 보낸다
Then { suggestions: ["프로젝트"] } 형식의 응답이 반환된다
And 제안어는 중복이 없다
And 최대 10개의 제안이 반환된다
```

### 시나리오 2: 최소 길이 미달

```gherkin
When GET /api/v1/search/suggestions?q=프 (1자) 요청을 보낸다
Then 422 Validation Error가 반환된다
And error detail에 "최소 2자 이상" 안내가 포함된다
```

### 시나리오 3: 매칭 결과 없음

```gherkin
Given 검색 인덱스에 특정 키워드가 없다
When GET /api/v1/search/suggestions?q=xyzabc 요청을 보낸다
Then { suggestions: [] } 가 반환된다
And 200 OK 상태 코드이다
```

### 시나리오 4: 응답 시간

```gherkin
When 자동완성 API를 호출한다
Then 응답 시간이 100ms 이하이다 (인덱싱된 데이터 100건 기준)
```

---

## AC-SEARCH-011: 최근 검색어 수락 기준 (REQ-SEARCH-010)

### 시나리오 1: 검색어 저장

```gherkin
Given 최근 검색어가 비어있다
When 사용자가 "프로젝트 회의" 검색을 실행한다
Then "프로젝트 회의"가 최근 검색어 최상단에 저장된다
And 검색창 포커스 시 "프로젝트 회의"가 표시된다
```

### 시나리오 2: 중복 검색어 갱신

```gherkin
Given 최근 검색어에 ["회의", "프로젝트", "회의록"] 이 저장되어 있다
When 사용자가 "회의" 검색을 다시 실행한다
Then 최근 검색어가 ["회의", "회의록", "프로젝트"] 로 갱신된다
And "회의"가 최상단으로 이동한다 (중복 없음)
```

### 시나리오 3: 최대 저장 수 초과

```gherkin
Given 최근 검색어가 20개 저장되어 있다
When 사용자가 새 검색어 "신규검색" 을 실행한다
Then "신규검색"이 최상단에 추가된다
And 가장 오래된 검색어가 삭제된다
And 총 검색어 수는 20개를 유지한다
```

### 시나리오 4: 개별 삭제

```gherkin
Given 최근 검색어에 ["회의", "프로젝트"] 가 저장되어 있다
When 사용자가 "회의" 항목을 스와이프하여 삭제한다
Then 최근 검색어가 ["프로젝트"] 로 갱신된다
```

### 시나리오 5: 전체 삭제

```gherkin
Given 최근 검색어에 여러 항목이 저장되어 있다
When 사용자가 "전체 삭제" 버튼을 탭한다
Then 최근 검색어가 빈 상태가 된다
```

---

## AC-SEARCH-012: 화자 이름 필터 수락 기준 (REQ-SEARCH-011)

### 시나리오 1: 화자 필터 적용

```gherkin
Given 검색 인덱스에 화자 "김팀장", "이대리"가 포함된 minutes 데이터가 존재한다
When GET /api/v1/search?q=회의&speaker=김팀장 요청을 보낸다
Then "김팀장"이 speaker_names에 포함된 결과만 반환된다
```

### 시나리오 2: 화자 필터 + task_type 조합

```gherkin
Given minutes와 summary 타입 데이터가 존재한다
When GET /api/v1/search?q=프로젝트&task_type=minutes&speaker=김팀장 요청을 보낸다
Then minutes 타입 중 "김팀장"이 포함된 결과만 반환된다
```

### 시나리오 3: 화자 미지정

```gherkin
When GET /api/v1/search?q=회의 요청을 보낸다 (speaker 파라미터 없음)
Then 화자 필터 없이 전체 결과가 반환된다 (기존 동작 유지)
```

---

## AC-SEARCH-013: 액션 아이템 / 핵심 결정 필터 수락 기준 (REQ-SEARCH-012)

### 시나리오 1: has_action_items 필터

```gherkin
Given 검색 인덱스에 action_items_text가 있고 없는 항목이 혼재한다
When GET /api/v1/search?q=프로젝트&has_action_items=true 요청을 보낸다
Then action_items_text가 비어있지 않은 결과만 반환된다
```

### 시나리오 2: has_key_decisions 필터

```gherkin
Given 검색 인덱스에 summary 타입 중 action_items_text가 있는/없는 항목이 있다
When GET /api/v1/search?q=결정&has_key_decisions=true 요청을 보낸다
Then summary 타입 중 action_items_text가 비어있지 않은 결과만 반환된다
```

### 시나리오 3: 복합 필터 조합

```gherkin
Given 다양한 타입과 속성의 데이터가 존재한다
When GET /api/v1/search?q=회의&task_type=summary&has_action_items=true&sort=newest 요청을 보낸다
Then summary 타입 + action_items 존재 + 최신순 정렬 조건이 모두 적용된다
```

### 시나리오 4: false 값 지정

```gherkin
When GET /api/v1/search?q=회의&has_action_items=false 요청을 보낸다
Then 필터가 적용되지 않고 전체 결과가 반환된다 (false는 no-op)
```

---

## AC-SEARCH-014: 하위 호환성 수락 기준

### 시나리오 1: 기존 API 호출 호환성

```gherkin
Given SPEC-SEARCH-001 기반 클라이언트가 존재한다
When GET /api/v1/search?q=회의&task_type=all&page=1&page_size=20 요청을 보낸다 (기존 파라미터만)
Then SPEC-SEARCH-001과 동일한 형식의 응답이 반환된다
And 새로운 필드가 추가되더라도 기존 필드 구조가 유지된다
And 정렬은 created_at DESC이다
```

### 시나리오 2: Flutter 기존 화면 동작

```gherkin
Given SPEC-SEARCH-001 기반 Flutter 앱이 설치되어 있다
When 새 백엔드 API가 배포된 후 기존 앱으로 검색을 실행한다
Then 검색 결과가 정상적으로 표시된다
And 에러가 발생하지 않는다
```

---

## 품질 게이트 (Quality Gates)

### TRUST 5 검증

- **Tested**: 모든 AC 시나리오에 대응하는 단위/통합 테스트 존재. 커버리지 85% 이상
- **Readable**: 동적 SQL 빌더는 명확한 함수 분리. 한국어 주석으로 의도 설명
- **Unified**: 기존 코드 스타일(ruff, black) 준수. 네이밍 컨벤션 일관성
- **Secured**: SQL 인젝션 방지 (파라미터 바인딩 사용). 입력값 검증 (Pydantic)
- **Trackable**: 커밋 메시지에 SPEC-SEARCH-002 참조. REQ 번호 추적성 유지

### 추적성 태그

- SPEC: `SPEC-SEARCH-002`
- AC-SEARCH-008 → REQ-SEARCH-007 (날짜 범위 필터)
- AC-SEARCH-009 → REQ-SEARCH-008 (정렬 옵션)
- AC-SEARCH-010 → REQ-SEARCH-009 (자동완성)
- AC-SEARCH-011 → REQ-SEARCH-010 (최근 검색어)
- AC-SEARCH-012 → REQ-SEARCH-011 (화자 필터)
- AC-SEARCH-013 → REQ-SEARCH-012 (액션 아이템/결정 필터)
- AC-SEARCH-014 → 하위 호환성
