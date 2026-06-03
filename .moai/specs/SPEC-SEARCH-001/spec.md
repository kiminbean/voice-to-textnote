---
id: SPEC-SEARCH-001
version: "1.0.0"
status: completed
created: "2026-03-22"
updated: "2026-06-03"
author: kisoo
priority: high
issue_number: 0
---

# HISTORY

| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|-----------|
| 1.0.0 | 2026-03-22 | kisoo | 초기 SPEC 작성 |
| 1.0.0 | 2026-06-03 | MoAI | 구현 완료 확인, status → completed |

---

# SPEC-SEARCH-001: 회의록 전문 검색 기능 (MVP)

## 1. 개요

### 1.1 현재 상태

Voice to TextNote 앱은 현재 20개 SPEC이 완료된 상태로, 전체 파이프라인(녹음 -> STT -> 화자분리 -> 회의록 -> AI 요약)이 동작한다. 사용자는 홈 화면에서 회의 목록을 볼 수 있지만, 특정 키워드로 과거 회의를 검색하는 기능이 없다. 데이터는 Redis(24h TTL) + SQLite/PostgreSQL(`task_results` 단일 테이블, `result_data` JSON 컬럼)에 저장된다.

### 1.2 범위 (MVP)

- Backend: SQLite FTS5 기반 전문 검색 인덱스 + 검색 API 엔드포인트
- Backend: Celery 작업 완료 시 자동 인덱싱 (기존 `persist_task_result()` 흐름에 훅)
- Flutter: 홈 화면 검색 바 + 검색 결과 화면 (스니펫 표시)
- 검색 대상: 요약 텍스트, 회의록 본문, 화자 이름, 액션 아이템, 핵심 결정사항

### 1.3 범위 외 (Phase 2)

- PostgreSQL `tsvector` 마이그레이션
- Elasticsearch 통합
- 실시간 검색 자동완성 (search-as-you-type)
- 고급 한국어 형태소 분석 (MeCab, `textsearch_ko`)
- 검색 분석/히스토리 기록
- 날짜 범위 필터링 (MVP에서는 제외, Phase 2에서 추가)

---

## 2. EARS 요구사항

### REQ-SEARCH-001: 검색 API 엔드포인트

**WHEN** 사용자가 `GET /api/v1/search?q={keyword}` 요청을 보내면 **THEN** 시스템은 FTS5 인덱스에서 키워드와 매칭되는 completed 상태의 작업 결과를 검색하여 스니펫과 함께 페이지네이션된 JSON 응답을 반환해야 한다.

- 엔드포인트: `GET /api/v1/search`
- 필수 파라미터: `q` (검색 쿼리, 최소 2자)
- 선택 파라미터: `task_type` (all | summary | minutes), `page` (기본 1), `page_size` (기본 20, 최대 50)
- 응답 형식: `{ items: SearchResultItem[], total: int, page: int, page_size: int, query: str }`
- `SearchResultItem`: `{ task_id, task_type, snippet, created_at, completed_at }`
- 응답 시간 목표: < 200ms (100건 이하 데이터 기준)

### REQ-SEARCH-002: FTS5 인덱스 테이블 및 자동 인덱싱

시스템은 **항상** SQLite FTS5 가상 테이블(`search_index`)을 유지하고, Celery 작업 완료 시 자동으로 검색 인덱스를 업데이트해야 한다.

- FTS5 테이블 스키마: `task_id`, `task_type`, `content` (본문 텍스트), `speaker_names`, `summary_text`, `action_items_text`, `created_at` (UNINDEXED)
- 토크나이저: `unicode61` (한국어 공백/구두점 기반 분리)
- 인덱싱 시점: `persist_task_result()` 호출 직후, best-effort (실패 시 로그만 기록)
- minutes 작업: `segments[].text` 결합 -> `content`, `segments[].speaker_name` 추출 -> `speaker_names`
- summary 작업: `summary_text` -> `summary_text`, `action_items[].task` + `key_decisions[]` + `next_steps[]` 결합 -> `action_items_text`
- transcription/diarization 작업: 인덱싱 대상 아님 (minutes/summary에 통합됨)

### REQ-SEARCH-003: 검색 결과 페이지네이션

**WHEN** 검색 결과가 `page_size`를 초과하면 **THEN** 시스템은 기존 History API와 동일한 1-based 페이지네이션 패턴(`page`, `page_size`, `total`)으로 결과를 분할하여 반환해야 한다.

- 기존 `HistoryListResponse` 패턴 준수: `{ items, total, page, page_size }`에 `query` 필드 추가
- `page` 기본값: 1, `page_size` 기본값: 20, 최대: 50
- `total`: 전체 매칭 결과 수
- 정렬: `created_at DESC` (최신 우선)

### REQ-SEARCH-004: 검색 타입 필터

**WHEN** 사용자가 `task_type` 파라미터를 지정하면 **THEN** 시스템은 해당 작업 유형의 결과만 필터링하여 반환해야 한다.

- `task_type=all` (기본값): minutes + summary 결과 모두 포함
- `task_type=summary`: 요약 결과만
- `task_type=minutes`: 회의록 결과만
- 유효하지 않은 `task_type` 값: 422 Validation Error 반환

### REQ-SEARCH-005: Flutter 검색 UI

**WHEN** 사용자가 홈 화면에서 검색 아이콘을 탭하면 **THEN** 시스템은 검색 바를 표시하고, 키워드 입력 후 서버 검색 결과를 스니펫과 함께 리스트로 표시해야 한다.

- 홈 화면 AppBar에 검색 아이콘 추가
- `SearchDelegate` 또는 커스텀 검색 바 위젯
- 디바운스 처리: 300ms (타이핑 중 불필요한 API 호출 방지)
- 검색 결과 화면: `SearchResultItem` 리스트 (작업 유형 아이콘 + 스니펫 + 날짜)
- 결과 탭 시 해당 회의 상세 화면으로 이동
- 빈 상태: "검색 결과가 없습니다" 메시지
- 로딩 상태: Shimmer 또는 CircularProgressIndicator
- 에러 상태: 재시도 버튼 포함 에러 메시지
- Riverpod `FutureProvider.family<SearchResponse, SearchQuery>` 패턴

### REQ-SEARCH-006: 검색 결과 하이라이트 (스니펫)

**WHEN** 검색 결과를 반환할 때 **THEN** 시스템은 FTS5 `snippet()` 함수를 사용하여 매칭된 텍스트 주변 100~200자의 미리보기를 생성해야 한다.

- Backend: FTS5 `snippet(search_index, -1, '<b>', '</b>', '...', 30)` 활용
- 스니펫 길이: 약 100~200자 (전후 문맥 포함)
- 매칭 키워드 마킹: `<b>` 태그로 감싸서 반환
- Flutter: 스니펫 내 `<b>` 태그를 `TextSpan` + `FontWeight.bold`로 렌더링

---

## 3. 수정 대상 파일

### Backend (신규)

| 파일 | 역할 |
|------|------|
| `backend/db/search_models.py` | FTS5 가상 테이블 정의 및 인덱싱 함수 |
| `backend/db/search_service.py` | 검색 쿼리 실행 서비스 (FTS5 MATCH + snippet) |
| `backend/schemas/search.py` | 검색 요청/응답 Pydantic 스키마 |
| `backend/app/api/v1/search.py` | 검색 API 라우터 (`GET /api/v1/search`) |

### Backend (수정)

| 파일 | 변경 내용 |
|------|-----------|
| `backend/db/sync_service.py` | `persist_task_result()` 후 `index_search_entry()` 호출 추가 |
| `backend/app/api/v1/__init__.py` | search 라우터 등록 |

### Flutter (신규)

| 파일 | 역할 |
|------|------|
| `client/lib/services/search_api.dart` | 검색 API 서비스 (Dio 기반) |
| `client/lib/providers/search_provider.dart` | 검색 상태 관리 (Riverpod) |
| `client/lib/screens/search_screen.dart` | 검색 결과 화면 |

### Flutter (수정)

| 파일 | 변경 내용 |
|------|-----------|
| `client/lib/screens/home_screen.dart` | AppBar에 검색 아이콘 추가 |
| `client/lib/widgets/meeting_card.dart` | 스니펫 표시 옵션 추가 (선택적) |

---

## 4. 기술 제약

### 4.1 한국어 검색 한계

- SQLite FTS5 `unicode61` 토크나이저는 공백/구두점 기반으로 한국어 조사를 분리하지 못함
- 예: "보고서를" 검색 시 "보고서" 매칭 실패 가능
- MVP 완화 방안: 클라이언트에서 LIKE 보조 검색, 사용자에게 핵심 키워드 사용 안내
- 장기 해결: Phase 2에서 PostgreSQL `pg_bigm` 또는 `textsearch_ko` 활용

### 4.2 데이터 정합성

- DB 저장이 best-effort이므로 일부 작업 결과가 DB에 없을 수 있음 (Redis에만 존재)
- 검색 인덱싱도 best-effort (인덱싱 실패 시 로그만 기록, 작업 완료에 영향 없음)
- 리인덱싱 스크립트는 Phase 2에서 제공

### 4.3 미팅 단위 vs 작업 단위

- 현재 DB는 작업(task) 단위이지만 사용자는 미팅 단위로 인식
- 검색 결과는 작업 단위로 반환 (task_id 기준)
- Flutter에서 Meeting 모델의 taskId 매핑을 통해 미팅 상세 화면으로 연결

### 4.4 성능

- MVP 규모(수십~수백 건)에서 FTS5로 충분
- 1000건 이상 시 인덱스 최적화 또는 PostgreSQL 전환 검토
- 검색 API 응답 목표: < 200ms

---

## 5. 추적성 태그

- SPEC: `SPEC-SEARCH-001`
- 요구사항: `REQ-SEARCH-001` ~ `REQ-SEARCH-006`
- 수락 기준: `AC-SEARCH-001` ~ `AC-SEARCH-007` (acceptance.md 참조)
- 구현 계획: `PHASE-1` ~ `PHASE-6` (plan.md 참조)
