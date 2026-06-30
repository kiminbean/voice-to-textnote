---
id: SPEC-SENTIMENT-001
version: "1.0.0"
status: completed
created: 2026-06-14
updated: 2026-06-14
completed: 2026-06-14
author: MoAI
priority: P1
issue_number: 29
related_specs: [SPEC-MIN-001, SPEC-SUM-001, SPEC-TONE-001]
---

# SPEC-SENTIMENT-001: 텍스트 감정 분석 통합 완료

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-06-14 | 기존 구현을 역추적하여 요구사항, 구현 계획, 검수 기준 문서화 | MoAI |
| 1.0.1 | 2026-06-14 | Run/Sync 완료 — status를 completed로 변경, Implementation Notes 추가 | GLM-5.2 |

---

## 1. 배경 및 목표

본 SPEC은 이미 약 85% 구현된 텍스트 감정 분석 기능에 대한 **역추적 SPEC(retrospective SPEC)** 이다. 백엔드 감정 분석 스키마, ZAI 기반 분석기, Celery 태스크, API 라우터, 일부 Flutter 카드 UI는 존재하지만 SPEC 문서가 없고, Celery 태스크 등록 누락으로 실제 워커가 `sentiment_celery_task`를 발견하지 못해 작업이 영원히 실행되지 않는 치명적 결함이 있다.

목표는 감정 분석 로직을 새로 작성하는 것이 아니라, 기존 구현을 보존하면서 다음을 완료하는 것이다.

- 기존 텍스트 감정 분석 구현의 요구사항 추적성 확보
- Celery 등록 및 SSE 상태 스트리밍 버그 수정
- Flutter 전용 감정 분석 탭과 `emotional_timeline` 렌더링 완성
- 클라이언트 오류를 숨기지 않고 재시도 가능한 UI로 노출
- README의 기능 상태와 AI 모델 설명을 실제 구현과 일치하도록 정정

---

## 2. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| platform | M4 Mac Mini 24GB, Apple Silicon, 로컬 우선 처리 환경 |
| runtime | Python >= 3.11, FastAPI >= 0.135, Flutter 3.x, Dart 3.x |
| AI API | ZAI API |
| model | `glm-5.2` |
| async | Celery >= 5.6, Redis >= 7.0 |
| input data | SPEC-MIN-001의 minutes 결과: `task:min:result:{minutes_task_id}` 및 `TaskResult.result_data` |

---

## 3. 가정 (Assumptions)

- `backend/pipeline/sentiment_analyzer.py`, `backend/workers/tasks/sentiment_task.py`, `backend/schemas/sentiment.py`, `backend/app/api/v1/analytics/sentiment.py`의 기존 감정 분석 로직은 재구현하지 않고 유지한다.
- 감정 분석 입력은 `minutes_task` 완료 후 생성된 화자별 회의록 세그먼트이며, 원본 오디오 파일은 필요하지 않다.
- ZAI API 키와 모델 설정은 기존 `backend/app/config.py`의 ZAI 설정을 따른다.
- 신규 라이브러리 의존성은 추가하지 않고 기존 ZAI SDK, Pydantic, Celery, Redis, Riverpod, Dio, Material 위젯만 사용한다.
- 기존 `/api/v1/sentiment/*` 엔드포인트와 `SentimentResponse` 스키마는 하위 호환성을 유지해야 한다.
- `emotional_timeline`은 백엔드가 이미 반환하는 `[{time, sentiment, emotion, speaker}]` 형태의 데이터를 클라이언트에서 시각화하는 범위로 제한한다.

---

## 4. 요구사항 (Requirements)

### 모듈 1: Celery 태스크 등록 및 실행

**[REQ-SEN-001] [유비쿼터스]** Celery 워커는 항상 `sentiment_task`를 발견하고 `sentiment_celery_task`를 실행할 수 있어야 한다. `backend/workers/celery_app.py:14-22`의 `include` 목록에는 `backend.workers.tasks.sentiment_task`가 포함되어야 한다.

**[REQ-SEN-002] [이벤트 기반]** WHEN 클라이언트가 `POST /api/v1/sentiment` 요청을 보내면 THEN 시스템은 `sentiment_celery_task.delay(...)`로 작업을 큐에 등록하고, Celery 워커는 해당 작업을 실제로 처리해야 한다.

**[REQ-SEN-003] [이벤트 기반]** WHEN `minutes_task`가 성공적으로 완료되고 자동 실행 옵션이 활성화되어 있으면 THEN 시스템은 summary 작업과 독립적으로 감정 분석 작업을 시작할 수 있어야 한다.

**[REQ-SEN-004] [유비쿼터스]** 감정 분석 동시 실행 제한은 항상 설정 기반으로 관리되어야 하며, 기존 하드코딩된 `MAX_CONCURRENT_SENTIMENT=3`은 `backend/app/config.py`의 설정 값으로 이관되어야 한다.

### 모듈 2: SSE 진행률 스트리밍

**[REQ-SEN-005] [유비쿼터스]** `backend/app/api/v1/transcription/stream.py`의 태스크 존재 확인 루프는 항상 `task:sentiment:status:` Redis prefix를 인식해야 한다.

**[REQ-SEN-006] [이벤트 기반]** WHEN 감정 분석 태스크가 진행 중이고 클라이언트가 `GET /api/v1/transcription/{task_id}/stream`을 호출하면 THEN 시스템은 `task:sentiment:status:{task_id}` 상태 이벤트를 SSE로 스트리밍해야 한다.

### 모듈 3: Flutter 감정 분석 UI

**[REQ-SEN-007] [이벤트 기반]** WHEN 사용자가 회의 결과 화면을 열면 THEN Flutter 앱은 기존 통계 탭 내부에 묻혀 있던 감정 분석 정보를 전용 `_SentimentTab`에서 접근할 수 있게 해야 한다.

**[REQ-SEN-008] [유비쿼터스]** `_SentimentTab`은 항상 전체 감정 분포, 전체 주요 감정, 화자별 감정 분포를 표시해야 하며, 백엔드의 `SpeakerSentiment` precomputed 데이터를 우선 사용해야 한다.

**[REQ-SEN-009] [이벤트 기반]** WHEN 백엔드 응답에 `emotional_timeline`이 포함되어 있으면 THEN Flutter 앱은 해당 데이터를 시간 순서의 시계열 시각화로 렌더링해야 한다.

**[REQ-SEN-010] [원치 않는 행동]** Flutter 앱은 감정 분석 API 오류를 `SizedBox.shrink()`로 숨기지 않아야 한다. 오류 발생 시 사용자가 재시도할 수 있는 `ErrorRetryWidget`을 표시해야 한다.

### 모듈 4: API 스키마 및 하위 호환성

**[REQ-SEN-011] [원치 않는 행동]** 시스템은 기존 `GET /api/v1/sentiment/{task_id}`, `GET /api/v1/sentiment/{task_id}/status`, `GET /api/v1/sentiment/meeting/{meeting_id}` 응답 스키마를 깨뜨리지 않아야 한다.

**[REQ-SEN-012] [유비쿼터스]** 새 응답 필드가 필요한 경우 모든 필드는 항상 optional이어야 하며 Pydantic에서는 `Field(default=None, description="...")` 패턴을 따라야 한다.

**[REQ-SEN-013] [유비쿼터스]** 감정 분석 결과는 항상 기존 `SentimentResponse`의 `segments`, `speakers`, `emotional_timeline`, `overall_sentiment`, `overall_emotion` 의미를 유지해야 한다.

### 모듈 5: 문서 정합성

**[REQ-SEN-014] [이벤트 기반]** WHEN 본 SPEC 구현이 완료되면 THEN README의 고급 분석 계획 항목은 완료된 텍스트 감정 분석과 향후 분석 항목을 분리하여 표시해야 한다.

**[REQ-SEN-015] [유비쿼터스]** README와 관련 문서는 항상 실제 구현 모델을 ZAI `glm-5.2`로 설명해야 하며, 부정확한 Claude 모델 표기를 유지하지 않아야 한다.

---

## 5. 비기능 요구사항 (Non-Functional Requirements)

| 항목 | 목표값 | 비고 |
|------|--------|------|
| 성능 | 작업 제출 API < 300ms, 상태 조회/SSE 존재 확인 < 100ms | Redis 캐시 및 기존 SSE 경로 활용 |
| 메모리 | 감정 분석 작업 추가 시 기존 STT/DIA 메모리 예산을 초과하지 않음 | 텍스트 기반 LLM 호출이므로 오디오 모델 추가 없음 |
| 보안 | API Key 보호 라우터 정책 유지, 민감 정보 로그 출력 금지 | `registry.py`의 sentiment 라우터 인증 정책 유지 |
| 하위 호환성 | 기존 `/api/v1/sentiment/*` 응답과 클라이언트 파싱 유지 | 새 필드는 optional만 허용 |
| 운영 안정성 | Celery 워커 재시작 후 sentiment task autodiscovery 성공 | `include` 목록에 명시 등록 |

---

## 6. 기술 제약 조건

- 감정 분석 로직은 기존 `SentimentAnalyzer`, `sentiment_task`, `SentimentResponse` 중심 구조를 유지한다.
- 신규 데이터베이스 마이그레이션은 만들지 않는다. 감정 분석 결과는 기존 `TaskResult.result_data` JSON 저장 패턴을 사용한다.
- 신규 Flutter 차트 라이브러리를 추가하지 않는다. Material 기본 위젯, `LinearProgressIndicator`, `Chip`, `Wrap`, `Row`/`Column`, 색상 막대 패턴을 재사용한다.
- 자동 트리거는 `minutes_task` 완료 이후에만 가능하며, minutes 결과가 없는 경우 감정 분석을 시작하지 않는다.
- 기존 `/api/v1/sentiment/*` URL 구조를 변경하거나 `/analytics/...` 형태의 신규 중복 URL을 만들지 않는다.
- 새 설정값은 환경변수로 오버라이드 가능해야 하며 기존 기본값 `3`과 의미가 일치해야 한다.

---

## 7. 의존성 (Dependencies)

| 라이브러리 | 버전 | 용도 |
|-----------|------|------|
| zai | 기존 프로젝트 버전 | ZAI `glm-5.2` 감정 분석 호출 |
| FastAPI | >= 0.135 | sentiment API 라우터 제공 |
| Pydantic | >= 2.9 | `SentimentResponse`, `SpeakerSentiment`, `SentimentSegment` 검증 |
| Celery | >= 5.6 | 감정 분석 백그라운드 태스크 실행 |
| Redis | >= 7.0 | Celery 브로커, 상태 캐시, SSE 이벤트 전달 |
| Flutter | 기존 프로젝트 버전 | 결과 화면 감정 분석 탭 렌더링 |
| Riverpod | 기존 프로젝트 버전 | `sentimentProvider` 및 결과 상태 관리 |
| Dio | 기존 프로젝트 버전 | `/api/v1/sentiment/*` HTTP 호출 |

**신규 의존성**: 없음.

---

## 8. 연결된 SPEC (Related SPECs)

| SPEC ID | 관계 | 설명 |
|---------|------|------|
| SPEC-MIN-001 | 직접 의존 | 감정 분석 입력인 minutes 결과를 생성 |
| SPEC-SUM-001 | 유사 패턴 | ZAI/LLM 기반 비동기 분석, Celery 상태 관리, 결과 캐시 패턴 참조 |
| SPEC-ANALYTICS-001 | 상위 로드맵 | 분석 기능 분할 로드맵의 첫 번째 완료 대상 |

---

## 9. 추적성 (Traceability)

| REQ ID | 모듈 | EARS 유형 | 컴포넌트/파일 |
|--------|------|-----------|---------------|
| REQ-SEN-001 | Celery 등록 | 유비쿼터스 | `backend/workers/celery_app.py` |
| REQ-SEN-002 | Celery 실행 | 이벤트 기반 | `backend/app/api/v1/analytics/sentiment.py`, `backend/workers/tasks/sentiment_task.py` |
| REQ-SEN-003 | 자동 트리거 | 이벤트 기반 | `backend/workers/tasks/minutes_task.py` |
| REQ-SEN-004 | 동시성 설정 | 유비쿼터스 | `backend/app/config.py`, `backend/workers/tasks/sentiment_task.py` |
| REQ-SEN-005 | SSE prefix | 유비쿼터스 | `backend/app/api/v1/transcription/stream.py` |
| REQ-SEN-006 | SSE 이벤트 | 이벤트 기반 | `create_sse_event_generator`, `publish_task_event_sync` |
| REQ-SEN-007 | 전용 탭 | 이벤트 기반 | `client/lib/screens/result_screen.dart` |
| REQ-SEN-008 | 화자별 렌더링 | 유비쿼터스 | `_SentimentTab`, `SpeakerSentiment` |
| REQ-SEN-009 | 타임라인 렌더링 | 이벤트 기반 | `emotional_timeline`, `client/lib/services/sentiment_api.dart` |
| REQ-SEN-010 | 오류 재시도 UI | 원치 않는 행동 | `ErrorRetryWidget`, `result_screen.dart` |
| REQ-SEN-011 | 응답 호환성 | 원치 않는 행동 | `backend/schemas/sentiment.py`, `/api/v1/sentiment/*` |
| REQ-SEN-012 | optional 필드 | 유비쿼터스 | Pydantic `Field(default=None)` 패턴 |
| REQ-SEN-013 | 결과 의미 유지 | 유비쿼터스 | `SentimentResponse`, `SentimentResult` |
| REQ-SEN-014 | 기능 상태 문서화 | 이벤트 기반 | `README.md` |
| REQ-SEN-015 | 모델명 정정 | 유비쿼터스 | `README.md`, `backend/app/config.py` |

---

*SPEC ID: SPEC-SENTIMENT-001*  
*생성일: 2026-06-14*  
*상태: completed*

---

## 10. Implementation Notes (As-Implemented)

구현 완료일: 2026-06-14 / Issue: #29

### 모듈 1: Celery 태스크 등록 및 실행 (REQ-SEN-001~004)

- `backend/workers/celery_app.py`: `include` 목록에 `backend.workers.tasks.sentiment_task` 추가
  - 기존 결함: 워커가 sentiment_celery_task를 발견하지 못해 작업이 pending에 영원히 머무름
- `backend/app/config.py`: `max_concurrent_sentiment: int = Field(default=3, ge=1, le=10)` 설정 추가
- `backend/workers/tasks/sentiment_task.py`: 모듈 수준 `MAX_CONCURRENT_SENTIMENT = 3` 상수 제거, `settings.max_concurrent_sentiment` 참조로 변경 (3곳)
- **Deferred (OUT OF SCOPE)**: REQ-SEN-003 (minutes_task 완료 후 자동 트리거)는 plan.md에서 명시적으로 "선택 구현"으로 표기되었으며, 수동 `POST /api/v1/sentiment` 경로가 이미 동작하므로 이번 구현에서는 제외

### 모듈 2: SSE 진행률 스트리밍 (REQ-SEN-005~006)

- `backend/app/api/v1/transcription/stream.py`: `stream_task_status()`의 prefix 튜플에 `task:sentiment:status:` 추가
  - 기존 결함: 감정 분석 태스크 진행 중 SSE 엔드포인트가 404 반환

### 모듈 3: Flutter 감정 분석 UI (REQ-SEN-007~010)

- `client/lib/services/sentiment_api.dart`: `SpeakerSentiment`, `EmotionTimelineEntry`, `SentimentFullResponse` 모델 추가. `getFullByMeeting(taskId)`, `getFullResult(taskId)` 메서드 추가. 기존 `getResult()`, `getByMeeting()` 시그니처/반환 타입 유지 (하위 호환성)
- `client/lib/providers/result_provider.dart`: `sentimentFullProvider` 추가. 오류를 `AsyncValue.error`로 전파하여 `ErrorRetryWidget` 표시. 기존 `sentimentProvider`는 다른 소비자를 위해 유지
- `client/lib/screens/result_screen.dart`: `_SentimentTab` 위젯 추가 (전체 분포 / 화자별 precomputed 데이터 / emotional_timeline / ErrorRetryWidget). `DefaultTabController length` 7→8. `_StatisticsTab`에서 silent error 감정 카드 제거, `_buildSentimentCard` 로직을 `_SentimentContent`로 이관

### 모듈 4: API 스키마 및 하위 호환성 (REQ-SEN-011~013)

- 기존 `SentimentResponse`, `SentimentSegment`, `SpeakerSentiment` 스키마 변경 없음
- 모든 새 필드는 optional (Dart 모델에서 nullable/기본값 처리)
- 기존 `/api/v1/sentiment/*` URL 구조 유지

### 모듈 5: 문서 정합성 (REQ-SEN-014~015)

- `README.md`: Claude 3.5 Sonnet → ZAI `glm-5.2` 정정 (7곳: 기능 설명, 환경변수, 비용, 성능, 아키텍처 다이어그램, 빠른 시작)
- 감정 분석 기능 섹션 추가 (Section 6)
- 완료된 SPEC 목록: 29/29 → 30/30
- Phase 5를 "계획" → "진행 중"으로 변경

### 검증 (Verification)

- `ruff check`: All checks passed (0 errors)
- `pytest` (sentiment/stream/celery 관련 112개): 112 passed
- `flutter analyze`: 수정 파일 0 errors (기존 info 3개는 범위 밖)
- `flutter test`: 301 passed, 0 failed

### Divergence from plan.md

- **Scope Expansion**: 없음
- **Deferred**: REQ-SEN-003 (자동 트리거) — 선택 구현으로 명시됨, OUT OF SCOPE
- **Unplanned Additions**:
  - `test_sentiment_bugs_reproduction.py` (신규): TDD RED phase 재현 테스트 7개. 회고형 SPEC의 버그 수정 이력을 보존하기 위해 명시적 재현 테스트로 작성
  - `test_sentiment_task.py`, `test_sentiment_task_coverage.py`: mock 설정에 `max_concurrent_sentiment` 추가 (기존 `MAX_CONCURRENT_SENTIMENT` 상수 참조가 `settings.max_concurrent_sentiment`로 변경되었으므로)
- **New Dependencies**: 없음
- **New Directories**: 없음
