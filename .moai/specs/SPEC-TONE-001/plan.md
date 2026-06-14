# SPEC-TONE-001 구현 계획

> Related SPEC: `spec.md` (EARS 요구사항 14개), `acceptance.md` (검수 시나리오 6개)
> Research Artifacts: `research.md`, `research-client.md`, `research-ser.md`, `roadmap.md`
> Development Methodology: TDD (RED-GREEN-REFACTOR)

## 1. 구현 단계 (모듈별)

### M1: ToneEngine 싱글톤 (REQ-TONE-001, 002, 003)

**목표**: opensmile + librosa 기반 prosody 추출 ML 싱글톤 클래스 구현.

**작업 항목**:
1. `backend/ml/tone_engine.py` 신규 파일 생성
2. `WhisperEngine`(`stt_engine.py` L65-450)의 double-checked locking 패턴 복제
3. `_check_memory_usage()` 메서드 구현 (stt_engine.py L425-434 참조, 19.2GB 경고선)
4. `analyze_segments(wav_path, segments)` 메서드 구현:
   - 세그먼트 길이 < `tone_min_segment_duration_sec`(0.5초) 스킵 (REQ-TONE-002)
   - opensmile eGeMAPSv02 88차원 feature 추출
   - librosa F0(pYIN), RMS energy, speaking rate 계산
   - tone 분류: calm/excited/authoritative/hesitant/monotone (5-class)
5. `lifecycle.py` startup warm-up에 ToneEngine 추가

**테스트**(RED 먼저):
- `test_tone_engine_singleton.py`: 동일 인스턴스 보장
- `test_tone_engine_memory_check.py`: 19.2GB 초과 시 예외 발생
- `test_tone_engine_short_segment.py`: 0.5초 미만 세그먼트 스킵

---

### M2: 오디오 보존 아키텍처 (REQ-TONE-004, 005, 006)

**목표**: DIA wav 삭제 시점을 tone_task 완료 후로 이연.

**작업 항목**:
1. `backend/workers/tasks/diarization_task.py` L446-450 수정:
   - 기존: `finally` 블록에서 DIA wav 즉시 삭제
   - 변경: tone_task 완료 콜백 또는 별도 정리 태스크에서 삭제
2. tone_task 실패/타임아웃 시 fallback 삭제 경로 구현 (orphan 방지)
3. tone_task 예외 격리: tone 실패가 STT/DIA/Minutes/Sentiment에 영향 주지 않도록 try-except 래핑 (REQ-TONE-006)

**테스트**:
- `test_dia_wav_preserved.py`: DIA 완료 후 tone_task 창구 동안 wav 존재 확인
- `test_dia_wav_cleanup_on_tone_complete.py`: tone_task 완료 후 wav 삭제 확인
- `test_tone_failure_isolation.py`: tone_task 실패 시 minutes/sentiment 정상 동작 확인

---

### M3: Celery 태스크 (REQ-TONE-007, 008)

**목표**: DIA 완료 후 tone_task 자동 트리거 및 Celery 등록.

**작업 항목**:
1. `backend/workers/tasks/tone_task.py` 신규 파일 생성:
   - `tone_celery_task` Celery 데코레이터(`soft_time_limit`, `max_retries=2`)
   - `_update_task_status()` Redis 상태 업데이트 (패턴: `summary_task.py` L34-73)
   - `_get_active_tone_count()` 동시성 추적 (Redis ZSET `active_tone_jobs_ts`)
   - Redis 키 패턴: `task:tone:status:{task_id}`, `task:tone:result:{task_id}`
   - SSE 이벤트 발행: `publish_task_event_sync()` 활용
2. `diarization_task.py`에 tone_task 트리거 추가:
   - DIA completed 전이 시 `tone_celery_task.delay()` 호출 (단, `tone_model` 빈 값이면 스킵)
3. `backend/workers/celery_app.py` `include` 리스트에 `"backend.workers.tasks.tone_task"` 추가 (REQ-TONE-008)
4. `backend/app/api/v1/transcription/stream.py` SSE prefix 루프에 `"task:tone:status:"` 추가

**테스트**:
- `test_tone_task_registered.py`: Celery registered task 목록에 tone_task 존재
- `test_tone_task_triggered_after_dia.py`: DIA 완료 후 tone_task 자동 실행
- `test_tone_task_skipped_when_model_empty.py`: tone_model 빈 값 시 트리거 안 함

---

### M4: 스키마/API (REQ-TONE-009, 010, 011)

**목표**: tone 전용 독립 엔드포인트 및 스키마 정의.

**작업 항목**:
1. `backend/schemas/tone.py` 신규 파일:
   - `ToneSegment`: start, end, speaker, tone(5-class), confidence, prosody_features(dict)
   - `SpeakerTone`: speaker, dominant_tone, tone_distribution(dict), avg_pitch, avg_energy
   - `ToneResponse`: task_id, status, segments, speakers, overall_tone, error_message
   - `ToneStatusResponse`: task_id, status, progress, message, error_message
2. `backend/app/api/v1/analytics/tone.py` 신규 라우터:
   - `GET /api/v1/tone/{task_id}`: ToneResponse 반환 (REQ-TONE-010)
   - `GET /api/v1/tone/{task_id}/status`: ToneStatusResponse
   - `GET /api/v1/tone/meeting/{meeting_id}`: meeting 기준 tone 결과
   - `DELETE /api/v1/tone/{task_id}`: Redis 캐시 삭제
   - `tone_model` 빈 값 시 503 Service Unavailable (REQ-TONE-011)
3. `backend/app/api/v1/registry.py` L113(sentiment.router) 근처에 tone.router 등록
4. 기존 `/api/v1/sentiment/*` 스키마 변경 금지 (REQ-TONE-009)

**테스트**:
- `test_tone_api_endpoints.py`: GET/status/meeting/DELETE 엔드포인트 동작
- `test_tone_api_503_when_disabled.py`: tone_model 빈 값 시 503
- `test_sentiment_schema_unchanged.py`: 기존 sentiment 스키마 호환성 유지

---

### M5: Flutter 통합 (REQ-TONE-012, 013)

**목표**: 감정 분석 탭 내 tone timeline 섹션 렌더링 및 에러 격리.

**작업 항목**:
1. `client/lib/services/tone_api.dart` 신규 파일:
   - `getToneResult(taskId)`: GET /api/v1/tone/{task_id}
   - `getToneByMeeting(meetingId)`: GET /api/v1/tone/meeting/{meeting_id}
   - API 실패 시 명시적 예외 throw (silent fallback 금지, REQ-TONE-013)
2. `client/lib/providers/result_provider.dart`에 toneProvider 추가:
   - `FutureProvider.family<ToneResponse, String>` 패턴
3. `client/lib/screens/result_screen.dart` 수정:
   - `_SentimentTab` 내 tone timeline 섹션 추가 (REQ-TONE-012)
   - tone 데이터 없을 시 EmptyStateWidget
   - 로딩 중 ProgressIndicator
   - tone API 실패 시 에러 메시지 + 재시도 버튼 (sentiment 카드와 분리, REQ-TONE-013)
4. tone timeline 시각화:
   - 세그먼트별 tone 색상 매핑(calm=파랑, excited=주황 등)
   - Material built-in 위젯 사용(기존 패턴 준수, 차트 라이브러리 추가 없음)

**테스트**:
- `test_tone_api_client.dart`: API 호출 및 예외 처리
- `test_tone_timeline_render.dart`: timeline 렌더링 및 빈 상태
- `test_tone_error_isolation.dart`: tone 실패 시 sentiment 카드 정상 유지

---

### M6: 설정 및 의존성 (REQ-TONE-008, 011, 014)

**목표**: tone 관련 설정 추가 및 의존성 선언.

**작업 항목**:
1. `backend/app/config.py` L60-84(DIA/요약 설정 블록 근처)에 추가:
   - `tone_model: str = ""` (빈 값이면 비활성화, REQ-TONE-011)
   - `tone_result_ttl: int = 86400` (24시간)
   - `max_concurrent_tone: int = 1` (concurrency=1 권장)
   - `tone_min_segment_duration_sec: float = 0.5` (REQ-TONE-002)
2. `pyproject.toml` 의존성 추가:
   - `opensmile = "^2.6.0"` (AGPL-3.0, REQ-TONE-014)
   - `librosa = "^0.10.0"` (ISC)
3. README 로컬 전용 처리 정책과 AGPL 호환성 명시 (REQ-TONE-014)

**테스트**:
- `test_config_tone_settings.py`: 설정 기본값 및 환경변수 오버라이드
- `test_dependencies_install.py`: opensmile/librosa import 가능

---

## 2. 파일 임팩트 표

### 신규 파일 (7개)

| 파일 | 설명 | 모듈 |
|------|------|------|
| `backend/ml/tone_engine.py` | opensmile+librosa prosody 추출 싱글톤 | M1 |
| `backend/workers/tasks/tone_task.py` | DIA 완료 후 tone 분석 Celery 태스크 | M3 |
| `backend/schemas/tone.py` | ToneSegment, SpeakerTone, ToneResponse | M4 |
| `backend/app/api/v1/analytics/tone.py` | /tone/{task_id}, /tone/meeting/{id} | M4 |
| `client/lib/services/tone_api.dart` | tone API 클라이언트 | M5 |
| `backend/tests/unit/test_tone_engine.py` | ToneEngine 단위 테스트 | M1 |
| `backend/tests/integration/test_tone_pipeline.py` | DIA → tone 통합 테스트 | M3 |

### 수정 파일 (6개)

| 파일 | 변경 내용 | 모듈 |
|------|-----------|------|
| `backend/workers/tasks/diarization_task.py` | L446-450 DIA wav 삭제 시점 이연 (tone_task 완료 후) | M2 |
| `backend/workers/celery_app.py` | `include`에 `tone_task` 추가 | M3 |
| `backend/app/api/v1/registry.py` | tone.router 등록 (L113 근처) | M4 |
| `backend/app/config.py` | tone_model, tone_min_segment_duration_sec 등 추가 | M6 |
| `backend/app/lifecycle.py` | startup warm-up에 ToneEngine 추가 | M1 |
| `client/lib/screens/result_screen.dart` | 감정 탭 내 tone 섹션 | M5 |

### 의존성 파일 (1개)

| 파일 | 변경 내용 | 모듈 |
|------|-----------|------|
| `pyproject.toml` | opensmile ^2.6.0, librosa ^0.10.0 추가 | M6 |

---

## 3. 아키텍처 결정사항

### A1: 오디오 보존 전략 — DIA wav 삭제 시점 이연

**결정**: `diarization_task.py` L446-450의 DIA wav 즉시 삭제를 tone_task 완료 후로 이연.

**배경**: 현재 DIA wav는 DIA 태스크 완료 시 즉시 삭제됨. tone 분석을 위해서는 세그먼트별 waveform 슬라이싱이 필요하므로 wav 보존이 필수.

**구현 방식**:
1. DIA wav 삭제 로직을 `finally` 블록에서 제거
2. tone_task의 `finally` 블록에서 wav 삭제 (성공/실패 무관)
3. fallback: tone_task 타임아웃 시에도 wav 삭제 (orphan 방지)
4. tone_min_segment_duration_sec(0.5초) 이상 세그먼트만 처리하여 불필요한 연산 방지

**대안 검토**:
- **A2: 세그먼트별 오디오 추출 후 results_dir 영구 저장** — 디스크 사용량 증가(1시간 회의 × 200~500세그먼트 × 16kHz 모노), 프라이버시 정책 충돌. 기각.
- **A3: DIA 태스크 인라인 통합** — DIA 태스크 책임 증가, 결합도 상승. 기각.

**리스크**: DIA wav 보존 기간 연장으로 인한 디스크 사용량 일시적 증가. 단, tone_task 처리 시간(< 90초/1시간 회의) 내 삭제되므로 실질적 영향 미미.

### A2: ToneEngine 싱글톤 패턴

**결정**: WhisperEngine/DiarizationEngine의 double-checked locking 패턴을 그대로 복제. 별도 추상 기반 클래스나 레지스트리 도입 없음.

**근거**: research.md Section 6.3 권장사항. 별도 리팩토링은 SPEC 범위 외.

### A3: tone 분류 체계 — 회의 맥락 5-class

**결정**: calm/excited/authoritative/hesitant/monotone 5-class 사용.

**근거**: 일반 감정 인식(7-class) 대신 회의 맥락에 특화. 기존 SentimentSegment.emotion(10 labels)과 독립 차원. 향후 SPEC-SER-001에서 융합 가능.

---

## 4. 라이브러리 의존성

| 라이브러리 | 버전 | 용도 | License | 비고 |
|-----------|------|------|---------|------|
| opensmile | ^2.6.0 | eGeMAPSv02 88차원 feature 추출 | AGPL-3.0 | 로컬 전용 사용으로 회피 가능 |
| librosa | ^0.10.0 | F0(pYIN), RMS energy, speaking rate | ISC | 제약 없음 |
| numpy | (기존) | waveform 배열 처리 | BSD | 이미 설치됨 |

**설치 명령**:
```bash
pip install "opensmile>=2.6.0" "librosa>=0.10.0"
```

**AGPL-3.0 리스크 관리**:
- voice-to-textnote는 "로컬 전용 처리" 정책(README)으로 네트워크 서비스 형태 제공 안 함
- AGPL의 소스 공개 의무는 "사용자가 네트워크를 통해 프로그램과 상호작용"하는 경우에만 발생
- 로컬 설치형 애플리케이션은 해당하지 않음
- 단, 향후 SaaS 전환 시 opensmile 대안 검토 필요(pyannote-audio 내부 extractor 또는 torchaudio 직접 구현)

---

## 5. 리스크 및 완화책

| 리스크 | 심각도 | 확률 | 완화책 |
|--------|--------|------|--------|
| DIA wav 보존 연장으로 디스크 부족 | 중간 | 낮음 | tone_task 처리 시간 < 90초, 즉시 삭제. retention.py 24시간 초과 파일 정리 유지 |
| opensmile AGPL 라이선스 위반 | 높음 | 낮음 | 로컬 전용 정책 명시, README에 AGPL 호환성 문서화. SaaS 전환 시 대안 준비 |
| tone 분류 5-class 정확도 부족 | 중간 | 중간 | 자체 eval set 구축 필수. 초기에는 confidence 임계값 미달 시 "unknown" 라벨 반환 |
| Celery concurrency=1 병목 | 중간 | 중간 | tone_task를 DIA 완료 후 비동기 트리거하여 STT/DIA 블로킹 방지 |
| tone_task 실패 시 기존 파이프라인 영향 | 높음 | 낮음 | try-except로 예외 완전 격리 (REQ-TONE-006). tone 실패는 로그만 남기고 파이프라인 계속 |
| 기존 /sentiment/* 스키마 호환성 깨짐 | 높음 | 낮음 | tone은 독립 엔드포인트(/tone/*) 제공. SentimentResponse 변경 금지 (REQ-TONE-009) |
| memory 경고선(19.2GB) 초과 | 높음 | 낮음 | _check_memory_usage() 사전 검사. opensmile+librosa 추가 메모리 < 0.2GB |

---

## 6. 메모리 예산 (M4 Mac mini 24GB)

| 컴포넌트 | 메모리 | 단계 |
|----------|--------|------|
| 현재 사용 (Whisper + pyannote + FastAPI + Redis) | ~12GB | 기준 |
| SPEC-TONE-001 추가 (opensmile + librosa 런트임) | +0.1GB | 본 SPEC |
| **총합** | **~12.1GB** | 경고선 19.2GB 내 안전 (여유 7.1GB) |
| 향후 SPEC-SER-001 추가 (emotion2vec_plus_base) | +0.4GB | 후속 SPEC |
| **최종 예상 총합** | **~12.5GB** | 경고선 19.2GB 내 안전 |

**근거**: roadmap.md Section 5.1 메모리 예산 분석. opensmile/librosa는 경량 라이브러리로 모델 로드 없이 피처 추출만 수행하므로 추가 메모리 미미.

---

## 7. 예상 소요 기간

| 단계 | 예상 기간 | 의존성 |
|------|-----------|--------|
| M1: ToneEngine 싱글톤 | 1~1.5일 | 없음 |
| M2: 오디오 보존 아키텍처 | 0.5~1일 | M1 완료 |
| M3: Celery 태스크 | 1일 | M1, M2 완료 |
| M4: 스키마/API | 0.5~1일 | M3 완료 |
| M5: Flutter 통합 | 1일 | M4 완료 |
| M6: 설정 및 의존성 | 0.5일 | 독립 수행 가능 |
| **총합** | **3~5일** | - |

---

## 8. 성공 기준

- [x] 모든 EARS 요구사항(REQ-TONE-001~014) 구현 및 테스트 통과
- [x] TDD RED-GREEN-REFACTOR 사이클 준수 (테스트 먼저 작성)
- [x] 코드 커버리지 85% 이상 (tone_engine.py, tone_task.py, tone.py)
- [x] 기존 /sentiment/* API 하위 호환성 유지 (회귀 테스트 통과)
- [x] DIA wav 삭제 시점 이연 후 디스크 정리 정상 동작
- [x] tone_model 빈 값 시 기능 비활성화 정상 동작
- [x] Flutter tone timeline 렌더링 및 에러 격리 정상 동작
- [x] acceptance.md 검수 시나리오 6개(AC-TONE-001~006) 전체 통과
- [x] TRUST 5 품질 게이트 통과 (0 에러, 0 타입 에러, 0 린트 에러)

2026-06-14 재검증:
- backend 전체 suite: `venv/bin/python -m pytest backend -q` -> `3323 passed, 16 skipped`, coverage `98.62%`
- focused e2e suite: `venv/bin/python -m pytest -o addopts="" backend/tests/e2e/test_pipeline_e2e.py -q` -> `16 passed`
- `venv/bin/python -m ruff check backend` -> `All checks passed!`
- `venv/bin/python -m ruff format --check backend` -> `394 files already formatted`
- `venv/bin/python -m mypy backend` -> `Success: no issues found in 394 source files`
- `cd client && flutter analyze` -> `No issues found!`
- `cd client && flutter test` -> `324 passed`
