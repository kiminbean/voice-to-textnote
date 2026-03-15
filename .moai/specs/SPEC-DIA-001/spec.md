---
id: SPEC-DIA-001
version: "1.0.0"
status: draft
created: 2026-03-15
updated: 2026-03-15
author: kisoo
priority: P1
issue_number: 0
---

# SPEC-DIA-001: Speaker Diarization - pyannote.audio 3.1 화자 분리 파이프라인

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-03-15 | 초안 작성 | kisoo |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 플랫폼 | M4 Mac Mini 24GB (Apple Silicon, CPU mode for pyannote) |
| 런타임 | Python >= 3.11, FastAPI >= 0.135.1, uvicorn >= 0.34.0 |
| ML 프레임워크 | pyannote.audio == 3.1.1, PyTorch == 2.3.0 (CPU), torchaudio == 2.3.0 |
| 모델 허브 | HuggingFace Hub >= 0.23.0 (모델 다운로드, HUGGINGFACE_TOKEN 필수) |
| 비동기 처리 | Celery >= 5.6.2, Redis >= 7.0 |
| 데이터 검증 | Pydantic >= 2.9 |
| 화자 분리 모델 | pyannote/speaker-diarization-3.1 |
| 세그멘테이션 모델 | pyannote/segmentation-3.0 (내부 의존) |

---

## 2. 가정 (Assumptions)

- pyannote.audio 3.1은 CPU 모드로만 동작한다. Apple Silicon MPS 가속은 지원하지 않는다.
- `HUGGINGFACE_TOKEN` 환경 변수가 설정되어 있으며, HuggingFace에서 pyannote/speaker-diarization-3.1 모델 라이선스에 동의한 상태이다.
- SPEC-STT-001의 전처리 결과물(16kHz mono WAV)을 화자 분리에 재사용한다. 별도의 오디오 전처리는 불필요하다.
- 동시 처리 작업 수를 2개로 제한하면 24GB 메모리 내에서 안정적으로 운영 가능하다 (STT 3-6GB + DIA 2-3GB = 5-9GB/작업).
- 화자 분리는 STT 완료 후 순차적으로 실행된다. SPEC-STT-001의 transcription_task가 완료된 이후 diarization_task가 실행된다.
- Redis 서버는 화자 분리 서비스 시작 전에 이미 실행 중이다.
- 처리 대상 오디오는 주로 회의/강의 등 비교적 선명한 음질이며, 화자 수는 보통 2-10명이다.

---

## 3. 요구사항 (Requirements)

### 모듈 1: DiarizationEngine (화자 분리 엔진)

**[REQ-DIA-001] [유비쿼터스]** DiarizationEngine은 항상 pyannote/speaker-diarization-3.1 모델을 싱글턴으로 로드하고 재사용해야 한다. 프로세스당 1개의 모델 인스턴스만 유지한다.

**[REQ-DIA-002] [이벤트 기반]** WHEN HUGGINGFACE_TOKEN이 설정되지 않았거나 유효하지 않을 때 THEN 시스템은 서버 시작 시 명확한 에러 메시지("HUGGINGFACE_TOKEN is not set or invalid. Please set a valid token and accept the model license at https://huggingface.co/pyannote/speaker-diarization-3.1")와 함께 시작을 거부해야 한다.

**[REQ-DIA-003] [유비쿼터스]** DiarizationEngine은 항상 오디오 파일 경로를 입력으로 받아 화자 세그먼트 목록(speaker_id, start, end)을 반환해야 한다. 각 세그먼트는 초 단위 float 타임스탬프를 포함한다.

**[REQ-DIA-004] [상태 기반]** IF 모델이 로드 중인 상태 THEN DiarizationEngine은 로드 완료까지 대기하고, 로드 완료 후 모델 인스턴스를 재사용해야 한다. 이 과정은 thread-safe여야 한다 (double-checked locking 패턴).

### 모듈 2: Diarization Celery Task

**[REQ-DIA-005] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/diarizations 요청을 보낼 때 THEN 시스템은 Celery 태스크를 생성하고 task_id를 202 Accepted 응답으로 반환해야 한다.

**[REQ-DIA-006] [유비쿼터스]** diarization_task는 항상 STT 전처리 파일(16kHz mono WAV, 경로: `settings.temp_dir/{stt_task_id}_normalized.wav`)을 재사용하여 별도 전처리 없이 화자 분리를 수행해야 한다.

**[REQ-DIA-007] [유비쿼터스]** diarization_task는 항상 최대 2개 동시 작업 제한을 유지해야 한다. 제한 초과 시 HTTP 429 Too Many Requests를 반환해야 한다.

**[REQ-DIA-008] [이벤트 기반]** WHEN 화자 분리 처리 중 오류가 발생 THEN 시스템은 최대 3회 지수 백오프 재시도(default_retry_delay=60초) 후 상태를 "failed"로 마킹해야 한다.

**[REQ-DIA-009] [원치 않는 행동]** 시스템은 diarization_task가 실행 중일 때 동일 stt_task_id에 대한 중복 화자 분리 작업의 실행을 방지해야 한다.

### 모듈 3: Speaker-STT Matching (타임스탬프 매칭)

**[REQ-DIA-010] [유비쿼터스]** speaker_matcher 모듈은 항상 STT 세그먼트와 화자 분리 결과를 타임스탬프 겹침(overlap) 기반으로 매칭해야 한다. 겹침 시간 = max(0, min(end_stt, end_dia) - max(start_stt, start_dia))로 계산한다.

**[REQ-DIA-011] [유비쿼터스]** 각 STT 세그먼트에 대해, 항상 가장 긴 겹침 시간을 가진 화자 ID를 speaker_id로 할당해야 한다. speaker_confidence는 (할당된 화자의 겹침 시간 / STT 세그먼트 전체 길이)로 계산한다.

**[REQ-DIA-012] [원치 않는 행동]** 시스템은 화자를 할당할 수 없는 STT 세그먼트(겹치는 화자 세그먼트가 없는 구간)에 대해 speaker_id=null, speaker_confidence=0.0으로 표시해야 한다. 유효하지 않은 화자 ID를 할당하지 않아야 한다.

**[REQ-DIA-013] [상태 기반]** IF 여러 화자가 동일한 최대 겹침 시간을 가진 동점 상태 THEN 시스템은 시작 시간이 가장 빠른 화자를 선택하고, 경고 로그를 기록해야 한다 ("Tie-breaking for segment {id}: speakers {speakers} with equal overlap {duration}s").

### 모듈 4: Status & Result API

**[REQ-DIA-014] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/diarizations/{task_id}/status를 요청 THEN 시스템은 처리 상태(pending/processing/completed/failed)와 진행률(0.0-1.0)을 반환해야 한다.

**[REQ-DIA-015] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/diarizations/{task_id}를 요청하고 작업이 completed 상태 THEN 시스템은 speaker_id가 주석된 세그먼트 목록, 화자 정보(speaker_id, total_duration, segment_count), 총 화자 수를 반환해야 한다.

**[REQ-DIA-016] [유비쿼터스]** 화자 분리 결과는 항상 Redis에 24시간 TTL로 캐시되어야 한다. 키 패턴: `task:dia:result:{task_id}`.

**[REQ-DIA-017] [이벤트 기반]** WHEN 클라이언트가 DELETE /api/v1/diarizations/{task_id}를 요청 THEN 시스템은 Redis 캐시(상태 키 + 결과 키)를 삭제하고 204 No Content를 반환해야 한다.

**[REQ-DIA-018] [원치 않는 행동]** 시스템은 존재하지 않는 task_id로 조회 시 404 Not Found를 반환해야 한다. 빈 결과나 기본값을 반환하지 않아야 한다.

### 모듈 5: Health & Model Management

**[REQ-DIA-019] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/health/diarization를 요청 THEN 시스템은 모델 로드 상태(loaded/loading/not_loaded)와 메모리 사용량(bytes)을 반환해야 한다.

**[REQ-DIA-020] [상태 기반]** IF 서버가 시작(startup) 상태 THEN DiarizationEngine은 백그라운드에서 모델을 pre-warm(사전 로드)해야 한다. 첫 번째 요청의 콜드 스타트 지연을 방지한다.

**[REQ-DIA-021] [원치 않는 행동]** 시스템은 메모리 사용량이 24GB의 80%(19.2GB)를 초과할 때 새 화자 분리 작업 요청을 503 Service Unavailable로 거부해야 한다. 기존 진행 중인 작업에는 영향을 주지 않아야 한다.

**[REQ-DIA-022] [유비쿼터스]** 시스템은 항상 화자 수를 모르는 경우 num_speakers=None으로 자동 감지를 지원해야 한다. 선택적으로 min_speakers/max_speakers 힌트를 수용하여 감지 정확도를 개선할 수 있어야 한다.

---

## 4. 비기능 요구사항 (Non-Functional Requirements)

### 성능 (Performance)

| 항목 | 목표값 | 비고 |
|------|--------|------|
| 화자 분리 처리 속도 | < 2x 실시간 | 30분 오디오 기준 60초 이내 처리 |
| 타임스탬프 매칭 처리 시간 | < 1초 | 1000개 세그먼트 기준 |
| 상태 조회 응답 시간 | < 100ms | Redis 캐시 활용 |
| 동시 처리 작업 수 | 최대 2개 | 메모리 제약 (24GB, STT 동시 고려) |
| 모델 웜업 시간 | < 10초 | 서버 시작 시 1회 |
| API 응답 시간 (작업 제출) | < 500ms | task_id 발급 |

### 메모리 (Memory)

| 항목 | 목표값 | 비고 |
|------|--------|------|
| 작업당 메모리 사용량 | < 3GB | pyannote.audio 모델 + 처리 |
| 모델 상주 메모리 | < 2GB | 싱글턴 로드 후 상시 |
| 메모리 임계값 | 19.2GB (80%) | 초과 시 신규 작업 거부 |

### 가용성 (Availability)

- 헬스 체크 엔드포인트(/api/v1/health/diarization)는 24/7 응답 가능해야 한다.
- 모델 로드 실패 시에도 헬스 체크는 상태 정보("not_loaded")를 반환해야 한다.

---

## 5. 기술 제약 조건 (Technical Constraints)

- **CPU 전용**: pyannote.audio 3.1은 Apple Silicon MPS 가속을 지원하지 않는다. PyTorch CPU 변형만 사용 가능.
- **HuggingFace 인증 필수**: 모델 다운로드에 유효한 HUGGINGFACE_TOKEN과 모델 라이선스 동의가 필수.
- **STT 동시 제한 영향**: SPEC-STT-001에서 동시 작업 3개 → DIA 활성화 시 전체 시스템 동시 작업 2개로 하향 조정 필요.
- **Redis 필수 선행 실행**: Celery 메시지 브로커 및 결과 캐시로 사용. 화자 분리 워커 시작 전에 Redis 서버가 실행 중이어야 함.
- **Python >= 3.11**: 최신 타입 힌팅 기능 및 프로젝트 일관성 필수.
- **STT 전처리 파일 의존**: diarization_task는 transcription_task가 생성한 WAV 파일에 의존. 파일 부재 시 실패 처리.

---

## 6. 의존성 (Dependencies)

| 라이브러리 | 권장 버전 | 용도 |
|-----------|-----------|------|
| pyannote.audio | == 3.1.1 | 화자 분리 파이프라인 |
| torch | == 2.3.0 (CPU) | PyTorch 런타임 (CPU 전용) |
| torchaudio | == 2.3.0 | 오디오 처리 |
| huggingface_hub | >= 0.23.0 | 모델 다운로드 |
| FastAPI | >= 0.135.1 | 웹 프레임워크 |
| Celery | >= 5.6.2 | 비동기 작업 큐 |
| Redis | >= 7.0 | 메시지 브로커 + 결과 캐시 |
| Pydantic | >= 2.9 | 데이터 검증 |

---

## 7. 연결된 SPEC (Related SPECs)

| SPEC ID | 관계 | 설명 |
|---------|------|------|
| SPEC-STT-001 | 의존 (Upstream) | STT 전처리 파일(16kHz mono WAV) 및 세그먼트 결과(SegmentResult) 활용 |
| SPEC-API-001 | 소비 (Downstream, 예정) | 회의록 생성에서 화자별 텍스트(DiarizedSegmentResult) 활용 |

---

## 8. 추적성 (Traceability)

| 요구사항 ID | 모듈 | EARS 패턴 | 관련 엔드포인트/컴포넌트 |
|-------------|------|-----------|------------------------|
| REQ-DIA-001 | DiarizationEngine | 유비쿼터스 | DiarizationEngine 싱글턴 |
| REQ-DIA-002 | DiarizationEngine | 이벤트 기반 | FastAPI lifespan |
| REQ-DIA-003 | DiarizationEngine | 유비쿼터스 | DiarizationEngine.diarize() |
| REQ-DIA-004 | DiarizationEngine | 상태 기반 | DiarizationEngine.get_instance() |
| REQ-DIA-005 | Celery Task | 이벤트 기반 | POST /api/v1/diarizations |
| REQ-DIA-006 | Celery Task | 유비쿼터스 | diarization_task |
| REQ-DIA-007 | Celery Task | 유비쿼터스 | diarization_task |
| REQ-DIA-008 | Celery Task | 이벤트 기반 | diarization_task |
| REQ-DIA-009 | Celery Task | 원치 않는 행동 | diarization_task |
| REQ-DIA-010 | Speaker Matcher | 유비쿼터스 | speaker_matcher.match() |
| REQ-DIA-011 | Speaker Matcher | 유비쿼터스 | speaker_matcher.match() |
| REQ-DIA-012 | Speaker Matcher | 원치 않는 행동 | speaker_matcher.match() |
| REQ-DIA-013 | Speaker Matcher | 상태 기반 | speaker_matcher.match() |
| REQ-DIA-014 | Status API | 이벤트 기반 | GET .../status |
| REQ-DIA-015 | Result API | 이벤트 기반 | GET .../{task_id} |
| REQ-DIA-016 | Result API | 유비쿼터스 | Redis 캐시 |
| REQ-DIA-017 | Result API | 이벤트 기반 | DELETE .../{task_id} |
| REQ-DIA-018 | Result API | 원치 않는 행동 | GET .../{task_id} |
| REQ-DIA-019 | Health | 이벤트 기반 | GET /api/v1/health/diarization |
| REQ-DIA-020 | Health | 상태 기반 | FastAPI lifespan |
| REQ-DIA-021 | Health | 원치 않는 행동 | 메모리 모니터링 |
| REQ-DIA-022 | Health | 유비쿼터스 | DiarizationEngine.diarize() |

---

*SPEC ID: SPEC-DIA-001*
*생성일: 2026-03-15*
*상태: draft*
