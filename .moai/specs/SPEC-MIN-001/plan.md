---
spec_id: SPEC-MIN-001
type: plan
version: "1.0.0"
created: 2026-03-15
updated: 2026-03-15
author: kisoo
---

# SPEC-MIN-001 구현 계획: 화자별 회의록 자동 생성

---

## 1. 구현 개요

### 목표

SPEC-DIA-001의 화자 분리 결과(DiarizedSegmentResult + SpeakerInfo)를 입력으로 받아 화자별 회의록을 자동 생성한다. 연속 동일 화자 발화를 병합하고, JSON/Markdown 형식으로 출력한다.

### 모듈 구조 (4개 모듈)

| 모듈 | 파일 | 핵심 역할 |
|------|------|----------|
| Module 1: MinutesFormatter | `backend/pipeline/minutes_formatter.py` | 세그먼트 병합, 통계 계산, 포맷 변환 |
| Module 2: Minutes Schema | `backend/schemas/minutes.py` | 요청/응답 데이터 모델 |
| Module 3: Minutes Task | `backend/workers/tasks/minutes_task.py` | Celery 비동기 처리 태스크 |
| Module 4: Minutes API | `backend/app/api/v1/minutes.py` | REST API 엔드포인트 |

### 신규 파일 목록

```
backend/
  pipeline/
    minutes_formatter.py          # (NEW) 회의록 포맷터
  schemas/
    minutes.py                    # (NEW) 회의록 스키마
  workers/tasks/
    minutes_task.py               # (NEW) Celery 회의록 태스크
  app/api/v1/
    minutes.py                    # (NEW) API 엔드포인트
```

### 수정 파일 목록

```
backend/
  app/
    config.py                     # (MODIFY) max_concurrent_minutes, minutes_result_ttl 추가
    main.py                       # (MODIFY) minutes router 등록
```

---

## 2. 모듈별 구현 상세

### Module 1: MinutesFormatter

**파일**: `backend/pipeline/minutes_formatter.py`

**참조 패턴**: `backend/pipeline/speaker_matcher.py` (overlap 매칭 알고리즘)

**핵심 함수**:

- `format_minutes(segments: list[DiarizedSegmentResult], speaker_names: dict[str, str] | None) -> MinutesResult`:
  1. 세그먼트를 시간순 정렬
  2. 연속 동일 화자 세그먼트 병합 (텍스트 연결, start=첫번째, end=마지막)
  3. speaker_id → 화자 이름 매핑 (기본: "Speaker N")
  4. 화자별 통계 계산

- `calculate_speaker_stats(segments) -> list[SpeakerStats]`:
  - 화자별 총 발화 시간, 발화 횟수, 발화 비율(%) 계산

- `to_markdown(minutes_result: MinutesResult) -> str`:
  - Markdown 포맷 변환: `**[HH:MM:SS] Speaker N**: 텍스트`

**엣지 케이스**:
- speaker_id=None → "Unknown Speaker"
- 빈 세그먼트 목록 → 빈 MinutesResult 반환
- 단일 세그먼트 → 병합 없이 그대로 반환

### Module 2: Minutes Schema

**파일**: `backend/schemas/minutes.py`

**데이터 모델**:

- **MinutesCreateRequest**: `diarization_task_id: str`, `output_format: str = "json"`, `speaker_names: dict[str, str] | None = None`
- **MinutesSegment**: `speaker_id: str | None`, `speaker_name: str`, `text: str`, `start: float`, `end: float`
- **SpeakerStats**: `speaker_id: str`, `speaker_name: str`, `total_speaking_time: float`, `segment_count: int`, `speaking_ratio: float`
- **MinutesResponse**: `task_id: str`, `status: TaskStatus`, `diarization_task_id: str`, `segments: list[MinutesSegment]`, `speakers: list[SpeakerStats]`, `total_duration: float`, `total_speakers: int`, `markdown: str | None`
- **MinutesStatusResponse**: `task_id: str`, `status: TaskStatus`, `progress: float`, `message: str | None`

### Module 3: Minutes Task

**파일**: `backend/workers/tasks/minutes_task.py`

**참조 패턴**: `backend/workers/tasks/diarization_task.py`

**태스크 설정**:
- `@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)`
- 동시 제한: `max_concurrent_minutes=3`
- Redis 상태 키: `task:min:status:{task_id}`
- Redis 결과 키: `task:min:result:{task_id}` (TTL: 24시간)

**실행 순서**:
1. 동시 작업 확인 (active_min_jobs >= 3이면 실패)
2. 상태 업데이트: pending → processing (progress: 0.0)
3. Redis에서 DIA 결과 조회 (task:dia:result:{diarization_task_id})
4. DIA 결과 없으면 즉시 실패 (재시도 없음)
5. MinutesFormatter.format_minutes() 실행 (progress: 0.5)
6. 출력 형식에 따라 Markdown 변환 (progress: 0.8)
7. Redis 캐시에 결과 저장 (TTL: 24시간)
8. 상태 완료: processing → completed (progress: 1.0)

### Module 4: Minutes API

**파일**: `backend/app/api/v1/minutes.py`

**엔드포인트**:

| Method | Path | 응답 | 설명 |
|--------|------|------|------|
| POST | /api/v1/minutes | 202 + {task_id, status_url} | 회의록 생성 요청 |
| GET | /api/v1/minutes/{task_id} | MinutesResponse | 회의록 결과 조회 |
| GET | /api/v1/minutes/{task_id}/status | MinutesStatusResponse | 작업 상태 조회 |
| DELETE | /api/v1/minutes/{task_id} | 204 No Content | 결과 삭제 |

---

## 3. 수정 파일 상세

### backend/app/config.py

추가 설정:
- `max_concurrent_minutes: int = 3`
- `minutes_result_ttl: int = 86400` (24시간)

### backend/app/main.py

- minutes router 등록: `app.include_router(minutes.router, prefix=api_prefix)`

---

## 4. TDD 테스트 전략

### 단위 테스트

| 테스트 파일 | 대상 모듈 | 핵심 테스트 케이스 |
|------------|----------|-------------------|
| `test_minutes_formatter.py` | MinutesFormatter | 세그먼트 병합, 통계 계산, Markdown 변환, 빈 입력, speaker_id=None |
| `test_minutes_schemas.py` | Schema | 스키마 검증, 직렬화/역직렬화, speaker_names 매핑 |
| `test_minutes_task.py` | Celery Task | 정상 처리, DIA 결과 미존재, 동시 제한, 재시도 |

### 통합 테스트

| 테스트 파일 | 핵심 테스트 케이스 |
|------------|-------------------|
| `test_minutes_api.py` | POST 생성, GET 상태/결과, DELETE, 동시 제한 429, 404 처리 |

### 커버리지 목표

| 모듈 | 목표 |
|------|------|
| minutes_formatter.py | 100% (핵심 알고리즘) |
| minutes.py (Schema) | 90%+ |
| minutes_task.py | 85%+ |
| minutes.py (API) | 85%+ |
| 전체 | 85%+ |

---

## 5. 리스크 매트릭스

| 리스크 | 확률 | 영향도 | 완화 전략 |
|--------|------|--------|----------|
| DIA 결과 미존재/만료 | 중간 | 높음 | 404 반환, 명확한 에러 메시지 |
| 대량 세그먼트 처리 지연 | 낮음 | 낮음 | 순수 텍스트 처리로 3초 이내 완료 |
| Redis 연결 실패 | 낮음 | 높음 | Celery 재시도 + 상태 추적 |

---

*Plan ID: SPEC-MIN-001*
*생성일: 2026-03-15*
*상태: completed*
