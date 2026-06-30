# SPEC-ANALYTICS-001 Research: STT 파이프라인 및 감정 분석 통합 지점 심층 분석

> Source: Explore subagent (bg_0f054374) | Date: 2026-06-14
> 모든 file:line reference는 실제 코드 검증 기반

## ⚠️ 가장 중요한 발견 (SPEC 기획에 즉시 영향)

**감정 분석이 이미 부분적으로 구현되어 있습니다.** 이를 모르고 SPEC-ANALYTICS-001을 "새 기능"으로 기획하면 중복 구축/충돌이 발생합니다.

| 구분 | 상태 | 위치 |
|------|------|------|
| **텍스트 기반 감정 분석 (LLM)** | ✅ 이미 구현됨 | `sentiment_analyzer.py`, `sentiment_task.py`, `schemas/sentiment.py`, `analytics/sentiment.py` (8개 API) |
| **텍스트 기반 감성 분석 (Lexicon)** | ✅ 이미 구현됨 | `services/sentiment_service.py` (한국어 사전 기반) |
| **오디오 기반 감정 인식 (SER)** | ❌ 없음 | **이것이 SPEC-ANALYTICS-001의 진정한 새 기능** |
| **발화 톤/운율 분석 (prosody)** | ❌ 없음 | pitch/energy/tempo 분석 미존재 |
| **SPEC-SENTIMENT-001 문서** | ❌ 없음 | 코드는 존재하나 `.moai/specs/SPEC-SENTIMENT-001/` 디렉토리 없음 |

또한 **README의 "Claude 3.5 Sonnet" 언급은 부정확**합니다. 실제 구현은 ZAI `glm-5.2`입니다 (`config.py` L78-84).

---

## 1. STT 세그먼트 데이터 모델 (CRITICAL)

### 1.1 관계형 테이블 부재 — JSON 문서 패턴

**핵심 발견**: Segment, Meeting, Transcription에 대한 **전용 DB 테이블이 존재하지 않습니다.** 모든 결과는 `TaskResult.result_data` (JSON 컬럼)에 직렬화되어 저장됩니다.

`backend/db/models.py`:
- `ActionItem` (L30-56): 액션 아이템
- `TaskResult` (L59-126): 모든 작업 결과(transcription/diarization/minutes/sentiment/summary)의 범용 저장소
  - `task_id: str` unique index (L76-81)
  - `task_type: str` (L84) — "transcription", "diarization", "minutes", "sentiment", "summary"
  - `result_data: dict | None` JSON (L93) — **세그먼트 데이터가 여기에 JSON 배열로 저장됨**
  - `is_guest: bool` (L116-121), `guest_session_id` (L123)
- `AuditLog` (L129-167): HTTP 감사 로그

### 1.2 세그먼트 스키마 계층 (3단계 진화)

**STT 세그먼트** — `backend/schemas/transcription.py` L27-36:
```python
class SegmentResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: int
    start: float       # 시작 시간 (초)
    end: float         # 종료 시간 (초)
    text: str          # 전사 텍스트
    confidence: float  # 0.0~1.0 (avg_logprob에서 변환)
```
→ `speaker_id`, `audio_uri`, `emotion` 필드 **없음**

**Diarization 세그먼트** — `backend/schemas/diarization.py` L14-38:
```python
class DiarizedSegmentResult(BaseModel):
    id: int | None            # 매칭 후 할당 (병렬 모드에선 None)
    start: float
    end: float
    text: str                 # 매칭 전 빈 문자열 가능
    confidence: float
    speaker_id: str | None    # "SPEAKER_00" 등
    speaker_confidence: float # overlap_time / segment_duration
```
→ `audio_uri`, `emotion` 필드 **여전히 없음**

**감정 세그먼트 (이미 존재)** — `backend/schemas/sentiment.py` L9-21:
```python
class SentimentSegment(BaseModel):
    start: float
    end: float
    speaker: str
    text: str
    sentiment: str          # positive/neutral/negative
    emotion: str            # joy/satisfaction/interest/neutral/frustration/anger/sadness/surprise/anxiety/confusion
    confidence: float       # 감정 분석 신뢰도
```

### 1.3 mlx-whisper 출력 → Segment 매핑

**매핑 코드 위치**: `backend/workers/tasks/transcription_task.py`
- 단일 파일: `_extract_segments()` L378-403
- 청크 분할: `_process_chunks()` L351-375 → `merge_segments()` (chunk_manager.py)

매핑 로직 (L387-403):
```python
avg_logprob = seg.get("avg_logprob", None)
confidence = min(1.0, max(0.0, math.exp(avg_logprob))) if avg_logprob is not None else 0.0
results.append(SegmentResult(id=i, start=..., end=..., text=text, confidence=round(confidence, 4)))
```

faster-whisper 백엔드 매핑 (`stt_engine.py` L367-393): `seg.start`, `seg.end`, `seg.text`, `seg.avg_logprob`, `seg.no_speech_prob`, `seg.compression_ratio`를 dict로 변환.

### 1.4 감정 메타데이터를 위해 "빠진" 필드

| 필요 필드 | 현재 상태 | 제안 |
|-----------|-----------|------|
| `emotion` (텍스트 기반) | SentimentSegment에만 존재 | DiarizedSegmentResult에 optional 추가 또는 emotion 세그먼트와 조인 |
| `emotion` (오디오/SER 기반) | 전혀 없음 | 새 필드 `audio_emotion` + `audio_emotion_confidence` |
| `audio_uri` (세그먼트별 오디오) | 전혀 없음 | 새 필드 — 아키텍처 변경 필요 (섹션 3 참조) |
| `prosody_features` (pitch/energy/tempo) | 전혀 없음 | JSON 필드 또는 별도 테이블 |
| `valence` / `arousal` (연속값) | 없음 | SER 모델 출력용 |

---

## 2. STT 파이프라인 실행 경로

### 2.1 전체 데이터 흐름도

```
[클라이언트]
   │ POST /api/v1/transcriptions (multipart)
   ▼
[transcription.py upload_transcription L45-130]
   │ 스트리밍 저장 → temp_dir/{task_id}{suffix}  (1MB 청크, L109-114)
   │ 매직 바이트 검증 (L119-129)
   │ Redis에 pending 상태 저장
   │ ┌─ transcription_celery_task.delay(audio_file_path=업로드파일)
   │ └─ diarization_celery_task.delay(audio_path=temp_dir/{task_id}_dia.wav)  ← 병렬
   ▼
[transcription_task.py L126-349]
   │ 1. 전처리: convert_and_normalize → 16kHz 모노 WAV, -20dBFS (L168)
   │ 2. DIA용 WAV 복사: temp_dir/{task_id}_dia.wav (L171-173)
   │ 3. 청크 분할 (>30분): split_audio (L191-196)
   │ 4. STT 추론: WhisperEngine.transcribe (L205 단일 / L368 청크)
   │ 5. 세그먼트 추출: _extract_segments (L213) / merge_segments (L375)
   │ 6. 저장:
   │    ├ Redis: task:result:{task_id} (L238)
   │    ├ 파일: results_dir/{task_id}.json (L241-242)
   │    └ DB: TaskResult.result_data (L246-253, persist_task_result)
   │ 7. finally 정리: processed WAV, 청크, 원본 업로드 삭제 (L335-348)
   │    DIA wav는 성공 시 보존 (L343 조건)
   ▼
[diarization_task.py L112-450]  ← STT와 병렬 실행
   │ DIA wav 로드 → pyannote 3.1 → SpeakerSegment[] 반환
   │ finally: DIA wav 삭제 (L446-450)
   ▼
[minutes_task.py L112-389]
   │ Redis에서 dia 결과 + stt 결과 조회 → SpeakerMatcher로 매칭
   │ MinutesFormatter.format_minutes → 연속 같은 화자 병합
   │ calculate_speaker_stats → 화자별 통계
   │ 저장: Redis task:min:result:{task_id} + DB
   ▼
[sentiment_task.py L97-247] 또는 [summary_task.py L111-378]
   │ minutes 결과 조회 → ZAI LLM 호출 → 결과 저장
```

### 2.2 STT 태스크 정의

`backend/workers/tasks/transcription_task.py`:
- Celery 데코레이터: L118-125 (`soft_time_limit=3600`, `time_limit=3900`, `max_retries=3`)
- 메인 함수: `transcription_task()` L126-349
- 동시성 제어: `_get_active_job_count()` L90-100, Redis ZSET `active_jobs_ts`
- 상태 업데이트: `_update_task_status()` L40-80, Redis + SSE 이벤트 발행

### 2.3 오디오 처리 위치 및 삭제 시점

| 파일 | 생성 | 삭제 시점 | 코드 위치 |
|------|------|-----------|-----------|
| 원본 업로드 | `temp_dir/{task_id}{suffix}` (transcription.py L106) | STT 완료/실패 후 finally (transcription_task.py L348) | cleanup_temp_file |
| 전처리 WAV | tempfile (convert_and_normalize) | STT finally (L335-336) | temp_files 리스트 |
| DIA용 WAV 복사 | `temp_dir/{task_id}_dia.wav` (L171-173) | DIA 완료/실패 후 finally (diarization_task.py L446-450) | Path.unlink |
| 30분 청크들 | tempfile.mkdtemp (L189-190) | STT finally (L338-339) | shutil.rmtree |

**핵심**: 원본 오디오는 STT 직후 삭제되며, DIA wav도 DIA 직후 삭제됩니다. minutes/sentiment/summary 실행 시점에는 **오디오 파일이 더 이상 존재하지 않습니다.**

---

## 3. 오디오 파일 생명주기 (SER에 CRITICAL)

### 3.1 현재 보존 정책

`backend/app/config.py`:
- `temp_dir: Path = ./storage/temp` (L33)
- `results_dir: Path = ./storage/results` (L34)
- `data_retention_days: int = 30` (L114) — DB 결과
- `temp_file_retention_hours: int = 24` (L117) — 임시 파일

`backend/services/retention.py`:
- `cleanup_expired_results()` L24-45: DB에서 30일 초과 TaskResult 삭제
- `cleanup_temp_files()` L50-98: temp_dir에서 24시간 초과 파일 삭제 (mtime 기준)
- 실행: Celery Beat 매일 03:00 (`cleanup_task.py` L11-37)

### 3.2 세그먼트별 오디오 청크 — 생성된 적 없음

**CHUNK_DURATION=1800 (30분)은 STT 처리용 청크**이지, 세그먼트별 오디오 추출이 아닙니다:
- `config.py` L48: `chunk_duration_minutes: int = 30`
- `transcription_task.py` L191-196: `split_audio(processed_path, chunk_duration_ms=settings.chunk_duration_ms, ...)`
- 이 청크들은 STT 추론 후 즉시 삭제됩니다 (L338-339)

**Diarization이 생성하는 SpeakerSegment는 start/end 타임스탬프만 있고 오디오 슬라이스를 저장하지 않습니다.** `diarization_engine.py`:
- `diarize()` L324-431: torchaudio로 waveform 로드 → pyannote pipeline → 결과는 segment 리스트만 반환
- `finally` L432-435: `waveform = None; compressed = None; result = None; gc.collect()` — 오디오 데이터 명시적 해제

### 3.3 SER를 위한 세그먼트별 오디오 추출이 필요한 위치

**현재 가능한 유일한 지점**: STT 태스크 내부, `{task_id}_dia.wav`가 존재하는 동안
- `transcription_task.py` L171-173 (DIA wav 생성 직후) ~ L349 (finally 삭제 전)
- 또는 `diarization_task.py` L362-410 (diarize 실행 중 waveform이 메모리에 있는 동안)

**추출 방법**: SpeakerSegment의 (start, end)로 waveform 슬라이싱 — `diarization_engine.py`의 `_compress_with_vad` L249-251가 이미 하는 방식 참조:
```python
seg_wav = waveform[:, ts["start"]:ts["end"]]  # 또는 waveform[ts["start"]:ts["end"]]
```

**아키텍처 결정 필요**: SER를 (a) DIA 태스크에 인라인 통합, (b) 별도 Celery 태스크로 DIA 이후 실행(단, DIA wav 보존 연장 필요), 또는 (c) 세그먼트별 오디오를 파일로 추출하여 results_dir에 영구 저장.

---

## 4. Diarization 통합 패턴

### 4.1 pyannote.audio 3.1 통합

`backend/ml/diarization_engine.py`:
- 모델: `pyannote/speaker-diarization-3.1` (L39)
- 로드: `Pipeline.from_pretrained(model_name, token=hf_token)` (L110-113)
- HuggingFace 토큰 필수 (L94-98)
- CPU 전용 실행 (REQ-DIA-009)

### 4.2 VAD 사전 필터 (성능 최적화)

`_compress_with_vad()` L163-280:
- Silero VAD로 음성 구간만 추출, 무음 제거 (회의 무음 30-50% 가속)
- 인접 짧은 음성 구간 병합 (L208-217, `VAD_MERGE_GAP_SEC=0.3`)
- 압축 효과 검증: 15% 미만 절약 시 원본 사용 (L223-231, `VAD_MIN_COMPRESSION_GAIN=0.85`)
- mapping 리스트로 compressed→original timestamp 역매핑 (`_map_segments` L282-322)

### 4.3 speaker_id와 STT 세그먼트 병합

`backend/pipeline/speaker_matcher.py` (SpeakerMatcher 클래스):
- `match(stt_segments, dia_segments)`: 시간 오버랩 기반 매칭
- 각 STT 세그먼트를 가장 많이 겹치는 화자에 할당

`diarization_task.py`:
- 레거시 직렬 모드 (L188-214): STT 결과 조회 → SpeakerMatcher.match() → DiarizedSegmentResult
- 병렬 모드 (L181-186): raw segments만 반환 (`matched=False`), minutes_task가 사후 매칭 (L198-231 in minutes_task.py)

### 4.4 재사용 가능한 세그먼트 경계

**Diarization은 정확한 시간 경계를 보존합니다** (SpeakerSegment.start/end, 소수점 3자리 정밀도). 이는 SER를 위한 오디오 슬라이싱에 직접 사용 가능합니다. 단, **오디오 waveform 자체는 처리 후 해제**되므로 (diarization_engine.py L432-435), waveform을 유지하거나 세그먼트별로 추출하는 로직이 추가로 필요합니다.

청크 분할 모드 `diarize_chunked()` L438-576: 긴 오디오를 10분 청크로 분할, 오버랩 영역 화자 매칭 (`_match_chunk_speakers` L600-658).

---

## 5. Minutes 생성 분석 (기존 통계)

### 5.1 이미 계산되는 통계

`backend/pipeline/minutes_formatter.py`:
- `calculate_speaker_stats()` L84-139: 각 화자별:
  - `total_speaking_time` (초)
  - `segment_count`
  - `speaking_ratio` (%, 전체 대화 시간 대비)
- `format_minutes()` L46-82: 연속 같은 화자 세그먼트 병합 (REQ-MIN-001)
- `to_markdown()` L141-162: `**[HH:MM:SS] Speaker N**: text` 형식

`backend/schemas/minutes.py` (참조): `MinutesSegment`, `SpeakerStats`

### 5.2 데이터 흐름: segments → minutes 통계

```
DiarizedSegmentResult[] (dia 결과)
   │ minutes_task.py L234 또는 L229-231 (SpeakerMatcher)
   ▼
MinutesFormatter.format_minutes(diarized_segments)
   │ → 연속 같은 화자 병합 → MinutesSegment[]
   ▼
MinutesFormatter.calculate_speaker_stats(minutes_segments, total_duration)
   │ → SpeakerStats[] (시간, 횟수, 비율)
   ▼
final_result["speakers"] = [s.model_dump() for s in speaker_stats]  (minutes_task.py L263)
   │ Redis + DB 저장
   ▼
sentiment_task / summary_task가 speakers 필드를 LLM 프롬프트에 사용
```

### 5.3 감정 분석이 기존 통계를 소비하는 방식

`sentiment_analyzer.py` `build_prompt()` L50-96: speaker_stats(비율) + segments(대화)를 프롬프트에 포함. `summary_generator.py` `build_prompt()` L39-123도 동일 패턴.

---

## 6. ML 모델 로딩 패턴

### 6.1 싱글톤 패턴 (두 엔진 공통)

**WhisperEngine** (`stt_engine.py` L65-450):
```python
class WhisperEngine:
    _instance: "WhisperEngine | None" = None
    _lock: Lock = Lock()
    
    @classmethod
    def get_instance(cls) -> "WhisperEngine":  # L88-95, double-checked locking
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def load(self, model_name): ...  # L97-141, lazy load
```

**DiarizationEngine** (`diarization_engine.py` L26-704): 동일한 double-checked locking 패턴 (L63-70).

### 6.2 메모리 예산

| 컴포넌트 | 메모리 | 출처 |
|----------|--------|------|
| STT (mlx-whisper) | ~6GB | README |
| Diarization (pyannote) | ~4GB | README |
| FastAPI + Redis | ~2GB | README |
| **현재 총합** | **~12GB** | M4 Mac mini 24GB |
| **경고 임계값** | 19.2GB (80%) | `stt_engine.py` L27 `MEMORY_WARNING_THRESHOLD_BYTES = 19 * 1024**3`; `config.py` L55 `memory_warning_threshold_mb = 19660` |

**SER 모델 추가 시 가용 예산**: ~7GB (19.2GB 경고선 - 12GB 현재). 경량 SER 모델 선택 필수 (예: Emotion2Vec, wav2vec2 기반, ~1-2GB).

`_check_memory_usage()` (stt_engine.py L425-434): transcribe() 호출 전마다 확인, 초과 시 WARNING 로그.

### 6.3 모델 레지스트리/팩토리 — 부재

**통합된 모델 레지스트리나 팩토리 패턴이 존재하지 않습니다.** 각 엔진(WhisperEngine, DiarizationEngine)이 독립적으로 hand-coded 싱글톤으로 구현되어 있습니다. 새 SER 엔진을 추가하려면:
- `backend/ml/emotion_engine.py` (또는 `ser_engine.py`) 새 싱글톤 클래스 생성 — 기존 패턴 복제
- `backend/app/lifecycle.py`에서 startup warm-up에 추가 (현재 WhisperEngine, DiarizationEngine 사전 로드)
- Celery 워커가 해당 엔진을 import하도록 설정

**권장**: SPEC-ANALYTICS-001에서 `EmotionEngine` 싱글톤을 새로 만들되, 기존 WhisperEngine/DiarizationEngine 패턴을 그대로 따를 것. 별도 추상 기반 클래스나 레지스트리 도입은 SPEC 범위를 벗어남 (별도 리팩토링 SPEC 권장).

---

## 7. LLM 통합 패턴 (Claude가 아닌 ZAI)

### 7.1 README 부정확성 — 실제는 ZAI

**README는 "Claude 3.5 Sonnet"이라 명시하나, 실제 구현은 ZAI `glm-5.2`입니다.**

`backend/app/config.py` L78-84:
```python
anthropic_api_key: str = ""  # ANTHROPIC_API_KEY 환경 변수 (미사용 - 호환성 유지)
zai_api_key: str = ""     # ZAI_API_KEY 환경 변수
summary_model: str = "glm-5.2"  # ZAI 모델명
```

감정 분석 (`sentiment_task.py` L173)과 요약 (`summary_task.py` L234) 모두 `settings.summary_model` (glm-5.2) 사용.

### 7.2 API 호출 패턴

**SummaryGenerator** (`summary_generator.py` L212-265):
```python
client = ZAI(api_key=api_key)  # 동기 클라이언트
response = client.chat.completions.create(
    model=model,
    max_tokens=max_tokens,
    messages=[{"role": "user", "content": prompt}],
    response_format={"type": "json_object"},  # L254 — JSON 강제
)
```

**SentimentAnalyzer** (`sentiment_analyzer.py` L192-233):
```python
client = ZAI(api_key=api_key)
response = client.chat.completions.create(
    model=model,
    max_tokens=max_tokens,
    messages=[{"role": "user", "content": prompt}],
    # response_format 미사용 — 프롬프트 지시 + 수동 JSON 정제에 의존
)
```

### 7.3 프롬프트 구조 및 에러 폴백

**프롬프트 구조** (두 제너레이터 공통):
1. 컨텍스트 섹션: `## 화자 정보`, `## 회의 대화 내용`
2. 지시 섹션: `## 요청 사항` / `## 분석 지시사항`
3. JSON 형식 지시: 명시적 스키마 명세

**폴백 로직**:
- Summary: JSON 파싱 실패 시 정규식으로 summary_text/sections 부분 추출 (L180-210), 실패해도 예외 없이 빈 결과 반환
- Sentiment: 파싱 실패 시 빈 `SentimentResult()` 반환 (L160)
- 빈 choices 방어: `if not response.choices` (sentiment_analyzer.py L218-223)

### 7.4 감정 분석 LLM 재사용 가능성

**기존 SentimentAnalyzer는 텍스트 기반 감정 분석에 최적화**되어 있습니다. SER 결과를 통합하려면:
- **옵션 A**: SentimentAnalyzer 프롬프트에 SER에서 추출한 audio_emotion을 추가 컨텍스트로 주입 → 텍스트+오디오 감정 융합
- **옵션 B**: SER 결과를 별도 필드로 저장, 텍스트 감정과 독립 유지 → 클라이언트/분석에서 조합

`EMOTION_LABELS` (sentiment_analyzer.py L25-36): joy, satisfaction, interest, neutral, frustration, anger, sadness, surprise, anxiety, confusion (10개). SER 모델의 출력 레이블을 이 집합에 매핑해야 일관성 유지.

**별도 존재**: `backend/ml/zai_client.py` — `AsyncZAI` 캐싱 싱글톤 (L14-61). 하지만 analyzer들은 동기 `ZAI`를 직접 사용하므로 사실상 미사용. 비동기 전환 시 활용 가능.

---

## 8. 종합: 갭 및 리스크

### 8.1 아키텍처 갭

| 갭 | 영향 | 심각도 |
|----|------|--------|
| 세그먼트별 오디오 미보존 | SER를 minutes/sentiment 실행 시점에 수행 불가 | **CRITICAL** |
| 관계형 Segment 테이블 부재 | 감정 메타데이터를 세그먼트에 효율적으로 조인하기 어려움 (JSON scan) | HIGH |
| 모델 레지스트리 부재 | SER 엔진 추가 시 보일러플레이트 중복 | MEDIUM |
| README와 코드 불일치 (Claude vs ZAI) | 기획자가 잘못된 전제로 접근 가능 | MEDIUM (문서 수정으로 해결) |

### 8.2 감정 분석 중복 리스크

**SPEC-SENTIMENT-001 코드가 이미 존재하나 문서가 없습니다.** SPEC-ANALYTICS-001 기획 시:
1. 기존 `sentiment_analyzer.py` (LLM 텍스트 감정)을 **대체할 것인지, 보완할 것인지** 결정 필요
2. 기존 `SentimentSegment.emotion` 필드와 새 SER emotion의 관계 정의 필요
3. `analytics/sentiment.py`의 8개 API 엔드포인트가 이미 emotion 데이터를 소비 → 호환성 유지 또는 마이그레이션

### 8.3 오디오 보존 정책 충돌

현재 정책 (`retention.py`, `cleanup_task.py`): 임시 오디오 24시간 후 삭제. SER를 위해서는:
- DIA wav 보존 기간 연장, 또는
- 세그먼트별 오디오 추출 후 results_dir 영구 저장 (디스크 사용량 증가 — 1시간 회의 × N세그먼트 × 16kHz 모노), 또는
- SER를 DIA 태스크에 인라인 통합 (오디오 삭제 전 처리)

프라이버시 정책(README "로컬 전용 처리")과 일관 — 오디오를 외부로 전송하지 않는 한 보존 연장은 정책 위반 아님.

### 8.4 메모리 및 성능 리스크

- M4 Mac mini 24GB, 현재 ~12GB 사용, 경고선 19.2GB → SER 모델 ~7GB 가용
- SER 모델 로드 시 STT/DIA와 동시 로드되면 메모리 압박
- Celery 워커 `concurrency=1` 권장 (README) — SER 태스크가 파이프라인에 병목 추가 가능
- MPS 지원 확인 필수 (일부 SER 모델은 CPU 전용)

---

## 9. 통합 지점 권장사항 (file:line)

### 9.1 SER 엔진 (신규 파일)

**생성**: `backend/ml/ser_engine.py` (또는 `emotion_engine.py`)
- `WhisperEngine` (stt_engine.py L65-450)과 `DiarizationEngine` (diarization_engine.py L26-704)의 싱글톤 패턴 복제
- `_check_memory_usage()` 패턴 채택 (stt_engine.py L425-434)
- `lifecycle.py` startup warm-up에 추가

### 9.2 오디오 세그먼트 추출 (아키텍처 결정 지점)

**권장: DIA 태스크 인라인 통합** (오디오 재로드 비용 회피)
- `backend/workers/tasks/diarization_task.py` L405-410 (`diarize()` 반환 직후, waveform 해제 전)
- diarization_engine.py L432-435 `finally` 블록 전에 waveform에서 세그먼트별 슬라이스 추출
- 또는 `diarize()` 메서드가 waveform도 반환하도록 시그니처 변경

**대안: 별도 SER Celery 태스크** (DIA wav 보존 연장 필요)
- `backend/workers/tasks/sentiment_task.py`와 유사한 새 태스크
- `diarization_task.py` L446-450의 DIA wav 삭제를 SER 태스크 완료 후로 이연

### 9.3 스키마 확장

`backend/schemas/diarization.py` DiarizedSegmentResult (L14-38)에 추가:
```python
audio_emotion: str | None = None        # SER 결과 레이블
audio_emotion_confidence: float | None = None
prosody_features: dict | None = None    # {pitch, energy, tempo, ...}
```

또는 기존 `SentimentSegment` (schemas/sentiment.py L9-21)에 `audio_emotion` 필드 추가하여 텍스트/오디오 감정 융합.

### 9.4 API 라우터

- 신규 생성: `backend/app/api/v1/analytics/emotion.py` (SER 전용 엔드포인트)
- 또는 기존 `backend/app/api/v1/analytics/sentiment.py` L288-404 확장
- `backend/app/api/v1/registry.py` L113 (`sentiment.router`) 근처에 등록

### 9.5 설정 추가

`backend/app/config.py` L60-84 (DIA/요약 설정 블록 근처)에:
```python
# SER 설정
ser_model: str = ""  # 모델명 (빈 값이면 비활성화)
ser_result_ttl: int = 604800
max_concurrent_ser: int = 2
ser_min_segment_duration_sec: float = 0.5  # 이보다 짧은 세그먼트는 SER 스킵
```

### 9.6 DB 마이그레이션 고려사항

현재 TaskResult.result_data (JSON)에 모든 데이터 저장. 감정 메타데이터가 많아지면:
- **옵션 A (최소 변경)**: result_data JSON에 emotion 필드 추가 — 기존 패턴 유지
- **옵션 B (시계열 확장)**: `emotion_timelines` 독립 테이블 생성 (time-series query 최적화)
- 마이그레이션 패턴: `alembic/versions/002_add_device_tokens.py` 참조 (manual `op.create_table`)

---

## 10. Critical Blocker: emotion2vec+ License

`emotion2vec_plus_large`의 license는 "model-license" (비-Apache)로 명시되어 있습니다. 상용 사용 전 Alibaba DAMO에 license 검증이 필요합니다. Fallback으로 `jungjongho/wav2vec2-xlsr-korean-speech-emotion-recognition` (Apache-2.0, 단 정확도 하락 감수) 고려.
