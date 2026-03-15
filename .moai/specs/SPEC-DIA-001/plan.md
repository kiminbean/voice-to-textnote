---
spec_id: SPEC-DIA-001
type: plan
version: "1.0.0"
created: 2026-03-15
updated: 2026-03-15
author: kisoo
---

# SPEC-DIA-001 구현 계획: pyannote.audio 3.1 화자 분리 파이프라인

---

## 1. 구현 개요

### 목표

SPEC-STT-001의 STT 파이프라인 완료 후, pyannote.audio 3.1 기반 화자 분리(Speaker Diarization) 기능을 추가하여 각 STT 세그먼트에 화자 ID를 주석 처리한다.

### 모듈 구조 (5개 모듈)

| 모듈 | 파일 | 핵심 역할 |
|------|------|----------|
| Module 1: DiarizationEngine | `backend/ml/diarization_engine.py` | 싱글턴 모델 로드 및 화자 분리 추론 |
| Module 2: SpeakerMatcher | `backend/pipeline/speaker_matcher.py` | STT-DIA 타임스탬프 overlap 매칭 |
| Module 3: Diarization Schema | `backend/schemas/diarization.py` | 요청/응답 데이터 모델 |
| Module 4: Diarization Task | `backend/workers/tasks/diarization_task.py` | Celery 비동기 처리 태스크 |
| Module 5: Diarization API | `backend/app/api/v1/diarization.py` | REST API 엔드포인트 |

### 신규 파일 목록

```
backend/
  ml/
    diarization_engine.py           # (NEW) DiarizationEngine 싱글턴
  pipeline/
    speaker_matcher.py              # (NEW) 타임스탬프 매칭 알고리즘
  schemas/
    diarization.py                  # (NEW) DiarizedSegmentResult 스키마
  workers/tasks/
    diarization_task.py             # (NEW) Celery 화자 분리 태스크
  app/api/v1/
    diarization.py                  # (NEW) API 엔드포인트
```

### 수정 파일 목록

```
backend/
  app/
    config.py                       # (MODIFY) HUGGINGFACE_TOKEN, diarization 설정 추가
    main.py                         # (MODIFY) DiarizationEngine warm-up, router 등록
  app/api/v1/
    health.py                       # (MODIFY) /health/diarization 엔드포인트 추가
pyproject.toml                      # (MODIFY) pyannote.audio, torch, torchaudio 의존성 추가
```

---

## 2. 모듈별 구현 상세

### Module 1: DiarizationEngine

**파일**: `backend/ml/diarization_engine.py`

**참조 패턴**: `backend/ml/stt_engine.py` (lines 24-49) WhisperEngine 싱글턴

**핵심 구조**:

- **클래스**: `DiarizationEngine`
  - `_instance: DiarizationEngine | None` (클래스 변수)
  - `_lock: Lock` (thread-safe 싱글턴)
  - `_model_loaded: bool`
  - `_pipeline: Pipeline | None` (pyannote Pipeline 인스턴스)

- **dataclass**: `SpeakerSegment`
  - `speaker_id: str` ("SPEAKER_00", "SPEAKER_01", ...)
  - `start: float` (초 단위)
  - `end: float` (초 단위)

- **dataclass**: `DiarizationResult`
  - `segments: list[SpeakerSegment]`
  - `num_speakers: int`

- **주요 메서드**:
  - `get_instance() -> DiarizationEngine`: double-checked locking 싱글턴
  - `load() -> None`: `Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=settings.huggingface_token)` 호출
  - `diarize(audio_path: str, num_speakers: int | None, min_speakers: int | None, max_speakers: int | None) -> DiarizationResult`: 화자 분리 실행
  - `unload() -> None`: 모델 해제 및 메모리 반환
  - `is_loaded() -> bool`: 모델 로드 상태 확인

- **HUGGINGFACE_TOKEN 주입**: `settings.huggingface_token` -> `Pipeline.from_pretrained(use_auth_token=...)`

---

### Module 2: SpeakerMatcher

**파일**: `backend/pipeline/speaker_matcher.py`

**알고리즘**: overlap duration 기반 STT-DIA 매칭

**입력**:
- `stt_segments: list[SegmentResult]` (SPEC-STT-001 출력)
- `dia_segments: list[SpeakerSegment]` (Module 1 출력)

**출력**:
- `list[DiarizedSegmentResult]`

**핵심 로직**:

```
각 STT 세그먼트 [start_stt, end_stt]에 대해:
  1. 겹치는 모든 화자 세그먼트 탐색
  2. 겹침 시간 = max(0, min(end_stt, end_dia) - max(start_stt, start_dia))
  3. 가장 긴 겹침 시간을 가진 화자 ID 할당
  4. speaker_confidence = 할당 화자 겹침 시간 / STT 세그먼트 길이
```

**엣지 케이스 처리**:
- 동점(tie): 시작 시간이 빠른 화자 선택 + 경고 로그
- 겹치는 화자 없음: `speaker_id=None`, `speaker_confidence=0.0`
- 빈 DIA 결과: 모든 세그먼트에 `speaker_id=None` 할당
- 빈 STT 결과: 빈 리스트 반환
- 타임스탬프 경계값: 정확히 같은 시작/끝 시간 → 겹침 0으로 처리

---

### Module 3: Diarization Schema

**파일**: `backend/schemas/diarization.py`

**데이터 모델**:

- **DiarizedSegmentResult** (SegmentResult 확장):
  - `id: int`
  - `start: float`
  - `end: float`
  - `text: str`
  - `confidence: float` (STT 신뢰도)
  - `speaker_id: str | None` ("SPEAKER_00" 등, 미할당 시 None)
  - `speaker_confidence: float` (겹침 비율 기반 0.0-1.0)

- **SpeakerInfo**:
  - `speaker_id: str`
  - `total_duration: float` (해당 화자의 총 발화 시간)
  - `segment_count: int` (해당 화자의 세그먼트 수)

- **DiarizationCreateRequest**:
  - `stt_task_id: str` (STT 결과 참조, 필수)
  - `num_speakers: int | None = None`
  - `min_speakers: int | None = None`
  - `max_speakers: int | None = None`

- **DiarizationResponse**:
  - `task_id: str`
  - `status: TaskStatus`
  - `segments: list[DiarizedSegmentResult]`
  - `speakers: list[SpeakerInfo]`
  - `num_speakers: int`

- **DiarizationStatusResponse**:
  - `task_id: str`
  - `status: TaskStatus` (pending/processing/completed/failed)
  - `progress: float` (0.0-1.0)
  - `message: str | None`

---

### Module 4: diarization_task Celery 태스크

**파일**: `backend/workers/tasks/diarization_task.py`

**참조 패턴**: `backend/workers/tasks/transcription_task.py` (lines 95-246)

**태스크 설정**:
- `@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)`
- 동시 제한: `max_concurrent_diarizations=2`
- Redis 상태 키: `task:dia:status:{task_id}`
- Redis 결과 키: `task:dia:result:{task_id}` (TTL: 24시간)

**실행 순서**:

1. **중복 검사**: 동일 stt_task_id에 대한 진행 중 작업 확인
2. **동시 작업 확인**: active_dia_job_count >= 2이면 429 반환
3. **상태 업데이트**: `pending` -> `processing` (progress: 0.0)
4. **STT 결과 로드**: Redis에서 STT 결과(SegmentResult 목록) 조회
5. **WAV 파일 확인**: `settings.temp_dir/{stt_task_id}_normalized.wav` 존재 확인
6. **화자 분리 실행**: `DiarizationEngine.get_instance().diarize(wav_path, ...)` (progress: 0.5)
7. **타임스탬프 매칭**: `SpeakerMatcher.match(stt_segments, dia_segments)` (progress: 0.8)
8. **결과 저장**: Redis 캐시에 DiarizationResponse 저장 (TTL: 24시간)
9. **상태 완료**: `processing` -> `completed` (progress: 1.0)

**에러 처리**:
- WAV 파일 미존재: 즉시 실패, 재시도 없음
- STT 결과 미존재: 즉시 실패, 재시도 없음
- pyannote 처리 오류: 지수 백오프 재시도 (최대 3회)
- 메모리 초과: 503 반환, 작업 대기열로 복귀

---

### Module 5: API 엔드포인트

**파일**: `backend/app/api/v1/diarization.py`

**엔드포인트**:

| Method | Path | 요청 | 응답 | 설명 |
|--------|------|------|------|------|
| POST | /api/v1/diarizations | DiarizationCreateRequest | 202 + {task_id, status_url} | 화자 분리 작업 생성 |
| GET | /api/v1/diarizations/{task_id} | - | DiarizationResponse | 화자 분리 결과 조회 |
| GET | /api/v1/diarizations/{task_id}/status | - | DiarizationStatusResponse | 작업 상태 조회 |
| DELETE | /api/v1/diarizations/{task_id} | - | 204 No Content | 결과 삭제 |

**요청/응답 예시**:

POST /api/v1/diarizations:
```json
{
  "stt_task_id": "abc123",
  "num_speakers": null,
  "min_speakers": 2,
  "max_speakers": 5
}
```

응답 (202):
```json
{
  "task_id": "dia_xyz789",
  "status": "pending",
  "status_url": "/api/v1/diarizations/dia_xyz789/status"
}
```

GET /api/v1/diarizations/{task_id} (completed):
```json
{
  "task_id": "dia_xyz789",
  "status": "completed",
  "num_speakers": 2,
  "speakers": [
    {"speaker_id": "SPEAKER_00", "total_duration": 120.5, "segment_count": 15},
    {"speaker_id": "SPEAKER_01", "total_duration": 95.3, "segment_count": 12}
  ],
  "segments": [
    {"id": 1, "start": 0.5, "end": 3.2, "text": "...", "confidence": 0.95, "speaker_id": "SPEAKER_00", "speaker_confidence": 0.87},
    ...
  ]
}
```

---

## 3. 수정 파일 상세

### 3.1 backend/app/config.py

추가 설정 필드:
- `huggingface_token: str` (필수, 환경 변수 HUGGINGFACE_TOKEN)
- `max_concurrent_diarizations: int = 2`
- `diarization_model: str = "pyannote/speaker-diarization-3.1"`
- `diarization_result_ttl: int = 86400` (24시간, 초)

### 3.2 backend/app/main.py

- `lifespan()` 함수에 DiarizationEngine warm-up 추가 (백그라운드 태스크)
- HUGGINGFACE_TOKEN 유효성 검증 (서버 시작 시)
- diarization router 등록: `app.include_router(diarization_router, prefix="/api/v1")`

### 3.3 backend/app/api/v1/health.py

- `GET /api/v1/health/diarization` 엔드포인트 추가
- 응답: `{"status": "loaded|loading|not_loaded", "memory_usage_bytes": 2147483648}`

### 3.4 pyproject.toml

추가 의존성:
```toml
pyannote-audio = "==3.1.1"
torch = "==2.3.0"
torchaudio = "==2.3.0"
huggingface-hub = ">=0.23.0"
```

---

## 4. 라이브러리 버전 (프로덕션 안정 버전)

| 라이브러리 | 버전 | 비고 |
|-----------|------|------|
| pyannote.audio | 3.1.1 | 최신 안정 버전 |
| torch | 2.3.0 (CPU variant) | Apple Silicon CPU 전용 |
| torchaudio | 2.3.0 | torch 버전과 일치 |
| huggingface_hub | >= 0.23.0 | 모델 다운로드 |

---

## 5. 마일스톤 (우선순위 기반)

### Primary Goal: 핵심 엔진 및 매칭 알고리즘

**대상 모듈**: Module 1 (DiarizationEngine), Module 2 (SpeakerMatcher), Module 3 (Schema)

**산출물**:
- DiarizationEngine 싱글턴 구현 및 단위 테스트
- SpeakerMatcher overlap 알고리즘 구현 및 경계값 테스트
- Pydantic 스키마 정의 및 검증 테스트

**완료 기준**:
- DiarizationEngine mock Pipeline 기반 단위 테스트 통과
- SpeakerMatcher 100% 커버리지 달성 (핵심 알고리즘)
- 모든 스키마 검증 테스트 통과

### Secondary Goal: Celery 태스크 및 API

**대상 모듈**: Module 4 (diarization_task), Module 5 (API)

**산출물**:
- Celery 태스크 구현 (동시 제한, 재시도, 상태 추적)
- REST API 엔드포인트 구현 (CRUD)
- 통합 테스트

**완료 기준**:
- 모든 API 엔드포인트 통합 테스트 통과
- 동시 작업 제한 동작 검증
- 상태 전이(pending -> processing -> completed/failed) 검증

### Final Goal: 시스템 통합 및 설정

**대상**: 수정 파일 (config.py, main.py, health.py, pyproject.toml)

**산출물**:
- 설정 통합 (HUGGINGFACE_TOKEN, 동시 제한)
- 서버 시작 시 모델 warm-up
- 헬스 체크 엔드포인트
- 의존성 추가

**완료 기준**:
- 서버 시작 시 HUGGINGFACE_TOKEN 검증 동작
- 모델 pre-warm 정상 작동
- 헬스 체크 엔드포인트 응답 확인
- 전체 통합 테스트 통과

---

## 6. TDD 테스트 전략

### 단위 테스트

| 테스트 파일 | 대상 모듈 | 핵심 테스트 케이스 |
|------------|----------|-------------------|
| `backend/tests/unit/test_diarization_engine.py` | DiarizationEngine | 싱글턴 패턴, mock Pipeline 로드/언로드, diarize 호출 |
| `backend/tests/unit/test_speaker_matcher.py` | SpeakerMatcher | 정상 매칭, 동점 처리, 빈 입력, 경계값, 겹침 없음 |
| `backend/tests/unit/test_diarization_schemas.py` | Schema | 스키마 검증, 직렬화/역직렬화, 선택적 필드 |

### 통합 테스트

| 테스트 파일 | 대상 | 핵심 테스트 케이스 |
|------------|------|-------------------|
| `backend/tests/integration/test_diarization_api.py` | 전체 API 흐름 | POST 작업 생성, GET 상태/결과, DELETE, 동시 제한 429, 404 처리 |

### 커버리지 목표

| 모듈 | 목표 커버리지 | 비고 |
|------|-------------|------|
| speaker_matcher.py | 100% | 핵심 알고리즘, 경계값 전수 테스트 |
| diarization_engine.py | 85%+ | mock Pipeline 기반 |
| diarization_task.py | 85%+ | mock Engine + mock Redis |
| diarization.py (API) | 85%+ | TestClient 기반 통합 테스트 |
| diarization.py (Schema) | 90%+ | Pydantic 모델 검증 |
| 전체 | 85%+ | TRUST 5 기준 |

---

## 7. 리스크 매트릭스

| 리스크 | 확률 | 영향도 | 완화 전략 |
|--------|------|--------|----------|
| HuggingFace 토큰 미설정/만료 | 높음 | 높음 | 서버 시작 시 토큰 검증, 명확한 에러 메시지 (REQ-DIA-002) |
| CPU-only 성능 저하 | 중간 | 중간 | Celery 비동기 처리, 타임아웃 설정, 진행률 추적 |
| STT+DIA 동시 실행 시 OOM | 중간 | 높음 | 동시 작업 2개 제한, 메모리 임계값 모니터링 (REQ-DIA-021) |
| 모델 첫 로드 지연 (3-5초) | 낮음 | 낮음 | 싱글턴 + pre-warm at startup (REQ-DIA-020) |
| 타임스탬프 정밀도 오류 (동점) | 낮음 | 중간 | 동점 처리 로직 + 경고 로그 (REQ-DIA-013) |
| STT 전처리 파일 부재 | 낮음 | 높음 | 파일 존재 확인 후 실행, 부재 시 즉시 실패 처리 |

---

## 8. 아키텍처 설계 방향

### 데이터 흐름

```
POST /api/v1/diarizations {stt_task_id}
  --> Celery diarization_task 생성
    --> Redis에서 STT 결과(SegmentResult) 로드
    --> STT 전처리 WAV 파일 경로 확인
    --> DiarizationEngine.diarize(wav_path) 실행
    --> SpeakerMatcher.match(stt_segments, dia_segments) 실행
    --> DiarizedSegmentResult 생성
    --> Redis에 결과 캐시 (24h TTL)
  --> GET /api/v1/diarizations/{task_id} 로 결과 조회
```

### Redis 키 패턴

| 키 패턴 | 용도 | TTL |
|---------|------|-----|
| `task:dia:status:{task_id}` | 작업 상태 + 진행률 | 24시간 |
| `task:dia:result:{task_id}` | DiarizationResponse JSON | 24시간 |
| `active_dia_jobs` | 활성 작업 ID 집합 | 없음 |
| `active_dia_job_count` | 동시 작업 수 카운터 | 없음 |

---

*Plan ID: SPEC-DIA-001*
*생성일: 2026-03-15*
*상태: completed*
