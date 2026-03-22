---
id: SPEC-SEARCH-001
type: plan
version: "1.0.0"
created: "2026-03-22"
updated: "2026-03-22"
author: kisoo
development_mode: tdd
---

# SPEC-SEARCH-001: 구현 계획

## 개발 방법론

TDD (RED-GREEN-REFACTOR) 접근 방식으로 구현한다.

---

## Phase 1: Backend - FTS5 인덱스 모듈

**목표**: SQLite FTS5 가상 테이블 생성 및 인덱싱 함수 구현
**관련 요구사항**: REQ-SEARCH-002
**우선순위**: Primary Goal

### RED (실패하는 테스트 작성)

- FTS5 테이블 생성 테스트
- `index_search_entry()` 함수 테스트: minutes result_data 입력 -> 인덱스 레코드 생성 확인
- `index_search_entry()` 함수 테스트: summary result_data 입력 -> 인덱스 레코드 생성 확인
- 중복 task_id 인덱싱 시 upsert 동작 테스트
- 인덱싱 실패 시 예외 미전파 확인 테스트 (best-effort)

### GREEN (최소 구현)

- `backend/db/search_models.py`: FTS5 `search_index` 테이블 DDL 정의
- 테이블 컬럼: `task_id`, `task_type`, `content`, `speaker_names`, `summary_text`, `action_items_text`, `created_at`
- `unicode61` 토크나이저 설정
- `index_search_entry(session, task_result)` 함수 구현
  - minutes: `segments[].text` 결합 -> `content`, `speaker_name` 추출 -> `speaker_names`
  - summary: `summary_text`, `action_items[].task` + `key_decisions[]` + `next_steps[]` -> `action_items_text`
- `delete_search_entry(session, task_id)` 함수 구현

### REFACTOR

- 인덱싱 로직을 전략 패턴으로 분리 (task_type별 인덱서)
- 에러 핸들링 및 로깅 표준화

---

## Phase 2: Backend - 검색 API + 스키마

**목표**: 검색 API 엔드포인트 및 Pydantic 스키마 구현
**관련 요구사항**: REQ-SEARCH-001, REQ-SEARCH-003, REQ-SEARCH-004, REQ-SEARCH-006
**우선순위**: Primary Goal

### RED

- `GET /api/v1/search?q=keyword` 요청 시 200 응답 테스트
- `q` 파라미터 누락 시 422 에러 테스트
- `q` 파라미터 1자 미만 시 422 에러 테스트
- `task_type=summary` 필터 동작 테스트
- `task_type=minutes` 필터 동작 테스트
- `task_type=invalid` 시 422 에러 테스트
- 페이지네이션 동작 테스트 (page=2, page_size=5)
- 응답 스키마 검증 테스트 (items, total, page, page_size, query)
- 스니펫 포함 확인 테스트

### GREEN

- `backend/schemas/search.py`: `SearchResultItem`, `SearchResponse` Pydantic 모델
- `backend/db/search_service.py`: `SearchService` 클래스
  - `search(session, query, task_type, page, page_size)` -> `SearchResponse`
  - FTS5 `MATCH` 쿼리 + `snippet()` 함수 활용
  - `COUNT(*)` 별도 쿼리로 total 계산
  - `ORDER BY created_at DESC` + `LIMIT/OFFSET`
- `backend/app/api/v1/search.py`: 검색 라우터
  - `GET /api/v1/search` 엔드포인트
  - Query 파라미터: `q`, `task_type`, `page`, `page_size`
  - 기존 History API 패턴 준수 (의존성 주입, 응답 구조)
- `backend/app/api/v1/__init__.py`: search 라우터 등록

### REFACTOR

- 쿼리 빌더 패턴으로 검색 조건 조합 정리
- 에러 메시지 국제화 준비 (에러 코드 상수화)

---

## Phase 3: Backend - 자동 인덱싱 (Celery Hook)

**목표**: Celery 작업 완료 시 자동으로 검색 인덱스 업데이트
**관련 요구사항**: REQ-SEARCH-002
**우선순위**: Primary Goal

### RED

- `persist_task_result()` 호출 후 `search_index` 테이블에 레코드 생성 확인 테스트
- minutes 작업 완료 시 인덱싱 테스트
- summary 작업 완료 시 인덱싱 테스트
- transcription 작업은 인덱싱하지 않는 것 확인 테스트
- 인덱싱 실패 시 `persist_task_result()`는 정상 완료되는 것 확인 테스트

### GREEN

- `backend/db/sync_service.py` 수정: `persist_task_result()` 함수 내부에서 `index_search_entry()` 호출 추가
- try-except로 감싸서 인덱싱 실패가 작업 저장에 영향을 주지 않도록 보호
- structlog로 인덱싱 성공/실패 로깅

### REFACTOR

- 인덱싱 호출을 별도 헬퍼 함수로 추출
- 로깅 포맷 일관성 확인

---

## Phase 4: Flutter - 검색 모델 + API 서비스

**목표**: Flutter 검색 데이터 모델 및 API 서비스 구현
**관련 요구사항**: REQ-SEARCH-005
**우선순위**: Secondary Goal

### RED

- `SearchResultItem` 모델 JSON 직렬화/역직렬화 테스트
- `SearchResponse` 모델 JSON 파싱 테스트
- `SearchApi.search()` 메서드 API 호출 테스트 (Mock Dio)
- 에러 응답 처리 테스트

### GREEN

- `client/lib/models/search_result.dart`: `SearchResultItem`, `SearchResponse` 모델
- `client/lib/services/search_api.dart`: `SearchApi` 클래스
  - `search(query, {taskType, page, pageSize})` -> `Future<SearchResponse>`
  - Dio 기반, `dioProvider` 패턴 활용
  - 에러 핸들링: `DioException` 처리
- `client/lib/providers/search_provider.dart`: Riverpod 프로바이더
  - `searchQueryProvider`: 현재 검색 쿼리 상태
  - `searchResultProvider`: `FutureProvider.family<SearchResponse, SearchQuery>` 패턴
  - 디바운스 처리 (300ms)

### REFACTOR

- API 서비스 에러 핸들링 공통 패턴 추출
- Provider 구조 최적화

---

## Phase 5: Flutter - 검색 UI

**목표**: 검색 바 및 검색 결과 화면 구현
**관련 요구사항**: REQ-SEARCH-005, REQ-SEARCH-006
**우선순위**: Secondary Goal

### RED

- 홈 화면에 검색 아이콘 존재 확인 테스트
- 검색 아이콘 탭 시 검색 화면 이동 테스트
- 검색 결과 리스트 렌더링 테스트
- 빈 결과 상태 UI 테스트
- 로딩 상태 UI 테스트
- 에러 상태 + 재시도 버튼 테스트
- 스니펫 내 볼드 텍스트 렌더링 테스트

### GREEN

- `client/lib/screens/search_screen.dart`: 검색 화면
  - 상단 검색 바 (텍스트 입력 + 클리어 버튼)
  - 결과 리스트 (작업 유형 아이콘 + 스니펫 + 날짜)
  - 빈 상태 / 로딩 상태 / 에러 상태 처리
  - 스니펫 `<b>` 태그 -> `TextSpan` + `FontWeight.bold` 파싱
  - 결과 탭 시 회의 상세 화면 네비게이션
- `client/lib/screens/home_screen.dart` 수정: AppBar에 검색 아이콘 추가
- 디바운스 타이머 구현 (300ms)

### REFACTOR

- 스니펫 파싱 로직을 유틸리티 함수로 분리
- 위젯 재사용성 개선

---

## Phase 6: 통합 검증

**목표**: 전체 검색 파이프라인 E2E 검증
**관련 요구사항**: 전체
**우선순위**: Final Goal

### 검증 항목

- Backend 단위 테스트 전체 통과 확인
- Flutter 위젯 테스트 전체 통과 확인
- Backend 통합 테스트: 인덱싱 -> 검색 -> 결과 반환 플로우
- API 응답 시간 < 200ms 확인 (100건 이하 데이터)
- 기존 테스트 회귀 없음 확인 (전체 테스트 스위트 실행)
- 스니펫 하이라이트 UI 확인

---

## 리스크 분석

| 리스크 | 확률 | 영향도 | 대응 전략 |
|--------|------|--------|-----------|
| 한국어 검색 품질 저하 (조사 미분리) | 높음 | 중간 | `unicode61` 토크나이저 사용, 사용자에게 핵심 키워드 안내, Phase 2에서 개선 |
| DB best-effort 저장으로 인한 인덱스 갭 | 중간 | 낮음 | 인덱싱도 best-effort, Phase 2에서 리인덱싱 스크립트 제공 |
| FTS5 테이블과 기존 task_results 동기화 실패 | 낮음 | 중간 | try-except 보호, 실패 로깅, 수동 리인덱싱 가능하도록 설계 |
| 미팅-작업 매핑 혼란 (작업 단위 결과 반환) | 중간 | 낮음 | Flutter Meeting 모델의 taskId 활용하여 매핑 |

---

## 의존성

### 외부 의존성

- SQLite FTS5 확장 (SQLite 기본 내장, 별도 설치 불필요)
- 기존 `persist_task_result()` 흐름 (backend/db/sync_service.py)
- 기존 History API 패턴 (backend/app/api/v1/history.py)

### 내부 의존성

- Phase 2는 Phase 1에 의존 (FTS5 테이블이 먼저 생성되어야 검색 가능)
- Phase 3은 Phase 1에 의존 (인덱싱 함수가 먼저 구현되어야 자동 인덱싱 가능)
- Phase 4는 Phase 2에 의존 (API가 먼저 구현되어야 Flutter 서비스 구현 가능)
- Phase 5는 Phase 4에 의존 (모델/서비스가 먼저 구현되어야 UI 구현 가능)
- Phase 6은 Phase 1~5 모두 완료 후 실행

### 병렬 실행 가능 구간

- Phase 1 + Phase 4(모델 정의만): 서버 스키마와 클라이언트 모델을 동시에 정의 가능
- Phase 2 + Phase 3: 검색 API와 자동 인덱싱을 병렬 구현 가능 (둘 다 Phase 1에만 의존)
