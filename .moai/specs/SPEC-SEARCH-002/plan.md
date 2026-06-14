---
id: SPEC-SEARCH-002
version: "1.0.0"
status: completed
created: "2026-06-03"
author: MoAI
priority: medium
completed: "2026-06-14"
---

# SPEC-SEARCH-002: 구현 계획

## 1. 마일스톤

### Primary Goal: 백엔드 검색 API 확장

기존 `search_service.py`와 `search.py` 라우터에 날짜 범위, 정렬, 상세 필터 기능을 추가한다.

- [x] `search_service.py`: 동적 WHERE/ORDER BY 생성 로직 구현
- [x] `search_service.py`: rank 컬럼 SELECT 추가
- [x] `schemas/search.py`: SearchResponse에 sort 필드 추가
- [x] `search.py`: date_from, date_to, sort, speaker, has_action_items, has_key_decisions 파라미터 추가
- [x] 단위 테스트: 각 필터/정렬 조합에 대한 테스트 케이스

### Primary Goal: 자동완성 API

검색어 접두사 기반 제안 엔드포인트를 신규 구현한다.

- [x] `suggestion_service.py`: FTS5 MATCH 결과에서 키워드 추출 로직
- [x] `search.py`: `GET /api/v1/search/suggestions` 엔드포인트 추가
- [x] `schemas/search.py`: SuggestionResponse 스키마 정의
- [x] 단위 테스트: 제안 로직 테스트

### Secondary Goal: Flutter 검색 UI 확장

백엔드 API 확장에 맞춰 Flutter 클라이언트를 업데이트한다.

- [x] `search_result.dart`: 모델 확장 (sort, SuggestionResponse)
- [x] `search_api.dart`: API 파라미터 확장, suggestions() 추가
- [x] `search_provider.dart`: SearchQuery 확장, 프로바이더 추가
- [x] `search_screen.dart`: 정렬 메뉴, 자동완성, 최근 검색어 UI
- [ ] `search_filter_sheet.dart`: 상세 필터 바텀시트 신규
- [ ] `recent_search_service.dart`: 최근 검색어 로컬 관리 신규
- [ ] 위젯 테스트: 필터 UI 동작 테스트

### Final Goal: 통합 테스트 및 검증

- [ ] 백엔드 + Flutter 통합 시나리오 테스트
- [ ] 기존 검색 기능 회귀 테스트 (하위 호환성)
- [ ] 성능 테스트 (필터 조합 시 응답 시간)

---

## 2. 기술 접근법

### 2.1 동적 SQL 생성 전략

기존 `SearchService.search()` 메서드의 SQL을 동적 생성 방식으로 변경한다.

**현재 방식**: 고정 SQL 문자열 2개 (type_filter 있음/없음)
**변경 방식**: 베이스 SQL + 조건부 WHERE + 동적 ORDER BY

```
베이스 SELECT:
  SELECT si.task_id, si.task_type, snippet(...), si.created_at, tr.completed_at, rank

동적 WHERE 조건 (모두 AND 결합):
  - MATCH :query (필수)
  - task_type = :task_type (선택)
  - created_at >= :date_from (선택)
  - created_at <= :date_to (선택)
  - speaker_names LIKE '%:speaker%' (선택)
  - action_items_text != '' (선택, has_action_items=true)
  - action_items_text IS NOT NULL AND action_items_text != '' (선택, has_key_decisions=true)

동적 ORDER BY:
  - sort=relevance → ORDER BY rank
  - sort=newest → ORDER BY si.created_at DESC
  - sort=oldest → ORDER BY si.created_at ASC
  - 기본(sort 미지정) → ORDER BY si.created_at DESC (하위 호환)
```

### 2.2 자동완성 구현 전략

**선택한 방식**: FTS5 MATCH 결과에서 토큰 추출

```
1. 사용자 입력을 FTS5 MATCH 쿼리로 변환 (기존 _build_match_query 재사용)
2. search_index에서 MATCH 결과의 content, summary_text 컬럼 조회 (LIMIT 20)
3. 결과 텍스트에서 공백 기반 토큰 분리
4. 사용자 입력(접두사)으로 시작하는 토큰 필터링
5. 빈도순 정렬 후 상위 10개 반환
```

**대안 검토**:
- 별도 `search_suggestions` 테이블: 정확도 높지만 인덱싱 로직 복잡도 증가
- LIKE 쿼리: 단순하지만 대량 데이터에서 성능 저하
- FTS5 prefix 토크나이저: 한국어 지원 한계

**선택 이유**: 기존 FTS5 인프라 재사용, 추가 스키마 없이 구현 가능, MVP에 적합

### 2.3 최근 검색어 구현 전략

**저장소**: SharedPreferences (shared_preferences 패키지)

```
데이터 형식: JSON 문자열 배열
키: 'recent_searches'
최대 항목: 20개
저장 시점: 검색 API 호출 성공 시
정렬: 최근 사용순 (LIFO)
중복 처리: 기존 항목 제거 후 최상단 추가
```

### 2.4 Flutter 아키텍처

기존 Riverpod 패턴을 유지하며 확장:

```
SearchQuery (확장)
├── query: String
├── taskType: String?
├── page: int
├── dateFrom: DateTime?       (NEW)
├── dateTo: DateTime?          (NEW)
├── sort: String?              (NEW)
├── speaker: String?           (NEW)
├── hasActionItems: bool?      (NEW)
└── hasKeyDecisions: bool?     (NEW)

신규 프로바이더:
- suggestionsProvider (FutureProvider.family)
- recentSearchesProvider (StateNotifierProvider)
```

---

## 3. 리스크 및 대응

| 리스크 | 확률 | 영향 | 대응 전략 |
|--------|------|------|-----------|
| FTS5 동적 WHERE 성능 저하 | 낮음 | 중간 | 복합 조건 시 인덱스 힌트 사용, 필요시 materialized view 검토 |
| 한국어 자동완성 정확도 낮음 | 높음 | 낮음 | 공백 토큰 기반으로 동작, 사용자에게 안내, 장기적으로 MeCab 도입 |
| 다수 필터 조합 시 쿼리 복잡도 증가 | 중간 | 중간 | SQL 빌더 유틸리티 함수 분리, 각 조건을 독립적으로 테스트 |
| has_key_decisions 간접 판별 한계 | 중간 | 낮음 | MVP에서는 간접 판별로 충분, 향후 스키마 분리 SPEC으로 해결 |

---

## 4. 구현 순서 (권장)

```
PHASE-SEARCH2-1: 백엔드 검색 서비스 확장
  → search_service.py: 동적 SQL 빌더 + rank 컬럼
  → schemas/search.py: 스키마 확장
  → search.py: 파라미터 확장
  → 단위 테스트

PHASE-SEARCH2-2: 자동완성 API
  → suggestion_service.py: 제안 로직
  → search.py: suggestions 엔드포인트
  → 단위 테스트

PHASE-SEARCH2-3: Flutter 모델 및 API 서비스 확장
  → search_result.dart: 모델 확장
  → search_api.dart: API 파라미터 확장 + suggestions()

PHASE-SEARCH2-4: Flutter UI 확장
  → search_provider.dart: 프로바이더 확장
  → recent_search_service.dart: 최근 검색어 서비스
  → search_filter_sheet.dart: 필터 바텀시트
  → search_screen.dart: 전체 UI 업데이트

PHASE-SEARCH2-5: 통합 테스트 및 검증
  → 회귀 테스트
  → 필터 조합 테스트
  → 성능 벤치마크
```

---

## 5. 추적성 태그

- SPEC: `SPEC-SEARCH-002`
- 요구사항 매핑:
  - PHASE-SEARCH2-1 → REQ-SEARCH-007, REQ-SEARCH-008, REQ-SEARCH-011, REQ-SEARCH-012
  - PHASE-SEARCH2-2 → REQ-SEARCH-009
  - PHASE-SEARCH2-3 → REQ-SEARCH-007 ~ REQ-SEARCH-012
  - PHASE-SEARCH2-4 → REQ-SEARCH-009, REQ-SEARCH-010
  - PHASE-SEARCH2-5 → 전체 REQ 검증
