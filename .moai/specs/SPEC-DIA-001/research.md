# SPEC-DIA-001 Research: pyannote.audio 3.1 화자 분리 통합

작성일: 2026-03-15
작성자: kisoo (MoAI Explore Agent)

---

## 1. 기존 STT 파이프라인 아키텍처 분석

### 1.1 전체 파이프라인 흐름

```
Upload → Validation → AudioProcessor.convert_and_normalize() → ChunkManager.split_into_chunks()
       → transcription_task(Celery) → WhisperEngine.transcribe() → merge_segments()
       → Redis 캐시(24h TTL) + JSON 파일 저장
```

### 1.2 핵심 데이터 구조 (backend/schemas/transcription.py)

**SegmentResult** - STT 출력 세그먼트:
```python
class SegmentResult(BaseModel):
    id: int
    start: float      # 초 단위
    end: float        # 초 단위
    text: str         # 인식 텍스트
    confidence: float # exp(avg_logprob) 기반 0.0-1.0
```

**TranscriptionResponse** - 최종 API 응답:
```python
class TranscriptionResponse(BaseModel):
    task_id: str
    status: TaskStatus
    language: str
    duration: float
    segments: list[SegmentResult]
    metadata: dict
```

### 1.3 Redis 키 패턴

- `task:status:{task_id}` — TaskStatus enum + progress (0.0-1.0) + message
- `task:result:{task_id}` — TranscriptionResponse JSON, TTL: 24h
- `active_jobs` — 활성 작업 ID 집합
- `active_job_count` — 동시 작업 수 카운터

### 1.4 Celery Task 패턴 (backend/workers/tasks/transcription_task.py)

- `@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)`
- 동시 작업 제한: `max_concurrent_jobs=3` (설정 가능)
- 진행률 추적: Redis 상태 업데이트 (0.0 → 0.2 → 0.5 → 0.8 → 1.0)
- 에러 처리: 지수 백오프 재시도, 실패 시 상태를 "failed"로 마킹
- 결과 저장: Redis(1차) + 파일시스템 JSON(폴백)

### 1.5 오디오 전처리 결과물

AudioProcessor.convert_and_normalize()가 생성하는 파일:
- 형식: 16kHz mono WAV
- 정규화: -20dBFS 목표 레벨
- 경로: `settings.temp_dir/{task_id}_normalized.wav`

**핵심 인사이트**: pyannote.audio도 16kHz 입력을 요구하므로 STT가 생성한 전처리 파일을 재사용 가능.

### 1.6 WhisperEngine 싱글턴 패턴 (backend/ml/stt_engine.py:24-49)

화자 분리 엔진 구현 시 동일 패턴 적용:
```python
class WhisperEngine:
    _instance: "WhisperEngine | None" = None
    _lock: Lock = Lock()
    _model_loaded: bool = False

    @classmethod
    def get_instance(cls) -> "WhisperEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
```

---

## 2. pyannote.audio 3.1 기술 요구사항

### 2.1 패키지 정보

- **패키지명**: `pyannote.audio` (버전: 3.1.1)
- **의존성**: PyTorch (CPU 변형), torchaudio
- **모델** (HuggingFace 자동 다운로드):
  - `pyannote/speaker-diarization-3.1` (주 화자 분리 모델)
  - `pyannote/segmentation-3.0` (내부적으로 사용되는 음성 활동 감지)

### 2.2 HuggingFace 인증 (필수)

- **환경 변수**: `HUGGINGFACE_TOKEN`
- 모델 라이선스 동의 필요: https://huggingface.co/pyannote/speaker-diarization-3.1
- 토큰 없이 실행 불가 → 서버 시작 시 토큰 유효성 검증 필수

### 2.3 CPU 모드 특성

- **Apple Silicon MPS 지원 없음**: pyannote.audio 3.1은 CPU 전용
- **처리 속도**: 1-2배 실시간 (30분 회의 → 30-60초 처리)
- PyTorch CPU 변형 사용 (mlx-whisper와 독립적)

### 2.4 메모리 프로필 (M4 Mac Mini 24GB 기준)

| 컴포넌트 | 메모리 사용량 |
|---------|-------------|
| mlx-whisper (STT) | 3-6 GB |
| pyannote.audio (DIA) | 2-3 GB |
| 합계 (STT + DIA 동시) | 5-9 GB |
| 안전 동시 작업 수 | 2개 (24GB × 80% / 9GB ≈ 2.1) |

**현재 STT 동시 제한 3 → DIA 활성화 시 2로 하향 조정 필요**

### 2.5 pyannote.audio 3.1 출력 형식

```python
# 파이프라인 실행
pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1",
                                     use_auth_token=HUGGINGFACE_TOKEN)
diarization = pipeline(audio_file_path)

# 이터레이션
for segment, _, speaker in diarization.itertracks(yield_label=True):
    # segment.start: float (초)
    # segment.end: float (초)
    # speaker: str ("SPEAKER_00", "SPEAKER_01", ...)
```

---

## 3. 통합 설계

### 3.1 타임스탬프 정렬 알고리즘 (Overlap-based matching)

STT 세그먼트와 화자 분리 결과를 겹침 시간 기반으로 매칭:

```
각 STT 세그먼트 [start_stt, end_stt]에 대해:
  1. 해당 구간과 겹치는 모든 화자 세그먼트 탐색
  2. 겹침 시간이 가장 긴 화자 ID 할당
  3. 동점(tie)인 경우: 시작 시간이 빠른 화자 선택 + 경고 로그

예시:
  STT: [0.5s, 3.2s] "안녕하세요 오늘 회의를"
  DIA: [0.4s, 2.0s] SPEAKER_00  →  겹침 1.5s
  DIA: [2.0s, 3.5s] SPEAKER_01  →  겹침 1.2s
  결과: SPEAKER_00 할당 (1.5s > 1.2s)
```

### 3.2 확장된 출력 스키마

**DiarizedSegmentResult** (기존 SegmentResult 확장):
```python
class DiarizedSegmentResult(BaseModel):
    id: int
    start: float
    end: float
    text: str
    confidence: float
    speaker_id: str | None          # "SPEAKER_00" 등, 미할당 시 None
    speaker_confidence: float | None # 겹침 비율 기반 0.0-1.0
```

### 3.3 API 통합 패턴

**POST /api/v1/transcriptions** 파라미터 확장:
```
diarize: bool = False  # 화자 분리 활성화 여부
num_speakers: int | None = None  # 화자 수 힌트 (없으면 자동 감지)
min_speakers: int | None = None  # 최소 화자 수
max_speakers: int | None = None  # 최대 화자 수
```

### 3.4 처리 플로우 (순차 방식)

```
transcription_task.py (기존)
  1. 업로드/전처리 (REQ-STT-015~016)
  2. 청킹 (REQ-STT-018)
  3. STT 처리 (WhisperEngine)
  4. 세그먼트 병합

→ diarization_task.py (신규, diarize=True일 때만)
  5. 전처리 WAV 재사용 (16kHz mono)
  6. DiarizationEngine.diarize()
  7. 화자-STT 타임스탬프 매칭 (overlap 알고리즘)
  8. 세그먼트에 speaker_id 주석 추가
  9. 결과 캐시 갱신 (기존 task_id 키에 덮어쓰기)
```

---

## 4. 코드베이스 내 참조 구현

| 참조 대상 | 파일 경로 | 적용 패턴 |
|---------|---------|---------|
| 싱글턴 엔진 | backend/ml/stt_engine.py:24-49 | DiarizationEngine 동일 패턴 |
| Celery 태스크 | backend/workers/tasks/transcription_task.py:95-246 | diarization_task 동일 구조 |
| Redis 캐싱 | backend/workers/tasks/transcription_task.py:34-69 | 동일 키 패턴 + TTL |
| 청크 병합 | backend/pipeline/chunk_manager.py:90-135 | 오프셋 조정 알고리즘 |
| 오디오 처리 | backend/pipeline/audio_processor.py:71-102 | WAV 파일 재사용 |

---

## 5. 리스크 분석

| 리스크 | 확률 | 영향도 | 완화 전략 |
|--------|------|--------|----------|
| HuggingFace 토큰 미설정 | 높음 | 높음 | 서버 시작 시 토큰 검증, 명확한 에러 메시지 |
| CPU-only 성능 (느린 처리) | 중간 | 중간 | 타임아웃 설정, Celery 비동기 처리로 해결 |
| STT+DIA 동시 실행 시 OOM | 중간 | 높음 | 동시 작업 수 3→2로 하향, 메모리 임계값 모니터링 |
| 모델 첫 로드 지연 (3-5초) | 낮음 | 낮음 | 싱글턴 + warm-up 엔드포인트 |
| 타임스탬프 정밀도 오류 | 낮음 | 중간 | 밀리초 반올림, 동점 처리 로직 |

---

## 6. 신규 추가 파일 목록

```
backend/
├── ml/
│   └── diarization_engine.py         # DiarizationEngine 싱글턴 (NEW)
├── workers/tasks/
│   └── diarization_task.py           # Celery 화자 분리 태스크 (NEW)
├── pipeline/
│   └── speaker_matcher.py            # 타임스탬프 매칭 알고리즘 (NEW)
├── schemas/
│   └── diarization.py                # DiarizedSegmentResult 스키마 (NEW)
├── api/v1/
│   └── diarization.py                # POST/GET /api/v1/diarizations 엔드포인트 (NEW)
└── app/
    ├── config.py                     # HUGGINGFACE_TOKEN, diarization 설정 추가 (MODIFY)
    ├── main.py                       # DiarizationEngine warm-up 추가 (MODIFY)
    └── api/v1/health.py              # /health/diarization 엔드포인트 추가 (MODIFY)
```

---

## 7. SPEC-DIA-001 권장 범위

### 포함 (In Scope)
- DiarizationEngine 싱글턴 (pyannote.audio 3.1 래퍼)
- diarization_task Celery 태스크
- speaker_matcher 타임스탬프 매칭 모듈
- /api/v1/diarizations 독립 엔드포인트
- /api/v1/health/diarization 헬스 체크
- HUGGINGFACE_TOKEN 설정 통합
- STT 결과에 speaker_id 주석 처리

### 제외 (Out of Scope → 향후 SPEC-API-001)
- 화자명 커스터마이징 (speaker_00 → "김철수")
- 화자 등록/인식 (Speaker Recognition)
- 회의록 생성 (Claude API 연동)
