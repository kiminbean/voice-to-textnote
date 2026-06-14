# SPEC-TONE-001 검수 기준

## 1. 개요

본 문서는 발화 톤/운율 분석 통합 완료의 수락 기준을 Given/When/Then 형식으로 정의한다. 검수는 Celery 태스크 등록, DIA 완료 후 자동 트리거, 세그먼트 스킵 로직, 기존 파이프라인 무영향, Flutter timeline 렌더링, 기능 비활성화가 충족되는지 확인한다.

본 검수 기준은 SPEC-SENTIMENT-001/acceptance.md의 패턴을 준수하여 작성되었다.

---

## 2. 검수 시나리오

### AC-TONE-001: Celery tone_task 등록 및 실행

**관련 요구사항**: REQ-TONE-007, REQ-TONE-008

**Given**
- Redis가 실행 중이다.
- Celery 워커가 `backend.workers.celery_app` 설정으로 시작되어 있다.
- `celery_app.py`의 `include` 리스트에 `"backend.workers.tasks.tone_task"`가 등록되어 있다.
- 유효한 `task_id`에 대해 DIA wav 파일이 `temp_dir/{task_id}_dia.wav` 경로에 존재한다.
- `config.tone_model` 설정값이 비어 있지 않다(예: "egemaps-v2").

**When**
- DIA 태스크가 completed 상태로 전이된다.
- 또는 클라이언트가 tone_task를 수동으로 트리거한다.

**Then**
- Celery 워커는 `tone_celery_task`를 실제로 실행한다.
- tone_task 상태가 pending에 영구 대기하지 않고 processing → completed/failed 상태로 전이된다.
- 성공 시 `task:tone:result:{task_id}` Redis 키에서 tone 분석 결과를 조회할 수 있다.
- SSE 이벤트가 `publish_task_event_sync`를 통해 발행된다.

**통과 조건**
- Celery registered task 목록(`celery -A backend.workers.celery_app inspect registered`)에 tone_task가 확인된다.
- SPEC-SENTIMENT-001에서 발견된 것과 동일한 "큐 메시지만 생성되고 실행되지 않는" 결함이 재현되지 않는다.
- worker 로그에서 tone_task 실행 기록이 확인된다.

---

### AC-TONE-002: DIA 완료 후 자동 트리거

**관련 요구사항**: REQ-TONE-007

**Given**
- DIA 태스크가 진행 중이며, 완료 시 `diarization_task.py`에서 tone_task 트리거 로직이 활성화되어 있다.
- `config.tone_model`이 빈 문자열이 아니다.
- DIA 결과(SpeakerSegment[])가 Redis에 저장되어 있다.

**When**
- DIA 태스크가 정상적으로 completed 상태로 전이된다.

**Then**
- 시스템이 자동으로 `tone_celery_task.delay(task_id=..., dia_wav_path=..., segments=...)`를 호출한다.
- tone_task가 minutes_task와 병렬로 실행된다(직렬 블로킹 없음).
- tone_task 완료 후 DIA wav 파일이 삭제된다(REQ-TONE-005).
- tone_task 결과가 `task:tone:result:{task_id}`에 저장된다.

**통과 조건**
- DIA 완료 이벤트와 tone_task 시작 이벤트의 타임스탬프 차이가 5초 이내이다.
- DIA 완료 후 DIA wav가 tone_task 완료 시점까지 존재한다.
- tone_task 완료 후 DIA wav가 더 이상 존재하지 않는다.

---

### AC-TONE-003: 짧은 세그먼트 스킵

**관련 요구사항**: REQ-TONE-002

**Given**
- `config.tone_min_segment_duration_sec`가 0.5초로 설정되어 있다.
- DIA 결과에 다양한 길이의 세그먼트가 포함되어 있다:
  - 세그먼트 A: 0.3초(0.5초 미만)
  - 세그먼트 B: 2.1초(0.5초 이상)
  - 세그먼트 C: 0.49초(0.5초 미만, 경계값)
  - 세그먼트 D: 0.5초(0.5초 이상, 경계값)

**When**
- ToneEngine이 `analyze_segments(wav_path, segments)`를 호출한다.

**Then**
- 세그먼트 A(0.3초)와 C(0.49초)는 prosody 분석이 스킵된다.
- 세그먼트 B(2.1초)와 D(0.5초)는 정상적으로 prosody 분석이 수행된다.
- 스킵된 세그먼트는 결과에서 tone=None, confidence=0.0으로 표시되거나 결과 리스트에서 제외된다.
- 스킵 여부가 로그에 기록된다.

**통과 조건**
- 0.5초 미만 세그먼트에 대해 opensmile/librosa 연산이 수행되지 않는다(성능 검증).
- 0.5초 이상 세그먼트는 정상적인 tone 분류 결과를 반환한다.
- 경계값(0.5초) 세그먼트는 처리 대상에 포함된다.

---

### AC-TONE-004: tone_task 실패 시 기존 파이프라인 무영향

**관련 요구사항**: REQ-TONE-006

**Given**
- DIA 태스크가 정상 완료되었다.
- tone_task 실행 중 메모리 부족, opensmile 오류, 또는 DIA wav 손상으로 인해 예외가 발생한다.
- 동일한 task_id에 대해 minutes_task, sentiment_task, summary_task가 실행 중이거나 대기 중이다.

**When**
- tone_task가 예외를 발생시키고 실패 상태로 전이된다.

**Then**
- minutes_task는 정상적으로 완료되어 회의록을 생성한다.
- sentiment_task는 정상적으로 완료되어 감정 분석 결과를 반환한다.
- summary_task는 정상적으로 완료되어 요약을 생성한다.
- tone_task 실패가 다른 태스크의 상태나 결과에 영향을 주지 않는다.
- DIA wav 파일이 tone_task 실패 후에도 정리된다(orphan 방지, REQ-TONE-005).
- tone_task 실패가 error 로그에 기록되지만 전체 파이프라인은 계속된다.

**통과 조건**
- tone_task 실패 후에도 `GET /api/v1/minutes/{meeting_id}`가 정상 응답을 반환한다.
- tone_task 실패 후에도 `GET /api/v1/sentiment/{task_id}`가 정상 응답을 반환한다.
- tone_task 실패가 Celery 워커를 크래시시키지 않는다(워커 재시작 없음).
- 실패한 tone_task의 에러 메시지가 `task:tone:status:{task_id}`에 기록된다.

---

### AC-TONE-005: Flutter tone timeline 렌더링

**관련 요구사항**: REQ-TONE-012, REQ-TONE-013

**Given**
- 회의 결과 화면을 열 수 있는 completed meeting/task가 있다.
- `GET /api/v1/tone/meeting/{meeting_id}` 응답에 `segments`, `speakers`, `overall_tone`이 포함되어 있다.
- 각 segment에는 tone(5-class), confidence, prosody_features가 포함되어 있다.
- Flutter 클라이언트가 `tone_api.dart`를 통해 tone 데이터를 조회할 수 있다.

**When**
- 사용자가 회의 결과 화면에서 감정 분석 탭을 클릭한다.

**Then**
- 감정 분석 탭 내에 tone timeline 섹션이 표시된다.
- tone timeline이 시간 순서대로 세그먼트별 tone 색상(calm=파랑, excited=주황 등)으로 렌더링된다.
- tone 데이터가 없을 때 EmptyStateWidget이 표시된다.
- 로딩 중에는 ProgressIndicator가 표시된다.
- tone API 호출 실패 시 에러 메시지와 재시도 버튼이 표시된다(REQ-TONE-013).
- tone 섹션 실패가 감정 분석 카드 렌더링에 영향을 주지 않는다.

**통과 조건**
- tone timeline이 시간 순서로 누락 없이 표시된다.
- tone API 실패 시 `SizedBox.shrink()` 기반 silent failure가 발생하지 않는다(SPEC-SENTIMENT-001 결함 반복 금지).
- tone 섹션 에러 시에도 감정 분석 카드는 정상 렌더링된다.
- 위젯 테스트에서 tone 데이터 로드, 빈 상태, 에러 상태, 재시도 콜백이 검증된다.

---

### AC-TONE-006: tone_model 빈 값 시 비활성화

**관련 요구사항**: REQ-TONE-011

**Given**
- `config.tone_model` 설정값이 빈 문자열(`""`)이다(기본값).
- DIA 태스크가 완료된 task_id가 존재한다.

**When**
- DIA 태스크가 completed 상태로 전이된다.
- 또는 클라이언트가 `GET /api/v1/tone/{task_id}`를 요청한다.

**Then**
- DIA 완료 후 tone_task가 트리거되지 않는다(`tone_celery_task.delay()` 호출 안 됨).
- `GET /api/v1/tone/{task_id}` API가 503 Service Unavailable을 반환한다.
- 응답 본문에 "Tone analysis is disabled (tone_model is not configured)" 메시지가 포함된다.
- 기존 파이프라인(STT/DIA/Minutes/Sentiment/Summary)은 정상 동작한다.
- Celery 워커 로그에 tone_model 미설정 관련 경고가 기록되지 않는다(정상 비활성화).

**통과 조건**
- tone_model 빈 문자열일 때 `celery_app.py`에 tone_task가 등록되어 있더라도 태스크가 실행되지 않는다.
- API 응답 코드가 503이며, 에러 메시지가 명확하다.
- tone 비활성화 상태에서 DIA wav 삭제 시점이 기존 정책(DIA 완료 후 즉시 삭제)으로 유지된다.
- tone_model을 유효한 값(예: "egemaps-v2")으로 설정하면 기능이 활성화된다.

---

## 3. 최종 완료 체크리스트

### 백엔드

- [x] `backend/workers/celery_app.py`에 `backend.workers.tasks.tone_task`가 등록되어 있다.
- [x] `backend/ml/tone_engine.py`가 WhisperEngine/DiarizationEngine 싱글톤 패턴을 따른다.
- [x] `_check_memory_usage()`가 19.2GB 초과 시 예외를 발생시킨다.
- [x] 세그먼트 길이 < `tone_min_segment_duration_sec`(0.5초) 시 분석이 스킵된다.
- [x] `diarization_task.py` L446-450의 DIA wav 삭제가 tone_task 완료 후로 이연되었다.
- [x] tone_task 실패 시 DIA wav가 orphan 없이 정리된다.
- [x] DIA 완료 후 tone_task가 자동 트리거된다(tone_model 빈 값이면 스킵).
- [x] `backend/schemas/tone.py`에 ToneSegment, SpeakerTone, ToneResponse가 정의되어 있다.
- [x] `GET /api/v1/tone/{task_id}`가 ToneResponse를 반환한다.
- [x] tone_model 빈 값 시 API가 503을 반환한다.
- [x] 기존 `/api/v1/sentiment/*` 스키마가 변경되지 않았다.
- [x] `stream.py` SSE prefix 루프에 `task:tone:status:`가 추가되었다.
- [x] `main.py` lifespan startup warm-up에 ToneEngine이 추가되었다.
- [x] `config.py`에 tone_model, tone_min_segment_duration_sec 등이 추가되었다.

### Flutter

- [x] `client/lib/services/tone_api.dart`가 tone API 클라이언트를 제공한다.
- [x] 감정 분석 탭 내 tone timeline 섹션이 렌더링된다.
- [x] tone API 실패 시 에러 메시지와 재시도 버튼이 표시된다(silent failure 아님).
- [x] tone 섹션 에러 시 감정 분석 카드가 정상 렌더링된다.
- [x] tone 데이터 없을 시 EmptyStateWidget이 표시된다.

### 의존성 및 라이선스

- [x] `pyproject.toml`에 `opensmile >=2.6.0`이 추가되었다.
- [x] `pyproject.toml`에 `librosa >=0.10.0`이 추가되었다.
- [x] opensmile AGPL-3.0 라이선스가 로컬 전용 사용으로 회피 가능함이 문서화되었다.

### 품질 게이트

- [x] TDD RED-GREEN-REFACTOR 사이클 준수(테스트 먼저 작성)
- [x] 코드 커버리지 85% 이상(tone_engine.py, tone_task.py, tone.py)
  - 2026-06-14 추가 검증: API aggregate `2545/2545`, `100.00%`, `missing=[]`
  - 대상 테스트: `backend/tests/unit/test_api_coverage_completion.py`, `backend/tests/unit/test_devices_api_coverage.py`
- [x] TRUST 5 통과(0 에러, 0 타입 에러, 0 린트 에러)
- [x] 기존 회귀 테스트 전체 통과(sentiment 포함)
  - 2026-06-14 backend 전체 suite: `3323 passed, 16 skipped`, coverage `99.01%`
  - `ruff check .` -> `All checks passed!`
  - `mypy .` -> `Success: no issues found in 394 source files`
- [x] acceptance.md 시나리오 6개(AC-TONE-001~006) 전체 통과

### 하위 호환성

- [x] 기존 `/api/v1/sentiment/*` 응답 스키마가 유지된다.
- [x] 기존 STT/DIA/Minutes/Sentiment/Summary 파이프라인 동작이 변경되지 않는다.
- [x] DIA wav 삭제 정책 변경이 기존 retention.py 동작에 영향을 주지 않는다.
