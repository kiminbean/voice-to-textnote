---
spec_id: SPEC-SUM-001
type: plan
version: "1.0.0"
created: 2026-03-15
updated: 2026-03-15
author: kisoo
---

# SPEC-SUM-001 구현 계획: Claude API 기반 회의 요약

---

## 1. 구현 개요

### 목표

SPEC-MIN-001의 회의록 결과(MinutesResponse)를 Claude API에 전송하여 회의 요약, 액션 아이템, 결정사항, 다음 단계를 자동 추출한다.

### 모듈 구조 (4개 모듈)

| 모듈 | 파일 | 핵심 역할 |
|------|------|----------|
| Module 1: SummaryGenerator | `backend/pipeline/summary_generator.py` | 프롬프트 구성, Claude API 호출, 응답 파싱 |
| Module 2: Summary Schema | `backend/schemas/summary.py` | 요청/응답 데이터 모델 |
| Module 3: Summary Task | `backend/workers/tasks/summary_task.py` | Celery 비동기 처리 태스크 |
| Module 4: Summary API | `backend/app/api/v1/summary.py` | REST API 엔드포인트 |

### 신규 파일 목록

```
backend/
  pipeline/
    summary_generator.py           # (NEW) Claude API 연동 요약 생성기
  schemas/
    summary.py                     # (NEW) 요약 스키마
  workers/tasks/
    summary_task.py                # (NEW) Celery 요약 태스크
  app/api/v1/
    summary.py                     # (NEW) API 엔드포인트
```

### 수정 파일 목록

```
backend/
  app/
    config.py                      # (MODIFY) anthropic_api_key, max_concurrent_summaries 추가
    main.py                        # (MODIFY) summary router 등록
pyproject.toml                     # (MODIFY) anthropic 의존성 추가
```

---

## 2. 모듈별 구현 상세

### Module 1: SummaryGenerator

**파일**: `backend/pipeline/summary_generator.py`

**핵심 함수**:

- `build_prompt(segments: list[MinutesSegment], speakers: list[SpeakerStats]) -> str`: 회의록 데이터를 Claude 프롬프트로 변환
- `generate_summary(client: Anthropic, prompt: str, model: str, max_tokens: int) -> dict`: Claude API 호출 후 구조화된 결과 반환
- `parse_response(response_text: str) -> SummaryResult`: API 응답을 파싱 (JSON 파싱 실패 시 원문을 summary_text로 사용)

**Claude API 프롬프트 전략**:
- System prompt: "당신은 전문 회의 요약 도우미입니다. 회의 내용을 분석하고 구조화된 JSON으로 응답하세요."
- User prompt: 화자별 발화 + 통계 포함
- 응답 형식: JSON (summary_text, action_items, key_decisions, next_steps)

### Module 2: Summary Schema

**파일**: `backend/schemas/summary.py`

- **ActionItem**: assignee(str|None), task(str), deadline(str|None), priority(str="medium")
- **SummaryCreateRequest**: minutes_task_id(str), max_tokens(int=2000)
- **SummaryResult**: summary_text(str), action_items(list[ActionItem]), key_decisions(list[str]), next_steps(list[str])
- **SummaryResponse**: task_id, status, minutes_task_id, summary_text, action_items, key_decisions, next_steps, tokens_used(dict), generation_time_seconds(float)
- **SummaryStatusResponse**: task_id, status, progress, message

### Module 3: Summary Celery Task

**태스크 설정**: `@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)`

**실행 순서**:
1. ANTHROPIC_API_KEY 확인 (미설정 시 즉시 실패, 재시도 없음)
2. 동시 작업 확인 (active_sum_jobs >= 2이면 실패)
3. Redis에서 MIN 결과 조회
4. SummaryGenerator.build_prompt() (progress: 0.3)
5. SummaryGenerator.generate_summary() (progress: 0.7)
6. 결과 캐시 (TTL: 24시간) (progress: 1.0)

### Module 4: Summary API

| Method | Path | 응답 | 설명 |
|--------|------|------|------|
| POST | /api/v1/summaries | 202 + {task_id} | 요약 생성 요청 |
| GET | /api/v1/summaries/{task_id} | SummaryResponse | 요약 결과 조회 |
| GET | /api/v1/summaries/{task_id}/status | SummaryStatusResponse | 상태 조회 |
| DELETE | /api/v1/summaries/{task_id} | 204 | 결과 삭제 |

---

## 3. 수정 파일 상세

### backend/app/config.py
- `anthropic_api_key: str = ""` (ANTHROPIC_API_KEY 환경 변수)
- `max_concurrent_summaries: int = 2`
- `summary_result_ttl: int = 86400`
- `summary_max_tokens: int = 2000`
- `summary_model: str = "claude-sonnet-4-20250514"`

### backend/app/main.py
- summary router 등록

### pyproject.toml
- `"anthropic>=0.28.0"` 의존성 추가

---

## 4. TDD 테스트 전략

| 테스트 파일 | 핵심 케이스 |
|------------|------------|
| test_summary_generator.py | 프롬프트 구성, 응답 파싱, JSON 파싱 실패 graceful, 빈 입력 |
| test_summary_schemas.py | 스키마 검증, ActionItem 기본값, 직렬화 |
| test_summary_task.py | 정상 처리, MIN 미존재, API 키 미설정, 동시 제한, 재시도 |
| test_summary_api.py | POST 202, GET 상태/결과, DELETE 204, 404, 429 |

### 커버리지 목표

| 모듈 | 목표 |
|------|------|
| summary_generator.py | 100% |
| summary.py (Schema) | 90%+ |
| summary_task.py | 85%+ |
| summary.py (API) | 85%+ |

---

*Plan ID: SPEC-SUM-001*
*생성일: 2026-03-15*
*상태: completed*
