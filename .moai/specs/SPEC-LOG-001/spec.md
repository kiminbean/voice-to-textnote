---
id: SPEC-LOG-001
version: "1.0.0"
status: completed
created: 2026-03-21
updated: 2026-03-21
author: kisoo
priority: P2
issue_number: 0
---

# SPEC-LOG-001: 감사 로깅 미들웨어

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-03-21 | 초안 작성 | kisoo |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 런타임 | Python >= 3.11, FastAPI >= 0.135.1 |
| 로깅 | structlog (기존) |
| 기존 미들웨어 | auth, rate_limit, security_headers, request_id |

---

## 2. 가정 (Assumptions)

- 감사 로그는 structlog를 통해 JSON 형식으로 stdout에 출력한다 (DB 저장은 향후).
- 요청 본문(body)은 파일 업로드를 제외하고 기록하지 않는다 (성능/보안).
- 응답 본문도 기록하지 않는다 (대용량 전사 결과 등).
- 헬스체크 엔드포인트는 감사 로그에서 제외한다 (노이즈 방지).

---

## 3. 요구사항 (Requirements)

### 모듈 1: 감사 로깅 미들웨어

**[REQ-LOG-001] [유비쿼터스]** 시스템은 모든 API 요청에 대해 감사 로그를 생성해야 한다.

**[REQ-LOG-002] [유비쿼터스]** 감사 로그는 최소 다음 필드를 포함해야 한다: timestamp, request_id, method, path, status_code, client_ip, user_agent, duration_ms.

**[REQ-LOG-003] [원치 않는 행동]** 감사 로그에 민감 정보(API Key, Authorization 헤더)를 포함하지 않아야 한다.

**[REQ-LOG-004] [상태 기반]** IF 요청 경로가 /api/v1/health 또는 /metrics인 경우 THEN 감사 로그를 생성하지 않아야 한다.

**[REQ-LOG-005] [이벤트 기반]** WHEN 요청 처리 시간이 5초를 초과 THEN 경고 수준(WARNING)으로 slow request 로그를 추가 기록해야 한다.

### 모듈 2: 접근 통계

**[REQ-LOG-006] [유비쿼터스]** 시스템은 Prometheus 카운터로 엔드포인트별 접근 횟수를 추적해야 한다.

---

## 4. 인수 조건 (Acceptance Criteria)

### AC-1: 감사 로그 생성
- **Given** 서버 실행 중
- **When** POST /api/v1/transcriptions 요청
- **Then** structlog에 audit 로그 출력 (method, path, status_code, duration_ms, client_ip 포함)

### AC-2: 민감 정보 필터링
- **Given** X-API-Key 헤더 포함 요청
- **When** 감사 로그 생성
- **Then** API Key가 로그에 포함되지 않음

### AC-3: 헬스체크 제외
- **Given** GET /api/v1/health 요청
- **When** 미들웨어 통과
- **Then** 감사 로그 미생성

### AC-4: Slow request 경고
- **Given** 처리 시간 5초 초과 요청
- **When** 응답 완료
- **Then** WARNING 수준 slow_request 로그 생성

---

## 5. 기술 접근 방식

### 파일 구조

```
backend/
├── app/
│   ├── middleware/
│   │   └── audit_log.py          # 감사 로깅 미들웨어
│   └── main.py                    # 미들웨어 등록
├── tests/unit/
│   └── test_audit_log.py
```
