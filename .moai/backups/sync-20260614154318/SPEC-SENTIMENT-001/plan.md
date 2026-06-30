# SPEC-SENTIMENT-001 구현 계획

## 1. 구현 개요

본 계획은 이미 구현된 텍스트 감정 분석 기능을 동작 가능 상태로 복구하고, Flutter UI와 문서 정합성을 완성하기 위한 brownfield 실행 계획이다. 구현은 다음 3단계로 진행한다.

1. **버그 수정**: Celery 태스크 등록 누락과 SSE prefix 누락을 먼저 수정하여 백엔드 작업이 실제로 실행되고 진행률이 스트리밍되도록 한다.
2. **Flutter UI 완성**: 기존 감정 카드 로직을 전용 탭으로 승격하고, 백엔드가 이미 반환하는 `emotional_timeline` 및 `SpeakerSentiment` precomputed 데이터를 렌더링한다.
3. **문서화**: README의 기능 상태와 모델명을 실제 구현과 일치시킨다.

---

## 2. 수정 대상 파일 테이블

### 2.1 수정 파일

| 파일 경로 | 변경 유형 | 설명 | SPEC REQ ID |
|-----------|-----------|------|-------------|
| `backend/workers/celery_app.py` | 버그수정 | `include` 목록에 `backend.workers.tasks.sentiment_task`를 추가하여 Celery 워커가 `sentiment_celery_task`를 발견하도록 한다. | REQ-SEN-001, REQ-SEN-002 |
| `backend/app/api/v1/transcription/stream.py` | 버그수정 | 태스크 존재 확인 prefix 튜플에 `task:sentiment:status:`를 추가하여 감정 분석 작업의 SSE 스트림을 허용한다. | REQ-SEN-005, REQ-SEN-006 |
| `backend/workers/tasks/minutes_task.py` | 기능추가 | 선택 구현: minutes 완료 후 감정 분석을 자동 트리거한다. 기존 수동 `POST /api/v1/sentiment` 경로는 유지한다. | REQ-SEN-003 |
| `backend/app/config.py` | 리팩토링 | `MAX_CONCURRENT_SENTIMENT` 값을 설정 항목으로 이관하고 기본값 3을 유지한다. | REQ-SEN-004 |
| `client/lib/screens/result_screen.dart` | 기능추가 | `_SentimentTab`을 신규 위젯으로 추가하고 TabBar/TabBarView에 감정 분석 탭을 연결한다. 기존 `_buildSentimentCard` 로직은 전용 탭에서 재사용/이관하고 `emotional_timeline` 시각화를 추가한다. | REQ-SEN-007, REQ-SEN-008, REQ-SEN-009, REQ-SEN-010 |
| `client/lib/services/sentiment_api.dart` | 기능추가 | 기존 segments 중심 응답 파싱을 확장하여 `getTimeline()`, `getSpeakerSentiment()` 또는 동등한 전체 응답 접근 메서드를 제공한다. | REQ-SEN-008, REQ-SEN-009, REQ-SEN-011 |
| `client/lib/providers/result_provider.dart` | 리팩토링 | `sentimentProvider`가 오류를 빈 리스트로 삼키지 않도록 하고, precomputed `SpeakerSentiment` 및 `emotional_timeline` 데이터를 UI에 전달한다. | REQ-SEN-008, REQ-SEN-010 |
| `README.md` | 문서 | 고급 분석 계획 항목에서 완료된 텍스트 감정 분석을 분리하고, 부정확한 Claude 모델 표기를 ZAI `glm-5.2`로 정정한다. | REQ-SEN-014, REQ-SEN-015 |

### 2.2 신규 파일

| 파일 경로 | 역할 | SPEC REQ ID |
|-----------|------|-------------|
| `.moai/specs/SPEC-SENTIMENT-001/spec.md` | 역추적 요구사항 명세. 기존 구현, 버그 수정, UI 완성 범위를 EARS 형식으로 문서화한다. | 전체 |
| `.moai/specs/SPEC-SENTIMENT-001/plan.md` | 수정 대상 파일, 구현 순서, 위험 및 완화 전략을 정의한다. | 전체 |
| `.moai/specs/SPEC-SENTIMENT-001/acceptance.md` | Given/When/Then 검수 시나리오와 통과 기준을 정의한다. | 전체 |

---

## 3. 기술 스택

| 영역 | 기술 | 사용 방식 | 신규 의존성 여부 |
|------|------|-----------|------------------|
| Backend API | FastAPI | 기존 `/api/v1/sentiment/*` 라우터 유지 | 없음 |
| Schema | Pydantic v2 | `SentimentResponse`, `SpeakerSentiment`, `SentimentSegment` 유지 | 없음 |
| LLM | ZAI SDK | 기존 `glm-5.2` 기반 감정 분석 호출 유지 | 없음 |
| Async | Celery + Redis | `sentiment_task` 등록, 상태 캐시, SSE 이벤트 전달 | 없음 |
| Flutter API | Dio | 기존 `SentimentApi` 확장 | 없음 |
| Flutter State | Riverpod | 기존 manual `FutureProvider.family` 패턴 유지 | 없음 |
| Flutter UI | Material widgets | 차트 라이브러리 없이 색상 막대, Chip, LinearProgressIndicator 재사용 | 없음 |

---

## 4. 위험 및 완화

| 위험 | 영향 | 완화 전략 | 관련 REQ |
|------|------|-----------|----------|
| Celery 등록 누락이 재발하여 작업이 pending에 머무름 | 감정 분석 기능 전체 사용 불가 | `celery_app.py` include 목록 검증 테스트와 실제 worker smoke test를 추가한다. | REQ-SEN-001, REQ-SEN-002 |
| SSE prefix 누락으로 UI가 진행률을 받지 못함 | 사용자가 작업 상태를 알 수 없음 | `task:sentiment:status:{task_id}` Redis 키가 있을 때 stream 엔드포인트가 404를 반환하지 않는 통합 테스트를 작성한다. | REQ-SEN-005, REQ-SEN-006 |
| Flutter가 오류를 빈 결과로 처리하여 장애가 숨겨짐 | 운영 장애 탐지 지연, 사용자 혼란 | `sentimentProvider`에서 예외를 삼키지 않고 `AsyncValue.error`로 전달하여 `ErrorRetryWidget`을 표시한다. | REQ-SEN-010 |
| 기존 클라이언트가 `List<SentimentSegment>`만 기대함 | 하위 호환성 파손 가능 | 기존 `getResult()`/`getByMeeting()`의 반환 의미를 유지하고, 전체 응답 접근 메서드는 별도로 추가한다. | REQ-SEN-011 |
| UI 탭 추가로 기존 TabController length 불일치 발생 | 런타임 예외 | TabBar와 TabBarView 항목 수를 함께 수정하고 위젯 테스트로 검증한다. | REQ-SEN-007 |
| README가 실제 모델과 계속 불일치 | 운영자 설정 오류 | `config.py`의 실제 ZAI 모델 설정과 README 문구를 대조하여 문서 테스트 또는 리뷰 체크리스트에 포함한다. | REQ-SEN-015 |

---

## 5. 구현 순서

1. **백엔드 태스크 등록 복구**
   - `backend/workers/celery_app.py`의 `include` 목록에 감정 분석 태스크 모듈을 추가한다.
   - Celery worker autodiscovery 또는 registered tasks 출력에서 `sentiment_celery_task` 등록을 확인한다.

2. **SSE 상태 스트리밍 복구**
   - `backend/app/api/v1/transcription/stream.py`의 prefix 튜플에 `task:sentiment:status:`를 추가한다.
   - Redis에 감정 분석 상태 키가 존재할 때 stream 엔드포인트가 정상 EventSourceResponse를 반환하는지 검증한다.

3. **동시성 설정 이관**
   - `backend/app/config.py`에 감정 분석 동시성 설정을 추가하고 기본값 3을 유지한다.
   - `backend/workers/tasks/sentiment_task.py`가 설정 값을 사용하도록 변경한다.

4. **선택 자동 트리거 연결**
   - `backend/workers/tasks/minutes_task.py` 완료 경로에서 감정 분석 자동 시작이 필요한지 결정한다.
   - 적용 시 기존 수동 `POST /api/v1/sentiment` 흐름은 그대로 유지한다.

5. **Flutter API 모델/서비스 확장**
   - `client/lib/services/sentiment_api.dart`에서 segments뿐 아니라 speakers와 timeline을 읽을 수 있게 한다.
   - 기존 `getResult()`와 `getByMeeting()`의 반환 타입/동작은 유지한다.

6. **Flutter provider 오류 처리 개선**
   - `client/lib/providers/result_provider.dart`의 silent fallback을 제거하거나 전용 전체 응답 provider로 대체한다.
   - 오류는 UI에서 재시도 가능하도록 전달한다.

7. **Flutter 전용 탭 완성**
   - `client/lib/screens/result_screen.dart`에 `_SentimentTab`을 추가한다.
   - 전체 감정 분포, 화자별 precomputed 감정 분포, `emotional_timeline` 시각화, 오류 재시도 UI를 포함한다.

8. **README 정합성 수정**
   - 완료된 텍스트 감정 분석 기능과 향후 분석 항목을 분리한다.
   - 모델 설명을 ZAI `glm-5.2`로 정정한다.

9. **검증**
   - Celery 등록, SSE 스트리밍, Flutter 탭 렌더링, 하위 호환성 시나리오를 `acceptance.md` 기준으로 확인한다.

---

## 6. 구현 제외 범위

- 감정 분석 엔진 재작성
- 신규 감정 라벨 체계 도입
- 신규 API URL 구조 도입
- 신규 Flutter 차트 라이브러리 추가
- 데이터베이스 마이그레이션 추가
- 기존 `/api/v1/sentiment/*` 응답의 required 필드 변경
