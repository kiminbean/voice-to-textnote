# Changelog

이 프로젝트의 주요 변경 사항을 기록합니다. 형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 따르고 [Semantic Versioning](https://semver.org/lang/ko/)을 사용합니다.

## [Unreleased]

### Added

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
