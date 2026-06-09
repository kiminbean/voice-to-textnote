---
id: SPEC-ERR-002
version: "1.0.0"
status: draft
created: 2026-06-09
updated: 2026-06-09
author: kisoo
priority: P1
issue_number: 0
depends_on:
  - SPEC-ERR-001
---

# SPEC-ERR-002: 에러 처리 정비 — Bare Except 제거 및 예외 전파 일원화

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-06-09 | 초안 작성 | kisoo |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 런타임 | Python >= 3.11, FastAPI >= 0.135.1 |
| 선행 SPEC | SPEC-ERR-001 (전역 예외 핸들러 + 커스텀 예외 계층) — 완료 |
| 예외 계층 | VoiceNoteError → 14종 커스텀 예외 (exceptions.py) |
| 에러 헬퍼 | errors.py (not_found, unauthorized, bad_request 등) |
| 워커 | Celery + Redis 기반 비동기 작업 (transcription, minutes, summary, diarization) |

---

## 2. 가정 (Assumptions)

- SPEC-ERR-001에서 구축한 커스텀 예외 계층과 전역 핸들러를 기반으로, 실제 코드의 예외 처리 패턴을 정비한다.
- API 엔드포인트에서 직접 `raise HTTPException`을 사용하는 코드는 커스텀 예외로 교체한다.
- Worker/Task의 DB 저장 실패는 무시하지 않고, 최소 로깅 + 알림 메커니즘을 보장한다.
- Lifecycle의 시작/종료 실패는 경고 수준에서 유지하되, 상태 추적을 강화한다.

---

## 3. 요구사항 (Requirements)

### 모듈 1: Bare Except 제거

**[REQ-ERR2-001] [유비쿼터스]** 시스템은 `except Exception:` (bare except)을 사용하지 않아야 하며, 항상 구체적인 예외 타입을 명시해야 한다.

**[REQ-ERR2-002] [이벤트 기반]** WHEN Redis 연결 확인 실패 THEN transcription 엔드포인트는 `ServiceUnavailableError`를 발생시켜야 한다 (silent fallback 금지).

**[REQ-ERR2-003] [유비쿼터스]** Worker/Task의 DB 저장 실패 시 예외를 삼키지 않고, 반드시 `logger.error`로 기록하고 필요시 재시도해야 한다.

### 모듈 2: HTTPException → 커스텀 예외 교체

**[REQ-ERR2-004] [유비쿼터스]** API 미들웨어(auth.py)와 의존성 주입(dependencies.py)에서 직접 `raise HTTPException`을 사용하는 코드는 `UnauthorizedError`, `ForbiddenError` 등 커스텀 예외로 교체해야 한다.

**[REQ-ERR2-005] [유비쿼터스]** API 엔드포인트에서 발생하는 모든 에러 응답은 SPEC-ERR-001에서 정의한 통일 포맷(`{"error_code": str, "message": str, "request_id": str}`)을 따라야 한다.

### 모듈 3: 이벤트/퍼블리셔 에러 처리

**[REQ-ERR2-006] [이벤트 기반]** WHEN 이벤트 발행(publisher) 실패 THEN 예외를 삼키지 않고 구조화된 로그를 남기고, 호출자에게 에러 전파 여부를 반환해야 한다.

**[REQ-ERR2-007] [이벤트 기반]** WHEN PDF 생성 중 JSON 파싱 실패 THEN 파싱 에러를 로깅하고, 안전한 fallback 데이터로 생성을 계속해야 한다.

### 모듈 4: Lifecycle 에러 추적 강화

**[REQ-ERR2-008] [상태 기반]** IF 시작 시 Redis/DB 연결 실패 THEN `status` 딕셔너리에 `"degraded": true` 플래그를 설정하고, 헬스체크 엔드포인트에서 이를 노출해야 한다.

---

## 4. 인수 조건 (Acceptance Criteria)

### AC-1: Bare Except 제거
- **Given** 백엔드 코드베이스
- **When** `grep -rn "except Exception" backend/` 실행
- **Then** 의도적인 broad except에만 해당하며, 모든 catch 블록이 구체적 예외 타입을 명시

### AC-2: Transcription Redis 체크
- **Given** 서버 실행 중, Redis 다운
- **When** POST /api/v1/transcriptions 요청
- **Then** 503 ServiceUnavailableError 반환 (silent fallback 금지)

### AC-3: Worker DB 저장 실패
- **Given** transcription_task 실행 중
- **When** DB 저장 실패
- **Then** logger.error로 에러 기록 + 결과가 Redis에만 남아있는 경우에도 추적 가능

### AC-4: HTTPException 교체
- **Given** auth 미들웨어
- **When** 인증 실패
- **Then** `UnauthorizedError` 커스텀 예외 발생 (HTTPException 직접 사용 금지)

### AC-5: Lifecycle Degraded 상태
- **Given** 서버 시작 시 Redis 연결 실패
- **When** GET /api/v1/health 요청
- **Then** `"status": "degraded"` 응답으로 외부 모니터링 가능

### AC-6: 이벤트 퍼블리셔
- **Given** 이벤트 발행 중
- **When** 발행 실패
- **Then** 구조화된 에러 로그 + 호출자에게 실패 전파

---

## 5. 기술 접근 방식

### 수정 대상 파일 (8개)

| 파일 | 심각도 | 변경 내용 |
|------|--------|----------|
| `backend/app/api/v1/transcription/transcription.py:143` | CRITICAL | Redis 실패 시 ServiceUnavailableError 발생 |
| `backend/workers/tasks/transcription_task.py:254` | HIGH | DB 저장 실패 시 에러 로깅 + 알림 |
| `backend/workers/tasks/minutes_task.py:282` | HIGH | DB 저장 실패 시 에러 로깅 + 알림 |
| `backend/workers/tasks/summary_task.py:272` | HIGH | DB 저장 실패 시 에러 로깅 + 알림 |
| `backend/workers/tasks/diarization_task.py:407` | HIGH | DB 저장 실패 시 에러 로깅 + 알림 |
| `backend/pipeline/pdf_generator.py:262` | MEDIUM | JSON 파싱 에러 → 안전한 fallback |
| `backend/events/publisher.py:62,78` | MEDIUM | 발행 실패 시 구조화 로그 + 에러 전파 |
| `backend/app/lifecycle.py:52,86,108,116,125` | MEDIUM | degraded 상태 플래그 추가 |

### HTTPException 교체 대상 (2개)

| 파일 | 발생 횟수 | 교체 내용 |
|------|----------|----------|
| `backend/app/middleware/auth.py` | 11건 | → UnauthorizedError, ForbiddenError |
| `backend/app/dependencies.py` | 4건 | → UnauthorizedError, ForbiddenError, NotFoundError |

### 테스트 파일

```
backend/tests/unit/
├── test_error_handling_transcription.py     # AC-2: Redis 실패 시나리오
├── test_error_handling_workers.py           # AC-3: Worker DB 저장 실패
├── test_error_handling_middleware.py         # AC-4: auth 미들웨어 커스텀 예외
├── test_error_handling_lifecycle.py          # AC-5: degraded 상태
└── test_error_handling_publisher.py          # AC-6: 이벤트 발행 실패
```

### 구현 전략

1. **Phase 1**: Bare except 제거 (CRITICAL/HIGH 5개 파일)
2. **Phase 2**: HTTPException → 커스텀 예외 교체 (2개 파일, 15건)
3. **Phase 3**: Lifecycle/Publisher/PDF 개선 (4개 파일)
4. **Phase 4**: 통합 테스트 작성 및 검증

---

## 6. 리스크 및 완화

| 리스크 | 확률 | 영향 | 완화 전략 |
|--------|------|------|----------|
| Worker DB 실패 → 작업 중단 | 낮음 | 높음 | 재시도 로직 + Redis 폴백 유지 |
| auth 미들웨어 교체 시 사이드 이펙트 | 중간 | 높음 | 기존 테스트 기반 회귀 검증 |
| Lifecycle degraded 상태 미인식 | 낮음 | 중간 | 헬스체크 엔드포인트 명시적 노출 |

---

## 7. 범위 외 (Out of Scope)

- Worker 재시도 로직 전면 도입 (별도 SPEC 권장)
- 서킷 브레이커 패턴 (별도 SPEC 권장)
- mypy 타입 오류 233건 (SPEC-TYPING-001 진행 중)
- ML 엔진 `Any` 타입 교체 (별도 SPEC 권장)
