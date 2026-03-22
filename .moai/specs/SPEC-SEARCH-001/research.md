# SPEC-SEARCH-001: 회의록 검색 기능 리서치

## 1. 현재 데이터 저장 아키텍처 분석

### 1.1 이중 저장 구조 (Redis + SQLite/PostgreSQL)

프로젝트는 **Redis-primary, DB-secondary** 아키텍처를 사용한다.

**Redis (1차 저장소)**:
- 모든 작업 결과가 Redis에 먼저 저장됨 (24h TTL)
- 작업 상태 추적도 Redis가 담당
- DB 저장은 best-effort (실패해도 무시)

**SQLite/PostgreSQL (2차 저장소)**:
- `task_results` 테이블 단일 테이블에 모든 작업 유형 저장
- `result_data` JSON 컬럼에 전체 결과를 비정규화하여 저장
- Redis 캐시 미스 시 폴백 용도

### 1.2 DB 스키마 (TaskResult 모델)

파일: `backend/db/models.py` (L29-94)

```
task_results 테이블:
- id: UUID (PK)
- task_id: str (유니크 인덱스) -- Celery 작업 ID
- task_type: str -- "transcription" | "diarization" | "minutes" | "summary"
- status: str -- "pending" | "processing" | "completed" | "failed"
- input_metadata: JSON (nullable) -- 입력 메타데이터
- result_data: JSON (nullable) -- 전체 결과 데이터
- error_message: Text (nullable)
- created_at: DateTime
- updated_at: DateTime
- completed_at: DateTime (nullable)
```

핵심 관찰: **별도 meetings/summaries/transcriptions 테이블이 없다.** 단일 `task_results` 테이블에 모든 유형이 JSON으로 저장된다.

### 1.3 Redis 키 패턴

| 작업 유형 | 상태 키 | 결과 키 | TTL |
|-----------|---------|---------|-----|
| Transcription (STT) | `task:stt:status:{task_id}` | `task:stt:result:{task_id}` | 24h |
| Diarization | `task:dia:status:{task_id}` | `task:dia:result:{task_id}` | 24h |
| Minutes | `task:min:status:{task_id}` | `task:min:result:{task_id}` | 24h |
| Summary | `task:sum:status:{task_id}` | `task:sum:result:{task_id}` | 24h |
| Template | `template:{template_id}` | -- | 영구 |

소스:
- `backend/workers/tasks/summary_task.py` (L47, L81)
- `backend/workers/tasks/minutes_task.py` (L47, L81)
- `backend/workers/tasks/transcription_task.py` (L42-49)
- `backend/workers/tasks/diarization_task.py` (L38-47)

### 1.4 result_data JSON 구조 (검색 대상 데이터)

**Minutes result_data** (`minutes_task.py` L190-201):
```json
{
  "task_id": "uuid",
  "diarization_task_id": "uuid",
  "status": "completed",
  "segments": [
    {"speaker_id": "SPEAKER_00", "speaker_name": "김팀장", "text": "발화 내용", "start": 0.0, "end": 5.0}
  ],
  "speakers": [
    {"speaker_id": "SPEAKER_00", "speaker_name": "김팀장", "total_speaking_time": 120.0, "segment_count": 15, "speaking_ratio": 45.2}
  ],
  "total_duration": 300.0,
  "total_speakers": 2,
  "markdown": "# 회의록\n...",
  "created_at": "2026-03-22T...",
  "completed_at": "2026-03-22T..."
}
```

**Summary result_data** (`summary_task.py` L226-237):
```json
{
  "task_id": "uuid",
  "minutes_task_id": "uuid",
  "status": "completed",
  "summary_text": "회의 전체 요약 텍스트...",
  "action_items": [
    {"assignee": "김팀장", "task": "보고서 작성", "deadline": "2026-03-25", "priority": "high"}
  ],
  "key_decisions": ["결정 1", "결정 2"],
  "next_steps": ["다음 단계 1"],
  "generation_time_seconds": 12.5,
  "created_at": "2026-03-22T...",
  "completed_at": "2026-03-22T..."
}
```

### 1.5 검색 가능한 데이터 필드 요약

| 필드 | 위치 | 검색 유형 | 중요도 |
|------|------|-----------|--------|
| segments[].text | minutes result_data | 전문 검색 (Full-text) | 최상 |
| segments[].speaker_name | minutes result_data | 정확 매칭/포함 | 높음 |
| summary_text | summary result_data | 전문 검색 | 높음 |
| action_items[].task | summary result_data | 전문 검색 | 중간 |
| action_items[].assignee | summary result_data | 정확 매칭 | 중간 |
| key_decisions[] | summary result_data | 전문 검색 | 중간 |
| next_steps[] | summary result_data | 전문 검색 | 낮음 |
| task_type | task_results 컬럼 | 정확 매칭 필터 | 필터 |
| status | task_results 컬럼 | 정확 매칭 필터 | 필터 |
| created_at | task_results 컬럼 | 범위 필터 | 필터 |

---

## 2. 기존 API 패턴 분석

### 2.1 History API (검색 API의 베이스 패턴)

파일: `backend/app/api/v1/history.py` (L23-68)

```python
@router.get("/history", response_model=HistoryListResponse)
async def list_history(
    task_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
) -> HistoryListResponse:
```

패턴:
- Query 파라미터 기반 필터링
- 1-based 페이지네이션 (`page`, `page_size`)
- `HistoryListResponse` = `{items, total, page, page_size}`
- `ResultService`를 통한 DB 접근 (의존성 주입)

### 2.2 History 응답 스키마

파일: `backend/schemas/history.py` (L14-58)

```python
class HistoryItem(BaseModel):
    task_id: str
    task_type: str
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None

class HistoryListResponse(BaseModel):
    items: list[HistoryItem]
    total: int
    page: int
    page_size: int
```

관찰: `HistoryItem`에는 `result_data`가 포함되지 않음 (목록 응답 크기 최소화). 검색 결과에는 스니펫(매칭된 텍스트 미리보기)이 필요할 수 있음.

### 2.3 ResultService 패턴

파일: `backend/db/service.py` (L104-135)

```python
async def list_results(self, session, task_type=None, status=None, limit=50, offset=0):
    stmt = select(TaskResult).order_by(TaskResult.created_at.desc())
    if task_type: stmt = stmt.where(TaskResult.task_type == task_type)
    if status: stmt = stmt.where(TaskResult.status == status)
    stmt = stmt.limit(limit).offset(offset)
```

패턴: SQLAlchemy select() + 조건부 where() 체이닝 + limit/offset

---

## 3. Flutter 클라이언트 분석

### 3.1 현재 미팅 목록 구조

**Meeting 모델** (`client/lib/models/meeting.dart`):
- `id`, `title`, `createdAt`, `status`, `duration`
- `transcriptionTaskId`, `diarizationTaskId`, `minutesTaskId`, `summaryTaskId`
- 미팅 → 4개 작업 ID로 파이프라인 연결
- **title 필드가 존재** (검색 대상)

**MeetingListNotifier** (`client/lib/providers/meeting_list_provider.dart`):
- 인메모리 `List<Meeting>` 상태
- `addMeeting()`, `updateMeeting()`, `removeMeeting()`
- **서버 목록 조회 API 호출 없음** (로컬 상태만 관리)

**HomeScreen** (`client/lib/screens/home_screen.dart`):
- `meetingListProvider`를 watch하여 `ListView.builder`로 표시
- `MeetingCard` 위젯으로 각 미팅 표시
- 현재 검색 UI 없음

### 3.2 API 클라이언트 패턴

파일: `client/lib/services/api_client.dart`

- Dio 기반, `AppConfig.apiBaseUrl` = `http://100.110.255.105:8000/api/v1`
- Provider 패턴으로 주입 (`dioProvider`)
- 각 도메인별 API 서비스 분리 (`MinutesApi`, `SummaryApi`, `TranscriptionApi` 등)

### 3.3 상태 관리 패턴

- Riverpod `Notifier` (동기 상태) + `FutureProvider.family` (비동기 데이터 로딩)
- Provider 이름 규칙: `{도메인}{기능}Provider` (예: `minutesResultProvider`, `summaryResultProvider`)

### 3.4 검색 UI 구현 시 고려사항

- HomeScreen AppBar에 검색 아이콘 추가 또는 `SearchBar` 위젯 삽입
- 검색 결과는 기존 `MeetingCard` 위젯 재사용 가능 (스니펫 추가 필요)
- Riverpod `FutureProvider.family<SearchResults, String>` 패턴으로 검색 쿼리 바인딩
- 디바운스 처리 필요 (300ms 권장)

---

## 4. 검색 기술 옵션 분석

### 4.1 옵션 A: SQLite JSON 쿼리 (현재 DB 그대로)

```sql
SELECT * FROM task_results
WHERE task_type IN ('minutes', 'summary')
  AND status = 'completed'
  AND (
    json_extract(result_data, '$.summary_text') LIKE '%검색어%'
    OR result_data LIKE '%검색어%'
  )
ORDER BY created_at DESC
LIMIT 20 OFFSET 0;
```

**장점**: 추가 설정 불필요, 즉시 사용 가능
**단점**: LIKE 검색은 인덱스 불가, 한국어 형태소 분석 없음, JSON 내부 검색 느림, 대규모 데이터 성능 문제

### 4.2 옵션 B: SQLite FTS5 (Full-Text Search)

SQLite 내장 전문 검색 모듈. 별도 FTS 테이블 생성:

```sql
CREATE VIRTUAL TABLE search_index USING fts5(
    task_id,
    task_type,
    content,
    speaker_names,
    summary_text,
    action_items_text,
    created_at UNINDEXED
);
```

**장점**: SQLite 내장, 추가 의존성 없음, 토큰 기반 검색, 스니펫 지원
**단점**: 한국어 토크나이저 기본 미지원 (unicode61 토크나이저 사용 시 단어 단위 분리 가능), 동기화 로직 필요

### 4.3 옵션 C: PostgreSQL tsvector (프로덕션 DB)

```sql
ALTER TABLE task_results ADD COLUMN search_vector tsvector;
CREATE INDEX idx_search_vector ON task_results USING GIN(search_vector);
```

**장점**: PostgreSQL 내장, GIN 인덱스로 빠른 검색, 가중치 부여 가능
**단점**: PostgreSQL 필수 (현재 개발 환경은 SQLite), 한국어 딕셔너리 별도 설정 필요

### 4.4 옵션 D: 앱 사이드 로컬 검색 (MVP 최적)

클라이언트에서 로컬 미팅 목록의 title + 캐시된 결과 내에서 검색:

**장점**: 서버 변경 최소화, 오프라인 지원, 즉시 응답
**단점**: 미팅 목록이 인메모리에만 존재 (앱 재시작 시 사라짐), 전문 검색 불가

### 4.5 MVP 권장 옵션: B (SQLite FTS5) + D (클라이언트 로컬 필터)

**이유**:
1. 현재 DB가 SQLite이므로 FTS5가 자연스러움
2. 추가 인프라 불필요
3. 한국어는 `unicode61` 또는 `trigram` 토크나이저로 기본 분리 가능
4. 클라이언트에서 title 기반 즉시 필터링 + 서버에서 본문 검색

---

## 5. 검색 데이터 흐름 설계

### 5.1 인덱싱 파이프라인

```
[Celery Task 완료]
    │
    ├─ Redis에 결과 캐싱 (기존)
    ├─ task_results DB 저장 (기존, best-effort)
    └─ search_index FTS 테이블 업데이트 (신규)
        ├─ minutes: segments[].text 결합, speaker_names 추출
        └─ summary: summary_text, action_items, key_decisions, next_steps 결합
```

인덱싱 시점: `persist_task_result()` 호출 직후 (동기, best-effort)

### 5.2 검색 API 흐름

```
[Flutter 클라이언트]
    │
    ├─ 1) 로컬 필터: meeting.title CONTAINS query (즉시, 디바운스 300ms)
    │
    └─ 2) 서버 검색: GET /api/v1/search?q={query}&task_type={type}&page=1&page_size=20
            │
            ├─ FTS5 MATCH 쿼리 실행
            ├─ snippet() 함수로 매칭 텍스트 하이라이트
            └─ 결과 반환: {items, total, page, page_size, query}
```

### 5.3 제안 API 엔드포인트

```
GET /api/v1/search
  - q: str (필수, 검색 쿼리, 최소 2자)
  - task_type: str | None (minutes, summary 필터)
  - date_from: date | None (시작 날짜 필터)
  - date_to: date | None (종료 날짜 필터)
  - page: int = 1
  - page_size: int = 20 (max 50)
```

### 5.4 제안 응답 스키마

```python
class SearchResultItem(BaseModel):
    task_id: str
    task_type: str  # "minutes" | "summary"
    snippet: str  # 매칭 텍스트 미리보기 (100~200자)
    created_at: datetime
    completed_at: datetime | None

class SearchResponse(BaseModel):
    items: list[SearchResultItem]
    total: int
    page: int
    page_size: int
    query: str
```

---

## 6. 리스크 및 제약사항

### 6.1 한국어 검색 품질

- SQLite FTS5의 기본 토크나이저는 공백/구두점 기반 분리
- 한국어 조사 ("을/를/이/가") 분리 불가 → "보고서를" 검색 시 "보고서" 매칭 실패
- 완화 방안: `unicode61` 토크나이저 + 클라이언트에서 LIKE 보조 검색
- 장기 해결: PostgreSQL 전환 시 `pg_bigm` 또는 `textsearch_ko` 확장 활용

### 6.2 데이터 정합성

- Redis TTL 24h 이후 데이터는 DB에만 존재
- DB 저장이 best-effort이므로 일부 결과가 DB에 없을 수 있음
- 완화 방안: 검색 인덱스 구축 시 Redis + DB 양쪽 확인, 리인덱싱 API 제공

### 6.3 단일 테이블 구조의 한계

- `task_results`는 단일 테이블에 4개 작업 유형이 혼재
- `result_data` JSON 내부에 실제 검색 대상이 있어 직접 인덱싱 불가
- FTS5 별도 테이블로 비정규화하여 해결

### 6.4 미팅 단위 검색 vs 작업 단위 검색

- 현재 DB는 "작업(task)" 단위이지만, 사용자는 "미팅" 단위로 인식
- 하나의 미팅 = 1 STT + 1 DIA + 1 MIN + 1 SUM (4개 작업)
- 검색 결과를 미팅 단위로 그룹핑하려면 작업 간 연결 정보 필요
- 현재 연결 정보: minutes.diarization_task_id, summary.minutes_task_id (Redis result_data 내부)
- **Flutter Meeting 모델에 4개 taskId가 모두 있음** → 클라이언트에서 그룹핑 가능

### 6.5 성능 고려

- MVP 규모 (수십~수백 건): FTS5로 충분
- 1000건 이상 시: FTS5 인덱스 최적화 또는 PostgreSQL 전환 검토
- 검색 API 응답 목표: < 200ms

---

## 7. 구현 범위 제안 (MVP)

### Phase 1: 백엔드 검색 인프라
1. FTS5 search_index 테이블 생성 (마이그레이션)
2. 인덱싱 함수 구현 (`index_search_entry()`)
3. `persist_task_result()` 후 인덱싱 호출
4. `SearchService` 구현 (FTS5 MATCH + snippet)
5. `GET /api/v1/search` 엔드포인트 구현

### Phase 2: Flutter 검색 UI
1. HomeScreen에 검색바 추가 (SearchDelegate 또는 커스텀)
2. `SearchApi` 서비스 생성
3. `searchResultProvider` (FutureProvider.family) 생성
4. 검색 결과 화면 (스니펫 + 미팅 카드 재사용)
5. 디바운스 처리

### Phase 3: 검색 품질 개선 (Post-MVP)
1. 기존 데이터 리인덱싱 스크립트
2. 한국어 토크나이저 개선
3. PostgreSQL tsvector 마이그레이션
4. 검색 하이라이트 UI 개선

---

## 8. 파일 변경 영향 범위

### 백엔드 (신규)
- `backend/db/search_models.py` -- FTS5 테이블 정의
- `backend/db/search_service.py` -- 검색 CRUD 서비스
- `backend/schemas/search.py` -- 검색 요청/응답 스키마
- `backend/app/api/v1/search.py` -- 검색 API 라우터

### 백엔드 (수정)
- `backend/db/sync_service.py` -- persist_task_result() 후 인덱싱 호출 추가
- `backend/app/api/v1/__init__.py` -- search 라우터 등록

### Flutter (신규)
- `client/lib/services/search_api.dart` -- 검색 API 서비스
- `client/lib/providers/search_provider.dart` -- 검색 상태 관리
- `client/lib/screens/search_screen.dart` -- 검색 결과 화면 (또는 HomeScreen 통합)

### Flutter (수정)
- `client/lib/screens/home_screen.dart` -- 검색 버튼/바 추가
- `client/lib/widgets/meeting_card.dart` -- 스니펫 표시 옵션 추가 (선택)

---

## 부록: 참조 파일 목록

| 파일 | 역할 | 핵심 라인 |
|------|------|----------|
| `backend/db/models.py` | TaskResult ORM 모델 | L29-94 |
| `backend/db/service.py` | ResultService CRUD | L104-135 (list_results) |
| `backend/db/sync_service.py` | Celery용 동기 저장 | L18-74 (persist_task_result) |
| `backend/db/engine.py` | SQLite/PG 엔진 설정 | L17 (SQLite 기본) |
| `backend/app/api/v1/history.py` | History API 패턴 | L23-68 |
| `backend/schemas/history.py` | 페이지네이션 응답 스키마 | L44-58 |
| `backend/workers/tasks/minutes_task.py` | 회의록 result_data 구조 | L190-201 |
| `backend/workers/tasks/summary_task.py` | 요약 result_data 구조 | L226-237 |
| `backend/app/config.py` | DB URL, Redis 설정 | L73 (database_url) |
| `client/lib/models/meeting.dart` | Meeting 데이터 모델 | L10-34 |
| `client/lib/providers/meeting_list_provider.dart` | 인메모리 미팅 목록 | L6-26 |
| `client/lib/screens/home_screen.dart` | 홈 화면 UI | L11-98 |
| `client/lib/services/api_client.dart` | Dio 설정 | L7-32 |
| `client/lib/config/app_config.dart` | API URL 설정 | L4 |
