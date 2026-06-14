---
id: SPEC-TONE-001
version: "1.0.0"
status: completed
created: 2026-06-14
updated: 2026-06-14
completed: 2026-06-14
author: MoAI
priority: P2
issue_number: 31
related_specs: [SPEC-SENTIMENT-001, SPEC-MIN-001, SPEC-DIA-001]
---

# SPEC-TONE-001: 발화 톤/운율 분석 (Speech Tone/Prosody Analysis)

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-06-14 | 초안 작성. SPEC-ANALYTICS-001에서 분리된 음향 특징 기반 톤 분석 SPEC | MoAI |

---

### 배경

본 SPEC은 원래 SPEC-ANALYTICS-001(발화 톤/감정 분석 통합)에서 분리되었다. 깊은 리서치 결과 텍스트 감정 분석이 SPEC-SENTIMENT-001로 이미 완료되었음이 확인되어, 음향 특징(pitch/energy/tempo) 기반 톤 분석을 독립 SPEC으로 분리했다. 향후 SPEC-SER-001(오디오 감정 인식)에서 텍스트 감정 + 톤 + SER 융합을 수행할 예정이다.

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 플랫폼 | M4 Mac mini 24GB (Apple Silicon, MPS) |
| 운영체제 | macOS 12+ (Apple Silicon M1/M2/M3/M4) |
| 런타임 | Python >= 3.11, FastAPI >= 0.135.1, uvicorn >= 0.34.0 |
| ML 프레임워크 | opensmile ^2.6.0 (eGeMAPSv02), librosa ^0.10.0 (F0/RMS/speaking rate) |
| 비동기 처리 | Celery >= 5.6.2, Redis >= 7.0 (concurrency=1 권장) |
| 메시지 브로커 | Redis (task:tone:status:{task_id}, task:tone:result:{task_id}) |
| 영속 저장 | TaskResult.result_data JSON (task_type="tone") |
| 클라이언트 | Flutter/Riverpod, dio (HTTP) |
| 입력 데이터 | DIA wav (`temp_dir/{task_id}_dia.wav`) + SpeakerSegment[] (start/end/speaker_id) |
| 오디오 포맷 | 16kHz 모노 WAV (DIA 전처리 산출물) |
| 디바이스 | CPU 기반 처리 (opensmile/librosa는 MPS 미사용) |

---

## 2. 가정 (Assumptions)

- SPEC-SENTIMENT-001(텍스트 감정 분석)이 completed 상태이며, `/api/v1/sentiment/*` 스키마가 안정적으로 동작한다.
- `diarization_task.py`가 생성한 DIA wav(`temp_dir/{task_id}_dia.wav`)가 tone 분석 창구 동안 보존된다. 현재 L446-450에서 즉시 삭제되는 정책을 tone_task 완료 후로 이연한다(아키텍처 결정 A1).
- 화자 분할(SpeakerSegment)의 start/end 타임스탬프(소수점 3자리 정밀도)가 세그먼트별 오디오 슬라이싱에 충분한 정확도를 제공한다.
- DIA wav는 16kHz 모노 WAV 포맷으로, opensmile/librosa 입력 요구사항을 충족한다.
- 본 SPEC은 로컬 전용 처리 환경에서만 동작한다. 클라우드 업로드나 네트워크 서비스 형태의 외부 제공을 하지 않는다(AGPL 회피 조건).
- WhisperEngine(`stt_engine.py` L65-450)과 DiarizationEngine(`diarization_engine.py` L26-704)의 double-checked locking 싱글톤 패턴을 ToneEngine이 그대로 복제한다.
- `_check_memory_usage()` 패턴(stt_engine.py L425-434, 경고선 19.2GB)을 ToneEngine이 동일하게 채택한다.
- tone 분류 체계는 회의 맥락에 특화된 5-class(calm/excited/authoritative/hesitant/monotone)를 사용하며, 기존 SentimentSegment.emotion(10 labels)과 독립적인 차원으로 취급한다.
- Celery 워커 `concurrency=1` 권장 하에서 tone_task가 STT/DIA와 동시 실행될 때 메모리 경합이 발생하지 않는다(추가 메모리 < 0.2GB).
- tone 분석 결과는 기존 `TaskResult` 테이블의 `result_data` JSON 컬럼에 task_type="tone"으로 저장되며, 별도 DB 마이그레이션은 필요 없다.
- 향후 SPEC-SER-001(오디오 감정 인식)이 본 SPEC의 오디오 보존 아키텍처를 재사용한다.
- 프라이버시 정책(README "로컬 전용 처리")과 일관되게, 오디오 파일은 외부로 전송되지 않으며 보존 연장은 정책 위반이 아니다.

---

## 3. 요구사항 (Requirements)

### 모듈 1: ToneEngine (ML 싱글톤)

ToneEngine은 opensmile(eGeMAPSv02 88차원 feature)과 librosa(F0, RMS energy, speaking rate)를 결합해 세그먼트별 prosody 특징을 추출하는 ML 싱글톤 클래스다. WhisperEngine/DiarizationEngine과 동일한 double-checked locking 패턴으로 프로세스당 단일 인스턴스를 보장한다.

**[REQ-TONE-001] [유비쿼터스]** ToneEngine은 항상 WhisperEngine/DiarizationEngine의 double-checked locking 싱글톤 패턴을 따라야 한다. `get_instance()` 클래스메서드로 프로세스당 단일 인스턴스를 보장하고, `lifecycle.py` startup warm-up에 등록해야 한다.

**[REQ-TONE-002] [이벤트 기반]** WHEN 세그먼트 길이가 `tone_min_segment_duration_sec`(기본 0.5초) 미만일 때 THEN ToneEngine은 해당 세그먼트의 prosody 분석을 스킵하고 빈 결과를 반환해야 한다. 짧은 세그먼트는 F0/RMS 추출이 불안정하기 때문이다.

**[REQ-TONE-003] [원치 않는 행동]** ToneEngine은 `_check_memory_usage()` 호출 결과 시스템 메모리가 19.2GB 경고선을 초과했을 때 분석을 중단하고 예외를 발생시켜야 한다. 기존 STT/DIA 파이프라인에 메모리 부족 영향을 주어서는 안 된다.

### 모듈 2: 오디오 보존 아키텍처

현재 DIA wav는 `diarization_task.py` L446-450에서 DIA 완료 즉시 삭제된다. tone 분석은 세그먼트별 waveform 슬라이싱이 필요하므로, wav 보존 시점을 tone_task 완료 후로 이연한다. tone_task 실패/타임아웃 시에도 orphan 파일이 남지 않도록 fallback 삭제 경로를 마련한다. 이 변경은 기존 STT/DIA/Minutes/Sentiment 파이프라인 동작에 영향을 주지 않는다.

**[REQ-TONE-004] [상태 기반]** IF `temp_dir/{task_id}_dia.wav` 파일이 존재할 때 THEN tone 분석이 수행 가능하다. 파일이 존재하지 않으면 tone_task는 skipped 상태로 종료하고 빈 ToneResponse를 반환해야 한다.

**[REQ-TONE-005] [이벤트 기반]** WHEN tone_task가 완료(성공 또는 실패)할 때 THEN 시스템은 DIA wav 파일을 삭제해야 한다. tone_task 타임아웃 발생 시에도 fallback 경로에서 wav를 삭제해 orphan 파일이 남지 않도록 해야 한다.

**[REQ-TONE-006] [원치 않는 행동]** 본 SPEC은 기존 STT/DIA/Minutes/Sentiment 파이프라인의 동작을 변경하지 않아야 한다. tone_task 실패 시에도 회의록 생성, 요약, 감정 분석은 정상적으로 완료되어야 한다.

### 모듈 3: Celery 태스크

tone_task는 DIA 태스크 완료 후 minutes_task와 병렬로 실행되는 Celery 태스크다. SPEC-SENTIMENT-001에서 발견된 Celery `include` 리스트 누락 버그를 반복하지 않도록, `celery_app.py`에 tone_task를 명시적으로 등록한다. Redis 기반 상태 추적과 SSE 이벤트 발행 패턴은 기존 `summary_task`/`sentiment_task`를 따른다.

**[REQ-TONE-007] [이벤트 기반]** WHEN DIA 태스크가 completed 상태로 전이할 때 THEN 시스템은 tone_task를 minutes_task와 병렬로 트리거해야 한다. 단, `tone_model` 설정값이 빈 문자열이면 트리거하지 않는다.

**[REQ-TONE-008] [유비쿼터스]** `backend/workers/celery_app.py`의 `include` 리스트에는 항상 `"backend.workers.tasks.tone_task"`가 등록되어야 한다. 이 누락은 SPEC-SENTIMENT-001에서 발견된 것과 동일한 태스크 미실행 버그를 방지한다.

### 모듈 4: 스키마/API

tone 분석 결과는 기존 `/api/v1/sentiment/*`와 독립된 `/api/v1/tone/*` 엔드포인트로 제공한다. ToneSegment, SpeakerTone, ToneResponse를 `backend/schemas/tone.py`에 신규 정의하고, 기존 SentimentResponse 스키마는 변경하지 않는다. `tone_model` 설정값이 빈 문자열이면 API는 503 Service Unavailable을 반환한다.

**[REQ-TONE-009] [원치 않는 행동]** 본 SPEC은 기존 `/api/v1/sentiment/*` 응답 스키마를 변경하지 않아야 한다. ToneSegment, SpeakerTone, ToneResponse는 `backend/schemas/tone.py`에 독립적으로 정의하고, SentimentResponse에 새 필드를 추가할 때는 반드시 `Field(default=None)`로 optional 처리한다.

**[REQ-TONE-010] [이벤트 기반]** WHEN 클라이언트가 `GET /api/v1/tone/{task_id}`를 요청할 때 THEN 시스템은 ToneResponse(task_id, status, segments, speakers, overall_tone, error_message)를 반환해야 한다. 존재하지 않는 task_id에 대해서는 404 Not Found를 반환한다.

**[REQ-TONE-011] [상태 기반]** IF `tone_model` 설정값이 빈 문자열일 때 THEN tone 기능은 비활성화되어야 한다. API 엔드포인트는 503 Service Unavailable을 반환하고, Celery 태스크는 트리거되지 않는다.

### 모듈 5: Flutter

Flutter 클라이언트는 감정 분석 탭 내에 tone timeline 섹션을 렌더링한다. tone API 호출 실패 시 SPEC-SENTIMENT-001의 silent failure(`SizedBox.shrink()`) 패턴을 반복하지 않고, 명시적 에러 메시지와 재시도 버튼을 제공한다. tone 섹션 에러는 감정 분석 카드 렌더링에 영향을 주지 않는다.

**[REQ-TONE-012] [이벤트 기반]** WHEN 사용자가 감정 분석 탭을 열 때 THEN Flutter는 tone timeline을 렌더링해야 한다. tone 데이터가 없을 때는 빈 상태(EmptyStateWidget)를 표시하고, 로딩 중에는 ProgressIndicator를 표시한다.

**[REQ-TONE-013] [원치 않는 행동]** tone API 호출이 실패할 때 THEN 기존 감정 분석 UI에 영향을 주지 않아야 한다. tone 섹션만 에러 상태로 표시하고, 감정 분석 카드는 정상 렌더링을 유지해야 한다. SPEC-SENTIMENT-001의 silent failure(`SizedBox.shrink()`) 패턴을 반복하지 않고, 명시적 에러 메시지와 재시도 버튼을 제공한다.

### 모듈 6: 라이선스

opensmile은 AGPL-3.0 라이선스로, 네트워크 서비스 형태 제공 시 소스 공개 의무가 발생한다. voice-to-textnote는 "로컬 전용 처리" 정책을 따르므로 현재는 AGPL 의무가 회피된다. 단, 향후 SaaS 전환 시 opensmile 대안 검토가 필요하다.

**[REQ-TONE-014] [원치 않는 행동]** opensmile(AGPL-3.0)은 로컬 전용 처리 환경에서만 사용되어야 한다. 네트워크 서비스 형태로 외부에 제공하거나 소스 코드 공개 의무가 발생하는 형태로 배포하지 않아야 한다. voice-to-textnote의 "로컬 전용 처리" 정책(README)과 일치해야 한다.

---

## 4. 비기능 요구사항 (Non-Functional Requirements)

| 항목 | 목표값 | 비고 |
|------|--------|------|
| 메모리 사용량(추가) | < 0.2GB | opensmile + librosa 런타임. 현재 ~12GB 사용 중, 경고선 19.2GB |
| 세그먼트당 처리 시간 | < 500ms | eGeMAPSv02 88차원 추출 + F0/RMS 계산 |
| 1시간 회의 전체 처리 | < 90초 | 세그먼트 수에 비례(약 200~500개) |
| API 응답 시간(결과 조회) | < 100ms | Redis 캐시 활용 |
| 동시 tone_task 수 | 최대 1개 | Celery `concurrency=1` 권장, 메모리 보호 |
| 결과 캐시 TTL | 24시간 | 기존 TaskResult 패턴 준수 |
| 디스크 사용량(일시적) | DIA wav 크기 | tone_task 완료 후 즉시 삭제(~190MB/1시간 회의) |
| 코드 커버리지 | 85% 이상 | tone_engine.py, tone_task.py, tone.py 대상 |
| 에러 발생 시 복구 | 자동 재시도 2회 | 기존 Celery `max_retries` 패턴 준수 |

---

## 5. 기술 제약 조건 (Technical Constraints)

- **DIA wav 의존**: tone_task는 DIA wav가 존재하는 동안에만 실행 가능. 파일 삭제 시점 이연이 선행되어야 함.
- **tone_model 설정 필수**: 빈 문자열이면 tone 기능 전체 비활성화. 기본값은 빈 문자열(명시적 활성화 필요).
- **로컬 전용**: AGPL-3.0 라이선스(openSMILE) 회피를 위해 외부 네트워크 서비스 형태 제공 금지.
- **Celery 워커 concurrency=1**: tone_task가 STT/DIA와 동시 실행될 때 메모리 경합을 피하기 위해 단일 워커 권장.
- **MPS 미사용**: opensmile/librosa는 CPU 기반 처리. MPS 가속 불필요.
- **세그먼트 슬라이싱 정밀도**: SpeakerSegment.start/end(밀리초 정밀도) 기반 waveform 슬라이싱. `diarization_engine.py`의 `_compress_with_vad` L249-251 패턴 참조.
- **기존 API 하위 호환성**: `/api/v1/sentiment/*` 스키마 변경 금지. tone은 독립 엔드포인트(`/api/v1/tone/*`)로 제공.
- **별도 DB 마이그레이션 불필요**: TaskResult.result_data JSON 컬럼에 task_type="tone"으로 저장. 기존 패턴 준수.
- **tone 분류 검증**: 5-class 분류 체계는 자체 eval set 구축이 선행되어야 신뢰성 확보 가능. 초기에는 confidence 임계값 미달 시 "unknown" 라벨 반환.
- **SSE 진행률 스트리밍**: `stream.py`의 prefix 루프에 `task:tone:status:` 추가 필요(SPEC-SENTIMENT-001 패턴 준수).

---

## 6. 의존성 (Dependencies)

| 라이브러리 | 버전 | 용도 | License |
|-----------|------|------|---------|
| opensmile | ^2.6.0 | eGeMAPSv02 감정 특화 feature(88차원) 추출 | AGPL-3.0 |
| librosa | ^0.10.0 | F0(pYIN), RMS energy, speaking rate, mel-spec | ISC |
| numpy | (기존) | 수치 연산, waveform 배열 처리 | BSD |
| Celery | >= 5.6.2 | 비동기 태스크 큐 | BSD |
| Redis | >= 7.0 | 캐시 + 메시지 브로커 | BSD |
| Pydantic | >= 2.9 | ToneSegment/SpeakerTone/ToneResponse 스키마 | MIT |

**신규 의존성**: opensmile ^2.6.0 (AGPL-3.0), librosa ^0.10.0 (ISC)

> **라이선스 주의**: opensmile은 AGPL-3.0으로, 네트워크 서비스 형태 제공 시 소스 공개 의무 발생. 본 프로젝트는 로컬 전용 처리이므로 회피 가능. 단, 향후 SaaS 전환 시 재검토 필요.

---

## 7. 연결된 SPEC (Related SPECs)

| SPEC ID | 관계 | 설명 |
|---------|------|------|
| SPEC-SENTIMENT-001 | 선행 의존 (Upstream) | 텍스트 감정 분석. tone과 융합 가능한 독립 차원 제공의 전제 조건 |
| SPEC-MIN-001 | 간접 의존 | DIA → MIN → tone 파이프라인. minutes_task와 tone_task는 DIA 완료 후 병렬 실행 |
| SPEC-DIA-001 | 직접 의존 (Upstream) | SpeakerSegment(start/end/speaker_id)와 DIA wav가 tone 분석의 입력 |
| SPEC-SER-001 | 후속 의존 (Downstream) | 오디오 보존 아키텍처(A1)를 재사용. 본 SPEC 완료 후 착수 |

---

## 8. 추적성 (Traceability)

| 요구사항 ID | 모듈 | EARS 패턴 | 관련 컴포넌트 |
|-------------|------|-----------|--------------|
| REQ-TONE-001 | ToneEngine | 유비쿼터스 | `backend/ml/tone_engine.py`, `lifecycle.py` |
| REQ-TONE-002 | ToneEngine | 이벤트 기반 | `tone_engine.py::analyze_segments()` |
| REQ-TONE-003 | ToneEngine | 원치 않는 행동 | `tone_engine.py::_check_memory_usage()` |
| REQ-TONE-004 | 오디오 보존 | 상태 기반 | `tone_task.py::_load_dia_wav()` |
| REQ-TONE-005 | 오디오 보존 | 이벤트 기반 | `tone_task.py::finally`, `diarization_task.py` L446-450 |
| REQ-TONE-006 | 오디오 보존 | 원치 않는 행동 | `tone_task.py` 예외 격리 |
| REQ-TONE-007 | Celery 태스크 | 이벤트 기반 | `diarization_task.py::_trigger_tone()` |
| REQ-TONE-008 | Celery 태스크 | 유비쿼터스 | `celery_app.py::include` |
| REQ-TONE-009 | 스키마/API | 원치 않는 행동 | `schemas/tone.py`, `schemas/sentiment.py`(변경 금지) |
| REQ-TONE-010 | 스키마/API | 이벤트 기반 | `api/v1/analytics/tone.py::get_tone_result()` |
| REQ-TONE-011 | 스키마/API | 상태 기반 | `config.py::tone_model`, `tone.py` 503 응답 |
| REQ-TONE-012 | Flutter | 이벤트 기반 | `result_screen.dart::_SentimentTab` tone 섹션 |
| REQ-TONE-013 | Flutter | 원치 않는 행동 | `tone_api.dart` 예외 처리 |
| REQ-TONE-014 | 라이선스 | 원치 않는 행동 | `pyproject.toml`, README 로컬 전용 정책 |

---

## 9. 구현 노트 (Implementation Notes)

### 구현 일자
- 2026-06-14: Run Phase 완료 (TDD RED-GREEN-REFACTOR)

### 구현된 모듈
| 모듈 | 파일 | 상태 |
|------|------|------|
| M1: ToneEngine 싱글톤 | `backend/ml/tone_engine.py` | ✅ 구현 완료 |
| M2: 오디오 보존 아키텍처 | `backend/workers/tasks/diarization_task.py` | ✅ DUAL-PATH 구현 |
| M3: Celery 태스크 | `backend/workers/tasks/tone_task.py` | ✅ 구현 완료 |
| M4: 스키마/API | `backend/schemas/tone.py`, `backend/app/api/v1/analytics/tone.py` | ✅ 4 엔드포인트 |
| M5: Flutter 통합 | `client/lib/services/tone_api.dart`, `client/lib/widgets/tone_timeline.dart` | ✅ 구현 완료 |
| M6: 설정 및 의존성 | `backend/app/config.py`, `pyproject.toml` | ✅ 구현 완료 |

### 계획에서의 주요 편차 (Divergence from Plan)
1. **Warm-up 위치**: plan.md는 `lifecycle.py` 예상했으나, 실제 WhisperEngine/DiarizationEngine warm-up은 `main.py`의 `lifespan()`에 위치. 기존 패턴 준수를 위해 `main.py`에 추가.
2. **Flutter 파일 분리**: `tone_model.dart` (Dart 모델)와 `tone_timeline.dart` (위젯)을 별도 파일로 분리. 테스트 가능성과 에러 격리를 위해 `ToneSection`을 독립 ConsumerWidget으로 구현.
3. **통합 테스트**: `test_tone_pipeline.py` 대신 단위 테스트 3개 파일 (`test_tone_engine.py`, `test_tone_task.py`, `test_tone_api.py`)로 동등 커버리지 달성.
4. **추가 수정 파일**: `stream.py` (SSE prefix), `_route_snapshot_baseline.json` (라우트 베이스라인), `test_core_coverage_final.py` 및 `test_diarization_task_v2.py` (mock fixture tone_model 속성 추가).

### 품질 메트릭
- 백엔드 테스트: 3323 passed, 16 skipped, 0 failed (2026-06-14 전체 suite)
- Flutter 테스트: 324 passed, 0 failed (`cd client && flutter test`)
- 커버리지: 전체 backend 98.62%, tone_engine.py 98%, tone_task.py 100%, schemas/tone.py 100%, API 100%
- API 커버리지 보강(2026-06-14): `backend/tests/unit/test_api_coverage_completion.py`, `backend/tests/unit/test_devices_api_coverage.py`
  - 검증: `19 passed`, ruff `All checks passed!`
  - Coverage JSON API aggregate: `2545/2545` covered lines, `100.00%`, `missing=[]`
- 품질 게이트(2026-06-14): `ruff check backend` clean, `ruff format --check backend` clean, `mypy backend` no issues in 394 source files
- AC-TONE-001~006: 6/6 충족

### 아키텍처 결정사항 요약
- **A1 (오디오 보존)**: DUAL-PATH 구현 — tone 활성화 시 wav 삭제 이연, 비활성화 시 기존 동작 유지 (제로 회귀)
- **A2 (싱글톤 패턴)**: WhisperEngine/DiarizationEngine 패턴 복제, 베이스 클래스 추출 안 함
- **A3 (5-class 분류)**: F0 std/RMS/발화밀도 휴리스틱 기반, confidence < 0.4 시 unknown 반환
- **MemoryError at 19.2GB**: STT/DIA보다 tone 우선순위 낮음 → 메모리 부족 시 tone만 포기

---

*SPEC ID: SPEC-TONE-001*
*생성일: 2026-06-14*
*상태: completed*
