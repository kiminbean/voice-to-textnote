---
id: SPEC-SEARCH-002
version: "1.0.0"
status: completed
created: "2026-06-03"
author: MoAI
priority: medium
completed: "2026-06-14"
---

# SPEC-SEARCH-002: 코드베이스 분석 (Research)

## 1. 기존 구현 분석

### 1.1 FTS5 테이블 스키마 (`backend/db/search_models.py`)

```
search_index (FTS5 가상 테이블)
├── task_id          - 작업 ID (FTS5 인덱싱)
├── task_type        - 작업 유형 (FTS5 인덱싱)
├── content          - 회의록 본문 텍스트 (FTS5 인덱싱)
├── speaker_names    - 화자 이름 (FTS5 인덱싱)
├── summary_text     - 요약 텍스트 (FTS5 인덱싱)
├── action_items_text - 액션아이템/결정/다음단계 병합 (FTS5 인덱싱)
└── created_at       - 생성 시각 (UNINDEXED)
토크나이저: unicode61
```

**발견사항**: `created_at`이 UNINDEXED로 선언되었으나, FTS5 WHERE 절에서 비교 연산자로 필터링 가능함. MATCH 조건과 함께 AND로 결합하면 날짜 범위 필터 구현 가능.

### 1.2 검색 서비스 (`backend/db/search_service.py`)

**현재 구조**:
- `_SEARCH_SQL`: 기본 검색 (MATCH + ORDER BY created_at DESC)
- `_SEARCH_SQL_WITH_TYPE`: task_type 필터 포함
- `_COUNT_SQL` / `_COUNT_SQL_WITH_TYPE`: 카운트 쿼리
- `_build_match_query()`: 사용자 입력 → FTS5 MATCH 쿼리 변환 (토큰 quoting)
- `search()`: 메인 검색 메서드 (비동기)

**변경 필요사항**:
1. 고정 SQL 문자열 2개 → 동적 SQL 빌더로 변경 (필터 조합 대응)
2. SELECT 절에 `rank` 컬럼 추가 (relevance 정렬용)
3. WHERE 절에 날짜 범위, 화자, 액션아이템 조건 동적 추가
4. ORDER BY 절을 파라미터에 따라 동적 생성
5. 기존 `_build_match_query()`는 그대로 재사용 가능

### 1.3 검색 스키마 (`backend/schemas/search.py`)

**현재 구조**:
- `SearchResultItem`: task_id, task_type, snippet, created_at, completed_at
- `SearchResponse`: items, total, page, page_size, query

**변경 필요사항**:
- `SearchResponse`에 `sort: str | None = None` 필드 추가 (적용된 정렬 정보)
- `SuggestionResponse` 신규 스키마: `suggestions: list[str]`

### 1.4 검색 API 라우터 (`backend/app/api/v1/search.py`)

**현재 엔드포인트**:
- `GET /search` - q, task_type, page, page_size 파라미터

**변경 필요사항**:
- 기존 엔드포인트에 파라미터 추가: date_from, date_to, sort, speaker, has_action_items, has_key_decisions
- 신규 엔드포인트: `GET /search/suggestions` - q 파라미터
- SearchService.search() 호출 시 추가 파라미터 전달

### 1.5 Flutter 검색 API 서비스 (`client/lib/services/search_api.dart`)

**현재 메서드**: `search(query, {taskType, page, pageSize})`

**변경 필요사항**:
- search() 파라미터 확장: dateFrom, dateTo, sort, speaker, hasActionItems, hasKeyDecisions
- suggestions() 메서드 신규 추가

### 1.6 Flutter 검색 프로바이더 (`client/lib/providers/search_provider.dart`)

**현재 구조**:
- `SearchQuery`: query, taskType, page (동등성 구현 포함)
- `searchQueryProvider`: StateProvider<String>
- `searchResultProvider`: FutureProvider.family<SearchResponse, SearchQuery>

**변경 필요사항**:
- SearchQuery에 dateRange, sort, speaker, hasActionItems, hasKeyDecisions 필드 추가
- 동등성(equality) 로직에 새 필드 포함
- suggestionsProvider 신규 추가 (FutureProvider.family)
- recentSearchesProvider 신규 추가 (StateNotifierProvider 또는 StateProvider)

### 1.7 Flutter 검색 화면 (`client/lib/screens/search_screen.dart`)

**현재 구조**:
- ConsumerStatefulWidget + TextEditingController + 300ms 디바운스
- AppBar에 TextField + clear 버튼
- 결과: ListView.builder (_SearchResultTile)
- 상태: 빈 쿼리 안내, 로딩, 에러, 결과 없음, 결과 목록

**변경 필요사항**:
- AppBar에 정렬 아이콘 버튼 + 팝업 메뉴 추가
- 본문에 상세 필터 버튼 → 바텀시트
- 검색어 입력 중 자동완성 제안 오버레이
- 포커스 + 빈 입력 시 최근 검색어 목록
- _SearchResultTile 변경 불필요 (기존 구조 유지)

### 1.8 Flutter 검색 결과 모델 (`client/lib/models/search_result.dart`)

**현재 구조**:
- `SearchResultItem`: taskId, taskType, snippet, createdAt, completedAt
- `SearchResponse`: items, total, page, pageSize, query

**변경 필요사항**:
- SearchResponse에 sort 필드 추가
- SuggestionResponse 클래스 신규 추가 (suggestions: List<String>)
- fromJson/toJson 업데이트

---

## 2. 데이터 흐름 분석

### 2.1 인덱싱 데이터 흐름 (기존, 변경 없음)

```
Celery 작업 완료
  → persist_task_result() (sync_service.py)
  → index_search_entry() (search_models.py)
    → _extract_index_data(): 결과 데이터에서 content, speaker_names, summary_text, action_items_text 추출
    → FTS5 DELETE + INSERT (upsert)
```

### 2.2 검색 데이터 흐름 (변경)

```
[기존]
Flutter 검색어 입력
  → SearchQuery(query, taskType, page)
  → searchResultProvider(SearchQuery)
  → SearchApi.search(query, taskType, page)
  → GET /search?q=X&task_type=Y&page=Z
  → SearchService.search(session, query, task_type, page, page_size)
  → FTS5 MATCH 쿼리 (고정 SQL)
  → SearchResponse 반환

[변경 후]
Flutter 검색어 입력
  → SearchQuery(query, taskType, page, dateFrom, dateTo, sort, speaker, hasActionItems, hasKeyDecisions)
  → searchResultProvider(SearchQuery)
  → SearchApi.search(query, taskType, page, dateFrom, dateTo, sort, speaker, hasActionItems, hasKeyDecisions)
  → GET /search?q=X&task_type=Y&page=Z&date_from=A&date_to=B&sort=C&speaker=D&has_action_items=E&has_key_decisions=F
  → SearchService.search(session, query, task_type, page, page_size, date_from, date_to, sort, speaker, has_action_items, has_key_decisions)
  → _build_search_sql() 동적 SQL 생성
  → FTS5 MATCH 쿼리 (동적 WHERE + ORDER BY)
  → SearchResponse 반환 (sort 필드 포함)
```

### 2.3 자동완성 데이터 흐름 (신규)

```
Flutter 검색어 입력 (2자 이상)
  → 300ms 디바운스
  → suggestionsProvider(query)
  → SearchApi.suggestions(query)
  → GET /search/suggestions?q=X
  → SuggestionService.suggestions(session, query)
  → FTS5 MATCH 결과에서 토큰 추출 + 접두사 필터링
  → SuggestionResponse { suggestions: string[] }
```

### 2.4 최근 검색어 데이터 흐름 (신규, 클라이언트 전용)

```
검색 실행 성공
  → RecentSearchService.add(query)
  → SharedPreferences 저장 (JSON 배열)

검색창 포커스 + 빈 입력
  → RecentSearchService.getAll()
  → 최근 검색어 목록 표시
```

---

## 3. 의존성 분석

### 3.1 백엔드 의존성

| 모듈 | 변경 여부 | 영향 범위 |
|------|-----------|-----------|
| search_service.py | 수정 | 핵심 검색 로직. 기존 테스트 회귀 확인 필요 |
| search_models.py | 변경 없음 | FTS5 테이블 스키마 동일 |
| schemas/search.py | 수정 | 스키마 확장. 기존 API 응답에 sort=null 추가 |
| search.py (라우터) | 수정 | 파라미터 확장. 기존 엔드포인트 하위 호환 |
| suggestion_service.py | 신규 | 의존성 없음 (독립 모듈) |

### 3.2 Flutter 의존성

| 모듈 | 변경 여부 | 영향 범위 |
|------|-----------|-----------|
| search_result.dart | 수정 | 모델 확장. 기존 fromJson 하위 호환 |
| search_api.dart | 수정 | API 파라미터 확장. 기존 메서드 시그니처 확장 |
| search_provider.dart | 수정 | SearchQuery 확장. 프로바이더 추가 |
| search_screen.dart | 수정 | UI 확장. 기존 검색 화면 구조 유지 |
| recent_search_service.dart | 신규 | shared_preferences 패키지 의존 |
| search_filter_sheet.dart | 신규 | 의존성 없음 (독립 위젯) |

### 3.3 패키지 의존성

| 패키지 | 용도 | 상태 |
|--------|------|------|
| shared_preferences (Flutter) | 최근 검색어 로컬 저장 | 신규 추가 필요 (pubspec.yaml) |

---

## 4. 기술적 발견사항

### 4.1 FTS5 rank 컬럼 사용법

FTS5는 기본 hidden column으로 `rank`를 제공한다. SELECT와 ORDER BY에 사용 가능:

```sql
SELECT task_id, rank FROM search_index WHERE search_index MATCH :query ORDER BY rank
```

rank 값은 낮을수록 관련성이 높음 (bm25 기반). 기본 정렬 ASC.

### 4.2 동적 SQL 생성 패턴

기존 2개 고정 SQL 패턴을 동적 생성으로 전환:

```python
def _build_search_sql(
    task_type: str | None,
    date_from: str | None,
    date_to: str | None,
    speaker: str | None,
    has_action_items: bool,
    has_key_decisions: bool,
    sort: str | None,
) -> tuple[str, dict]:
    """동적 WHERE + ORDER BY 생성"""
    conditions = ["search_index MATCH :query"]
    params = {}

    if task_type:
        conditions.append("si.task_type = :task_type")
        params["task_type"] = task_type
    if date_from:
        conditions.append("si.created_at >= :date_from")
        params["date_from"] = date_from
    # ... 나머지 조건

    where_clause = " AND ".join(conditions)
    order_by = _get_order_by(sort)

    sql = f"SELECT ... WHERE {where_clause} {order_by} LIMIT :limit OFFSET :offset"
    return sql, params
```

### 4.3 자동완성 토큰 추출 전략

FTS5 MATCH 결과에서 토큰 추출:

```python
async def get_suggestions(session, query: str, limit: int = 10) -> list[str]:
    # 1. MATCH 쿼리로 관련 행 조회
    rows = await session.execute(text(
        "SELECT content, summary_text FROM search_index "
        "WHERE search_index MATCH :query LIMIT 20"
    ), {"query": _build_match_query(query)})

    # 2. 텍스트에서 토큰 추출
    tokens = Counter()
    prefix = query.strip().lower()
    for row in rows:
        text = f"{row.content} {row.summary_text}"
        for token in text.split():
            if token.lower().startswith(prefix) and len(token) >= 2:
                tokens[token] += 1

    # 3. 빈도순 상위 N개 반환
    return [t for t, _ in tokens.most_common(limit)]
```

### 4.4 SharedPreferences 최근 검색어 패턴

```dart
class RecentSearchService {
  static const _key = 'recent_searches';
  static const _maxItems = 20;

  Future<List<String>> getAll() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getStringList(_key) ?? [];
  }

  Future<void> add(String query) async {
    final items = await getAll();
    items.remove(query); // 중복 제거
    items.insert(0, query); // 최상단 추가
    if (items.length > _maxItems) {
      items.removeRange(_maxItems, items.length);
    }
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList(_key, items);
  }
}
```

---

## 5. 기존 테스트 분석

### 5.1 백엔드 테스트

기존 `backend/tests/unit/test_search_index.py` 파일이 존재함 (git status에 untracked로 표시).

새로 작성 필요한 테스트:
- `test_search_filters.py`: 날짜, 정렬, 화자, 상세 필터 단위 테스트
- `test_search_suggestions.py`: 자동완성 제안 로직 테스트

### 5.2 Flutter 테스트

기존 `client/test/services/search_api_test.dart` 파일이 존재함 (git status에 untracked로 표시).

확장 필요한 테스트:
- search_api_test.dart: 확장 파라미터 + suggestions API 테스트
- search_provider_test.dart: 확장 SearchQuery 동등성, 프로바이더 테스트
- recent_search_service_test.dart: 최근 검색어 CRUD 테스트

---

## 추적성 태그

- SPEC: `SPEC-SEARCH-002`
- 분석 대상: SPEC-SEARCH-001 구현 코드
- 분석 파일 수: 8개 (backend 4, flutter 4)
- 발견된 제약사항: 4건 (UNINDEXED 필터링, rank 사용법, 한국어 자동완성, action_items_text 병합)
