# Voice to TextNote - 프로젝트 구조

> 현재 상태: Phase 1-7 완료 (Release Candidate). 31개 SPEC 구현 완료.
> 테스트: 3353 backend tests (97.23% coverage), 328 Flutter tests, E2E 포함.

## 최상위 디렉토리 구조

```
voice-to-textnote/
├── backend/          # FastAPI 서버, Celery 워커, 음성 처리 파이프라인
├── client/           # Flutter 크로스플랫폼 클라이언트 (Web/iOS/Android/macOS)
├── models/           # 사전 학습된 모델 파일 및 구성
├── scripts/          # 개발 설정, 모델 다운로드, 모바일 검증 자동화
├── tests/            # 통합 및 E2E 테스트
├── docs/             # 프로젝트 문서 및 아키텍처 다이어그램
├── deploy/           # 서버 배포 스크립트 (Ubuntu systemd)
├── .github/workflows/# CI/CD 파이프라인 (Test, Android/iOS 빌드, Release 게이트)
├── .env.example      # 환경 변수 템플릿
├── pyproject.toml    # Python 의존성 관리
└── pubspec.yaml      # Flutter 의존성 관리
```

## 백엔드 구조 (`/backend/`)

FastAPI 서버 + Celery 비동기 작업 큐 + ML 파이프라인. Phase 1-7 전 기능 구현.

```
backend/
├── app/
│   ├── main.py                  # FastAPI 앱 초기화, 모델 워밍업
│   ├── config.py                # 환경 설정 (Redis, Whisper, OpenAI, 동시 제한)
│   ├── dependencies.py          # 의존성 주입 (DB, Redis, JWT)
│   ├── errors.py                # 공통 에러 헬퍼 (not_found, bad_request)
│   ├── exceptions.py            # 도메인 예외 계층 (VoiceNoteError + 서브클래스)
│   ├── error_handlers.py        # 전역 예외 핸들러 (JSON 통일 응답)
│   ├── lifecycle.py             # 앱 lifespan 관리 (startup/shutdown)
│   ├── metrics.py               # Prometheus 메트릭 정의
│   ├── result_fallback.py       # 네트워크 실패 시 폴백
│   │
│   ├── middleware/              # Phase 2: API 보안
│   │   ├── auth.py              # JWT + API Key 인증
│   │   ├── rate_limit.py        # slowapi 레이트 리미팅
│   │   ├── security_headers.py  # HSTS, X-Content-Type-Options 등
│   │   ├── request_id.py        # 요청 ID 추적
│   │   ├── audit_log.py         # 요청/응답 감사 로깅
│   │   └── validators.py        # 입력 검증 (매직 바이트 포함, Phase 7)
│   │
│   ├── api/v1/                  # 라우터 그룹 (registry.py로 통합 등록)
│   │   ├── transcription/       # STT: 업로드, 상태, 결과, batch, stream(SSE)
│   │   ├── audio/               # 오디오 전처리, 분석, QA, 품질 평가
│   │   ├── auth/                # JWT 로그인, 디바이스 토큰
│   │   ├── collaboration/       # 팀, 미팅 공유, 화자, 버전, 웹훅, 북마크
│   │   ├── minutes/             # 회의록, 요약, 액션아이템, 키워드, 태그
│   │   ├── analytics/           # 통계, 고급검색, 감정, 톤, 효율성, 어휘
│   │   ├── admin/               # 관리자, 헬스, 이력, 캘린더, 내보내기, 템플릿
│   │   └── registry.py          # 라우트 레지스트리 (CI 검증 대상)
│   │
│   ├── schemas/                 # 앱 내부 스키마 (action_item)
│   └── workers/                 # Celery 앱 설정
│
├── schemas/                     # Pydantic 요청/응답 스키마 (37개)
│   ├── transcription.py, diarization.py, minutes.py, summary.py
│   ├── sentiment.py, tone.py, search.py, advanced_search.py
│   ├── auth.py, team.py, collab.py, template.py, export.py
│   └── ... (화자, 북마크, 태그, 버전, 웹훅, QA, 통계 등)
│
├── services/                    # 비즈니스 로직 계층 (28개 서비스)
│   ├── auth_service.py          # JWT 인증, 토큰 Rotation
│   ├── team_service.py          # 팀 CRUD, 멤버 관리
│   ├── search_service.py        # 전문 검색
│   ├── advanced_search.py       # 필터/정렬/자동완성
│   ├── sentiment_service.py     # 감정 분석 (Phase 7)
│   ├── collab_service.py        # 실시간 협업 (WebSocket + LWW)
│   ├── meeting_share_service.py # 미팅 공유
│   ├── retention.py             # 데이터 보유 정책 (30일 DB, 24h 임시)
│   ├── push_service.py          # 모바일 Push 알림
│   ├── oauth_service.py         # 소셜 로그인
│   ├── action_item_service.py, bookmark_service.py
│   ├── calendar_service.py, efficiency_service.py
│   ├── keyword_service.py, qa_service.py, quality_service.py
│   ├── speaker_service.py, speaker_voice_service.py
│   ├── statistics.py, enhanced_statistics.py
│   ├── sync_service.py, tag_service.py
│   ├── version_service.py, vocabulary_service.py
│   ├── webhook_notifier.py, webhook_service.py
│   └── __init__.py
│
├── pipeline/                    # 오디오 처리 및 문서 생성 파이프라인 (13개)
│   ├── audio_processor.py       # 오디오 전처리 (16kHz 모노 WAV)
│   ├── enhanced_audio_processor.py  # 고급 전처리 (Phase 7 매직 바이트)
│   ├── chunk_manager.py         # 청크 분할/병합 (30분 단위)
│   ├── speaker_matcher.py       # STT-DIA 타임스탬프 overlap 매칭
│   ├── minutes_formatter.py     # 회의록 포맷터 (세그먼트 병합, 통계, Markdown)
│   ├── summary_generator.py     # OpenAI gpt-4o-mini 요약 생성기
│   ├── sentiment_analyzer.py    # 감정 분석 파이프라인 (Phase 7)
│   ├── template_parser.py       # DOCX/PDF 양식 구조 추출
│   ├── pdf_generator.py         # PDF 내보내기 (fpdf2 + NotoSansKR)
│   ├── docx_generator.py        # DOCX 내보내기
│   └── mind_map_generator.py    # 마인드맵 생성
│
├── ml/                          # ML 엔진 (7개)
│   ├── stt_engine.py            # mlx-whisper 래퍼 (싱글톤)
│   ├── diarization_engine.py    # pyannote.audio 3.1 화자 분리 (싱글톤)
│   ├── openai_client.py         # OpenAI gpt-4o-mini 클라이언트 (요약/감정)
│   ├── tone_engine.py           # opensmile eGeMAPSv02 + librosa 톤 분석 (Phase 7)
│   ├── audio_analysis_engine.py # 오디오 품질 분석
│   ├── action_items_engine.py   # 액션 아이템 추출
│   └── tagging_engine.py        # 자동 태깅
│
├── db/                          # 데이터베이스 계층
│   ├── engine.py                # SQLAlchemy 비동기 엔진 (PostgreSQL)
│   ├── sync_engine.py           # 동기 엔진 (테스트용 SQLite)
│   ├── service.py               # 공통 DB 서비스 유틸
│   ├── models.py                # 베이스 모델
│   └── *_models.py              # 도메인별 ORM (auth, collab, search, tag, version,
│                                #   bookmark, speaker, vocabulary, webhook, device_token,
│                                #   quality_feedback 등)
│
├── events/                      # SSE 이벤트 (Phase 3)
│   ├── publisher.py             # SSE 이벤트 퍼블리셔
│   └── subscriber.py            # SSE 구독자 관리
│
├── workers/tasks/               # Celery 비동기 태스크 (8개)
│   ├── transcription_task.py    # mlx-whisper STT
│   ├── diarization_task.py      # pyannote 화자 분리 (동시 2개)
│   ├── minutes_task.py          # 회의록 생성 (동시 3개)
│   ├── summary_task.py          # AI 요약 (동시 2개, OpenAI gpt-4o-mini)
│   ├── sentiment_task.py        # 감정 분석 (동시 3개, Phase 7)
│   ├── tone_task.py             # 톤/운율 분석 (Phase 7)
│   ├── mind_map_task.py         # 마인드맵 생성
│   └── cleanup_task.py          # 데이터 보유 정량 정리 (Celery Beat)
│
├── utils/                       # 유틸리티
│   ├── logger.py                # 구조화된 JSON 로깅
│   ├── validators.py            # 입력 검증 (파일 형식, 크기)
│   ├── file_signature.py        # 매직 바이트 검증 (Phase 7)
│   └── json_helpers.py          # JSON 직렬화 헬퍼
│
├── tests/
│   ├── unit/                    # 단위 테스트
│   ├── integration/             # 통합 테스트
│   └── e2e/                     # E2E 테스트 (전체 파이프라인)
│
├── alembic/                     # DB 마이그레이션 (Phase 3)
├── assets/fonts/                # PDF 내보내기용 폰트 (NotoSansKR)
└── conftest.py                  # pytest 픽스처
```

## 클라이언트 구조 (`/client/`)

Flutter 크로스플랫폼 앱 (Web + macOS + iOS + Android). Riverpod 상태 관리.

```
client/lib/
├── main.dart                    # 앱 진입점
├── firebase_options.dart        # Firebase 설정
├── config/                      # API 엔드포인트, 앱 전역 설정
├── router/                      # go_router 네비게이션
│
├── models/ (13개)               # meeting, transcription, summary_result,
│                                #   tone_model, search_result, team, template,
│                                #   action_item, speaker_profile, vocabulary,
│                                #   mind_map_result, pipeline_state, auth_user 등
│
├── theme/ (4개)                 # 디자인 시스템 토큰 (모던 미니멀 + 인디고/바이올렛)
│   ├── app_colors.dart          # 시맨틱 컬러 스킴 (라이트/다크) + 브랜드 그라데이션
│   ├── app_typography.dart      # 타이포그래피 스케일 + 모노스페이스 타이머
│   ├── app_spacing.dart         # 스페이싱/반경/그림자 토큰 (4px 기반)
│   └── app_theme.dart           # Light/Dark ThemeData 통합 빌더
│
├── screens/ (14개)              # home, recording, processing, result,
│                                #   login, register, search, settings,
│                                #   team_list, team_detail, speaker_profile,
│                                #   vocabulary, template, model_download
│
├── services/ (35개)             # API 클라이언트 + 디바이스 서비스
│   ├── api_client.dart          # Dio HTTP 기반
│   ├── transcription_api.dart, diarization_api.dart, minutes_api.dart
│   ├── summary_api.dart, sentiment_api.dart, tone_api.dart
│   ├── search_api.dart, history_api.dart, export_api.dart
│   ├── auth_api.dart, team_api.dart, template_api.dart
│   ├── speaker_api.dart, bookmark_api.dart, qa_api.dart
│   ├── statistics_api.dart, vocabulary_api.dart, health_api.dart
│   ├── sse_service.dart         # SSE 실시간 스트리밍
│   ├── collab_service.dart      # 실시간 협업 (WebSocket)
│   ├── local_stt_service.dart   # 오프라인 STT 하이브리드 (whisper.cpp)
│   ├── local_stt_runtime_whisper.dart, local_stt_provider.dart
│   ├── model_manager.dart       # 로컬 STT 모델 관리
│   ├── reprocess_queue.dart     # 오프라인 재처리 큐
│   ├── background_recording_service.dart  # 백그라운드 녹음
│   ├── recording_recovery_service.dart    # 녹음 복구
│   ├── push_notification_service.dart     # Push 알림
│   ├── deep_link_service.dart, device_api.dart
│   ├── permission_service.dart, connectivity_service.dart
│   └── auth_service.dart, audio_api.dart
│
├── providers/ (19개)            # Riverpod 상태 관리
│   ├── pipeline_provider.dart, recording_provider.dart
│   ├── result_provider.dart, meeting_list_provider.dart
│   ├── auth_provider.dart, team_provider.dart, collab_provider.dart
│   ├── search_provider.dart, template_provider.dart
│   ├── speaker_provider.dart, vocabulary_provider.dart
│   ├── hybrid_pipeline_provider.dart, model_download_provider.dart
│   ├── notification_provider.dart, permission_recheck_provider.dart
│   ├── connectivity_provider.dart, qa_provider.dart
│   ├── audio_player_provider.dart
│   └── theme_mode_provider.dart # 다크모드 토글 (SharedPreferences 영속화)
│
├── widgets/ (19개)              # meeting_card, shimmer_card/text, offline_banner,
│                                #   error_dialog, error_retry_widget, permission_dialog,
│                                #   pipeline_progress, presence_overlay, tone_timeline,
│                                #   speaker_segment, audio_player_bar, team_share_dialog,
│                                #   recording_recovery_dialog, search_filter_bottom_sheet,
│                                #   find_replace_bar, recent_searches_widget,
│                                #   empty_state_widget, status_badge
│
├── utils/                       # logger, extensions, validators
└── dataconnect_generated/       # Firebase Data Connect 생성 코드
```

**모바일 플랫폼**: `ios/`, `android/`, `macos/`, `web/` 각각 네이티브 설정 포함.
iOS는 ATS(App Transport Security), Android는 Network Security Config 적용 (Phase 7).

## 모델 디렉토리 (`/models/`)

```
models/
├── whisper/whisper-large-v3-turbo/  # mlx-whisper 모델 (safetensors)
└── pyannote/
    ├── segmentation_v3/             # 화자 분할 모델
    └── speaker_embedding/           # 스피커 임베딩 모델
```

## 아키텍처 의존성

```
Flutter 클라이언트 (Web/iOS/Android/macOS)
    ↓ HTTP/REST + WebSocket + SSE
FastAPI 서버 (Uvicorn)
├── middleware/ (JWT, Rate Limit, Security Headers, Audit Log)
├── api/v1/ (10개 라우터 그룹)
└── services/ (28개 비즈니스 로직)
    ↓
Celery 작업 큐 ← Redis (브로커/캐시)
├── STT 워커 → mlx-whisper (MPS 가속)
├── DIA 워커 → pyannote.audio
├── MIN 워커 → 회의록 포맷터
├── SUM 워커 → OpenAI gpt-4o-mini  (요약)
├── SENTIMENT 워커 → OpenAI gpt-4o-mini  (감정 분석)
└── TONE 워크 → opensmile + librosa  (톤/운율)
    ↓
PostgreSQL (영구 저장소) + Alembic (마이그레이션)
```

## 주요 환경 변수

```
DATABASE_URL=postgresql://...     # 프로덕션 (개발: SQLite)
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=sk-...             # gpt-4o-mini (요약/감정 분석)
API_KEY_SECRET=...                # API Key 암호화
WHISPER_MODEL_PATH=/models/whisper/whisper-large-v3-turbo
TONE_MODEL=                       # 빈 값 시 톤 분석 503 비활성화 (opensmile AGPL)
```
