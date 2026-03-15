# Voice to TextNote - 프로젝트 구조

## 최상위 디렉토리 구조

```
voice-to-textnote/
├── backend/                    # FastAPI 서버, Celery 워커, 음성 처리 파이프라인
├── client/                     # Flutter 크로스플랫폼 클라이언트 (웹/iOS/Android/macOS)
├── models/                     # 사전 학습된 모델 파일 및 구성
├── scripts/                    # 개발 설정, 모델 다운로드 자동화
├── tests/                      # 통합 및 E2E 테스트
├── docs/                       # 프로젝트 문서 및 아키텍처 다이어그램
├── docker-compose.yml          # 로컬 개발 환경 설정 (FastAPI, Redis, Celery)
├── .env.example                # 환경 변수 템플릿
├── pyproject.toml              # Python 의존성 관리
├── pubspec.yaml                # Flutter 의존성 관리
└── README.md                   # 프로젝트 개요 및 빠른 시작 가이드
```

## 백엔드 디렉토리 구조

### `/backend/` - FastAPI 서버 및 음성 처리 파이프라인

**목적**:
- RESTful API 엔드포인트 제공
- 음성 파일 수신 및 저장
- Celery 비동기 작업 큐 관리
- STT, 스피커 식별, AI 요약 작업 조율

**구조**:

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 앱 초기화 및 라우팅 설정
│   ├── config.py               # 환경 설정 (DB, Redis, API 키)
│   ├── dependencies.py         # 의존성 주입 (DB 세션, 인증)
│   │
│   ├── api/
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── router.py       # 모든 엔드포인트 통합 라우터
│   │   │   ├── audio.py        # 오디오 녹음 업로드, 조회 엔드포인트
│   │   │   ├── transcription.py # STT 결과 조회, 상태 확인 엔드포인트
│   │   │   ├── meeting.py      # 회의 생성, 조회, 삭제 엔드포인트
│   │   │   ├── users.py        # 사용자 관리, 팀 멤버 엔드포인트
│   │   │   └── exports.py      # 회의록 내보내기 (PDF, Markdown)
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py         # SQLAlchemy 데이터베이스 모델
│   │   ├── meeting.py          # 회의(Meeting) 모델
│   │   ├── audio.py            # 오디오 파일(Audio) 모델
│   │   ├── transcription.py    # 전사(Transcription) 모델
│   │   ├── speaker.py          # 스피커 정보(Speaker) 모델
│   │   └── user.py             # 사용자(User) 모델
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── audio.py            # Pydantic 요청/응답 스키마 (AudioUpload, AudioResponse)
│   │   ├── transcription.py    # 전사 스키마 (TranscriptionRequest, TranscriptionResponse)
│   │   ├── meeting.py          # 회의 스키마 (MeetingCreate, MeetingResponse)
│   │   ├── speaker.py          # 스피커 스키마
│   │   └── user.py             # 사용자 스키마
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── storage_service.py  # 로컬 파일시스템 또는 S3 저장소 관리
│   │   ├── auth_service.py     # JWT 토큰 발급, 검증
│   │   └── notification_service.py # 이메일/Slack 알림 발송
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logger.py           # 중앙화된 로깅 설정
│       └── validators.py       # 입력값 검증 함수
│
├── workers/
│   ├── __init__.py
│   ├── celery_app.py           # Celery 앱 초기화 및 설정
│   │
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── transcription_task.py # STT 처리 Celery 작업
│   │   ├── diarization_task.py   # 스피커 식별 Celery 작업
│   │   ├── summary_task.py       # AI 요약 Celery 작업
│   │   └── export_task.py        # 회의록 내보내기 Celery 작업
│   │
│   └── pipeline/
│       ├── __init__.py
│       ├── audio_processor.py   # 오디오 전처리 (샘플링, 노이즈 제거)
│       └── orchestrator.py      # 작업 흐름 관리 (STT → Diarization → Summary)
│
├── ml/
│   ├── __init__.py
│   ├── stt_engine.py           # mlx-whisper 래퍼 (음성 인식)
│   ├── diarization_engine.py   # pyannote.audio 래퍼 (스피커 식별)
│   ├── claude_summarizer.py    # Claude API 통합 (요약 생성)
│   └── models/
│       ├── whisper_config.py   # Whisper 모델 설정
│       └── pyannote_config.py  # Pyannote 모델 설정
│
├── tests/
│   ├── __init__.py
│   ├── test_api.py             # API 엔드포인트 단위 테스트
│   ├── test_services.py        # 서비스 로직 테스트
│   ├── test_ml_models.py       # ML 모델 통합 테스트
│   └── fixtures/
│       ├── sample_audio.wav    # 테스트용 샘플 오디오 파일
│       └── mock_data.py        # 모의 데이터
│
├── requirements.txt            # Python 의존성
├── pyproject.toml              # 프로젝트 메타데이터
└── Dockerfile                  # 백엔드 컨테이너 이미지
```

**주요 파일 설명**:

- `main.py`: FastAPI 앱 생성, 라우터 등록, 미들웨어 설정
- `celery_app.py`: Celery 워커 설정, 브로커(Redis) 연결
- `transcription_task.py`: mlx-whisper 호출하여 음성을 텍스트로 변환
- `diarization_task.py`: pyannote.audio로 누가 언제 발화했는지 식별
- `summary_task.py`: Claude API로 회의 요약 생성

## 클라이언트 디렉토리 구조

### `/client/` - Flutter 크로스플랫폼 애플리케이션

**목적**:
- 웹(Chrome/Firefox), iOS, Android, macOS에서 동일한 UX 제공
- 오디오 녹음 캡처 및 스트리밍
- 실시간 시각화 및 상태 표시
- 로컬 저장 및 동기화

**구조**:

```
client/
├── lib/
│   ├── main.dart               # 앱 진입점, 라우팅 설정
│   ├── config/
│   │   ├── api_config.dart     # API 엔드포인트 설정
│   │   └── app_config.dart     # 앱 전역 설정
│   │
│   ├── models/
│   │   ├── meeting.dart        # 회의 데이터 모델
│   │   ├── audio.dart          # 오디오 파일 모델
│   │   ├── transcription.dart  # 전사 결과 모델
│   │   └── user.dart           # 사용자 모델
│   │
│   ├── screens/
│   │   ├── home_screen.dart    # 홈 화면 (최근 회의 목록)
│   │   ├── recording_screen.dart # 녹음 화면 (실시간 파형 표시)
│   │   ├── meeting_detail_screen.dart # 회의 상세 화면
│   │   ├── transcription_screen.dart  # 전사 결과 표시 화면
│   │   ├── settings_screen.dart # 설정 화면 (서버 주소, 팀 정보)
│   │   └── team_members_screen.dart # 팀 멤버 관리 화면
│   │
│   ├── widgets/
│   │   ├── audio_waveform.dart      # 실시간 오디오 파형 위젯
│   │   ├── recording_button.dart    # 녹음 시작/중지 버튼
│   │   ├── meeting_card.dart        # 회의 카드 위젯
│   │   ├── transcription_view.dart  # 전사 결과 표시 위젯
│   │   └── speaker_label.dart       # 스피커 라벨 위젯
│   │
│   ├── services/
│   │   ├── api_service.dart    # HTTP 클라이언트 (Dio)
│   │   ├── audio_service.dart  # 오디오 녹음 관리 (microphone 패키지)
│   │   ├── storage_service.dart # 로컬 저장소 (Hive/SQLite)
│   │   └── auth_service.dart   # 인증 토큰 관리
│   │
│   ├── providers/
│   │   ├── meeting_provider.dart     # 상태 관리 (Riverpod)
│   │   ├── audio_provider.dart       # 오디오 상태 관리
│   │   ├── recording_provider.dart   # 녹음 상태 관리
│   │   └── user_provider.dart        # 사용자 상태 관리
│   │
│   ├── utils/
│   │   ├── logger.dart         # 로깅 유틸리티
│   │   ├── extensions.dart     # 문자열, 날짜 확장 함수
│   │   └── validators.dart     # 입력 검증 함수
│   │
│   └── localization/
│       ├── app_ko.arb          # 한국어 번역
│       ├── app_en.arb          # 영어 번역
│       └── app_ja.arb          # 일본어 번역
│
├── assets/
│   ├── images/
│   │   ├── logo.svg            # 앱 로고
│   │   ├── icons/              # 버튼, 상태 표시 아이콘
│   │   └── illustrations/      # 온보딩 일러스트레이션
│   │
│   ├── fonts/
│   │   ├── Pretendard-Regular.ttf # 주 폰트
│   │   └── Pretendard-Bold.ttf
│   │
│   └── audio/
│       ├── click_sound.mp3     # UI 음향 효과
│       └── notification.mp3    # 알림 음향
│
├── test/
│   ├── widget_test.dart        # 위젯 테스트
│   ├── integration_test.dart   # 통합 테스트
│   └── mocks/
│       └── mock_api_service.dart # API 모의 객체
│
├── web/
│   ├── index.html              # 웹 앱 진입점
│   ├── favicon.ico
│   └── manifest.json           # PWA 매니페스트
│
├── ios/
│   ├── Runner.xcworkspace      # Xcode 프로젝트
│   ├── Podfile                 # iOS 의존성
│   └── Runner/
│       ├── GeneratedPluginRegistrant.swift
│       └── Info.plist
│
├── android/
│   ├── app/
│   │   ├── build.gradle        # Gradle 빌드 설정
│   │   └── src/
│   │       ├── main/
│   │       │   ├── kotlin/
│   │       │   │   └── MainActivity.kt
│   │       │   └── AndroidManifest.xml
│   │
├── macos/
│   ├── Runner.xcworkspace
│   └── Runner/
│       ├── GeneratedPluginRegistrant.swift
│       └── Info.plist
│
├── pubspec.yaml                # Flutter 의존성
├── pubspec.lock                # 잠금 파일
└── README.md                   # 클라이언트 개발 가이드
```

**주요 패키지**:

- `riverpod`: 상태 관리
- `dio`: HTTP 클라이언트
- `hive`: 로컬 저장소
- `record`: 오디오 녹음
- `audio_waveforms`: 파형 시각화
- `flutter_localization`: 다국어 지원
- `go_router`: 네비게이션

## 모델 디렉토리 구조

### `/models/` - 사전 학습 모델 및 설정

**목적**:
- mlx-whisper 모델 파일 저장
- pyannote.audio 모델 파일 저장
- 모델 설정 및 가중치 관리

**구조**:

```
models/
├── whisper/
│   ├── whisper-large-v3-turbo/
│   │   ├── model.safetensors   # 모델 가중치 (mlx 포맷)
│   │   ├── tokenizer.json      # 토크나이저
│   │   ├── config.json         # 모델 설정
│   │   └── preprocessor_config.json
│   │
│   └── model_cache.db          # 모델 캐시 메타데이터
│
├── pyannote/
│   ├── segmentation_v3/
│   │   ├── pytorch_model.bin   # 모델 가중치
│   │   └── config.yaml         # 설정
│   │
│   └── speaker_embedding/
│       ├── pytorch_model.bin   # 스피커 임베딩 모델
│       └── config.yaml
│
├── download_models.py          # 모델 자동 다운로드 스크립트
└── README.md                   # 모델 설정 문서
```

## 스크립트 디렉토리 구조

### `/scripts/` - 개발 편의 자동화

**목적**:
- 프로젝트 환경 설정 자동화
- 모델 다운로드 자동화
- 데이터베이스 마이그레이션
- 개발 서버 시작

**주요 스크립트**:

```
scripts/
├── setup_dev.sh               # 개발 환경 초기 설정
│   └── Python venv 생성, 의존성 설치, Redis/PostgreSQL 시작
│
├── download_models.py         # 모델 파일 다운로드
│   └── whisper-large-v3-turbo, pyannote 모델 자동 다운로드
│
├── start_backend.sh           # FastAPI + Celery 시작
│   └── uvicorn, Celery worker, Celery beat 동시 실행
│
├── start_client.sh            # Flutter 개발 서버 시작
│   └── Flutter hot reload 활성화
│
├── test_backend.sh            # 백엔드 테스트 실행
│   └── pytest 실행, 커버리지 리포트 생성
│
├── migrate_db.py              # 데이터베이스 마이그레이션
│   └── Alembic으로 DB 스키마 업데이트
│
└── docker_compose_up.sh       # 전체 스택 Docker 시작
    └── FastAPI, Redis, PostgreSQL, Celery 모두 실행
```

## 문서 디렉토리 구조

### `/docs/` - 프로젝트 문서

**목적**:
- 아키텍처 설명 문서
- API 문서
- 개발자 가이드
- 배포 가이드

**구조**:

```
docs/
├── architecture.md            # 시스템 아키텍처 개요
├── api/
│   ├── overview.md            # API 설계 원칙
│   ├── audio.md               # 오디오 녹음 API 문서
│   ├── transcription.md       # STT API 문서
│   ├── meeting.md             # 회의 관리 API 문서
│   └── openapi.json           # OpenAPI 스키마
│
├── development/
│   ├── setup.md               # 로컬 환경 설정
│   ├── backend_guide.md       # 백엔드 개발 가이드
│   ├── frontend_guide.md      # 프론트엔드 개발 가이드
│   └── testing.md             # 테스트 전략
│
├── deployment/
│   ├── local_deployment.md    # 로컬 배포
│   ├── docker_setup.md        # Docker 구성
│   └── production.md          # 프로덕션 배포
│
└── diagrams/
    ├── architecture_diagram.mmd # Mermaid 아키텍처 다이어그램
    ├── api_sequence.mmd         # API 시퀀스 다이어그램
    └── data_flow.mmd            # 데이터 흐름 다이어그램
```

## 데이터베이스 스키마

### 주요 테이블

**users 테이블**:
- user_id (Primary Key)
- email (Unique)
- username
- password_hash
- created_at
- updated_at

**meetings 테이블**:
- meeting_id (Primary Key)
- user_id (Foreign Key)
- title
- start_time
- end_time
- audio_file_id (Foreign Key)
- status (pending, processing, completed)
- created_at

**audio_files 테이블**:
- audio_file_id (Primary Key)
- meeting_id (Foreign Key)
- file_path
- duration_seconds
- sample_rate
- upload_time

**transcriptions 테이블**:
- transcription_id (Primary Key)
- audio_file_id (Foreign Key)
- raw_text
- formatted_text
- language
- confidence_score
- processing_time_seconds

**speakers 테이블**:
- speaker_id (Primary Key)
- meeting_id (Foreign Key)
- speaker_name
- speaker_embedding (vector)
- first_appearance_time
- total_speaking_time_seconds

**summaries 테이블**:
- summary_id (Primary Key)
- meeting_id (Foreign Key)
- summary_text
- action_items (JSON)
- key_decisions (JSON)
- generated_at

## 의존성 구조

```
클라이언트 (Flutter)
    ↓ HTTP/REST
FastAPI 서버
    ↓
Celery 작업 큐 ← Redis (메시지 브로커)
    ↓
├─ STT 워커 → mlx-whisper
├─ Diarization 워커 → pyannote.audio
└─ Summary 워커 → Claude API
    ↓
PostgreSQL (영구 저장소)
```

## 파일 저장소 구조

```
/data/
├── audio_uploads/
│   ├── 2024-01-15/
│   │   ├── meeting_001_raw.wav
│   │   └── meeting_001_processed.wav
│   └── 2024-01-16/
│
├── transcriptions/
│   ├── meeting_001_transcript.txt
│   └── meeting_001_speakers.json
│
└── exports/
    ├── meeting_001_minutes.pdf
    └── meeting_001_minutes.md
```

## 환경 변수 구조

```
.env 파일에 포함되는 주요 변수:

[Backend]
FASTAPI_HOST=localhost
FASTAPI_PORT=8000
DATABASE_URL=postgresql://user:password@localhost/voice_to_textnote
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key

[Celery]
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

[Claude API]
CLAUDE_API_KEY=sk-...

[Model]
WHISPER_MODEL_PATH=/models/whisper/whisper-large-v3-turbo
PYANNOTE_MODEL_PATH=/models/pyannote
```

이 구조를 통해 명확한 관심사의 분리(Separation of Concerns)와 확장성을 보장합니다.
