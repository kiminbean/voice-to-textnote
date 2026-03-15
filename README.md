# Voice to TextNote - 백엔드 (STT 파이프라인)

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.135+-green)
![mlx-whisper](https://img.shields.io/badge/mlx--whisper-0.4+-orange)
![License](https://img.shields.io/badge/License-MIT-blue)

프라이버시 보호 우선의 회의 자동 기록 시스템. **로컬 전용 처리**로 모든 음성 데이터를 조직 내에서만 관리합니다.

## 📋 목차

- [소개](#소개)
- [주요 기능](#주요-기능)
- [기술 스택](#기술-스택)
- [빠른 시작](#빠른-시작)
- [API 엔드포인트](#api-엔드포인트)
- [개발 설정](#개발-설정)
- [디렉토리 구조](#디렉토리-구조)
- [라이선스](#라이선스)

## 소개

**Voice to TextNote**는 FastAPI와 mlx-whisper를 기반으로 한 **로컬 음성 인식 백엔드**입니다.

### 주요 특징

✅ **프라이버시 최우선**: 모든 처리가 로컬에서만 수행되며, 클라우드 업로드 불가
✅ **Apple Silicon 최적화**: M1/M2/M3/M4 Mac에서 MPS 가속
✅ **높은 정확도**: Whisper Large-v3-Turbo 모델 (WER < 5%)
✅ **비동기 처리**: Celery 작업 큐로 장시간 STT 백그라운드 처리
✅ **Redis 캐시**: 24시간 TTL로 처리 결과 빠른 재조회
✅ **완전한 테스트**: 150개 테스트, 95.50% 커버리지

## 주요 기능

### 1. 오디오 업로드 API
- **엔드포인트**: `POST /api/v1/transcriptions`
- **지원 형식**: WAV, MP3, M4A, OGG
- **최대 크기**: 500MB
- **응답**: 고유 task_id 및 상태 조회 URL

### 2. STT 처리 (mlx-whisper)
- **모델**: whisper-large-v3-turbo
- **언어**: 한국어 고정 (`language="ko"`)
- **처리**: Apple Silicon MPS 가속 또는 CPU 폴백
- **속도**: 약 0.3~0.5배 실시간

### 3. 작업 상태 조회
- **엔드포인트**: `GET /api/v1/transcriptions/{task_id}/status`
- **상태**: pending, processing, completed, failed

### 4. 결과 조회 API
- **엔드포인트**: `GET /api/v1/transcriptions/{task_id}`
- **응답**: 전사 결과 (세그먼트, 타임스탬프, 신뢰도 점수)
- **캐싱**: Redis 24시간 TTL

### 5. 헬스체크
- **엔드포인트**: `GET /api/v1/health`
- **확인 항목**: FastAPI, Redis, Celery 워커 상태
- **모델 상태**: `GET /api/v1/health/model` (로드 상태, 메모리)

## 기술 스택

### 백엔드 프레임워크
- **FastAPI** 0.135+: 비동기 웹 프레임워크
- **uvicorn** 0.34+: ASGI 서버
- **Pydantic** 2.9+: 데이터 검증

### 음성 처리
- **mlx-whisper** 0.4+: Whisper STT 추론 (MLX 가속)
- **mlx** 0.31+: Apple Silicon ML 프레임워크
- **pydub** 0.25+: 오디오 처리 (ffmpeg 래핑)

### 비동기 작업
- **Celery** 5.6+: 작업 큐
- **Redis** 7.0+: 메시지 브로커 + 결과 캐시

### 개발/테스트
- **pytest** 8.0+: 테스트 프레임워크
- **pytest-cov** 4.0+: 커버리지 측정
- **ruff** 0.4+: 린터 (파이썬 코드 품질)

## 빠른 시작

### 로컬 개발 환경

#### 1. 사전 요구사항
```bash
# Python 3.11+ 설치
brew install python@3.11

# Redis 설치 (macOS)
brew install redis

# ffmpeg 설치 (오디오 처리 필수)
brew install ffmpeg
```

#### 2. 프로젝트 클론 및 환경 설정
```bash
git clone <repository-url>
cd voice-to-textnote

# Python 가상환경 생성
python3.11 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -e ".[dev]"
```

#### 3. Redis 시작
```bash
# 터미널 1: Redis 서버
redis-server

# 터미널 2: Celery 워커
celery -A backend.workers.celery_app worker --loglevel=info --concurrency=1
```

#### 4. FastAPI 서버 시작
```bash
# 터미널 3: FastAPI 개발 서버
cd backend
uvicorn app.main:app --reload --host localhost --port 8000
```

**API 문서**: http://localhost:8000/docs (Swagger UI)

### Docker를 사용한 실행

```bash
# Docker Compose로 전체 스택 실행 (FastAPI, Redis, Celery)
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 중지
docker-compose down
```

## API 엔드포인트

### 1. 오디오 업로드
```http
POST /api/v1/transcriptions
Content-Type: multipart/form-data

file: <audio_file>
language: ko (기본값)
```

**응답 (201 Created)**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "status_url": "/api/v1/transcriptions/550e8400-e29b-41d4-a716-446655440000/status",
  "result_url": "/api/v1/transcriptions/550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2026-03-15T10:30:00Z"
}
```

### 2. 작업 상태 조회
```http
GET /api/v1/transcriptions/{task_id}/status
```

**응답**:
```json
{
  "task_id": "550e8400-...",
  "status": "processing",
  "progress": 45,
  "created_at": "2026-03-15T10:30:00Z",
  "started_at": "2026-03-15T10:30:05Z",
  "completed_at": null
}
```

### 3. 전사 결과 조회
```http
GET /api/v1/transcriptions/{task_id}
```

**응답 (completed)**:
```json
{
  "task_id": "550e8400-...",
  "status": "completed",
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 2.5,
      "text": "안녕하세요.",
      "confidence": 0.98
    },
    {
      "id": 1,
      "start": 2.5,
      "end": 5.0,
      "text": "오늘 회의를 시작하겠습니다.",
      "confidence": 0.97
    }
  ],
  "language": "ko",
  "total_duration": 300.5,
  "created_at": "2026-03-15T10:30:00Z",
  "completed_at": "2026-03-15T10:35:00Z"
}
```

### 4. 헬스체크
```http
GET /api/v1/health
```

**응답**:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2026-03-15T10:40:00Z",
  "components": {
    "api": "healthy",
    "redis": "healthy",
    "celery_workers": "healthy"
  }
}
```

### 5. 모델 상태
```http
GET /api/v1/health/model
```

**응답**:
```json
{
  "model_loaded": true,
  "model_name": "whisper-large-v3-turbo",
  "memory_usage_mb": 3200,
  "memory_limit_mb": 19200,
  "device": "mps"
}
```

## 개발 설정

### 테스트 실행
```bash
# 전체 테스트
pytest

# 커버리지 리포트 생성
pytest --cov=backend --cov-report=term-missing

# 특정 테스트만 실행
pytest backend/tests/unit/test_stt_engine.py -v
```

### 코드 품질 검사
```bash
# 린터 (ruff)
ruff check backend/

# 자동 포맷팅
ruff format backend/

# 타입 체킹 (선택)
mypy backend/ --ignore-missing-imports
```

### 개발 환경 변수
```bash
# .env.local 파일 생성
cp .env.example .env.local

# 필요한 변수 설정
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
WHISPER_MODEL=whisper-large-v3-turbo
LOG_LEVEL=INFO
```

## 디렉토리 구조

```
backend/
├── app/
│   ├── main.py              # FastAPI 앱 초기화
│   ├── config.py            # 설정 (환경 변수)
│   ├── dependencies.py      # 의존성 주입 (Redis, 모델)
│   └── api/v1/
│       ├── transcription.py # 전사 API 엔드포인트
│       └── health.py        # 헬스체크 엔드포인트
│
├── schemas/
│   ├── transcription.py     # Pydantic 요청/응답 스키마
│   └── health.py            # 헬스 스키마
│
├── workers/
│   ├── celery_app.py        # Celery 설정
│   └── tasks/
│       └── transcription_task.py # STT 처리 작업
│
├── ml/
│   └── stt_engine.py        # mlx-whisper 래퍼 (싱글톤)
│
├── pipeline/
│   ├── audio_processor.py   # 오디오 전처리 (16kHz 모노, 정규화)
│   └── chunk_manager.py     # 청크 분할 및 병합
│
├── utils/
│   ├── logger.py            # 구조화된 로깅
│   └── validators.py        # 입력 검증 (형식, 크기)
│
├── tests/
│   ├── unit/                # 단위 테스트
│   │   ├── test_stt_engine.py
│   │   ├── test_transcription_task.py
│   │   ├── test_audio_processor.py
│   │   └── test_schemas.py
│   └── integration/         # 통합 테스트
│       └── test_api.py
│
└── conftest.py              # pytest 설정
```

## 설정 옵션

### `backend/app/config.py`

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 연결 URL |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Celery 메시지 브로커 |
| `WHISPER_MODEL` | `whisper-large-v3-turbo` | Whisper 모델 이름 |
| `LANGUAGE` | `ko` | 전사 언어 코드 |
| `MAX_FILE_SIZE` | `500` | 최대 파일 크기 (MB) |
| `MAX_DURATION` | `14400` | 최대 재생 시간 (초) = 4시간 |
| `CHUNK_DURATION` | `1800` | 청크 크기 (초) = 30분 |
| `LOG_LEVEL` | `INFO` | 로그 레벨 |
| `CONCURRENCY` | `1` | Celery 동시 작업 수 |

## 성능 특성

| 항목 | 성능 | 비고 |
|------|------|------|
| 업로드 응답 시간 | < 500ms | 파일 저장 + task_id 발급 |
| STT 처리 속도 | 0.3~0.5배 실시간 | 30분 회의 = 15~25분 처리 |
| 상태 조회 응답 시간 | < 100ms | Redis 캐시 활용 |
| 메모리 사용 | ~6GB | mlx-whisper 모델 + 추가 처리 |
| 동시 처리 능력 | 1~3개 | Celery 워커 수 + 메모리 제약 |

## 모니터링 및 로깅

### 로그 확인
```bash
# FastAPI 로그
tail -f logs/app.log

# Celery 워커 로그
celery -A backend.workers.celery_app worker --loglevel=info
```

### JSON 로그 포맷
```json
{
  "timestamp": "2026-03-15T10:30:00Z",
  "level": "INFO",
  "logger": "backend.app.api.v1.transcription",
  "message": "오디오 파일 업로드",
  "task_id": "550e8400-...",
  "file_size_mb": 45.2,
  "duration_seconds": 300.5
}
```

## 보안

### 로컬 전용 서비스
- 모든 HTTP 통신이 `localhost`에서만 가능
- CORS는 로컬 포트(8000, 3000 등)만 허용

### 입력 검증
- 오디오 파일 형식 검증 (WAV, MP3, M4A, OGG만 허용)
- 파일 크기 검증 (최대 500MB)
- 재생 시간 검증 (최대 4시간)

### 임시 파일 관리
- 처리 완료 후 임시 오디오 파일 자동 삭제
- 삭제 요청 시 모든 캐시, 결과, 파일 제거

## 제약 조건

### 시스템 요구사항
- **OS**: macOS 12+ (Apple Silicon M1/M2/M3/M4)
- **RAM**: 최소 16GB, 권장 24GB
- **Python**: 3.11 이상
- **ffmpeg**: 시스템 PATH에 설치

### 기술 제약
- **단일 프로세스 모델**: Whisper 모델은 프로세스당 싱글톤으로 관리
- **MLX 지원**: Apple Silicon 필수 (Intel Mac은 CPU 폴백만 가능)
- **Redis 필수**: Celery 메시지 브로커 및 캐시로 반드시 필요

## 라이선스

MIT License - 자유로운 상업적 사용 가능

---

## 문의 및 기여

- 문제 보고: GitHub Issues
- 기여: Pull Requests 환영합니다
- 기술 문서: `docs/` 디렉토리 참조

---

**마지막 업데이트**: 2026-03-15
**버전**: 0.1.0
**상태**: Production Ready ✅
