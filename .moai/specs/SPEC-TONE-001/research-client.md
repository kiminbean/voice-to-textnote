# SPEC-ANALYTICS-001 Research: API/스키마/Flutter 통합 패턴 분석

> Source: Explore subagent (bg_35d5e88b) | Date: 2026-06-14

# CRITICAL FINDING (Read First)

**SPEC-ANALYTICS-001 is NOT a greenfield feature.** Emotion/sentiment analysis is **~85% implemented across the full stack** under the codename `SPEC-SENTIMENT-001` (referenced in code comments at `backend/schemas/sentiment.py:3`, `backend/pipeline/sentiment_analyzer.py:3`, `backend/workers/tasks/sentiment_task.py:3`).

However, **no SPEC document exists** at `.moai/specs/SPEC-SENTIMENT-001/` or `.moai/specs/SPEC-ANALYTICS-001/`. The README still lists "발화 토 분석, 감정 분석" as Phase 5 planned (`README.md` Phase 5 section). The code shipped without its SPEC doc and without Celery registration.

## Three blocking gaps the new SPEC must resolve

1. **`backend/workers/celery_app.py:14-22`** — `include=[...]` list registers transcription/diarization/minutes/summary/mind_map/cleanup tasks but **OMITS `sentiment_task`**. The task module exists and `sentiment_celery_task.delay()` is called from the API (`analytics/sentiment.py:313`), but Celery workers cannot discover or execute it. This is a 1-line fix.
2. **No SPEC document** at `.moai/specs/SPEC-SENTIMENT-001/spec.md` — the feature has no requirements traceability despite being implemented. This violates the project's EARS SPEC workflow.
3. **Flutter integration is incomplete** — `sentimentProvider` (`result_provider.dart:167`) and `_buildSentimentCard` (`result_screen.dart:714`) exist but:
   - Card is buried inside `_StatisticsTab`, fails silently on error (`SizedBox.shrink()` at line 704)
   - No dedicated tab for emotion analytics
   - `emotional_timeline` data is returned by backend (`sentiment.py:59`) but **never rendered** in Flutter
   - No chart library used — only `LinearProgressIndicator` + `Chip` + `Expanded` flex bars

---

# 1. API Schema Patterns (Pydantic v2)

## 1.1 Schema files inventory (34 total)

Located at `/Users/ibkim/Projects/voice-to-textnote/backend/schemas/`. Emotion-relevant: `sentiment.py`, `statistics.py`, `enhanced_statistics.py`, `minutes.py`, `summary.py`, `transcription.py`.

## 1.2 Response structure conventions

**No envelope wrapper.** All responses are flat Pydantic models. Reference: `backend/schemas/minutes.py:53-65`:

```python
class MinutesResponse(BaseModel):
    """GET /api/v1/minutes/{task_id} 응답"""
    task_id: str = Field(..., description="회의록 작업 ID")
    status: TaskStatus
    diarization_task_id: str = Field(..., description="원본 화자 분리 작업 ID")
    segments: list[MinutesSegment] = Field(default_factory=list, description="...")
    speakers: list[SpeakerStats] = Field(default_factory=list, description="...")
    total_duration: float = Field(..., description="총 대화 시간 (초)")
    markdown: str | None = Field(default=None, description="...")
    error_message: str | None = Field(default=None, description="실패 시 오류 메시지")
```

## 1.3 Backward-compat convention for optional fields

Reference: `backend/schemas/transcription.py:90-96` (SPEC-MOBILE-002 addition):

```python
# SPEC-MOBILE-002: 전사 출처 및 로컬 결과 (오프라인→온라인 재처리 추적용)
transcription_source: TranscriptionSource | None = Field(
    default=None, description="전사 처리 출처 (server/local/hybrid)"
)
local_result: str | None = Field(
    default=None, description="오프라인 로컬 STT 결과 텍스트 (재처리 전 임시)"
)
```

**Pattern rules** (verified across all schemas):
- New optional fields: `Field(default=None, description="...")` with SPEC-ID comment
- New required fields: forbidden in brownfield additions
- `default_factory=list` for collections; `default_factory=dict` for maps
- `model_config = ConfigDict(frozen=True)` for value objects (e.g. `SegmentResult` at `transcription.py:30`)
- `StrEnum` for closed vocabularies (e.g. `TaskStatus` at `transcription.py:13`, `SentimentLabel` at `analytics/sentiment.py:45`)
- `Field(..., ge=0.0, le=1.0)` for ratios/scores (see `sentiment.py:29-31`, `statistics.py:13`)

## 1.4 Existing emotion schema (already production-ready)

`backend/schemas/sentiment.py` (87 lines, full file) defines:

| Class | Lines | Purpose |
|-------|-------|---------|
| `SentimentSegment` | 9-21 | Per-utterance: start, end, speaker, text, sentiment (pos/neu/neg), emotion (10 labels), confidence |
| `SpeakerSentiment` | 24-35 | Per-speaker: total_segments, positive/neutral/negative_ratio, dominant_emotion, emotion_distribution dict |
| `SentimentCreateRequest` | 38-42 | POST body: minutes_task_id, max_tokens |
| `SentimentResult` | 45-62 | Internal pipeline result: overall_sentiment, overall_emotion, segments[], speakers[], emotional_timeline[] |
| `SentimentStatusResponse` | 65-72 | Status: task_id, status, progress, message, error_message |
| `SentimentResponse` | 75-87 | Full result response |

**For SPEC-ANALYTICS-001**: Do NOT redefine these. Extend `SentimentSegment` with optional `tone` field if tone analysis is added (e.g. `tone: str | None = Field(default=None, description="발화 톤 (calm/excited/authoritative/...)")`). The 10 emotion labels are defined as a module constant at `sentiment_analyzer.py:25-36`: joy, satisfaction, interest, neutral, frustration, anger, sadness, surprise, anxiety, confusion.

---

# 2. API Router Structure

## 2.1 Layout

Routers live at `backend/app/api/v1/<domain>/<feature>.py` with domain subdirectories: `transcription/`, `minutes/`, `analytics/`, `audio/`, `auth/`, `collaboration/`, `admin/`. Each router file defines `router = APIRouter(prefix="/<feature>", tags=["<feature>"])`.

## 2.2 Registration SSOT

`backend/app/api/v1/registry.py` (127 lines) is the **single source of truth** for router order and auth policy. Marked `@MX:ANCHOR` at line 4. Format: `ROUTER_REGISTRY: list[tuple[APIRouter, bool]]` where bool = `requires_api_key`.

**Sentiment is already registered** at line 113: `(sentiment.router, True)`. Order matters — `batch` MUST precede `transcription` (line 80-82 comment).

## 2.3 Your proposed endpoint `/api/v1/analytics/{meeting_id}/emotion`

**Already exists differently.** Reference `backend/app/api/v1/analytics/sentiment.py:42`:

```python
router = APIRouter(prefix="/sentiment", tags=["sentiment"])
```

The `analytics/` is a **directory name**, not a URL prefix. Effective URLs are:
- `POST /api/v1/sentiment` (line 288)
- `GET /api/v1/sentiment/{task_id}` (line 357)
- `GET /api/v1/sentiment/{task_id}/status` (line 331)
- `GET /api/v1/sentiment/meeting/{meeting_id}` (line 91) ← **this is what you proposed**
- `GET /api/v1/sentiment/speaker/{speaker_id}` (line 179)
- `GET /api/v1/sentiment/trends?days=30` (line 137)
- `GET /api/v1/sentiment/dashboard/summary?days=30` (line 221)
- `DELETE /api/v1/sentiment/{task_id}` (line 395)

**Recommendation for SPEC-ANALYTICS-001**: Do NOT introduce `/analytics/{meeting_id}/emotion`. Reuse existing `/sentiment/meeting/{meeting_id}` and `/sentiment/{task_id}`. If tone analysis is a new dimension, add `/sentiment/{task_id}/tone` as a sub-resource or extend `SentimentResponse` with optional `tone_analysis` field.

## 2.4 SSE endpoint pattern

`backend/app/api/v1/transcription/stream.py:71-108`:

```python
@router.get("/{task_id}/stream")
async def stream_task_status(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> EventSourceResponse:
    # Check task exists across all prefix patterns
    for prefix in ("task:status:", "task:dia:status:", "task:min:status:",
                   "task:sum:status:", "task:mind:status:"):
        if await redis_client.exists(f"{prefix}{task_id}"):
            task_exists = True
            break
    # ...
    return EventSourceResponse(
        create_sse_event_generator(redis_client, task_id),
        ping=HEARTBEAT_INTERVAL,  # 15 seconds
        media_type="text/event-stream",
    )
```

**GAP for SPEC-ANALYTICS-001**: `task:sentiment:status:` prefix is NOT in the SSE task-existence check loop (`stream.py:87-93`). To enable SSE streaming of sentiment progress, add `"task:sentiment:status:"` to the prefix tuple. The `sentiment_task.py:64` already publishes events via `publish_task_event_sync`.

---

# 3. Database Migration Patterns

## 3.1 Location

- Config: `/Users/ibkim/Projects/voice-to-textnote/alembic.ini`
- Versions: `/Users/ibkim/Projects/voice-to-textnote/alembic/versions/`
- Only **2 migrations exist**: `20260321_001_initial_schema.py` and `002_add_device_tokens.py`
- `file_template = %%(year)d%%(month).2d%%(day).2d_%%(rev)s_%%(slug)s` (alembic.ini:9)

## 3.2 Pattern for emotion analytics: NO migration needed

The sentiment feature uses the **generic `TaskResult` table** (`backend/db/models.py:59-126`):

```python
class TaskResult(Base):
    __tablename__ = "task_results"
    task_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "sentiment"
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    result_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ... timestamps, guest fields
```

Sentiment results persist via `backend/services/sync_service.py::persist_task_result(task_type="sentiment", ...)` — already wired in `sentiment_task.py:202-207`. **The JSON column absorbs any schema evolution without DDL changes.**

## 3.3 Pattern when a migration IS needed

Reference `alembic/versions/002_add_device_tokens.py` (49 lines): manual `op.create_table` with explicit columns, `op.create_index`, symmetric `downgrade()`. No autogenerate observed in repo history.

**Recommendation**: Stay with `TaskResult.result_data` JSON for v1. Only add a dedicated table if querying across meetings (trend analysis at scale) becomes a hot path.

---

# 4. Celery Task Patterns

## 4.1 Registration gap (BLOCKER)

`backend/workers/celery_app.py:14-22`:

```python
include=[
    "backend.workers.tasks.transcription_task",
    "backend.workers.tasks.diarization_task",
    "backend.workers.tasks.minutes_task",
    "backend.workers.tasks.summary_task",
    "backend.workers.tasks.mind_map_task",
    "backend.workers.tasks.cleanup_task",
],
```

**Missing**: `"backend.workers.tasks.sentiment_task"`. Without this, `sentiment_celery_task.delay()` enqueues a message but no worker can execute it — it stays pending indefinitely.

## 4.2 Task chain (where emotion fits)

```
STT (transcription_task)
   ↓
   ├──→ DIA (diarization_task) ──┐
   │                              ↓
   └── (parallel) ────────────→ MIN (minutes_task)
                                  ↓
                   ┌──────────────┼──────────────┐
                   ↓              ↓              ↓
                 SUM           SENTIMENT      MIND_MAP
             (summary_task)  (sentiment_task)  (mind_map_task)
```

**Verified**: `sentiment_task.py:144-150` reads `task:min:result:{minutes_task_id}` from Redis. It depends on MIN completion but runs **independently** of SUM. Currently NOT auto-chained — user must explicitly `POST /api/v1/sentiment` with `minutes_task_id`.

**For SPEC-ANALYTICS-001 decision**: Emotion analysis should fire automatically after MIN completes, parallel to SUM. Options:
- **Option A (recommended, minimal)**: Add Celery chord/callback in `minutes_task.py` that triggers `sentiment_celery_task.delay(...)` after MIN success. Mirror how SUM is triggered.
- **Option B**: Keep manual trigger; just fix the `include=[]` registration gap.

## 4.3 Task status reporting pattern (Redis)

Reference `backend/workers/tasks/summary_task.py:34-73` (identical pattern in `sentiment_task.py:28-64`):

```python
def _update_task_status(task_id, status, progress=0.0, message=None, error_message=None):
    r = _get_redis()
    status_key = f"task:sum:status:{task_id}"  # sentiment uses task:sentiment:status:
    # ... preserve existing created_at
    r.setex(status_key, settings.summary_result_ttl, json.dumps(data))
    # SSE event publication
    event_type = "completed" if status == TaskStatus.completed else ...
    publish_task_event_sync(r, task_id, event_type, data)
```

**Concurrency tracking pattern**: Redis sorted set with timestamp for orphan cleanup (`summary_task.py:88-108`):

```python
def _get_active_sum_count() -> int:
    r = _get_redis()
    now = time.time()
    stale_cutoff = now - 7200  # 2 hours
    pipe = r.pipeline()
    pipe.zremrangebyscore("active_sum_jobs_ts", "-inf", stale_cutoff)  # cleanup orphans
    pipe.zcard("active_sum_jobs_ts")
    return pipe.execute()[1]
```

Sentiment mirrors this with `active_sentiment_jobs_ts` key (`sentiment_task.py:74-81`), `MAX_CONCURRENT_SENTIMENT = 3` hardcoded at line 94 (note: should be moved to `settings` for parity with `settings.max_concurrent_summaries`).

## 4.4 Redis client pattern

`backend/workers/redis_client.py` (28 lines): shared sync connection pool, `get_worker_redis()` returns `redis.Redis` with `decode_responses=True`. Use this in any new worker code — do NOT instantiate `redis.Redis()` directly.

---

# 5. Flutter State Management (Riverpod)

## 5.1 Provider conventions

Reference `client/lib/providers/result_provider.dart`:

```dart
// Family provider keyed by task_id
final sentimentProvider =
    FutureProvider.family<List<SentimentSegment>, String>((ref, taskId) async {
  final api = ref.watch(sentimentApiProvider);
  try {
    return api.getByMeeting(taskId);
  } catch (_) {
    return <SentimentSegment>[];  // silent fallback
  }
});
```

**Pattern rules observed**:
- `Provider<XApi>` for service registration via `dioProvider`
- `FutureProvider.family<ResultType, String>` for async data keyed by task_id
- No code generation (`@riverpod`) — manual `final xxxProvider = FutureProvider.family(...)` style throughout
- `ConsumerStatefulWidget` + `ConsumerState` for stateful widgets (e.g. `_StatisticsTabState` at `result_screen.dart:583`)
- `ConsumerWidget` for stateless (e.g. `_MindMapTab` at line 2000)
- Async handling via `.when(loading:, error:, data:)` (line 602, 702)

## 5.2 Existing sentiment integration in Flutter

**Provider**: `result_provider.dart:167-175` — already wired with `getByMeeting`.

**Rendering**: `result_screen.dart:700-855` — `_buildSentimentCard` already renders:
- Overall sentiment stacked bar (positive/neutral/negative with green/grey/red, `result_screen.dart:764-794`)
- Emotion types as `Chip` widgets with icons (line 810-818)
- Per-speaker sentiment mini-bars (line 821-850)
- Color legend (line 796-804)

**Hook point**: `_StatisticsTab.buildContent` at `result_screen.dart:606-711` calls `ref.watch(sentimentProvider(widget.taskId!))` at line 608, renders card conditionally at line 702-709.

## 5.3 Gaps in Flutter integration

1. **`emotional_timeline` never rendered** — backend returns it (`schemas/sentiment.py:59`, populated in `sentiment_analyzer.py:136-144`) but Flutter `SentimentSegment` model only handles discrete segments. The timeline data shape is `[{time, sentiment, emotion, speaker}]`.
2. **`SpeakerSentiment` summary never rendered** — backend computes `positive_ratio`, `dominant_emotion`, `emotion_distribution` per speaker, but Flutter recomputes from raw segments in `_buildSentimentCard` (line 716-727). The `/sentiment/meeting/{id}` endpoint already returns this precomputed.
3. **Card fails silently** — `error: (_, __) => const SizedBox.shrink()` at line 704 hides failures. No retry, no user feedback.
4. **No dedicated tab** — buried at bottom of Statistics tab. The TabBar at `result_screen.dart:214-220` has 7 tabs (회의 내용, 회의록, AI 요약, 마인드맵, 액션 아이템, Q&A, 통계). Adding "감정 분석" as an 8th tab requires:
   - New `Tab(text: '감정 분석')` entry
   - New `_SentimentTab` ConsumerStatefulWidget (mirror `_StatisticsTab` structure)
   - Move `_buildSentimentCard` logic into the new tab
   - Add timeline visualization

---

# 6. Existing Statistics Visualization (reusable components)

## 6.1 No external chart library

`client/pubspec.yaml` (verified via grep — no `fl_chart`, `charts_flutter`, `syncfusion_flutter_charts`). All visualization uses Material built-ins:

| Pattern | Location | Reusable for emotion? |
|---------|----------|----------------------|
| `LinearProgressIndicator(value: ratio)` | `result_screen.dart:659-662` | Yes — already used for speaking_ratio, applies to positive_ratio |
| Stacked flex bars (`Expanded(flex: pct, child: Container(color:...))`) | `result_screen.dart:768-791` | Yes — already used for sentiment distribution |
| `Chip(avatar: Icon(...), label: Text(...))` | `result_screen.dart:689-693`, `813-817` | Yes — already used for keywords and emotions |
| `Wrap(spacing:, runSpacing:, children:)` | `result_screen.dart:686-694` | Yes — for emotion chips |
| `_legendDot(Color, String)` helper | `result_screen.dart:857-866` | Yes — already used for sentiment legend |
| `EmptyStateWidget` / `ErrorRetryWidget` | widgets directory | Yes — standard empty/error states |

## 6.2 Recommendation for emotion timeline visualization

For the `emotional_timeline` (time series), without adding a chart library:
- **Option A**: Horizontal scrollable Row of colored vertical bars (1 per segment, colored by sentiment)
- **Option B**: Stacked horizontal bar per speaker showing sentiment progression
- **Option C**: If richer charts justified, add `fl_chart: ^0.69.0` to pubspec — `LineChart` for timeline, `PieChart` for distribution

---

# 7. SPEC EARS Structure Reference

## 7.1 SPEC-SUM-001 (AI/ML precedent, Korean EARS)

File: `.moai/specs/SPEC-SUM-001/spec.md` (170 lines). Structure:

```markdown
---
id: SPEC-SUM-001
version: "1.0.0"
status: completed
created: 2026-03-15
updated: 2026-03-15
author: kisoo
priority: P1
issue_number: 0
---

# SPEC-SUM-001: <title>

## HISTORY
| 버전 | 날짜 | 변경 내용 | 작성자 |

## 1. 환경 (Environment) — table: platform, runtime, AI API, model, async, input data
## 2. 가정 (Assumptions) — bullet list
## 3. 요구사항 (Requirements) — grouped by module

### 모듈 1: SummaryGenerator
**[REQ-SUM-001] [유비쿼터스]** SummaryGenerator는 항상 ...
**[REQ-SUM-003] [이벤트 기반]** WHEN Claude API 호출이 실패할 때 THEN ...
**[REQ-SUM-004] [원치 않는 행동]** SummaryGenerator는 ... 오류를 발생시키지 않아야 한다.

## 4. 비기능 요구사항 — table with 목표값/비고
## 5. 기술 제약 조건 — bullet list
## 6. 의존성 — table with 라이브러리/버전/용도 + 신규 의존성 callout
## 7. 연결된 SPEC — table with SPEC ID/관계/설명
## 8. 추적성 (Traceability) — table mapping REQ ID → module → EARS pattern → component
## 9. 구현 노트 — post-completion notes
```

**EARS patterns (Korean)**:
- `[유비쿼터스]` = Ubiquitous (always)
- `[이벤트 기반]` = Event-driven (WHEN...THEN)
- `[원치 않는 행동]` = Unwanted behavior (must NOT)

## 7.2 SPEC-SEARCH-002 (advanced feature precedent, English EARS)

File: `.moai/specs/SPEC-SEARCH-002/spec.md` (206 lines). Differences:
- English EARS: `**WHEN** ... **THEN** 시스템은 ... 해야 한다.`
- Section "3. 수정 대상 파일" with **modifying vs new file tables** — perfect template for SPEC-ANALYTICS-001
- Section "4. 기술 제약" with **하위 호환성** subsection (line 192-196): "기존 GET 호출은 동일하게 동작해야 함, 새 파라미터는 모두 optional"
- Section "5. 추적성 태그"

**Recommendation for SPEC-ANALYTICS-001**: Use SPEC-SEARCH-002's structure (more detailed file-impact tables, explicit backward-compat section) but SPEC-SUM-001's Korean EARS labels for consistency with AI/ML SPECs.

## 7.3 Suggested SPEC-ANALYTICS-001 outline

```markdown
---
id: SPEC-ANALYTICS-001
version: "1.0.0"
status: draft
created: 2026-XX-XX
author: MoAI
priority: P2
issue_number: 0
related_specs: [SPEC-SENTIMENT-001, SPEC-MIN-001, SPEC-SUM-001]
---

# SPEC-ANALYTICS-001: 발화 톤/감정 분석 통합 완료

## 1. 배경
- SPEC-SENTIMENT-001 코드가 구현되었으나 SPEC 문서 누락, Celery 미등록, Flutter timeline 미렌더링
- 본 SPEC은 기존 구현을 문서화하고 3개 갭을 해결

## 2. 범위
### 2.1 Backend (수정)
| 파일 | 변경 |
| backend/workers/celery_app.py | include[]에 sentiment_task 추가 (1줄) |
| backend/app/api/v1/transcription/stream.py | SSE prefix loop에 task:sentiment:status: 추가 |
| backend/workers/tasks/minutes_task.py (optional) | MIN 완료 후 sentiment_task 자동 트리거 |

### 2.2 Flutter (수정)
| 파일 | 변경 |
| client/lib/screens/result_screen.dart | _SentimentTab 신규, _buildSentimentCard 이관, emotional_timeline 렌더링 추가 |
| client/lib/services/sentiment_api.dart | getSpeakerSentiment(), getTimeline() 추가 |

### 2.3 Documentation (신규)
| 파일 | 역할 |
| .moai/specs/SPEC-SENTIMENT-001/spec.md | 기존 구현에 대한 역추적 SPEC 문서 |

## 3. EARS 요구사항
**[REQ-ANA-001] [유비쿼터스]** Celery 워커는 항상 sentiment_task를 발견/실행할 수 있어야 한다.
**[REQ-ANA-002] [이벤트 기반]** WHEN 회의록 생성이 완료되면 THEN 시스템은 감정 분석을 자동 시작해야 한다.
**[REQ-ANA-003] [이벤트 기반]** WHEN 사용자가 통계 탭을 열면 THEN Flutter는 emotional_timeline을 시각화해야 한다.
**[REQ-ANA-004] [원치 않는 행동]** 시스템은 기존 /sentiment/* 응답 스키마를 변경하지 않아야 한다.

## 4. 하위 호환성
- 기존 /api/v1/sentiment/* 엔드포인트 응답 스키마 변경 금지
- SentimentResponse에 새 필드 추가 시 반드시 Field(default=None)
- TaskResult.task_type="sentiment" 영속화 패턴 유지
```
