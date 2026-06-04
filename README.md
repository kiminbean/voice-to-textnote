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
✅ **완전한 STT 파이프라인**: STT → Diarization → Minutes → AI Summary 자동 처리
✅ **비동기 처리**: Celery 작업 큐로 장시간 처리 백그라운드 실행
✅ **PostgreSQL 영속성**: 회의록 및 이력 데이터 영구 저장
✅ **실시간 스트리밍**: SSE로 진행률 실시간 업데이트
✅ **API 보안**: API Key 인증, 레이트 리미팅, CORS, Security Headers
✅ **모니터링**: Prometheus 메트릭, 요청 ID 추적, 구조화된 로깅
✅ **프로덕션 배포**: Ubuntu systemd + Redis + Tailscale 원격 접속
✅ **완전한 테스트**: 2400+ 백엔드 테스트 (단위/통합/E2E) + Flutter 67, 98%+ 커버리지

## 주요 기능

### 음성 처리 파이프라인

#### 1. 오디오 업로드
- **엔드포인트**: `POST /api/v1/transcriptions`
- **지원 형식**: WAV, MP3, M4A, OGG
- **최대 크기**: 500MB
- **응답**: 고유 task_id 및 상태 조회 URL

#### 2. STT 처리 (mlx-whisper)
- **모델**: whisper-large-v3-turbo (WER < 5%)
- **언어**: 한국어 고정 또는 자동 감지
- **처리**: Apple Silicon MPS 가속
- **속도**: 약 0.3~0.5배 실시간

#### 3. 화자 분리 (Speaker Diarization)
- **모델**: pyannote.audio 3.1
- **처리**: CPU 기반 (GPU 미사용, 안정성 우선)
- **출력**: 타임스탬프와 화자 ID 매칭
- **DER**: < 15% (5명 이하 회의)

#### 4. 회의록 생성
- **입력**: STT + Diarization 결과
- **처리**: 화자별 발화 병합, 통계 계산
- **출력**: JSON 및 Markdown 형식
- **메타데이터**: 화자별 발화 시간, 횟수, 비율

#### 5. AI 요약 생성
- **모델**: Claude 3.5 Sonnet
- **추출**: 핵심 결정사항, 액션 아이템
- **포맷**: 구조화된 JSON
- **폴백**: API 실패 시 원문 텍스트로 자동 대체

### API 엔드포인트

#### 상태 조회
- **STT 상태**: `GET /api/v1/transcriptions/{task_id}/status`
- **DIA 상태**: `GET /api/v1/diarization/{task_id}/status`
- **요약 상태**: `GET /api/v1/summary/{task_id}/status`

#### 결과 조회
- **STT 결과**: `GET /api/v1/transcriptions/{task_id}`
- **회의록**: `GET /api/v1/minutes/{meeting_id}`
- **요약**: `GET /api/v1/summary/{summary_id}`

#### 회의 관리
- **목록 조회**: `GET /api/v1/history?page=1&limit=20&filter=status`
- **상세 조회**: `GET /api/v1/meetings/{meeting_id}`
- **삭제**: `DELETE /api/v1/meetings/{meeting_id}`

#### 실시간 스트리밍
- **SSE**: `GET /api/v1/stream/{task_id}` (진행률 실시간 푸시)

#### 모니터링
- **헬스체크**: `GET /api/v1/health` (API, Redis, Celery 상태)
- **준비 상태**: `GET /api/v1/ready` (모델 로드 확인)
- **메트릭**: `GET /metrics` (Prometheus 형식)

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

### 사전 요구사항

```bash
# Python 3.11+ 설치
brew install python@3.11

# 필수 도구 설치
brew install redis postgresql git

# ffmpeg 설치 (오디오 처리)
brew install ffmpeg
```

### 환경 설정

#### 1. 프로젝트 클론
```bash
git clone <repository-url>
cd voice-to-textnote

# 환경 변수 설정
cp .env.example .env.local
# .env.local 파일 편집 (CLAUDE_API_KEY 등 설정)
```

#### 2. Python 환경 설정
```bash
# 가상환경 생성
python3.11 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -e ".[dev]"
```

#### 3. 데이터베이스 초기화 (개발 환경)
```bash
# SQLite 자동 초기화 (개발 환경)
cd backend
python -c "from app.db.sync_engine import init_db; init_db()"
```

### 로컬 개발 환경 실행

#### 터미널 1: Redis 서버
```bash
redis-server
```

#### 터미널 2: Celery 워커
```bash
source venv/bin/activate
celery -A backend.workers.celery_app worker --loglevel=info --concurrency=1
```

#### 터미널 3: FastAPI 개발 서버
```bash
cd backend
uvicorn app.main:app --reload --host localhost --port 8000
```

#### 터미널 4: Flutter 앱 (웹)
```bash
cd client
flutter pub get
flutter run -d chrome
```

**API 문서**: http://localhost:8000/docs (Swagger UI)
**Flutter 앱**: http://localhost:50505

### 서버 배포 (Ubuntu + systemd)

#### 우분투 서버 설치
```bash
git clone https://github.com/kiminbean/voice-to-textnote.git
cd voice-to-textnote
bash deploy/setup-ubuntu.sh
```

#### 서비스 시작/중지
```bash
# .env 설정 후 서비스 시작
sudo systemctl start voicenote-api voicenote-worker

# 상태 확인
sudo systemctl status voicenote-api

# 로그 확인
journalctl -u voicenote-api -f

# 중지
sudo systemctl stop voicenote-api voicenote-worker
```

#### 외부 접속 (Tailscale)
- 서버와 클라이언트 모두 Tailscale 설치
- Flutter 앱에서 Tailscale IP로 접속 (예: `http://100.x.x.x:8000`)

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
# 백엔드 전체 테스트 (700개)
pytest backend/

# 커버리지 리포트 생성 (목표: 98%+)
pytest backend/ --cov=backend --cov-report=html --cov-report=term-missing

# 특정 테스트 실행
pytest backend/tests/unit/test_stt_engine.py -v
pytest backend/tests/integration/test_api.py -v

# Flutter 테스트 (67개)
cd client
flutter test
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

### 환경 변수 설정

`.env.local` 파일 예시:

```bash
# Backend
FASTAPI_HOST=localhost
FASTAPI_PORT=8000
DATABASE_URL=sqlite:///./voice_textnote.db  # 개발
LOG_LEVEL=INFO

# Redis & Celery
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Claude API
CLAUDE_API_KEY=sk-...

# API Security
API_KEY_SECRET=your-secret-key

# Model Paths (선택사항)
WHISPER_MODEL_PATH=/models/whisper/whisper-large-v3-turbo
PYANNOTE_MODEL_PATH=/models/pyannote
```

### API 보안

```bash
# API Key 생성
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Bearer Token 사용 (curl 예시)
curl -H "Authorization: Bearer YOUR_API_KEY" http://localhost:8000/api/v1/health
```

## 디렉토리 구조

```
backend/
├── app/
│   ├── main.py              # FastAPI 앱 초기화
│   ├── config.py            # 설정 (환경 변수)
│   ├── dependencies.py      # 의존성 주입 (DB, Redis, JWT)
│   ├── errors.py            # 공통 에러 헬퍼 (not_found, bad_request 등)
│   ├── exceptions.py        # 도메인 예외 계층 (VoiceNoteError + 14 서브클래스)
│   ├── error_handlers.py    # 전역 예외 핸들러 (JSON 통일 응답)
│   ├── lifecycle.py         # 앱 lifespan 관리
│   ├── middleware/           # 인증, 감사로깅, 보안헤더, Rate Limit
│   └── api/v1/              # 35개 라우터 (에러 헬퍼 기반)
│       ├── transcription.py
│       ├── summary.py
│       ├── search.py
│       └── ...
│
├── db/                      # 모델 전용 (서비스는 services/로 이동 완료)
│   ├── models.py            # SQLAlchemy 베이스 모델
│   ├── engine.py            # DB 엔진 관리
│   ├── *_models.py          # 도메인별 모델 (auth, bookmark, search 등)
│   └── service.py           # 공통 DB 서비스 유틸
│
├── services/                # 비즈니스 로직 (26개 서비스 통합)
│   ├── auth_service.py
│   ├── search_service.py
│   ├── summary_service.py
│   └── ...
│
├── schemas/                 # Pydantic 요청/응답 스키마 (20+)
│
├── workers/
│   ├── celery_app.py        # Celery 설정
│   └── tasks/               # 비동기 처리 태스크
│
├── ml/
│   └── stt_engine.py        # mlx-whisper 래퍼 (싱글톤)
│
├── pipeline/                # 오디오 처리 파이프라인
│
├── utils/                   # 로깅, 검증 유틸리티
│
├── tests/
│   ├── unit/                # 단위 테스트 (50+ 파일)
│   ├── integration/         # 통합 테스트
│   └── e2e/                 # E2E 테스트
│
└── conftest.py              # pytest 설정
```

## 설정 옵션

### 주요 설정 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DATABASE_URL` | `sqlite:///voice_textnote.db` | 데이터베이스 연결 (개발: SQLite, 프로덕션: PostgreSQL) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 연결 URL |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Celery 메시지 브로커 |
| `WHISPER_MODEL` | `whisper-large-v3-turbo` | Whisper 모델 이름 |
| `LANGUAGE` | `ko` | 전사 언어 코드 |
| `MAX_FILE_SIZE` | `500` | 최대 파일 크기 (MB) |
| `MAX_DURATION` | `14400` | 최대 재생 시간 (초) = 4시간 |
| `CHUNK_DURATION` | `1800` | 청크 크기 (초) = 30분 |
| `LOG_LEVEL` | `INFO` | 로그 레벨 (DEBUG, INFO, WARNING, ERROR) |
| `API_KEY_SECRET` | (필수) | API Key 암호화 시크릿 |
| `CLAUDE_API_KEY` | (필수) | Anthropic Claude API 키 |
| `RATE_LIMIT` | `60/minute` | IP당 분당 요청 제한 |
| `DATA_RETENTION_DAYS` | `30` | DB 데이터 보유 기간 |
| `TEMP_FILE_RETENTION_HOURS` | `24` | 임시 파일 보유 기간 |

### STT 동시 처리 제한

| 작업 | 동시 수 | 이유 |
|------|--------|------|
| STT (mlx-whisper) | 1~3개 | 메모리 사용 (6GB/개) |
| Diarization | 2개 | CPU 기반 처리 |
| Minutes 생성 | 3개 | 빠른 처리 |
| 요약 생성 | 2개 | Claude API 비용 관리 |

## 성능 특성

### 처리 시간

| 단계 | 시간 | 참고 |
|------|------|------|
| 오디오 업로드 | < 500ms | 파일 저장 + task_id 발급 |
| STT 처리 (1시간) | 20~30분 | 0.3~0.5배 실시간 (mlx-whisper) |
| Diarization (1시간) | 15~25분 | CPU 기반 (pyannote.audio) |
| Minutes 생성 | 1~5초 | 세그먼트 병합 및 통계 |
| AI 요약 생성 | 2~5초 | Claude API 응답 시간 |
| 상태 조회 | < 100ms | Redis 캐시 활용 |

### 리소스 사용량

| 항목 | 사용량 | 비고 |
|------|--------|------|
| STT 메모리 | ~6GB | mlx-whisper 모델 로드 |
| Diarization 메모리 | ~4GB | pyannote.audio 모델 로드 |
| FastAPI + Redis | ~2GB | 기본 운영 |
| 총합 | ~12GB | M4 Mac Mini 24GB 충분 |
| 동시 처리 | 1~3개 | 메모리 제약 기반 |

### 테스트 커버리지

| 항목 | 개수 | 커버리지 |
|------|------|---------|
| 백엔드 단위/통합 | 2400+개 | 98%+ |
| Flutter 테스트 | 67개 | - |
| E2E 테스트 | 16개 | 전체 파이프라인 |
| 총합 | 2480+개 | - |

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

### 인증 & 권한

- **JWT 인증**: 이메일/비밀번호 로그인, Access Token(15분) + Refresh Token(7일) Rotation
- **API Key 인증**: Bearer token 기반 API 키 검증 (기존 엔드포인트 호환)
- **RBAC**: 팀 내 역할 기반 접근 제어 (admin / member / viewer)

### API 보안

- **레이트 리미팅**: slowapi로 IP당 분당 요청 제한 (기본 60/minute)
- **CORS 정책**: 등록된 도메인만 허용
- **Security Headers**: HSTS, X-Content-Type-Options, X-Frame-Options 등
- **CSRF 보호**: Starlette 미들웨어

### 데이터 보안

- **전송 암호화**: 모든 HTTPS 통신 (자체 서명 인증서 포함)
- **저장 암호화**: 선택적 AES-256 암호화 (민감한 조직용)
- **클라우드 제약**: 로컬 전용 처리, 외부 업로드 불가

### 입력 검증

- **파일 형식**: WAV, MP3, M4A, OGG만 허용
- **파일 크기**: 최대 500MB
- **재생 시간**: 최대 4시간
- **Pydantic 검증**: 모든 API 요청 자동 검증

### 감사 로깅

- **요청 로깅**: 모든 API 호출 상세 기록
- **사용자 추적**: API 키로 사용자 행동 추적
- **에러 로깅**: 모든 예외 상황 기록
- **JSON 포맷**: 로그 분석 및 검색 용이

### 임시 파일 관리

- **자동 정리**: 24시간 후 /tmp의 오디오 파일 자동 삭제
- **캐시 정리**: Redis 캐시 24시간 TTL 자동 만료
- **DB 정리**: PostgreSQL 데이터 30일 후 자동 삭제
- **수동 삭제**: API로 언제든 수동 삭제 가능

## 제약 조건

### 시스템 요구사항

| 항목 | 요구사항 |
|------|---------|
| **OS** | macOS 12+ (Apple Silicon M1/M2/M3/M4) 또는 Linux |
| **RAM** | 최소 16GB, 권장 24GB+ |
| **Python** | 3.11 이상 |
| **Node.js** | 20+ (Flutter 웹 빌드용) |
| **의존성** | ffmpeg, PostgreSQL, Redis |

### 지원 플랫폼

| 플랫폼 | 상태 | 참고 |
|--------|------|------|
| **Web** | ✅ 완료 | Chrome, Firefox, Safari 지원 |
| **macOS** | ✅ 완료 | ARM64 (Apple Silicon) |
| **iOS** | 🔜 계획 | Flutter iOS 네이티브 구현 필요 |
| **Android** | 🔜 계획 | Flutter Android 네이티브 구현 필요 |

### 기술 제약

| 제약 | 설명 |
|------|------|
| **모델 로드** | Whisper 모델은 프로세스당 싱글톤으로 관리 |
| **MLX 지원** | Apple Silicon 최적화 (Intel Mac은 CPU 폴백) |
| **Redis 필수** | Celery 메시지 브로커 및 캐시로 필수 |
| **데이터베이스** | 개발: SQLite, 프로덕션: PostgreSQL 권장 |
| **파일 저장** | 최소 50GB 여유공간 필요 (모델 + 오디오) |

### 데이터 보유 정책

| 항목 | 기간 | 설명 |
|------|------|------|
| **DB 데이터** | 30일 | PostgreSQL에서 자동 삭제 |
| **임시 파일** | 24시간 | /tmp의 오디오 파일 자동 정리 |
| **Redis 캐시** | 24시간 | STT 결과 캐시 |
| **감사 로그** | 무제한 | 삭제 이력 영구 보관 |

## 아키텍처 개요

### 3계층 구조

```
┌─────────────────────────────────────┐
│   클라이언트 계층                     │
│   Flutter Web/macOS (Riverpod)      │
└────────────────┬────────────────────┘
                 │ HTTP/REST
┌────────────────▼────────────────────┐
│   API 계층                           │
│   FastAPI (Uvicorn)                 │
│   ├─ 보안: API Key, Rate Limit      │
│   ├─ 모니터링: Prometheus, Logging  │
│   └─ 실시간: SSE 스트리밍            │
└────────────────┬────────────────────┘
        ┌────────┼────────┐
        │        │        │
    ┌───▼──┐ ┌──▼────┐ ┌─▼──────┐
    │데이터│ │작업큐 │ │캐싱    │
    ├──────┤ ├───────┤ ├────────┤
    │PostgreSQL│Celery │ Redis  │
    │(영속)  │(비동기)│(임시)  │
    └───┬──┘ └──┬────┘ └────────┘
        │       │
        │   ┌───┴──────┬─────┬───────┐
        │   │          │     │       │
    ┌───▼──▼──┐  ┌──┬──┐ ┌──▼──┐ ┌─▼──────┐
    │모델 로드 │  │STT│DIA│MIN │ │요약   │
    │(싱글톤) │  └──┴──┘ └─────┘ │(Claude)│
    └────────┘                    └────────┘
```

## 배포 옵션

### 로컬 개발 환경 (macOS)

```bash
# Redis 시작
brew services start redis

# 백엔드 서버 시작
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

# Celery 워커 시작 (별도 터미널)
celery -A backend.workers.celery_app:celery_app worker --loglevel=info
```

### 프로덕션 배포 (Ubuntu + systemd)

```bash
# 원클릭 설치
git clone https://github.com/kiminbean/voice-to-textnote.git
cd voice-to-textnote
bash deploy/setup-ubuntu.sh

# 서비스 시작
sudo systemctl start voicenote-api voicenote-worker
```

### 외부 접속 (Tailscale)

- 서버/클라이언트에 Tailscale 설치 후 고정 IP로 접속
- 포트 개방 불필요, VPN 메시 네트워크로 보안 접속

## 다음 단계

### Phase 5 (계획)

- **고급 분석**: 발화 톤 분석, 감정 분석
- **통합**: Slack, Teams, Google Calendar 연동
- **OAuth**: Google/Apple 소셜 로그인
- **실시간 협업**: 공동 편집, 댓글 기능

## 라이선스

MIT License - 자유로운 상업적 사용 가능

---

## 기술 지원

| 항목 | 정보 |
|------|------|
| **문제 보고** | GitHub Issues 또는 이메일 |
| **기여** | Pull Requests 환영합니다 |
| **기술 문서** | `docs/` 디렉토리 참조 |
| **API 문서** | http://localhost:8000/docs (Swagger) |

---

**마지막 업데이트**: 2026-03-22
**버전**: 1.1.0
**상태**: Production Ready ✅ (25/25 SPECs 완료)

### 완료된 SPEC 목록

✅ SPEC-STT-001: Speech-to-Text (mlx-whisper)
✅ SPEC-DIA-001: Speaker Diarization (pyannote.audio)
✅ SPEC-MIN-001: Minutes Generation
✅ SPEC-SUM-001: AI Summary & Action Items
✅ SPEC-APP-001: Flutter Client (Web + macOS)
✅ SPEC-SEC-001: API Security
✅ SPEC-INFRA-001: Monitoring & Metrics
✅ SPEC-ERR-001: Error Handling
✅ SPEC-LOG-001: Audit Logging
✅ SPEC-DEPLOY-001: Ubuntu systemd 배포
✅ SPEC-DB-001: PostgreSQL & Alembic
✅ SPEC-SSE-001: Real-time Streaming
✅ SPEC-PERSIST-001: Data Persistence
✅ SPEC-LIFECYCLE-001: App Lifecycle
✅ SPEC-HISTORY-001: Meeting History API
✅ SPEC-RETENTION-001: Data Retention Policy
✅ SPEC-E2E-001: E2E Integration Tests
✅ SPEC-APP-002: Flutter Enhancement
✅ CI/CD: GitHub Actions Pipeline
✅ SPEC-TMPL-001: Meeting Templates
✅ SPEC-SEARCH-001: Full-text Search
✅ SPEC-SEARCH-002: Advanced Search (Filters/Sort/Autocomplete)
✅ SPEC-EXPORT-001: PDF Export
✅ SPEC-TEAM-001: JWT Auth + Team CRUD + Member Management + Meeting Share + Flutter Auth/Team UI
✅ SPEC-MOBILE-001: Mobile Optimization
