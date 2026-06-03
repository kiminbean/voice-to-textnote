---
id: SPEC-SEARCH-002
version: "1.0.0"
status: completed
created: "2026-06-03"
author: MoAI
priority: medium
issue_number: 0
---

# HISTORY

| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|-----------|
| 1.0.0 | 2026-06-03 | MoAI | 초기 SPEC 작성 |
| 1.0.0 | 2026-06-03 | MoAI | 구현 완료, status → completed |

---

# SPEC-SEARCH-002: 고급 검색 기능 확장 (Advanced Search)

## 1. 개요

### 1.1 배경

SPEC-SEARCH-001에서 FTS5 기반 전문 검색 MVP가 완료되었다. 기본 키워드 검색, task_type 필터, 페이지네이션, 스니펫 하이라이트 기능이 동작 중이다. 사용자 피드백과 제품 로드맵에 따라 날짜 범위 필터, 정렬 옵션, 자동완성, 상세 필터 4가지 고급 검색 기능을 추가한다.

### 1.2 범위

- **Backend**: 날짜 범위 필터, 정렬 옵션, 상세 필터를 검색 API에 추가
- **Backend**: 자동완성(검색어 제안) API 엔드포인트 신규 추가
- **Flutter**: 날짜 범위 선택 UI, 정렬 드롭다운, 상세 필터 바텀시트 추가
- **Flutter**: 자동완성 제안 목록, 최근 검색어 로컬 저장

### 1.3 선행 조건

- SPEC-SEARCH-001 완료 (status: completed)
- FTS5 `search_index` 테이블 운영 중
- 기존 `GET /api/v1/search` 엔드포인트 동작 중

### 1.4 범위 외

- PostgreSQL `tsvector` 마이그레이션 (별도 SPEC)
- Elasticsearch 통합
- 고급 한국어 형태소 분석 (MeCab)
- 검색 결과 분석/통계 대시보드

---

## 2. EARS 요구사항

### REQ-SEARCH-007: 날짜 범위 필터

**WHEN** 사용자가 `date_from` 및/또는 `date_to` 파라미터를 지정하여 검색 요청을 보내면 **THEN** 시스템은 해당 날짜 범위 내의 결과만 반환해야 한다.

- 엔드포인트: 기존 `GET /api/v1/search` (파라미터 확장)
- 선택 파라미터: `date_from` (ISO 8601 날짜, 예: `2026-01-01`), `date_to` (ISO 8601 날짜)
- `date_from`만 지정 시: 해당 날짜 이후 결과만
- `date_to`만 지정 시: 해당 날짜 이전 결과만
- 둘 다 지정 시: 해당 범위 내 결과만
- 날짜 필터링 기준: `search_index.created_at` (UNINDEXED 컬럼, FTS5 WHERE 절에서 비교 연산 가능)
- 백엔드 구현: 기존 SQL WHERE 절에 `AND si.created_at >= :date_from` / `AND si.created_at <= :date_to` 조건 추가
- Flutter: `showDateRangePicker` 위젯으로 날짜 범위 선택 UI 제공

### REQ-SEARCH-008: 정렬 옵션

**WHEN** 사용자가 `sort` 파라미터를 지정하면 **THEN** 시스템은 해당 정렬 기준에 따라 결과를 정렬하여 반환해야 한다.

- 선택 파라미터: `sort` (relevance | newest | oldest)
- 기본값: `relevance` (기존 동작은 `newest`였으나, 검색 관련성 기본값이 더 자연스러움)
  - 단, 정렬 파라미터 미지정 시 기존 동작(`created_at DESC`)을 유지하여 하위 호환성 보장
- `relevance`: FTS5 `rank` 컬럼(bm25 알고리즘) 기준, `ORDER BY rank`
- `newest`: `created_at DESC` (기존 기본 정렬)
- `oldest`: `created_at ASC`
- 백엔드 구현: SELECT 절에 `rank` 추가, ORDER BY 절을 파라미터에 따라 동적 생성
- Flutter: 정렬 아이콘 버튼 + 드롭다운 메뉴 (AppBar에 배치)

### REQ-SEARCH-009: 검색 자동완성 (Search Autocomplete)

**WHEN** 사용자가 검색창에 2자 이상의 텍스트를 입력하면 **THEN** 시스템은 300ms 디바운스 후 인덱싱된 콘텐츠에서 접두사 기반 제안을 최대 10개 반환해야 한다.

- 엔드포인트: `GET /api/v1/search/suggestions?q={prefix}`
- 필수 파라미터: `q` (접두사, 최소 2자)
- 응답 형식: `{ suggestions: string[] }`
- 백엔드 구현: FTS5 MATCH 쿼리로 `content`, `summary_text` 컬럼에서 키워드 추출
  - 대안: `search_index`에서 MATCH 쿼리로 매칭된 행의 텍스트에서 토큰 추출 후 접두사 필터링
  - 최적화: 별도 `search_suggestions` 테이블 생성 (인덱싱 시 토큰 분리 저장)
- 디바운스: Flutter에서 300ms 적용 (기존 검색 디바운스와 동일)
- 최대 제안 수: 10개
- 중복 제거: 동일 제안어는 한 번만 반환

### REQ-SEARCH-010: 최근 검색어 (Recent Searches)

**WHEN** 사용자가 검색을 실행하면 **THEN** 시스템은 해당 검색어를 로컬에 저장하고, 검색창 포커스 시 최근 검색어 목록을 표시해야 한다.

- 저장소: Flutter `SharedPreferences` (로컬 스토리지)
- 최대 저장 수: 20개 (초과 시 오래된 순서로 삭제)
- 중복 처리: 동일 검색어 재검색 시 기존 항목 삭제 후 최상단에 추가
- 표시 위치: 검색창 포커스 + 입력 텍스트 없음 → 최근 검색어 목록 표시
- 삭제 기능: 개별 검색어 스와이프 삭제, 전체 삭제 버튼
- 백엔드 API 불필요 (클라이언트 전용 기능)

### REQ-SEARCH-011: 화자 이름 필터 (Speaker Name Filter)

**WHEN** 사용자가 `speaker` 파라미터를 지정하면 **THEN** 시스템은 해당 화자가 포함된 결과만 필터링하여 반환해야 한다.

- 선택 파라미터: `speaker` (화자 이름 문자열)
- 백엔드 구현: FTS5 MATCH 쿼리의 speaker_names 컬럼에 대한 필터링
  - 방법 1: `AND speaker_names : speaker_name` (FTS5 컬럼 필터)
  - 방법 2: 추가 WHERE 조건 `AND si.speaker_names LIKE '%:speaker%'`
  - 권장: 방법 2 (LIKE) - FTS5 UNINDEXED 제약 없이 안정적 동작
- Flutter: 상세 필터 바텀시트에 화자 이름 입력 필드

### REQ-SEARCH-012: 액션 아이템 / 핵심 결정 필터 (Detail Filters)

**WHEN** 사용자가 `has_action_items` 또는 `has_key_decisions` 파라미터를 지정하면 **THEN** 시스템은 해당 항목이 포함된 결과만 필터링하여 반환해야 한다.

- 선택 파라미터:
  - `has_action_items`: boolean (true 시 action_items_text가 비어있지 않은 결과만)
  - `has_key_decisions`: boolean (true 시 action_items_text에 결정 내용이 포함된 결과만)
    - 주: 현재 스키마에서 key_decisions와 action_items가 동일 컬럼(`action_items_text`)에 병합 저장됨
    - 따라서 `has_key_decisions`는 summary 타입 중 action_items_text가 비어있지 않은 결과로 간주
- 백엔드 구현: WHERE 절에 `AND si.action_items_text != ''` / `AND si.action_items_text IS NOT NULL` 조건 추가
- 기존 `task_type` 필터와 결합 가능 (AND 조건)
- Flutter: 상세 필터 바텀시트에 토글 스위치

---

## 3. 수정 대상 파일

### Backend (수정)

| 파일 | 변경 내용 |
|------|-----------|
| `backend/db/search_service.py` | 날짜 범위, 정렬, 화자, 상세 필터 로직 추가. 정렬에 따른 동적 ORDER BY 생성. rank 컬럼 SELECT 추가 |
| `backend/schemas/search.py` | SearchResponse에 sort 필드 추가. SuggestionResponse 신규 스키마 추가 |
| `backend/app/api/v1/search.py` | date_from, date_to, sort, speaker, has_action_items, has_key_decisons 쿼리 파라미터 추가. suggestions 엔드포인트 신규 추가 |

### Backend (신규)

| 파일 | 역할 |
|------|------|
| `backend/db/suggestion_service.py` | 검색어 자동완성 제안 로직 (FTS5 기반 키워드 추출) |

### Flutter (수정)

| 파일 | 변경 내용 |
|------|-----------|
| `client/lib/models/search_result.dart` | SearchResponse에 sort 필드 추가. SuggestionResponse 모델 추가 |
| `client/lib/services/search_api.dart` | search() 메서드 파라미터 확장 (dateFrom, dateTo, sort, speaker, 필터). suggestions() 메서드 추가 |
| `client/lib/providers/search_provider.dart` | SearchQuery 확장 (dateRange, sort, speaker, 필터). suggestions 프로바이더 추가. recentSearches 프로바이더 추가 |
| `client/lib/screens/search_screen.dart` | 정렬 메뉴, 상세 필터 바텀시트, 자동완성 목록, 최근 검색어 UI 추가 |

### Flutter (신규)

| 파일 | 역할 |
|------|------|
| `client/lib/services/recent_search_service.dart` | SharedPreferences 기반 최근 검색어 관리 서비스 |
| `client/lib/widgets/search_filter_sheet.dart` | 상세 필터 바텀시트 위젯 (날짜, 화자, 액션아이템, 결정사항) |

---

## 4. 기술 제약

### 4.1 FTS5 UNINDEXED 컬럼 필터링

- `created_at`은 UNINDEXED로 선언되었으나, FTS5 WHERE 절에서 비교 연산자(`>=`, `<=`) 사용 가능
- MATCH 조건과 UNINDEXED 컬럼 조건은 AND로 결합 가능
- 단, UNINDEXED 컬럼으로만 필터링할 때는 MATCH 조건이 필수 (FTS5 제약)
- 모든 쿼리에는 `search_index MATCH :query`가 포함되므로 문제 없음

### 4.2 FTS5 rank 컬럼

- FTS5는 기본적으로 `rank`라는 hidden column을 제공 (bm25 기반)
- `SELECT ..., rank FROM search_index WHERE ... ORDER BY rank` 형식으로 사용
- rank 값이 낮을수록 관련성이 높음 (기본 정렬: ASC)
- 기존 쿼리에 rank를 SELECT에 추가해야 함

### 4.3 한국어 자동완성 한계

- `unicode61` 토크나이저는 공백/구두점 기반 분리이므로 한국어 접두사 매칭이 제한적
- 예: "회의록" 입력 시 "회의록을" 토큰 매칭 불가
- 완화 방안: 클라이언트에서 입력 텍스트의 공백 분리 토큰을 사용하여 FTS5 MATCH
- 장기 해결: Phase 3에서 MeCab 또는 pg_bigm 도입

### 4.4 action_items_text 컬럼 공유

- 현재 `action_items_text` 컬럼에 action_items + key_decisions + next_steps가 병합 저장됨
- `has_key_decisions` 필터는 action_items_text 비어있지 않음으로만 간접 판별 가능
- 정확한 분리가 필요하면 향후 스키마 분리 필요 (별도 SPEC)

### 4.5 하위 호환성

- 기존 `GET /api/v1/search` 호출 (파라미터 없이)은 동일하게 동작해야 함
- `sort` 미지정 시 기존 정렬(`created_at DESC`) 유지
- 새 파라미터는 모두 선택사항 (optional)

---

## 5. 추적성 태그

- SPEC: `SPEC-SEARCH-002`
- 선행 SPEC: `SPEC-SEARCH-001` (completed)
- 요구사항: `REQ-SEARCH-007` ~ `REQ-SEARCH-012`
- 수락 기준: `AC-SEARCH-008` ~ `AC-SEARCH-014` (acceptance.md 참조)
- 구현 계획: `PHASE-SEARCH2-1` ~ `PHASE-SEARCH2-5` (plan.md 참조)
