# SPEC-STT-001: STT Pipeline 구현 계획

## 1. SPEC 식별 정보

| 항목 | 내용 |
|------|------|
| SPEC ID | SPEC-STT-001 |
| 제목 | STT Pipeline - mlx-whisper 한국어 음성 인식 백엔드 |
| 도메인 | API (백엔드 서비스) |
| 우선순위 | P1 (핵심 기능, 최초 구현 대상) |
| 상태 | Planned |
| 플랫폼 | M4 Mac Mini 24GB (Apple Silicon, MLX 가속) |
| 주요 언어 | 한국어 (ko) |

---

## 2. EARS 요구사항 구조

### 모듈 1: 오디오 업로드 API

**[유비쿼터스]** 시스템은 항상 업로드된 오디오 파일의 형식(WAV, MP3, M4A, OGG)과 크기(최대 500MB)를 검증해야 한다.

**[이벤트 기반]** WHEN 클라이언트가 multipart/form-data로 오디오 파일을 POST /api/v1/transcriptions 엔드포인트에 업로드 THEN 시스템은 파일을 임시 저장소에 저장하고 고유한 task_id와 상태 조회 URL을 즉시 반환해야 한다.

**[이벤트 기반]** WHEN 업로드된 파일의 형식이 허용 목록(WAV, MP3, M4A, OGG)에 포함되지 않거나 크기가 500MB를 초과하거나 재생 시간이 4시간을 초과 THEN 시스템은 HTTP 422 응답과 함께 구체적인 검증 실패 사유를 반환해야 한다.

**[원치 않는 행동]** 시스템은 검증을 통과하지 못한 오디오 파일을 저장소에 보관하지 않아야 한다.

**[상태 기반]** IF 동시 업로드 요청이 활성 처리 용량(3개)을 초과 THEN 시스템은 작업을 대기열에 추가하고 pending 상태의 task_id를 반환해야 한다.

### 모듈 2: STT 처리 워커

**[이벤트 기반]** WHEN 새로운 전사 작업이 Celery 대기열에 등록 THEN STT 워커는 mlx-whisper의 whisper-large-v3-turbo 모델을 사용하여 한국어 강제 디코딩(`language="ko"`)으로 음성을 텍스트로 변환해야 한다.

**[유비쿼터스]** 시스템은 항상 MLX 프레임워크를 통해 Apple Silicon 가속을 활용하여 STT 처리를 수행해야 한다. MLX 디바이스를 사용할 수 없는 경우에만 CPU로 폴백해야 한다.

**[상태 기반]** IF whisper-large-v3-turbo 모델이 아직 메모리에 로드되지 않은 상태 THEN 워커는 첫 번째 요청 시 모델을 지연 로딩(lazy load)하고, 이후 요청에서는 이미 로드된 모델 인스턴스를 재사용해야 한다.

**[이벤트 기반]** WHEN STT 처리가 완료 THEN 워커는 세그먼트별 텍스트, 시작 시간, 종료 시간, 신뢰도 점수를 포함한 구조화된 JSON 결과를 생성해야 한다.

**[원치 않는 행동]** 시스템은 STT 처리 중 오류가 발생한 경우 부분 결과를 최종 결과로 저장하지 않아야 한다. 실패 상태(failed)와 오류 메시지를 기록해야 한다.

### 모듈 3: 작업 상태 및 결과 API

**[이벤트 기반]** WHEN 클라이언트가 GET /api/v1/transcriptions/{task_id}/status를 요청 THEN 시스템은 현재 작업 상태(pending, processing, completed, failed)를 반환해야 한다.

**[이벤트 기반]** WHEN 클라이언트가 GET /api/v1/transcriptions/{task_id}를 요청하고 작업이 completed 상태 THEN 시스템은 전체 전사 결과(세그먼트 목록, 언어, 총 재생 시간, 타임스탬프)를 JSON으로 반환해야 한다.

**[상태 기반]** IF 전사 결과가 Redis에 캐시되어 있는 상태 THEN 시스템은 데이터베이스 조회 없이 캐시에서 직접 결과를 반환해야 한다.

**[유비쿼터스]** 시스템은 항상 Redis에 전사 결과를 24시간 TTL로 캐시해야 한다.

**[이벤트 기반]** WHEN 클라이언트가 DELETE /api/v1/transcriptions/{task_id}를 요청 THEN 시스템은 해당 작업의 캐시, 결과 데이터, 그리고 임시 오디오 파일을 모두 삭제해야 한다.

### 모듈 4: 오디오 전처리

**[이벤트 기반]** WHEN 오디오 파일이 업로드되어 STT 처리 전 단계에 진입 THEN 시스템은 오디오를 16kHz 모노 WAV 형식으로 변환해야 한다.

**[유비쿼터스]** 시스템은 항상 오디오 레벨을 정규화하여 일관된 입력 품질을 보장해야 한다.

**[이벤트 기반]** WHEN 오디오 파일이 손상되었거나 디코딩이 불가능 THEN 시스템은 작업 상태를 failed로 변경하고 구체적인 오류 메시지("지원되지 않는 오디오 코덱" 또는 "파일 손상")를 기록해야 한다.

**[상태 기반]** IF 오디오 재생 시간이 30분을 초과 THEN 시스템은 오디오를 30분 단위 청크로 분할하여 순차적으로 처리하고, 결과를 병합해야 한다.

### 모듈 5: 헬스체크 및 모델 관리

**[이벤트 기반]** WHEN 클라이언트가 GET /api/v1/health를 요청 THEN 시스템은 서비스 상태, Redis 연결 상태, Celery 워커 상태를 반환해야 한다.

**[이벤트 기반]** WHEN 클라이언트가 GET /api/v1/health/model을 요청 THEN 시스템은 모델 로드 상태, 메모리 사용량, 모델 버전 정보를 반환해야 한다.

**[이벤트 기반]** WHEN FastAPI 서버가 시작(startup) THEN 시스템은 whisper-large-v3-turbo 모델을 사전 로드(warm-up)하여 첫 번째 요청의 콜드 스타트 지연을 방지해야 한다.

**[유비쿼터스]** 시스템은 항상 메모리 사용량을 모니터링하고, 24GB 한도의 80%(약 19GB) 초과 시 경고 로그를 기록해야 한다.

---

## 3. 기술 제약 조건 및 리스크

### 성능 목표

| 항목 | 목표값 | 비고 |
|------|--------|------|
| 업로드 응답 시간 | < 500ms | 파일 저장 + task_id 발급 |
| STT 처리 속도 | < 2x 실시간 | 30분 회의를 60분 이내 처리 |
| 동시 처리 작업 수 | 최대 3개 | 메모리 제약 (24GB) |
| 상태 조회 응답 시간 | < 100ms | Redis 캐시 활용 |
| 모델 웜업 시간 | < 30초 | 서버 시작 시 1회 |

### 핵심 리스크

| 리스크 | 확률 | 영향도 | 완화 전략 |
|--------|------|--------|----------|
| mlx-whisper 모델 콜드 스타트 지연 (~10-30초) | 높음 | 높음 | 서버 시작 시 모델 사전 로드(warm-up). lifespan 이벤트에서 모델 초기화 |
| 장시간 오디오(>1시간) 메모리 부족(OOM) | 높음 | 높음 | 30분 단위 청크 분할 처리. 청크별 결과 병합 로직 구현 |
| whisper-large-v3-turbo 메모리 사용량 (~3-6GB) | 중간 | 높음 | 동시 처리 작업 수를 3개로 제한. 메모리 모니터링 및 경고 시스템 |
| 한국어 고유명사/전문용어 인식 정확도 저하 | 중간 | 중간 | 후처리 사전(dictionary) 기반 보정. 사용자 피드백 루프 고려 |
| mlx-whisper API 변경 또는 호환성 이슈 | 중간 | 중간 | 버전 고정(pinning). 통합 테스트로 API 변경 조기 감지 |
| Redis 연결 실패 시 결과 캐시 손실 | 낮음 | 중간 | PostgreSQL을 영구 저장소로 병행 사용. Redis는 캐시 전용 |
| ffmpeg 시스템 종속성 미설치 | 낮음 | 높음 | Docker 이미지에 ffmpeg 포함. 헬스체크에서 ffmpeg 존재 여부 확인 |

### 주요 의존성 및 버전

| 라이브러리 | 권장 버전 | 비고 |
|-----------|-----------|------|
| Python | >= 3.11 | f-string, 타입 힌팅 최신 기능 |
| FastAPI | >= 0.135.1 | 최신 안정 버전 (2026-03 기준) |
| mlx-whisper | >= 0.4.3 | 최신 안정 버전 (2025-08 기준) |
| mlx | >= 0.31.1 | Apple Silicon MLX 프레임워크 |
| Celery | >= 5.6.2 | 최신 안정 버전 |
| Redis | >= 7.0 | 메시지 브로커 + 결과 캐시 |
| Pydantic | >= 2.9 | v2 데이터 검증 |
| uvicorn | >= 0.34.0 | ASGI 서버 |
| ffmpeg | 시스템 패키지 | 오디오 형식 변환 (brew install ffmpeg) |
| pydub 또는 ffmpeg-python | >= 0.25.1 | Python에서 ffmpeg 래핑 |

---

## 4. API 설계

### 엔드포인트 목록

| 메서드 | 경로 | 설명 | 인증 |
|--------|------|------|------|
| POST | /api/v1/transcriptions | 오디오 업로드 및 전사 작업 생성 | 선택적 |
| GET | /api/v1/transcriptions/{task_id} | 전사 결과 조회 | 선택적 |
| GET | /api/v1/transcriptions/{task_id}/status | 작업 상태 폴링 | 선택적 |
| DELETE | /api/v1/transcriptions/{task_id} | 작업 및 관련 파일 삭제 | 선택적 |
| GET | /api/v1/health | 서비스 헬스체크 | 불필요 |
| GET | /api/v1/health/model | 모델 상태 조회 | 불필요 |

### 요청/응답 설계

#### POST /api/v1/transcriptions

**요청**: multipart/form-data

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| file | UploadFile | 필수 | 오디오 파일 (WAV, MP3, M4A, OGG) |
| language | string | 선택 | 기본값 "ko". 언어 코드 |
| model | string | 선택 | 기본값 "whisper-large-v3-turbo" |

**응답** (201 Created):

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "status_url": "/api/v1/transcriptions/550e8400-e29b-41d4-a716-446655440000/status",
  "result_url": "/api/v1/transcriptions/550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2026-03-15T10:30:00Z"
}
```

**에러 응답** (422 Unprocessable Entity):

```json
{
  "detail": [
    {
      "field": "file",
      "message": "지원하지 않는 파일 형식입니다. 허용: WAV, MP3, M4A, OGG",
      "type": "unsupported_format"
    }
  ]
}
```

#### GET /api/v1/transcriptions/{task_id}

**응답** (200 OK, completed 상태):

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "language": "ko",
  "duration": 1823.4,
  "model": "whisper-large-v3-turbo",
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 4.2,
      "text": "안녕하세요, 오늘 회의를 시작하겠습니다.",
      "confidence": 0.95
    },
    {
      "id": 1,
      "start": 4.5,
      "end": 8.1,
      "text": "먼저 지난주 스프린트 리뷰부터 시작하겠습니다.",
      "confidence": 0.92
    }
  ],
  "metadata": {
    "file_name": "meeting_20260315.wav",
    "file_size_bytes": 52428800,
    "sample_rate": 16000,
    "processing_time_seconds": 142.5
  },
  "created_at": "2026-03-15T10:30:00Z",
  "completed_at": "2026-03-15T10:32:22Z"
}
```

#### GET /api/v1/transcriptions/{task_id}/status

**응답** (200 OK):

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 0.45,
  "message": "STT 처리 중... (세그먼트 45/100)",
  "created_at": "2026-03-15T10:30:00Z",
  "updated_at": "2026-03-15T10:31:15Z"
}
```

#### GET /api/v1/health

**응답** (200 OK):

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "components": {
    "api": "healthy",
    "redis": "healthy",
    "celery_workers": {
      "status": "healthy",
      "active_workers": 2,
      "active_tasks": 1
    },
    "ffmpeg": "available"
  },
  "timestamp": "2026-03-15T10:30:00Z"
}
```

#### GET /api/v1/health/model

**응답** (200 OK):

```json
{
  "model_name": "whisper-large-v3-turbo",
  "model_loaded": true,
  "device": "mps",
  "memory_usage_mb": 3200,
  "total_system_memory_mb": 24576,
  "available_memory_mb": 18000,
  "load_time_seconds": 12.5,
  "version": "0.4.3"
}
```

---

## 5. 구현 마일스톤

### 마일스톤 1: 기반 인프라 구축 (최우선 목표)

- FastAPI 프로젝트 스켈레톤 생성 (main.py, config.py, dependencies.py)
- Pydantic v2 요청/응답 스키마 정의
- Redis 연결 설정 및 헬스체크 엔드포인트 구현
- Celery 워커 초기 설정 (celery_app.py)
- Docker Compose 환경 구성 (FastAPI + Redis)
- 프로젝트 의존성 관리 (pyproject.toml 또는 requirements.txt)

### 마일스톤 2: 오디오 업로드 및 전처리 (1차 목표)

- POST /api/v1/transcriptions 엔드포인트 구현
- 파일 형식 검증 (WAV, MP3, M4A, OGG)
- 파일 크기 검증 (500MB 제한)
- 오디오 전처리 파이프라인 구현 (16kHz 모노 WAV 변환)
- 오디오 레벨 정규화
- 손상된 파일 감지 및 에러 처리
- 임시 파일 저장소 관리

### 마일스톤 3: STT 엔진 통합 (2차 목표)

- mlx-whisper 래퍼 클래스 구현 (stt_engine.py)
- whisper-large-v3-turbo 모델 로딩 및 추론 로직
- 한국어 강제 디코딩 설정 (`language="ko"`)
- 세그먼트별 타임스탬프 추출
- 모델 지연 로딩(lazy load) 및 재사용 패턴
- 서버 시작 시 모델 웜업(warm-up) 구현
- 장시간 오디오 청크 분할 처리 (30분 단위)

### 마일스톤 4: 비동기 작업 처리 (3차 목표)

- Celery 전사 작업(transcription_task) 구현
- 작업 상태 추적 및 진행률 업데이트
- GET /api/v1/transcriptions/{task_id}/status 구현
- GET /api/v1/transcriptions/{task_id} 결과 조회 구현
- Redis 결과 캐싱 (24시간 TTL)
- DELETE /api/v1/transcriptions/{task_id} 구현
- 에러 핸들링 및 실패 작업 관리

### 마일스톤 5: 품질 및 안정성 (최종 목표)

- 메모리 사용량 모니터링 구현
- GET /api/v1/health/model 모델 상태 엔드포인트
- 동시 처리 제한 (최대 3개) 구현
- 통합 테스트 작성 (API 엔드포인트)
- 단위 테스트 작성 (전처리, 스키마 검증)
- 에러 로깅 및 구조화된 JSON 로깅

### 선택적 목표

- 진행률 실시간 업데이트 (WebSocket 또는 SSE)
- 후처리 사전 기반 한국어 고유명사 보정
- 배치 업로드 지원 (여러 파일 동시 업로드)
- 결과 내보내기 (TXT, SRT 자막 형식)

---

## 6. 인수 기준 요약

### 시나리오 1: 한국어 오디오 업로드 후 전사 결과 수신 (Happy Path)

```
Given 30분 분량의 한국어 회의 녹음 WAV 파일이 준비되어 있을 때
When 클라이언트가 POST /api/v1/transcriptions에 해당 파일을 업로드하면
Then 시스템은 201 응답과 함께 task_id를 반환하고
And 작업 상태가 pending -> processing -> completed 순서로 전이되며
And GET /api/v1/transcriptions/{task_id} 응답에 한국어 텍스트 세그먼트,
    각 세그먼트의 start/end 타임스탬프, confidence 점수가 포함되어야 한다
```

### 시나리오 2: 잘못된 파일 형식 업로드 거부

```
Given 지원하지 않는 형식의 파일(.exe, .pdf, .txt 등)이 준비되어 있을 때
When 클라이언트가 POST /api/v1/transcriptions에 해당 파일을 업로드하면
Then 시스템은 422 응답과 함께 "지원하지 않는 파일 형식" 오류 메시지를 반환하고
And 해당 파일이 서버 저장소에 보관되지 않아야 한다
```

### 시나리오 3: 작업 상태 폴링을 통한 진행 추적

```
Given 오디오 파일이 성공적으로 업로드되어 task_id를 받은 상태에서
When 클라이언트가 GET /api/v1/transcriptions/{task_id}/status를 주기적으로 요청하면
Then 첫 번째 응답에서 status가 "pending" 또는 "processing"이고
And 처리가 완료되면 status가 "completed"로 변경되며
And 실패 시 status가 "failed"로 변경되고 error_message가 포함되어야 한다
```

### 시나리오 4: Apple Silicon MLX 가속 사용 확인

```
Given M4 Mac Mini에서 STT 서비스가 실행 중일 때
When GET /api/v1/health/model을 요청하면
Then device 필드가 "mps"로 표시되어야 하고
And 30분 오디오의 처리 시간이 실시간의 2배(60분) 이내여야 한다
```

### 시나리오 5: 대용량 파일 크기 제한

```
Given 500MB를 초과하는 오디오 파일이 준비되어 있을 때
When 클라이언트가 POST /api/v1/transcriptions에 해당 파일을 업로드하면
Then 시스템은 422 응답과 함께 "파일 크기가 제한(500MB)을 초과합니다" 오류를 반환해야 한다
```

### 시나리오 6: 장시간 오디오 청크 분할 처리

```
Given 2시간 분량의 한국어 오디오 파일이 업로드되었을 때
When STT 워커가 해당 파일을 처리하면
Then 시스템은 오디오를 30분 단위 청크(4개)로 분할하고
And 각 청크의 전사 결과를 순차적으로 처리한 후
And 최종 결과에서 세그먼트의 타임스탬프가 원본 오디오 기준으로 정확하게 보정되어야 한다
```

---

## 7. 구현 리스크 평가

| 리스크 | 확률 | 영향도 | 완화 전략 |
|--------|------|--------|----------|
| mlx-whisper API 변경 | 중간 | 중간 | 버전 고정 (>=0.4.3), 래퍼 클래스로 추상화, 통합 테스트 추가 |
| 장시간 오디오 메모리 OOM | 높음 | 높음 | 30분 단위 청크 분할, 청크 간 메모리 해제, 동시 작업 수 3개 제한 |
| 한국어 고유명사 인식 정확도 | 중간 | 중간 | 후처리 사전(dictionary) 보정, 향후 사용자 피드백 루프 도입 검토 |
| 콜드 스타트 지연 (~10-30초) | 높음 | 중간 | FastAPI lifespan 이벤트에서 모델 사전 로드, 헬스체크로 로드 상태 확인 |
| Celery 워커 장애 | 낮음 | 높음 | 작업 재시도 정책 (최대 3회), 데드 레터 큐 설정, 워커 상태 모니터링 |
| Redis 장애 시 캐시 손실 | 낮음 | 중간 | Redis는 캐시 전용 사용, 영구 결과는 별도 저장소(파일 또는 DB) 병행 |
| ffmpeg 누락/호환성 | 낮음 | 높음 | Docker 이미지에 ffmpeg 포함, 헬스체크에서 존재 여부 검증, 시작 시 경고 |
| 동시 요청 경합 조건 | 낮음 | 중간 | Celery 작업 ID 기반 격리, Redis 분산 락 활용 |

---

## 8. 기술적 접근 방식

### 아키텍처 개요

```
클라이언트 (Flutter/Web/curl)
    |
    | HTTP POST (multipart/form-data)
    v
FastAPI 서버 (uvicorn)
    |--- 파일 검증 (형식, 크기)
    |--- 임시 저장소에 파일 저장
    |--- Celery 작업 등록
    |--- task_id 즉시 반환
    |
    v
Celery Worker (Redis 브로커)
    |--- 오디오 전처리 (ffmpeg: 16kHz 모노 WAV 변환)
    |--- 오디오 레벨 정규화
    |--- mlx-whisper 추론 (whisper-large-v3-turbo, language="ko")
    |--- 세그먼트별 타임스탬프 추출
    |--- 결과 Redis 캐시 저장 (24h TTL)
    |--- 작업 상태 업데이트 (completed/failed)
    v
Redis (캐시 + 브로커)
    |--- 전사 결과 캐시
    |--- 작업 상태 저장
    |--- Celery 메시지 브로커
```

### 핵심 설계 결정

1. **비동기 처리 패턴**: STT 처리는 수 분이 소요되므로, 요청-응답 분리가 필수. Celery를 통한 비동기 작업 처리로 API 응답성 보장

2. **모델 수명 관리**: whisper-large-v3-turbo는 메모리 소비가 크므로 (3-6GB), 프로세스 수준에서 싱글톤으로 관리. 워커 프로세스당 1개의 모델 인스턴스 유지

3. **청크 분할 전략**: 30분 단위 분할은 메모리 효율과 처리 안정성의 균형점. 청크 경계에서 발화가 잘리는 문제는 5초 오버랩으로 완화

4. **캐시 전략**: Redis를 캐시 전용으로 사용하고, 영구 결과는 파일 시스템(JSON) 또는 향후 PostgreSQL에 저장. 캐시 미스 시 파일에서 복원

5. **에러 복구**: Celery 작업 실패 시 최대 3회 재시도. 지수 백오프(exponential backoff) 적용. 최종 실패 시 failed 상태로 기록

### 디렉토리 구조 (구현 시 참고)

```
backend/
├── app/
│   ├── main.py                    # FastAPI 앱 + lifespan 이벤트
│   ├── config.py                  # 환경 설정
│   ├── dependencies.py            # 의존성 주입
│   └── api/v1/
│       ├── transcription.py       # 전사 엔드포인트 (POST, GET, DELETE)
│       └── health.py              # 헬스체크 엔드포인트
├── schemas/
│   ├── transcription.py           # Pydantic 스키마
│   └── health.py                  # 헬스 응답 스키마
├── workers/
│   ├── celery_app.py              # Celery 설정
│   └── tasks/
│       └── transcription_task.py  # STT Celery 작업
├── ml/
│   └── stt_engine.py              # mlx-whisper 래퍼
├── pipeline/
│   ├── audio_processor.py         # 오디오 전처리 (ffmpeg)
│   └── chunk_manager.py           # 청크 분할/병합
└── utils/
    ├── logger.py                  # 구조화된 로깅
    └── validators.py              # 파일 검증
```

---

## 9. 전문가 협의 권장사항

이 SPEC은 백엔드 API 설계 및 ML 파이프라인 통합을 포함하므로, 다음 전문가 에이전트의 협의를 권장합니다:

- **expert-backend**: API 설계 검토, Celery 워커 아키텍처, 비동기 처리 패턴 최적화
- **expert-performance**: M4 Mac Mini 환경에서의 메모리 최적화, 동시 처리 성능 튜닝

---

## 10. 다음 단계

1. 사용자가 이 계획을 검토하고 승인
2. `/moai:1-plan` 완료 후 spec.md 및 acceptance.md 생성
3. `/moai:2-run SPEC-STT-001`으로 구현 단계 진입
4. expert-backend 에이전트에 API 구현 위임

---

*생성일: 2026-03-15*
*SPEC ID: SPEC-STT-001*
*상태: Planned*
