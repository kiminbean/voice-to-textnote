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
├── deploy/                     # 서버 배포 스크립트 및 의존성 (Ubuntu systemd)
├── .env.example                # 환경 변수 템플릿
├── pyproject.toml              # Python 의존성 관리
├── pubspec.yaml                # Flutter 의존성 관리
└── README.md                   # 프로젝트 개요 및 빠른 시작 가이드
```

## 백엔드 디렉토리 구조

### `/backend/` - FastAPI 서버 및 음성 처리 파이프라인

**목적** (현재 완료: STT + 화자 분리 + 회의록 + AI 요약):
- RESTful API 엔드포인트 제공 (오디오 업로드, 상태 조회, 결과 반환, 화자 분리, 회의록 생성)
- 음성 파일 수신, 저장, 전처리
- Celery 비동기 작업 큐 관리
- mlx-whisper STT 처리
- pyannote.audio 3.1 화자 분리 (Speaker Diarization)
- 화자별 회의록 자동 생성 (Meeting Minutes)
- Claude API 기반 회의 요약 및 액션 아이템 추출

**현재 구현 구조** (SPEC-STT-001 + SPEC-DIA-001 + SPEC-MIN-001 + SPEC-SUM-001 완료):

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 앱 초기화, 모델 워밍업
│   ├── config.py               # 환경 설정 (Redis, Whisper 모델)
│   ├── dependencies.py         # 의존성 주입 (Redis, Whisper)
│   │
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py             # API Key 인증 미들웨어
│   │   ├── rate_limit.py       # slowapi 레이트 리미팅
│   │   ├── security_headers.py  # HSTS, X-Content-Type-Options 등
│   │   ├── request_id.py        # 요청 ID 추적
│   │   └── audit_log.py         # 요청/응답 감사 로깅
│   │
│   ├── api/
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── transcription.py # STT 업로드, 상태, 결과 엔드포인트
│   │       ├── diarization.py   # 화자 분리 작업 생성, 상태, 결과, 삭제 엔드포인트
│   │       ├── minutes.py       # 회의록 생성, 상태, 결과, 삭제 엔드포인트
│   │       ├── summary.py       # 요약 CRUD API 엔드포인트
│   │       ├── templates.py     # 템플릿 CRUD API (업로드, 목록, 조회, 삭제)
│   │       ├── stream.py        # SSE 실시간 스트리밍 엔드포인트
│   │       ├── history.py       # 회의 이력 API (페이지네이션, 필터링)
│   │       ├── admin.py         # 관리자 엔드포인트
│   │       ├── health.py        # 헬스체크, 모델 상태 (STT + DIA), readiness 프로브
│   │       └── metrics.py       # Prometheus 메트릭 엔드포인트
│   │
│   ├── metrics.py              # Prometheus 메트릭 정의 및 수집
│   ├── error_handlers.py        # 전역 예외 처리 (에러 응답 표준화)
│   ├── exceptions.py            # 커스텀 예외 정의
│   ├── lifecycle.py             # 앱 시작/종료 이벤트 핸들러
│   └── result_fallback.py       # 네트워크 실패 시 폴백 메커니즘
│
├── schemas/
│   ├── __init__.py
│   ├── transcription.py        # STT Pydantic 요청/응답 스키마
│   ├── diarization.py          # 화자 분리 스키마 (DiarizedSegmentResult, SpeakerInfo 등)
│   ├── minutes.py              # 회의록 스키마 (MinutesSegment, SpeakerStats, MinutesResponse 등)
│   ├── summary.py              # 요약 스키마 (ActionItem, SummaryResult, SummaryResponse 등)
│   ├── template.py             # 템플릿 스키마 (TemplateUpload, TemplateResponse, TemplateStructure 등)
│   └── health.py               # 헬스 상태 스키마
│
├── utils/
│   ├── __init__.py
│   ├── logger.py               # 구조화된 JSON 로깅
│   └── validators.py           # 입력 검증 (파일 형식, 크기)
│
│
├── workers/
│   ├── __init__.py
│   ├── celery_app.py           # Celery 앱 초기화, Redis 연결
│   └── tasks/
│       ├── __init__.py
│       ├── transcription_task.py # mlx-whisper STT 처리
│       ├── diarization_task.py   # pyannote 화자 분리 처리 (동시 2개 제한)
│       ├── minutes_task.py       # 회의록 생성 처리 (동시 3개 제한)
│       └── summary_task.py      # AI 요약 생성 처리 (동시 2개 제한)
│
├── ml/
│   ├── __init__.py
│   ├── stt_engine.py           # mlx-whisper 래퍼 (싱글톤 패턴)
│   └── diarization_engine.py   # pyannote.audio 3.1 화자 분리 엔진 (싱글턴)
│
├── db/
│   ├── __init__.py
│   ├── engine.py               # SQLAlchemy 비동기 엔진 (PostgreSQL)
│   ├── models.py               # SQLAlchemy ORM 모델 (meetings, summaries, history)
│   ├── service.py              # 비동기 데이터베이스 서비스
│   ├── sync_engine.py          # 동기 엔진 (테스트용 SQLite)
│   └── sync_service.py         # 동기 데이터베이스 서비스
│
├── events/
│   ├── __init__.py
│   ├── publisher.py            # SSE 이벤트 퍼블리셔
│   └── subscriber.py           # SSE 구독자 관리
│
├── services/
│   ├── __init__.py
│   └── retention.py            # 데이터 보유 정책 (30일 DB, 24h 임시파일)
│
├── pipeline/
│   ├── __init__.py
│   ├── audio_processor.py      # 오디오 전처리 (16kHz 모노 WAV)
│   ├── chunk_manager.py        # 청크 분할 및 병합 (30분 단위)
│   ├── speaker_matcher.py      # STT-DIA 타임스탬프 overlap 매칭 알고리즘
│   ├── minutes_formatter.py    # 회의록 포맷터 (세그먼트 병합, 통계, Markdown)
│   ├── summary_generator.py    # Claude API 요약 생성기 (프롬프트 구성, 응답 파싱)
│   └── template_parser.py      # DOCX/PDF 양식 구조 추출 파서 (python-docx, pdfplumber)
│
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_stt_engine.py             # mlx-whisper 엔진 테스트
│   │   ├── test_transcription_task.py     # STT 작업 테스트
│   │   ├── test_audio_processor.py        # 오디오 전처리 테스트
│   │   ├── test_schemas.py                # STT Pydantic 스키마 테스트
│   │   ├── test_diarization_engine.py     # DiarizationEngine 싱글턴 테스트
│   │   ├── test_diarization_schemas.py    # 화자 분리 스키마 테스트
│   │   ├── test_diarization_task.py       # 화자 분리 Celery 태스크 테스트
│   │   ├── test_speaker_matcher.py        # 타임스탬프 매칭 테스트 (100% 커버리지)
│   │   ├── test_minutes_formatter.py      # 회의록 포맷터 테스트 (100% 커버리지)
│   │   ├── test_minutes_schemas.py        # 회의록 스키마 테스트
│   │   ├── test_minutes_task.py           # 회의록 Celery 태스크 테스트
│   │   ├── test_summary_generator.py     # 요약 생성기 테스트 (100% 커버리지)
│   │   ├── test_summary_schemas.py       # 요약 스키마 테스트
│   │   ├── test_summary_task.py          # 요약 Celery 태스크 테스트
│   │   └── test_template_parser.py       # 템플릿 파서 단위 테스트
│   └── integration/
│       ├── __init__.py
│       ├── test_api.py                    # STT API 통합 테스트
│       ├── test_diarization_api.py        # 화자 분리 API 통합 테스트
│       ├── test_minutes_api.py            # 회의록 API 통합 테스트
│       ├── test_summary_api.py           # 요약 API 통합 테스트
│       └── test_template_api.py          # 템플릿 API 통합 테스트
│
├── conftest.py                 # pytest 픽스처 및 설정
├── pyproject.toml              # Python 의존성 관리
├── deploy/
│   ├── setup-ubuntu.sh         # Ubuntu 원클릭 배포 스크립트 (systemd 서비스 등록)
│   └── requirements-ubuntu.txt # Ubuntu 서버 Python 의존성
├── alembic/                    # 데이터베이스 마이그레이션
│   ├── versions/               # 마이그레이션 스크립트
│   ├── env.py                  # Alembic 환경 설정
│   ├── script.py.mako          # 마이그레이션 템플릿
│   └── alembic.ini             # Alembic 설정
├── nginx/                      # Nginx 설정 (리버스 프록시)
│   ├── nginx.conf              # Nginx 설정 파일
│   └── ssl/                    # SSL 인증서
└── .github/
    ├── workflows/              # GitHub Actions 워크플로우
    │   ├── test.yml            # PR 테스트 자동화
    │   ├── build.yml           # 빌드 및 배포
    │   └── dependabot.yml      # 의존성 자동 업데이트
    └── ISSUE_TEMPLATE/         # 이슈 템플릿
```

**현재 구현 상황**:

- ✅ **app/main.py**: FastAPI 앱, STT + DIA 모델 워밍업
- ✅ **app/config.py**: Redis, Whisper, HUGGINGFACE_TOKEN, 동시 제한 설정
- ✅ **app/api/v1/transcription.py**: STT 업로드, 상태, 결과 엔드포인트
- ✅ **app/api/v1/diarization.py**: 화자 분리 작업 생성, 상태, 결과, 삭제 엔드포인트
- ✅ **app/api/v1/health.py**: 헬스체크 (STT + DIA 모델 상태)
- ✅ **schemas/**: STT + DIA Pydantic 요청/응답 스키마
- ✅ **workers/tasks/transcription_task.py**: mlx-whisper 호출
- ✅ **workers/tasks/diarization_task.py**: pyannote 화자 분리 (동시 2개, 재시도 3회)
- ✅ **ml/stt_engine.py**: Whisper 싱글톤 엔진
- ✅ **ml/diarization_engine.py**: pyannote.audio 3.1 싱글턴 엔진
- ✅ **pipeline/audio_processor.py**: 오디오 전처리 (16kHz 모노)
- ✅ **pipeline/chunk_manager.py**: 청크 분할 (30분 단위)
- ✅ **pipeline/speaker_matcher.py**: STT-DIA 타임스탬프 overlap 매칭
- ✅ **pipeline/minutes_formatter.py**: 회의록 포맷터 (세그먼트 병합, 통계, Markdown)
- ✅ **workers/tasks/minutes_task.py**: 회의록 생성 Celery 태스크 (동시 3개 제한)
- ✅ **app/api/v1/minutes.py**: 회의록 CRUD API 엔드포인트
- ✅ **schemas/minutes.py**: 회의록 Pydantic 스키마
- ✅ **pipeline/summary_generator.py**: Claude API 요약 생성기 (프롬프트/파싱/graceful fallback)
- ✅ **workers/tasks/summary_task.py**: AI 요약 Celery 태스크 (동시 2개 제한)
- ✅ **app/api/v1/summary.py**: 요약 CRUD API 엔드포인트
- ✅ **schemas/summary.py**: 요약 Pydantic 스키마 (ActionItem 포함)
- ✅ **tests/**: 377개 테스트, 97.06% 커버리지

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
│   │   ├── template.dart       # 템플릿 데이터 모델
│   │   └── user.dart           # 사용자 모델
│   │
│   ├── screens/
│   │   ├── home_screen.dart    # 홈 화면 (최근 회의 목록)
│   │   ├── recording_screen.dart # 녹음 화면 (실시간 파형 표시)
│   │   ├── meeting_detail_screen.dart # 회의 상세 화면
│   │   ├── transcription_screen.dart  # 전사 결과 표시 화면
│   │   ├── template_screen.dart # 템플릿 관리 화면 (업로드, 목록, 삭제)
│   │   ├── settings_screen.dart # 설정 화면 (서버 주소, 팀 정보)
│   │   └── team_members_screen.dart # 팀 멤버 관리 화면
│   │
│   ├── widgets/
│   │   ├── audio_waveform.dart      # 실시간 오디오 파형 위젯
│   │   ├── recording_button.dart    # 녹음 시작/중지 버튼
│   │   ├── meeting_card.dart        # 회의 카드 위젯
│   │   ├── transcription_view.dart  # 전사 결과 표시 위젯
│   │   ├── speaker_label.dart       # 스피커 라벨 위젯
│   │   ├── error_dialog.dart        # 오류 메시지 다이얼로그
│   │   ├── offline_banner.dart      # 오프라인 상태 배너
│   │   ├── shimmer_card.dart        # Shimmer 로딩 카드
│   │   └── shimmer_text.dart        # Shimmer 로딩 텍스트
│   │
│   ├── services/
│   │   ├── api_service.dart    # HTTP 클라이언트 (Dio)
│   │   ├── audio_service.dart  # 오디오 녹음 관리 (record 패키지)
│   │   ├── storage_service.dart # 로컬 저장소 (Hive/SQLite)
│   │   ├── template_api.dart   # 템플릿 API 서비스 (CRUD)
│   │   ├── auth_service.dart   # 인증 토큰 관리
│   │   ├── sse_service.dart    # SSE 실시간 스트리밍
│   │   └── connectivity_service.dart # 네트워크 상태 감지
│   │
│   ├── providers/
│   │   ├── meeting_provider.dart     # 상태 관리 (Riverpod)
│   │   ├── audio_provider.dart       # 오디오 상태 관리
│   │   ├── recording_provider.dart   # 녹음 상태 관리
│   │   ├── template_provider.dart    # 템플릿 목록/선택 상태 관리
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
│   ├── services/
│   │   └── template_api_test.dart # 템플릿 API 서비스 테스트
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
└── deploy/setup-ubuntu.sh     # Ubuntu 서버 배포 (Redis, Python, systemd)
    └── voicenote-api, voicenote-worker systemd 서비스 등록
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
│   ├── ubuntu_setup.md        # Ubuntu systemd 배포
│   └── tailscale_access.md    # Tailscale 외부 접속 설정
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
