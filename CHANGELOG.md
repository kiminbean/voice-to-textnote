# Changelog

이 프로젝트의 주요 변경 사항을 기록합니다. 형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 따르고 [Semantic Versioning](https://semver.org/lang/ko/)을 사용합니다.

## [Unreleased]

### Added

- **클라이언트 디자인 시스템 구축 + 전체 UI 재설계**: 모던 미니멀 미학(Linear/Notion 계열) + 인디고/바이올렛 브랜드 컬러 도입. 중앙 집중식 토큰 시스템(`client/lib/theme/`)으로 컬러·타이포그래피·스페이싱·그림자·반경 일관성 확보. 모든 하드코딩 색상 제거.

- **다크모드 전면 지원**: 시스템/라이트/다크 3모드 토글. `SharedPreferences` 영속화. 모든 14개 화면과 공유 위젯이 시맨틱 스킴(`AppColors.of(context)`)으로 자동 전환.

- **설정 화면 신규 추가** (`screens/settings_screen.dart`): 테마 선택 바텀시트, 데이터 메뉴 통합(검색/팀/양식/사전), 계정 정보 + 로그아웃. `/settings` 라우트 추가.

- **공용 상태 배지** (`widgets/status_badge.dart`): 6가지 톤(brand/success/warning/danger/info/neutral)의 알약형 배지. 상태 텍스트 자동 톤 추론 헬퍼 제공.

### Changed

- **핵심 화면 재설계**: login(브랜드 그라데이션 로고 + 소셜 버튼), register(환영 메시지), home(SliverAppBar + 빈 상태 CTA + 메뉴 간소화), recording(펄스 링 + 깜빡이는 상태 점 + 모노스페이스 타이머), processing(그라데이션 인디케이터 + 스텝 진행), search(에러/빈 상태 공유 위젯).

- **위젯 폴리싱**: meeting_card(소프트 보더 + 시간/상태 분리), pipeline_progress(체크/원형 스텝 인디케이터 + 연결선), speaker_segment(10색 모던 팔레트 + 다크모드 호환 검색 하이라이트), empty_state(소프트 아이콘 컨테이너 + CTA 버튼).

- **홈 메뉴 간소화**: 7개 메뉴 → 3개(검색 / 테마 토글 / 설정). 나머지는 설정 화면으로 이관.

- **통계 탭 개선**: 평면 나열 → 2x2 그리드 통계 타일(아이콘 + 라벨 + 값).

- **중복 코드 제거**: template/vocabulary의 개별 빈/에러 뷰 4개 클래스 제거 → 공유 `EmptyStateWidget`으로 통합.

### Fixed

- 검색 하이라이트가 다크모드에서 노란색 배경으로 가독성 저하되던 문제 → 모드에 따라 앰버/노랑 자동 전환
- tone_timeline 컬러 매핑이 `Colors.black54`로 다크모드에서 보이지 않던 문제 → 시맨틱 토큰 사용

## [1.6.0] - 2026-06-15

### Added

- **SPEC-BUGFIX-001: 18건 런타임 버그 fix** — Pydantic v2 마이그레이션 (efficiency.py `regex=` → `pattern=`), async blocking 해소 (7곳 `asyncio.to_thread`), temp file leak fix (3곳), race condition 해결 (dict iteration snapshot, version UniqueConstraint), error swallowing 해소 (14곳 `except: pass` → `logger.warning`)

- **SPEC-BUGFIX-002: 버그 fix 후속 작업 6종** — FCM `asyncio.to_thread` wrap, version_service UniqueConstraint Alembic migration (004), collab_service Lua script atomic race condition, asyncio.to_thread 회귀 테스트 8개 (AST 기반), temp file leak AST 정적 분석 gate, 운영 로그 `category` 필드 (13곳)

- **SPEC-TECHDEBT-001: 기술 부채 정리** — `datetime.utcnow()` 38곳 → `datetime.now(UTC)`, `asyncio.get_event_loop()` 3곳 대체, Pydantic class-based `Config` 5곳 → `ConfigDict`, pytest-asyncio `asyncio_default_fixture_loop_scope` 설정

- **SPEC-UX-002: 사용자 경험 개선** — 접근성 `Semantics` 라벨링 (WCAG 2.1 AA), 국제화 인프라 (`flutter_localizations` + ARB ko/en 36키), 홈 화면 반응형 마스터-디테일 (600px+), 마이크로 인터랙션 (HapticFeedback, Hero 애니메이션, TweenAnimationBuilder)

- **SPEC-RELEASE-001: Release Readiness 절차 문서화** — 5단계 순차 절차 (Firebase, APNs, App Store Connect, 물리 기기 E2E, self-hosted runner)

### Changed

- 테스트: 2976 → **3374 passed** (+398 신규 회귀/접근성/gate 테스트)
- Flutter 테스트: 269 → **328 passed** (+59)
- 커버리지: 97.23% 유지
- Alembic migration: 003 → **004** (UniqueConstraint on minutes_versions)

### Fixed

- CI 환경(Python 3.11) vs 로컬(Python 3.14) `app.routes` 노출 차이로 인한 efficiency test 실패 → `ROUTER_REGISTRY` SSOT에서 직접 확인하도록 수정
- `config.py` `default_factory=list` mypy 타입 불일치 → lambda로 fix
- `lifecycle.py`, `health.py` redis `ping()` sync/async 반환 타입 불일치 → `hasattr __await__` 패턴

## [0.1.0] - 2026-06-06

### Added

- **감성 분석 파이프라인 (ebb127f)**: 회의 음성 감성 분석 기능
  - `backend/pipeline/sentiment_analyzer.py`: 감성 분석 파이프라인
  - `backend/ml/action_items_engine.py`: 고급 액션 아이템 추출 (Claude API 연동)
  - `backend/services/sentiment_service.py`, `action_item_service.py`: 비즈니스 로직
  - 관련 API 엔드포인트, 스키마, 워커 태스크

- **테스트 커버리지 97% 달성 (0988c20)**: 신규 124개 테스트 추가
  - 코어 모듈 커버리지 강화: main.py, lifecycle.py, error_handlers.py, middleware
  - ML 모듈: stt_engine, tagging_engine, diarization_engine
  - 서비스: statistics, keyword, search, team, auth
  - 총 2478개 테스트, 97.35% 커버리지

- **테스트 커버리지 99.58% 달성 (6d981b4)**: 커버리지 작업 마무리
  - 신규 커버리지 테스트 16개 파일(conftest 2 + `test_*_coverage.py` 14) + 기존 단위 테스트 보강
  - 총 2976 passed, 16 skipped, 99.58% 커버리지

### Changed

- **커버리지 집계 정밀화 (48b2523)**: 분모/마킹 정리
  - 미도달 방어 코드·미완성 경로에 `# pragma: no cover` 마킹 (services/ml/pipeline/workers/app 전반)
  - `pyproject.toml` coverage `omit`를 `backend/tests/*` 전체로 확장 (테스트 코드 자체를 커버리지 분모에서 제외)
  - `advanced_search`: 미완성(TaskResult 미존재 컬럼 참조) 명시

- **개발 환경 정리 (d5df43a)**: `.gitignore`에 `.serena/`(Serena MCP 로컬 설정·메모리) 추가

- **백엔드 구조 리팩토링 (SPEC-REFACTOR-001) Iteration 3**: 라우터 registry 도입 및 main.py 보일러플레이트 축소
  - `backend/app/api/v1/registry.py` 추가(신규): `ROUTER_REGISTRY` 35개 라우터의 SSOT(Single Source of Truth) — 순서 보존 리스트 형식, 각 항목 `(router, requires_api_key)` 튜플로 인증 전략 명시
  - `backend/app/main.py` 간소화: 35개 정적 `include_router` 호출 + 35개 모듈 import 블록 → registry 순회 루프 1개소로 축소 (main.py 80+ 줄 → 10줄 이상 감소)
  - `backend/tests/unit/test_route_registry_invariance.py` + `_route_snapshot_baseline.json` 신규: 라우트 테이블 불변성 증명 (135 routes, path/methods 스냅샷)
  - **범위 축소**: 파일 이동 제외 (REQ-RM-C1 deferred). ~40개 테스트가 27개 라우터 서브모듈을 직접 import하므로 파일 재배치 시 import 경로 깨짐. 대신 registry.py 도입으로 URL/인증 불변성 보장.
  - **테스트 통과**: 2478 passed, 4 skipped, 0 failed (coverage 97.35%)

- **백엔드 구조 리팩토링 (SPEC-REFACTOR-001) Iterations 1-2**: 에러 처리 표준화 및 서비스 계층 통합
  - `backend/app/errors.py` 추가: 도메인 에러 헬퍼 10종 (`not_found`, `bad_request`, `unauthorized`, `forbidden`, `conflict`, `rate_limit`, `unprocessable`, `request_entity_too_large`, `internal_error`, `service_unavailable`)
  - `backend/app/exceptions.py` 확장: 기존 3종 → 14종 서브클래스 (`NotFoundError`, `UnauthorizedError`, `ForbiddenError`, `ConflictError`, `RateLimitError` 등)
  - 29개 API 라우터에서 raw `HTTPException` 제거 → 에러 헬퍼로 전환
  - `backend/db/`에서 11개 서비스 파일(`*_service.py`) 삭제 → `backend/services/`(26개)로 통합
  - `backend/db/`는 모델(`*_models.py`)만 유지
  - 21개 모듈 레벨 서비스 싱글톤 → FastAPI `Depends()` 의존성 주입으로 전환

### Added

- **고급 검색 기능 (SPEC-SEARCH-002)**: SPEC-SEARCH-001 확장 — 필터/정렬/자동완성
  - Backend: 동적 WHERE/ORDER BY 빌더, `GET /api/v1/search/suggestions` 자동완성 엔드포인트
  - 날짜 범위 필터 (date_from, date_to), 정렬 (relevance/newest/oldest)
  - 화자 이름 필터, 액션아이템/핵심결정 필터
  - Flutter: 정렬 드롭다운, 필터 바텀시트, 자동완성 오버레이, 최근 검색어 (SharedPreferences)
  - 테스트: Backend 107 passed, Flutter 269 passed

- **회의록 전문 검색 기능 (SPEC-SEARCH-001)**: SQLite FTS5 기반 전문 검색 시스템 구현
  - Backend: FTS5 가상 테이블 (`search_index`) 및 자동 인덱싱 시스템
    - `persist_task_result()` 후 자동 인덱싱 (minutes/summary 작업만 대상)
    - `unicode61` 토크나이저로 한국어 공백/구두점 기반 분리
    - 스니펫 생성: FTS5 `snippet()` 함수로 매칭 키워드 주변 100~200자 하이라이트
    - 검색 API: `GET /api/v1/search` (페이지네이션, task_type 필터링 지원)
  - Flutter: 검색 UI 및 상태 관리
    - 홈 화면 AppBar 검색 아이콘
    - 검색 화면: 디바운스(300ms) + 결과 리스트 + 스니펫 하이라이트
    - Riverpod `FutureProvider.family` 패턴으로 검색 상태 관리
    - 검색 결과 탭 시 회의 상세 화면으로 네비게이션
  - 테스트: 백엔드 검색 API 테스트 10개 + Flutter 위젯 테스트 13개
  - API 응답 시간: < 200ms (100건 이하 데이터 기준), 전체 테스트 커버리지 90.78%

- **모바일 클라이언트 MVP (SPEC-MOBILE-001)**: iOS/Android 네이티브 앱 최적화 구현
  - Android 플랫폼 빌드 설정 (Gradle, Manifest, MainActivity, RecordingService)
  - iOS 백그라운드 오디오 녹음 지원 (Xcode 설정 업데이트)
  - 백그라운드 오디오 녹음 서비스 (iOS/Android 공통)
  - FCM 푸시 알림 (Flutter 클라이언트 + 백엔드 Push Service)
  - 권한 관리 UX (마이크, 알림, 저장소 권한 다이얼로그)
  - 디바이스 등록 API (`POST /api/v1/devices/register`)
  - Flutter 테스트 62개 (89% 커버리지), 백엔드 테스트 39개 (100% 성공률)

- **STT 백엔드 다중화 (REQ-STT-PERF-001)**: `backend/ml/stt_engine.py`에 `faster-whisper` 백엔드 추가.
  - 로드 우선순위: MLX → faster-whisper → openai-whisper
  - Linux CPU 환경에서 `int8` 양자화로 small 모델 RT가 0.6+ → **약 0.45**로 단축
  - `beam_size=1`, `vad_filter=True`, `word_timestamps=False`로 추가 가속
  - 의존성 추가: `faster-whisper>=1.0.0`
- **STT/DIA 병렬 실행 (REQ-STT-PERF-002)**: `POST /api/v1/transcriptions`가 STT 등록 시 화자 분리 task도 동시에 시작.
  - 응답에 `diarization_task_id` 포함 (선택, 레거시 호환)
  - `diarization_task`에 `audio_path` 직접 입력 모드 추가 (`matched=False` flag로 매칭 위임)
  - `minutes_task`가 raw dia + STT 결과를 받아 `SpeakerMatcher`로 매칭
- **SSE 기반 진행 상태 수신**: `client/lib/providers/pipeline_provider.dart`가 폴링 대신 SSE를 우선 사용.
  - 단계별 평균 1.5초 폴링 지연 제거 (3단계 ×3초 = 9초 절약)
  - SSE 실패 시 기존 폴링으로 자동 폴백
  - `SseService`에 `X-API-Key` 헤더 추가 (SPEC-SEC-001 호환)
- **DIA 화자 수 힌트 (REQ-DIA-PERF-001)**: `diarize()`에 `num_speakers`/`min_speakers`/`max_speakers` 옵션 추가.
  - 회의록 앱 기본 `max_speakers=4`로 clustering 후보 축소
- **DIA Silero VAD 사전 필터 (REQ-DIA-PERF-002)**: 무음 비율이 큰 회의에서 pyannote 입력을 압축.
  - `_compress_with_vad()` + `_map_segments()`로 timestamp 역매핑
  - 안전장치 4개: 인접 segment 병합, padding 최소화(0.1s), 음성 ratio threshold(0.85), VAD 실패 시 graceful fallback
  - 의존성 추가: `silero-vad>=5.0`
- **DIA 다운샘플링 옵션 (REQ-DIA-PERF-003, 실험적)**: `diarize(target_sample_rate=...)` 인자 추가.
  - default 비활성(`settings.dia_target_sample_rate=0`)
  - pyannote 3.1은 16kHz로 학습되어 다운샘플링 시 정확도 손실 가능성 있어 운영자 명시적 활성화 시에만 동작
- **단위 테스트**: `faster-whisper` 백엔드 + DIA hint/VAD/다운샘플링 mock 테스트 17개 추가

### Fixed

- **DIA 병렬 모드 변수 참조 버그**: 분기 밖 `logger.info`가 정의되지 않은 `diarized_segments`를 참조해 모든 화자분리가 실패하던 문제. `final_result["segments"]` 참조로 양쪽 분기에서 안전하게 동작.
- **SSE 401 Unauthorized**: 클라이언트 `SseService`가 인증 헤더를 누락해 SSE 연결이 즉시 끊기고 폴링으로 폴백되던 문제 수정.
- **VAD segment 폭증/padding overhead 역효과**: 초기 VAD 통합이 100s 오디오를 24-segment로 잘라 DIA가 2.5배 느려진 문제. `min_silence_duration_ms=1500`, segment 병합, 압축 효과 검증 안전장치로 자동 skip 도입.
- **SQLite `task_results.is_guest` 컬럼 누락**: SQLAlchemy 모델은 정의됐지만 alembic 001에 없던 컬럼을 ALTER로 추가 (`is_guest BOOLEAN NOT NULL DEFAULT 0`, `guest_session_id VARCHAR(36)`). 기존 208행 보존.
- **ruff UP038**: `backend/db/version_service.py`의 `isinstance(x, (str, int))` → `isinstance(x, str | int)` 변환 (부수 lint).
- **E2E 테스트 Python 3.14 호환성**: `c4efc3b` — E2E 테스트가 Python 3.14에서 실패하던 문제 수정
- **CI 테스트 14건 그린화**: ffmpeg 설치 추가, STT/retention 테스트 환경 비의존화 (`9bedd37`)
- **openai 의존성 누락**: 런타임 의존성에 `openai` 추가 (CI 테스트 collection 실패 해소)
- **ruff 위반 84건 정리**: `46b127d` + export.py 예외 import 누락 수정

### Changed

- `WhisperEngine.load()`의 로드 우선순위가 MLX → faster-whisper → openai-whisper로 변경됨 (Apple Silicon은 MLX, Linux는 faster-whisper, 그 외는 openai-whisper).
- `DiarizationEngine.diarize()` 시그니처가 `vad_filter`/`num_speakers`/`min_speakers`/`max_speakers`/`target_sample_rate` 인자를 받도록 확장. 기본값은 기존 동작과 호환.
- `MinutesCreateRequest`에 `stt_task_id` 선택 필드 추가 (병렬 모드에서 매칭에 사용).
- `TranscriptionCreate` 응답에 `diarization_task_id` 선택 필드 추가.

### Performance (실측)

오디오 길이/내용에 따라 효과가 다름. NUC(Intel CPU)에서 측정.

| 시나리오 | 변경 전 E2E | 변경 후 E2E | 단축 |
|---|---|---|---|
| 짧은 녹음 (8~10s) | ~30s | **~16s** | -47% |
| 중간 녹음 (15~20s) | ~30s | **~21s** | -30% |
| 긴 녹음 (100s, 단순) | ~140s | ~110s | -21% |
| 긴 녹음 (100s, 복잡) | ~140s | ~360s ※ | (변동성) |

※ pyannote는 segment 변화점이 많을수록 CPU 추론 시간이 비선형 증가. CPU 환경의 본질적 한계.

### Known Limitations

- pyannote 3.1 + CPU는 segment 복잡도에 매우 민감 (RT 1.4~3.5 변동). 진정한 가속은 GPU 도입 또는 모델 교체 필요.
- 다운샘플링 옵션은 실험적이며 정확도 손실 위험으로 default 비활성.
- VAD는 음성 비율 < 85%인 회의에서만 자동 적용 (안전장치).

### Migration Notes

- NUC venv: `pip install faster-whisper>=1.0.0 silero-vad>=5.0` 필요.
- SQLite DB는 `is_guest`/`guest_session_id` 컬럼 추가 마이그레이션 적용 권장 (이 변경 세션에서 NUC에는 ALTER로 적용 완료).
- 백엔드 재시작 필요: Celery worker가 새 코드를 import해야 함.
- iPhone 앱은 SSE 변경을 위해 재빌드 필요 (`flutter run --release ... --dart-define=API_KEY=... -d <UDID>`).
