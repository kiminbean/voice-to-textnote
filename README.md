# Voice to TextNote - 백엔드 (STT 파이프라인)

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.135+-green)
![mlx-whisper](https://img.shields.io/badge/mlx--whisper-0.4+-orange)
![License](https://img.shields.io/badge/License-All%20Rights%20Reserved-red)

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
✅ **모던 UI/UX**: 모던 미니멀 디자인 시스템 (인디고/바이올렛), 다크모드 지원, 반응형 레이아웃
✅ **자동화 테스트**: 3907 백엔드 테스트 (단위/통합/E2E) + Flutter 415, 백엔드 100.00% 커버리지

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
- **모델**: OpenAI `gpt-4o-mini`
- **추출**: 핵심 결정사항, 액션 아이템
- **포맷**: 구조화된 JSON
- **폴백**: API 실패 시 원문 텍스트로 자동 대체

#### 6. 감정 분석 (Sentiment Analysis)
- **모델**: OpenAI `gpt-4o-mini`
- **입력**: 회의록 세그먼트 (minutes 결과)
- **처리**: 구간별/화자별 감정 분석, 감정 타임라인 추출
- **출력**: 전체 감정 분포, 화자별 감정 통계, 감정 변화 타임라인
- **레이블**: positive/neutral/negative + 세부 감정 (joy/satisfaction/frustration/anger/sadness/surprise)
- **동시성**: 최대 3개 작업 (설정 가능)

#### 7. 발화 톤/운율 분석 (Speech Tone/Prosody Analysis)
- **엔진**: opensmile eGeMAPSv02 (88차원) + librosa (F0/RMS/speaking rate)
- **분류**: 5-class (calm/excited/authoritative/hesitant/monotone) + unknown
- **처리**: DIA wav 세그먼트 슬라이싱 후 prosody 특징 추출
- **출력**: 세그먼트별 tone, 화자별 tone 분포, 전체 dominant tone
- **비활성화**: tone_model 빈 값 시 503 Service Unavailable

#### 8. Obsidian Vault 연계 (SPEC-OBSIDIAN-001)
- **방식**: Direct file write (로컬 vault 폴더에 .md 파일 atomic write)
- **자동화**: 파이프라인 완료 시 자동 export (설정 토글)
- **노트 포맷**: YAML frontmatter + 개요 + 액션 아이템 + 주요 결정 + 회의록 + 감정/톤 분석 + 위키링크
- **보안**: 경로 탐색 방지, 심볼릭 링크 거부, vault 외부 작성 차단
- **API**: `POST /api/v1/obsidian/config`, `POST /api/v1/obsidian/export/{meeting_id}`, `POST /api/v1/obsidian/validate`
- **클라이언트**: 내보내기 메뉴 "Obsidian에 저장" + `obsidian://` URI로 "Obsidian에서 열기"

#### 9. Cross-Meeting Q&A 근거 검색
- **목적**: 특정 회의를 먼저 고르지 않아도 질문과 관련된 회의록/요약/Study Pack/영업 브리프 근거를 찾음
- **방식**: 자연어 질문을 검색 핵심어로 정규화하고 기존 SQLite FTS5 인덱스를 관련도순 검색
- **출력**: 근거 기반 합성 답변, task ID, 작업 유형, 스니펫, 생성/완료 시각
- **클라이언트**: 검색 화면 상단에 AI 근거 검색 패널로 관련 회의 바로 열기 지원
- **API**: `POST /api/v1/qa/ask-across`

### API 엔드포인트

#### 상태 조회
- **STT 상태**: `GET /api/v1/transcriptions/{task_id}/status`
- **DIA 상태**: `GET /api/v1/diarization/{task_id}/status`
- **요약 상태**: `GET /api/v1/summary/{task_id}/status`

#### 결과 조회
- **STT 결과**: `GET /api/v1/transcriptions/{task_id}`
- **회의록**: `GET /api/v1/minutes/{meeting_id}`
- **요약**: `GET /api/v1/summary/{summary_id}`

#### Q&A
- **회의별 질문**: `POST /api/v1/qa/ask`
- **여러 회의 근거 검색**: `POST /api/v1/qa/ask-across`
- **Q&A 이력**: `GET /api/v1/qa/{task_id}/history`

#### 번역
- **회의록/요약 번역 생성**: `POST /api/v1/minutes/{task_id}/translation`
- **캐시된 번역 조회**: `GET /api/v1/minutes/{task_id}/translation?target_language=en`

#### 영업 브리프
- **고객 후속 브리프 생성**: `POST /api/v1/minutes/{task_id}/sales-contact-brief`
- **고객/회사 목록 조회**: `GET /api/v1/sales-contacts?q=Acme`
- **CRM CSV 내보내기**: `GET /api/v1/sales-contacts/export.csv`

#### 외부 자료 가져오기
- **URL/Transcript 가져오기**: `POST /api/v1/imports/external-text`
- **문서/이미지 가져오기**: `POST /api/v1/imports/document`

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

### 클라이언트 UI/UX

- **디자인 시스템**: 중앙 집중식 토큰(`client/lib/theme/`)으로 컬러·타이포그래피·스페이싱 일관성 확보. 모던 미니멀 미학(Linear/Notion 계열), 인디고/바이올렛 브랜드 컬러.
- **다크모드**: 시스템/라이트/다크 3모드 토글 지원. `SharedPreferences`로 사용자 선택 영속화. 모든 컴포넌트가 시맨틱 스킴을 통해 자동 전환.
- **핵심 화면**: 로그인(브랜드 로고 + 소셜), 홈(SliverAppBar + 풀투리프레시 + 빈 상태 CTA), 녹음(펄스 애니메이션 + 모노스페이스 타이머), 결과(8개 탭 + 2x2 통계 그리드), 설정(테마/데이터/계정).
- **접근성**: `Semantics` 라벨링(WCAG 2.1 AA), 한국어/영어 국제화(ARB 36키), 600px+ 반응형 레이아웃.
- **공유 컴포넌트**: `StatusBadge`, `EmptyStateWidget`, `MeetingCard`, `PipelineProgress`(스텝 인디케이터), `SpeakerSegment`(10색 팔레트 + 검색 하이라이트).

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
# .env.local 파일 편집 (OPENAI_API_KEY 등 설정)
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

개발용 SQLite 테이블은 FastAPI 시작 시 `backend.app.lifecycle.validate_startup()`에서 자동 생성됩니다. 별도 초기화 명령 없이 아래 개발 서버를 실행하면 됩니다.

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
source venv/bin/activate
uvicorn backend.app.main:app --reload --host localhost --port 8000
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
ruff check backend/ client/scripts

# 자동 포맷팅
ruff format backend/

# 타입 체킹
mypy backend/ client/scripts --ignore-missing-imports
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

# OpenAI API
OPENAI_API_KEY=sk-...

# API Security
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
API_KEYS=<generated-api-key>

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
| `API_KEYS` | (프로덕션 필수) | 쉼표로 구분된 API Key 목록 |
| `JWT_SECRET` | (프로덕션 필수) | JWT 서명 시크릿. 32자 이상의 랜덤 문자열 필요 |
| `FIREBASE_CREDENTIALS_PATH` | (프로덕션 필수) | Firebase Admin SDK 서비스 계정 JSON 경로. Docker 프로덕션 compose는 이 파일을 읽기 전용 secret mount로 주입 |
| `OPENAI_API_KEY` | (필수) | OpenAI API 키 (gpt-4o-mini 모델 - 요약/감정분석) |
| `RATE_LIMIT` | `60/minute` | IP당 분당 요청 제한 |
| `DATA_RETENTION_DAYS` | `30` | DB 데이터 보유 기간 |
| `TEMP_FILE_RETENTION_HOURS` | `24` | 임시 파일 보유 기간 |

### STT 동시 처리 제한

| 작업 | 동시 수 | 이유 |
|------|--------|------|
| STT (mlx-whisper) | 1~3개 | 메모리 사용 (6GB/개) |
| Diarization | 2개 | CPU 기반 처리 |
| Minutes 생성 | 3개 | 빠른 처리 |
| 요약 생성 | 2개 | OpenAI API 비용 관리 |

## 성능 특성

### 처리 시간

| 단계 | 시간 | 참고 |
|------|------|------|
| 오디오 업로드 | < 500ms | 파일 저장 + task_id 발급 |
| STT 처리 (1시간) | 20~30분 | 0.3~0.5배 실시간 (mlx-whisper) |
| Diarization (1시간) | 15~25분 | CPU 기반 (pyannote.audio) |
| Minutes 생성 | 1~5초 | 세그먼트 병합 및 통계 |
| AI 요약 생성 | 2~5초 | OpenAI API 응답 시간 |
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
| 백엔드 단위/통합/E2E | 3907개 | 100.00% |
| Flutter 테스트 | 415개 | - |
| E2E 테스트 | 16개 | 전체 파이프라인 |
| 총합 | 4322개 | - |

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
| **Android 빌드** | Android SDK 36, Build Tools 36.0.0/28.0.3, NDK 27.0.12077973, CMake 3.22.1 |
| **iOS 빌드** | Xcode 26.5+, CocoaPods 1.16.2+, iOS deployment target 15.0 |

### 지원 플랫폼

| 플랫폼 | 상태 | 참고 |
|--------|------|------|
| **Web** | ✅ 완료 | Chrome, Firefox, Safari 지원 |
| **macOS** | ✅ 완료 | ARM64 (Apple Silicon) |
| **iOS** | RC | `flutter build ios --debug --no-codesign` 검증 완료, strict 실기기 release evidence 필요 |
| **Android** | RC | `flutter build apk --release` 검증 완료, strict 실기기 release evidence 필요 |

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
│   Flutter Web/macOS/iOS/Android     │
│   Riverpod + native mobile bridges  │
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
    │(싱글톤) │  └──┴──┘ └─────┘ │(OpenAI)│
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

### 모바일 네이티브 검증

```bash
cd client

# 기본 게이트: pub get, analyze, test, local STT smoke
./scripts/verify_mobile.sh

# 네이티브 게이트: 기본 게이트 + Android APK + iOS no-codesign build
./scripts/verify_mobile.sh --native
```

검증된 로컬 Android SDK 경로는 `/Users/ibkim/Library/Android/sdk`이며, Flutter 설정은 `flutter config --android-sdk /Users/ibkim/Library/Android/sdk`로 고정했다. CI는 `.github/workflows/mobile.yml`에서 Android SDK 36과 필요한 build tools를 설치한다. iOS는 `client/ios/Flutter/Profile.xcconfig`가 `Pods-Runner.profile.xcconfig`를 include해야 Profile 빌드에서 CocoaPods 설정이 누락되지 않는다.

### 모바일 릴리스 readiness

```bash
# 로컬/CI 기본 사전검사: Firebase, App Store metadata, native wiring, release docs
python3 client/scripts/verify_release_readiness.py

# signed Android/iOS native gate: Android keystore secret, 연결 기기, native artifact 필요
cd client && REQUIRE_ANDROID_RELEASE_SIGNING=true ./scripts/verify_mobile.sh --native

# 실기기 릴리스 게이트: 외부 secret, 연결 기기, Push/딥링크/녹음/공유 evidence 필요
REQUIRE_ANDROID_RELEASE_SIGNING=true \
RELEASE_E2E_EVIDENCE_PATH=docs/release-e2e-evidence.example.json \
python3 client/scripts/verify_release_readiness.py --strict
```

`--strict`는 예제 파일을 그대로 통과시키는 용도가 아니다. `docs/release-e2e-evidence.example.json`을 복사해 실제 Android/iOS 기기 ID, 빌드 산출물, Push/딥링크/백그라운드 녹음/HTTP 정책/PDF 공유 시나리오 증거로 채운 뒤 실행한다. Android release APK는 `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`로 복원한 keystore로 서명하고 `REQUIRE_ANDROID_RELEASE_SIGNING=true ./scripts/verify_mobile.sh --native`에서 `apksigner verify --print-certs`까지 통과해야 한다. 필요한 환경 변수와 scenario key 매핑은 `docs/e2e-device-checklist.md`에 있다.

```bash
# Generate an editable scaffold with every required release E2E scenario key
ANDROID_DEVICE_SERIAL=<adb-device-serial> IOS_DEVICE_UDID=<ios-device-udid> \
REQUIRE_ANDROID_RELEASE_SIGNING=true \
python3 client/scripts/create_release_e2e_evidence.py --output docs/release-e2e-evidence.json
```

GitHub Actions에서도 동일한 strict 게이트를 실행할 수 있다. `.github/workflows/mobile.yml`의 `workflow_dispatch`에 `evidence_path`를 입력하면 `mobile-release` GitHub Environment와 `self-hosted`, `macOS`, `mobile-release` 라벨을 가진 러너에서 `python3 client/scripts/verify_mobile_release_runner.py`, `REQUIRE_ANDROID_RELEASE_SIGNING=true ./scripts/verify_mobile.sh --native`, `python3 client/scripts/verify_release_readiness.py --strict` 순서로 실행한다. 필요한 Android signing/Firebase/APNs/App Store Connect secrets와 Android/iOS device vars는 `docs/e2e-device-checklist.md`의 GitHub Actions strict release gate 표를 따른다.

```bash
# macOS runner candidate preflight: toolchain + physical Android/iOS availability
ANDROID_DEVICE_SERIAL=<adb-device-serial> IOS_DEVICE_UDID=<ios-device-udid> \
python3 client/scripts/verify_mobile_release_runner.py

# GitHub Environment, self-hosted runner labels, secret/variable names preflight
python3 client/scripts/verify_github_mobile_release_env.py --repo kiminbean/voice-to-textnote

# Configure Environment secrets/vars from same-named local env vars, then verify
python3 client/scripts/configure_github_mobile_release_env.py --repo kiminbean/voice-to-textnote
```

## 다음 단계

### Phase 7 (완료) — Release Candidate

Phase 1-7의 핵심 릴리스 SPEC이 모두 구현 완료된 상태다. 자동화/빌드 게이트는 통과했으며, 최종 전환 상태는 strict 실기기 release evidence 대기다.

- **Phase 7 완료 항목**: 텍스트 감정 분석 (SPEC-SENTIMENT-001, OpenAI gpt-4o-mini), 음성 톤/운율 분석 (SPEC-TONE-001, opensmile eGeMAPSv02 + librosa), 보안 강화 (SPEC-SEC-002, 매직 바이트 검증 + iOS ATS/Android Network Security)
- **직전 완료**: 실시간 협업 편집 (SPEC-COLLAB-001), 오프라인 STT 하이브리드 (SPEC-MOBILE-002), 모바일 프로덕션 (SPEC-MOBILE-004/005)

### Phase 8 (진행 중) — 생태계 확장

- **SPEC-OBSIDIAN-001 완료**: Obsidian Vault 연계 — 회의록/요약/감정·톤 분석을 로컬 Obsidian vault에 자동 기록 (Direct file write + YAML frontmatter + wikilinks)

### 향후 로드맵

- **i18n**: 11개 언어 다국어 지원
- **클라우드 동기화**: 멀티 기기 지원
- **Slack/Teams 연동**: 외부 협업 도구 통합
- **OAuth**: Google/Apple 소셜 로그인

## 라이선스

Copyright (c) 2026 kiminbean. **All Rights Reserved.**

본 프로젝트의 모든 소스 코드, 문서, 바이너리 형태를 포함한 일체(이하 "소프트웨어")는 사유재산이며, 저작권자의 사전 서면 허가 없이 복제·배포·수정·게시·전송·방송·상업적 활용 등 일체의 사용을 엄격히 금지합니다. 허가 없는 사용은 저작권법 위반에 해당합니다.

타사 컴포넌트는 각각의 원래 라이선스를 유지합니다:
- `opensmile` (AGPL-3.0): SPEC-TONE-001 톤 분석에 사용되며, **로컬 전용 처리** 환경에서만 활성화. 외부 네트워크 서비스/SaaS 형태로 tone 기능 제공 시 AGPL 소스 공개 의무 또는 대체 구현 필요.
- 기타 의존성: 각 업스트림 라이선스 준수.

라이선스 문의, 상업적 사용, 재배포 허가: kiminbean@gmail.com

---

## 기술 지원

| 항목 | 정보 |
|------|------|
| **문제 보고** | GitHub Issues 또는 이메일 |
| **기여** | Pull Requests는 사전 협의된 기여자에 한함 |
| **기술 문서** | `docs/` 디렉토리 참조 |
| **API 문서** | http://localhost:8000/docs (Swagger) |

---

**마지막 업데이트**: 2026-06-17
**버전**: 1.7.0
**상태**: Phase 8 진행 중 — SPEC-OBSIDIAN-001 Obsidian Vault 연계 완료 + UI 재설계(디자인 시스템, 다크모드) 완료, 감정/톤 분석 활성화, 라이선스 All Rights Reserved 전환
**최근 확인**: 백엔드 3907 테스트 + Flutter 415 테스트 + Flutter analyze + 기본 Release Readiness 통과. Strict release readiness는 Android signing/Firebase/APNs/App Store Connect secret, Android/iOS 실기기, 실제 E2E evidence가 준비되어야 통과 가능.

### 구현 완료 SPEC 목록

아래 SPEC은 코드와 자동화 게이트 기준으로 구현 완료 상태다. App Store Connect/APNs/Firebase 실계정, Android/iOS 실기기 Push/딥링크/백그라운드 녹음/공유/HTTP 정책 검증은 `python3 client/scripts/verify_release_readiness.py --strict`와 `RELEASE_E2E_EVIDENCE_PATH`가 통과해야 최종 release-ready로 본다.

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
✅ SPEC-MOBILE-004: 모바일 프로덕션 완성 (Push 알림, 백그라운드 녹음, 권한 재확인, 녹음 복구)
✅ SPEC-COLLAB-001: 실시간 협업 편집 (WebSocket + LWW + Presence + Flutter 클라이언트)
✅ SPEC-MOBILE-002: 오프라인 STT 하이브리드 파이프라인 (모델 관리 + 로컬 전사 + 재처리 큐)
✅ SPEC-MOBILE-005: iOS 백그라운드 녹음 안정성 고도화 (인터럽션 처리 + 백그라운드 태스크 + 라이프사이클 + 복구)
✅ SPEC-SEC-002: 보안 강화 — 매직 바이트 검증 + iOS ATS/Android Network Security + 보안 헤더 고도화
✅ SPEC-SENTIMENT-001: 텍스트 감정 분석 — OpenAI gpt-4o-mini 기반 화자별/구간별 감정 분석 + 타임라인 + Flutter 전용 탭
✅ SPEC-TONE-001: 발화 톤/운율 분석 — opensmile eGeMAPSv02 + librosa 기반 prosody 추출, 5-class 톤 분류, Flutter tone timeline
✅ SPEC-BUGFIX-002: 버그 fix 후속 작업 — asyncio.to_thread 회귀 테스트, collab Lua script atomic race condition 해결, FCM timebomb 예방, version_service UniqueConstraint + Alembic migration, temp file leak AST gate, 운영 로그 category 필드
✅ SPEC-TECHDEBT-001: 기술 부채 정리 — datetime.utcnow() 38곳 전환, asyncio.get_event_loop() 3곳 대체, Pydantic class-based Config 5곳 ConfigDict 전환, pytest-asyncio 설정
✅ SPEC-UX-002: 사용자 경험 개선 — 접근성 Semantics 라벨링, 국제화 인프라 (ko/en ARB + gen-l10n), 홈 화면 반응형 마스터-디테일, 마이크로 인터랙션 (햅틱 피드백, Hero 애니메이션)
✅ SPEC-RELEASE-001: Release Readiness 절차 — Release Candidate → Production Ready 전환 5단계 실행 가이드 (Firebase, APNs, App Store Connect, 물리 기기 E2E, self-hosted runner)
✅ SPEC-OBSIDIAN-001: Obsidian Vault 연계 — Direct file write 방식 회의록/요약/감정·톤 분석 자동 기록, YAML frontmatter, wikilinks, atomic write (os.link), 경로 탐색 방지, 10라운드 Oracle 심사 통과 (17개 버그 수정, 30개 회귀 테스트)
