---
id: SPEC-STT-001
version: "1.1.0"
status: completed
created: 2026-03-15
updated: 2026-06-13
author: kisoo
priority: P1
issue_number: 0
---

# SPEC-STT-001: STT Pipeline - mlx-whisper 한국어 음성 인식 백엔드

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-03-15 | 초안 작성 | kisoo |
| 1.1.0 | 2026-06-13 | 기본 모델 실제 구현 반영: whisper-large-v3-turbo → mlx-community/whisper-small-mlx, Redis TTL 24시간 → 7일 | MoAI |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 플랫폼 | M4 Mac Mini 24GB (Apple Silicon, MLX 가속) |
| 런타임 | Python >= 3.11, FastAPI >= 0.135.1, uvicorn >= 0.34.0 |
| ML 프레임워크 | mlx >= 0.31.1, mlx-whisper >= 0.4.3 |
| 비동기 처리 | Celery >= 5.6.2, Redis >= 7.0 |
| 데이터 검증 | Pydantic >= 2.9 |
| 오디오 처리 | ffmpeg (시스템 패키지), pydub >= 0.25.1 |
| 대상 언어 | 한국어 (language="ko") |
| 모델 | mlx-community/whisper-small-mlx (기본값, `WHISPER_MODEL` 설정 변경 가능) |

---

## 2. 가정 (Assumptions)

- M4 Mac Mini에서 MLX 프레임워크를 통해 Apple Silicon GPU(MPS) 가속이 정상 작동한다.
- mlx-community/whisper-small-mlx 모델의 메모리 사용량은 약 1-2GB 범위이다.
- Redis 서버는 STT 서비스 시작 전에 이미 실행 중이다.
- ffmpeg가 시스템에 설치되어 있으며 PATH에서 접근 가능하다.
- 처리 대상 오디오는 주로 한국어 음성이며, 회의/강의 등 비교적 선명한 음질이다.
- 동시 처리 작업 수를 3개로 제한하면 24GB 메모리 한도 내에서 안정적으로 운영할 수 있다.
- 로컬 전용 서비스로, 외부 네트워크로 데이터를 전송하지 않는다.

---

## 3. 요구사항 (Requirements)

### 모듈 1: 오디오 업로드 API

**[REQ-STT-001] [유비쿼터스]** 시스템은 항상 업로드된 오디오 파일의 형식(WAV, MP3, M4A, OGG)과 크기(최대 500MB)를 검증해야 한다.

**[REQ-STT-002] [이벤트 기반]** WHEN 클라이언트가 multipart/form-data로 오디오 파일을 POST /api/v1/transcriptions 엔드포인트에 업로드 THEN 시스템은 파일을 임시 저장소에 저장하고 고유한 task_id와 상태 조회 URL을 즉시 반환해야 한다.

**[REQ-STT-003] [이벤트 기반]** WHEN 업로드된 파일의 형식이 허용 목록(WAV, MP3, M4A, OGG)에 포함되지 않거나 크기가 500MB를 초과하거나 재생 시간이 4시간을 초과 THEN 시스템은 HTTP 422 응답과 함께 구체적인 검증 실패 사유를 반환해야 한다.

**[REQ-STT-004] [원치 않는 행동]** 시스템은 검증을 통과하지 못한 오디오 파일을 저장소에 보관하지 않아야 한다.

### 모듈 2: STT 처리 워커

**[REQ-STT-005] [이벤트 기반]** WHEN 새로운 전사 작업이 Celery 대기열에 등록 THEN STT 워커는 mlx-whisper의 mlx-community/whisper-small-mlx 모델을 사용하여 한국어 강제 디코딩(`language="ko"`)으로 음성을 텍스트로 변환해야 한다.

**[REQ-STT-006] [유비쿼터스]** 시스템은 항상 MLX 프레임워크를 통해 Apple Silicon 가속을 활용하여 STT 처리를 수행해야 한다. MLX 디바이스를 사용할 수 없는 경우에만 CPU로 폴백해야 한다.

**[REQ-STT-007] [상태 기반]** IF mlx-community/whisper-small-mlx 모델이 아직 메모리에 로드되지 않은 상태 THEN 워커는 첫 번째 요청 시 모델을 지연 로딩(lazy load)하고, 이후 요청에서는 이미 로드된 모델 인스턴스를 재사용해야 한다.

**[REQ-STT-008] [이벤트 기반]** WHEN STT 처리가 완료 THEN 워커는 세그먼트별 텍스트, 시작 시간, 종료 시간, 신뢰도 점수를 포함한 구조화된 JSON 결과를 생성해야 한다.

**[REQ-STT-009] [원치 않는 행동]** 시스템은 STT 처리 중 오류가 발생한 경우 부분 결과를 최종 결과로 저장하지 않아야 한다. 실패 상태(failed)와 오류 메시지를 기록해야 한다.

### 모듈 3: 작업 상태 및 결과 API

**[REQ-STT-010] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/transcriptions/{task_id}/status를 요청 THEN 시스템은 현재 작업 상태(pending, processing, completed, failed)를 반환해야 한다.

**[REQ-STT-011] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/transcriptions/{task_id}를 요청하고 작업이 completed 상태 THEN 시스템은 전체 전사 결과(세그먼트 목록, 언어, 총 재생 시간, 타임스탬프)를 JSON으로 반환해야 한다.

**[REQ-STT-012] [상태 기반]** IF 전사 결과가 Redis에 캐시되어 있는 상태 THEN 시스템은 데이터베이스 조회 없이 캐시에서 직접 결과를 반환해야 한다.

**[REQ-STT-013] [유비쿼터스]** 시스템은 항상 Redis에 전사 결과를 캐시해야 한다. TTL은 `cache_ttl_seconds` 설정값(기본 604800초 = 7일)을 따른다.

**[REQ-STT-014] [이벤트 기반]** WHEN 클라이언트가 DELETE /api/v1/transcriptions/{task_id}를 요청 THEN 시스템은 해당 작업의 캐시, 결과 데이터, 그리고 임시 오디오 파일을 모두 삭제해야 한다.

### 모듈 4: 오디오 전처리

**[REQ-STT-015] [이벤트 기반]** WHEN 오디오 파일이 업로드되어 STT 처리 전 단계에 진입 THEN 시스템은 오디오를 16kHz 모노 WAV 형식으로 변환해야 한다.

**[REQ-STT-016] [유비쿼터스]** 시스템은 항상 오디오 레벨을 정규화하여 일관된 입력 품질을 보장해야 한다.

**[REQ-STT-017] [이벤트 기반]** WHEN 오디오 파일이 손상되었거나 디코딩이 불가능 THEN 시스템은 작업 상태를 failed로 변경하고 구체적인 오류 메시지("지원되지 않는 오디오 코덱" 또는 "파일 손상")를 기록해야 한다.

**[REQ-STT-018] [상태 기반]** IF 오디오 재생 시간이 30분을 초과 THEN 시스템은 오디오를 30분 단위 청크로 분할하여 순차적으로 처리하고, 결과를 병합해야 한다.

### 모듈 5: 헬스체크 및 모델 관리

**[REQ-STT-019] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/health를 요청 THEN 시스템은 서비스 상태, Redis 연결 상태, Celery 워커 상태를 반환해야 한다.

**[REQ-STT-020] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/health/model을 요청 THEN 시스템은 모델 로드 상태, 메모리 사용량, 모델 버전 정보를 반환해야 한다.

**[REQ-STT-021] [이벤트 기반]** WHEN FastAPI 서버가 시작(startup) THEN 시스템은 mlx-community/whisper-small-mlx 모델을 사전 로드(warm up)하여 첫 번째 요청의 콜드 스타트 지연을 방지해야 한다.

**[REQ-STT-022] [유비쿼터스]** 시스템은 항상 메모리 사용량을 모니터링하고, 24GB 한도의 80%(약 19GB) 초과 시 경고 로그를 기록해야 한다.

---

## 4. 비기능 요구사항 (Non-Functional Requirements)

### 성능 (Performance)

| 항목 | 목표값 | 비고 |
|------|--------|------|
| 업로드 응답 시간 | < 500ms | 파일 저장 + task_id 발급 |
| STT 처리 속도 | < 2x 실시간 | 30분 회의를 60분 이내 처리 |
| 동시 처리 작업 수 | 최대 3개 | 메모리 제약 (24GB) |
| 상태 조회 응답 시간 | < 100ms | Redis 캐시 활용 |
| 모델 웜업 시간 | < 30초 | 서버 시작 시 1회 |

### 보안 (Security)

- 로컬 전용 처리: 모든 오디오 데이터와 전사 결과는 로컬 시스템에서만 처리되며, 외부 네트워크로 전송하지 않는다.
- 임시 파일 관리: 처리 완료 또는 삭제 요청 시 임시 오디오 파일을 확실히 제거한다.
- 입력 검증: 모든 업로드 파일에 대해 형식, 크기, 재생 시간을 검증하여 악의적 파일 처리를 방지한다.

### 신뢰성 (Reliability)

- Celery 작업 재시도: 실패 시 최대 3회 재시도, 지수 백오프(exponential backoff) 적용.
- 부분 결과 방지: STT 처리 중 오류 발생 시 부분 결과를 저장하지 않고 failed 상태로 기록.
- 캐시 복원: Redis 캐시 미스 시 파일 시스템의 영구 저장소에서 결과 복원 가능.
- 메모리 보호: 24GB 한도의 80% 초과 시 경고, 동시 작업 수 제한으로 OOM 방지.

---

## 5. 기술 제약 조건 (Technical Constraints)

- **Python >= 3.11**: f-string 확장, 최신 타입 힌팅 기능 필수.
- **Apple Silicon 필수**: MLX 프레임워크는 Apple Silicon(M1/M2/M3/M4)에서만 가속 지원. Intel Mac에서는 CPU 폴백만 가능.
- **ffmpeg 시스템 종속성**: 오디오 형식 변환(16kHz 모노 WAV)에 필수. `brew install ffmpeg`로 설치하거나 Docker 이미지에 포함.
- **Redis 필수 선행 실행**: Celery 메시지 브로커 및 결과 캐시로 사용. STT 워커 시작 전에 Redis 서버가 실행 중이어야 함.
- **단일 프로세스 모델 관리**: mlx-community/whisper-small-mlx 모델은 프로세스 수준에서 싱글톤으로 관리. 워커 프로세스당 1개의 모델 인스턴스.
- **청크 분할 경계 처리**: 30분 단위 분할 시 발화가 잘리는 문제를 5초 오버랩으로 완화.
- **모델 변경 가능**: `WHISPER_MODEL` 환경 변수로 대체 모델 지정 가능. mlx-community 모델명을 사용하며, `MLX_DEFAULT_MODEL`이 기본값.

---

## 6. 의존성 (Dependencies)

| 라이브러리 | 권장 버전 | 용도 |
|-----------|-----------|------|
| Python | >= 3.11 | 런타임 |
| FastAPI | >= 0.135.1 | 웹 프레임워크 (ASGI) |
| mlx-whisper | >= 0.4.3 | Whisper STT 추론 (MLX 가속) |
| mlx | >= 0.31.1 | Apple Silicon ML 프레임워크 |
| Celery | >= 5.6.2 | 비동기 작업 큐 |
| Redis | >= 7.0 | 메시지 브로커 + 결과 캐시 |
| Pydantic | >= 2.9 | 데이터 검증 (v2 model_validate) |
| uvicorn | >= 0.34.0 | ASGI 서버 |
| ffmpeg | 시스템 패키지 | 오디오 형식 변환 |
| pydub | >= 0.25.1 | Python ffmpeg 래핑 |

---

## 7. 추적성 (Traceability)

| 요구사항 ID | 모듈 | EARS 패턴 | 관련 엔드포인트 |
|-------------|------|-----------|----------------|
| REQ-STT-001 | 업로드 API | 유비쿼터스 | POST /api/v1/transcriptions |
| REQ-STT-002 | 업로드 API | 이벤트 기반 | POST /api/v1/transcriptions |
| REQ-STT-003 | 업로드 API | 이벤트 기반 | POST /api/v1/transcriptions |
| REQ-STT-004 | 업로드 API | 원치 않는 행동 | POST /api/v1/transcriptions |
| REQ-STT-005 | STT 워커 | 이벤트 기반 | Celery 작업 |
| REQ-STT-006 | STT 워커 | 유비쿼터스 | Celery 작업 |
| REQ-STT-007 | STT 워커 | 상태 기반 | Celery 작업 |
| REQ-STT-008 | STT 워커 | 이벤트 기반 | Celery 작업 |
| REQ-STT-009 | STT 워커 | 원치 않는 행동 | Celery 작업 |
| REQ-STT-010 | 상태/결과 API | 이벤트 기반 | GET .../status |
| REQ-STT-011 | 상태/결과 API | 이벤트 기반 | GET .../{task_id} |
| REQ-STT-012 | 상태/결과 API | 상태 기반 | GET .../{task_id} |
| REQ-STT-013 | 상태/결과 API | 유비쿼터스 | Redis 캐시 |
| REQ-STT-014 | 상태/결과 API | 이벤트 기반 | DELETE .../{task_id} |
| REQ-STT-015 | 전처리 | 이벤트 기반 | Celery 작업 |
| REQ-STT-016 | 전처리 | 유비쿼터스 | Celery 작업 |
| REQ-STT-017 | 전처리 | 이벤트 기반 | Celery 작업 |
| REQ-STT-018 | 전처리 | 상태 기반 | Celery 작업 |
| REQ-STT-019 | 헬스체크 | 이벤트 기반 | GET /api/v1/health |
| REQ-STT-020 | 헬스체크 | 이벤트 기반 | GET /api/v1/health/model |
| REQ-STT-021 | 헬스체크 | 이벤트 기반 | FastAPI lifespan |
| REQ-STT-022 | 헬스체크 | 유비쿼터스 | 모니터링 |

---

## Implementation Notes

### 구현 완료 정보

**구현 날짜**: 2026-03-15

**개발 모드**: TDD (RED-GREEN-REFACTOR)

### v1.1.0 변경 사항 (2026-06-13)

실제 코드베이스 감사 결과, 기본 STT 모델이 SPEC에 기재된 `whisper-large-v3-turbo`가 아닌 **mlx-community/whisper-small-mlx**로 구현되어 있다:

| 항목 | v1.0.0 (SPEC) | v1.1.0 (실제 구현) |
|------|---------------|-------------------|
| 기본 모델 | `whisper-large-v3-turbo` | `mlx-community/whisper-small-mlx` |
| 메모리 사용량 | 약 3-6GB | 약 1-2GB |
| Redis 캐시 TTL | 24시간 | 604800초 (7일, `cache_ttl_seconds`) |

**검증 소스**:
- `backend/app/config.py:39`: `whisper_model: str = "mlx-community/whisper-small-mlx"`
- `backend/ml/stt_engine.py:30`: `MLX_DEFAULT_MODEL = "mlx-community/whisper-small-mlx"`
- `backend/app/api/v1/transcription/transcription.py:57`: `model: str = Form(default="mlx-community/whisper-small-mlx")`
- `backend/app/api/v1/transcription/batch.py:50`: `model: str = Form(default="mlx-community/whisper-small-mlx")`
- `backend/app/config.py:57`: `cache_ttl_seconds: int = 604800` (7일)

> **참고**: `mlx-community/whisper-large-v3-turbo`는 모델 매핑 테이블에 존재하며(`stt_engine.py:39`), `WHISPER_MODEL` 환경 변수로 변경 가능하다. 단, 프로덕션 기본값은 `whisper-small-mlx`이다.

### 구현된 요구사항

모든 22개 EARS 요구사항 구현 완료:
- **REQ-STT-001 ~ REQ-STT-004**: 오디오 업로드 API 및 검증
- **REQ-STT-005 ~ REQ-STT-009**: STT 처리 워커 (mlx-whisper)
- **REQ-STT-010 ~ REQ-STT-014**: 작업 상태 및 결과 API
- **REQ-STT-015 ~ REQ-STT-018**: 오디오 전처리 및 청크 분할
- **REQ-STT-019 ~ REQ-STT-022**: 헬스체크 및 모델 관리

### 주요 구현 결정사항

1. **FastAPI 웹 프레임워크 선택**
   - 비동기 처리로 높은 동시성 지원
   - Pydantic v2로 강력한 입력 검증
   - 자동 OpenAPI/Swagger 문서 생성

2. **Celery + Redis 비동기 큐**
   - 장시간 STT 처리를 백그라운드에서 비동기 실행
   - Redis를 메시지 브로커 및 캐시로 활용
   - 작업 상태 추적 및 결과 저장

3. **MLX-Whisper 모델 선택**
   - Apple Silicon MPS 가속으로 최고 성능
   - 로컬 처리로 프라이버시 보장
   - mlx-community/whisper-small-mlx로 메모리 효율성 확보

4. **싱글톤 모델 인스턴스 관리**
   - WhisperEngine.get_instance()로 프로세스당 1개 모델 인스턴스
   - 첫 요청 시 지연 로딩(lazy load), 이후 재사용
   - 메모리 효율성과 성능의 균형

5. **30분 단위 오디오 청크 분할**
   - 긴 회의(>30분)를 청크 단위로 처리
   - 5초 오버랩으로 발화 경계 문제 해결
   - 순차 처리 및 결과 병합

6. **구조화된 로깅 (JSON)**
   - structlog으로 구조화된 JSON 로그 생성
   - 운영 환경에서 로그 분석 용이
   - 디버깅 및 모니터링 지원

### 테스트 결과

- 백엔드 전체: 3621 passed, 0 failed, coverage 100.00%
- 커밋: 6ada5f7 (feature/SPEC-MOBILE-002)

---

*SPEC ID: SPEC-STT-001*
*생성일: 2026-03-15*
*최종 수정: 2026-06-13*
*상태: completed*
