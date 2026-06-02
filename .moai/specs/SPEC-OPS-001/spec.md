---
id: SPEC-OPS-001
version: "1.0.0"
status: completed
created: 2026-03-16
updated: 2026-03-16
author: kisoo
priority: P2
issue_number: 0
---

# SPEC-OPS-001: 모니터링 및 관찰성 - Prometheus 메트릭 및 구조화 로깅

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-03-16 | 초안 작성 | kisoo |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 플랫폼 | M4 Mac Mini 24GB (Apple Silicon) |
| 런타임 | Python >= 3.11, FastAPI >= 0.135.1 |
| 메트릭 | prometheus-fastapi-instrumentator >= 7.0 |
| 로깅 | structlog (기존), 요청 ID 추적 추가 |
| 테스트 | pytest >= 8.0 |

---

## 2. 가정 (Assumptions)

- Prometheus 서버는 별도 설치이며, 이 SPEC에서는 메트릭 엔드포인트 노출만 구현한다.
- Grafana 대시보드 설정은 이 SPEC 범위 밖이다.
- 기존 structlog 기반 로깅을 확장하여 요청 ID 추적을 추가한다.
- /metrics 엔드포인트는 인증 없이 접근 가능해야 한다 (Prometheus 수집기용).

---

## 3. 요구사항 (Requirements)

### 모듈 1: Prometheus 메트릭

**[REQ-OPS-001] [유비쿼터스]** 시스템은 /metrics 엔드포인트를 통해 Prometheus 형식의 메트릭을 노출해야 한다.

**[REQ-OPS-002] [유비쿼터스]** 시스템은 HTTP 요청 수, 응답 시간(히스토그램), 상태 코드 분포를 자동으로 계측해야 한다.

**[REQ-OPS-003] [유비쿼터스]** 시스템은 커스텀 메트릭으로 활성 작업 수(stt, diarization, minutes, summary), 작업 처리 시간, 작업 실패 수를 추적해야 한다.

**[REQ-OPS-004] [유비쿼터스]** 시스템은 시스템 메트릭으로 메모리 사용량(RSS), CPU 사용률을 노출해야 한다.

### 모듈 2: 요청 ID 추적

**[REQ-OPS-005] [유비쿼터스]** 시스템은 모든 HTTP 요청에 고유한 요청 ID(UUID)를 할당하고 X-Request-ID 응답 헤더에 포함해야 한다.

**[REQ-OPS-006] [유비쿼터스]** 시스템은 요청 ID를 모든 로그 엔트리에 포함하여 요청 단위 추적을 가능하게 해야 한다.

**[REQ-OPS-007] [이벤트 기반]** WHEN 클라이언트가 X-Request-ID 헤더를 포함하여 요청 THEN 시스템은 해당 ID를 그대로 사용해야 한다.

### 모듈 3: 헬스체크 강화

**[REQ-OPS-008] [유비쿼터스]** 시스템은 /api/v1/health/ready 엔드포인트를 추가하여 Kubernetes readiness probe로 활용 가능해야 한다.

**[REQ-OPS-009] [유비쿼터스]** readiness 체크는 Redis 연결 상태, Celery 워커 가용성을 검증해야 한다.

---

## 4. 인수 조건 (Acceptance Criteria)

### AC-1: 메트릭 엔드포인트
- **Given** 서버 실행 중
- **When** GET /metrics 요청
- **Then** Prometheus 텍스트 형식 메트릭 반환

### AC-2: HTTP 메트릭 자동 계측
- **Given** API 요청 처리 후
- **When** /metrics 확인
- **Then** http_requests_total, http_request_duration_seconds 메트릭 존재

### AC-3: 요청 ID 추적
- **Given** X-Request-ID 없이 요청
- **When** 응답 수신
- **Then** X-Request-ID 헤더에 UUID 포함

### AC-4: 클라이언트 요청 ID 전파
- **Given** X-Request-ID: custom-123 헤더로 요청
- **When** 응답 수신
- **Then** X-Request-ID: custom-123 헤더 반환

### AC-5: Readiness 엔드포인트
- **Given** Redis 연결 정상
- **When** GET /api/v1/health/ready
- **Then** HTTP 200 + {"status": "ready"}

---

## 5. 기술 접근 방식

### 파일 구조

```
backend/
├── app/
│   ├── middleware/
│   │   └── request_id.py        # 요청 ID 미들웨어
│   ├── metrics.py               # Prometheus 메트릭 설정
│   ├── api/v1/health.py         # readiness 엔드포인트 추가
│   └── main.py                  # 메트릭 + 요청 ID 미들웨어 등록
├── tests/
│   └── unit/
│       ├── test_metrics.py
│       ├── test_request_id.py
│       └── test_health_ready.py
```

---

## Implementation Notes

### 구현 현황

**구현 날짜**: 2026-06-02

**진행 상태**: partially completed

### 구현된 기능

**완료됨**:
- Prometheus 메트릭 (prometheus-fastapi-instrumentator)
- 구조화된 JSON 로깅 (structlog 기존)
- 요청 ID 추적 (request_id.py 미들웨어)
- HTTP 요청/응답 시간, 상태 코드, 예외 수집

**부분 구현 (검증 필요)**:
- /metrics 엔드포인트 (Prometheus 형식)
- 커스텀 비즈니스 메트릭 (STT 처리 시간, 큐 길이 등)
- 로그 집중 시스템 (ELK, Loki 등)

**미구현**:
- Grafana 대시보드 설정
- 알림 규칙 (Prometheus AlertManager)
- 로그 보존 정책 및 자동 삭제

### 추가 작업 필요

**검증 대상**:
- [ ] Prometheus /metrics 엔드포인트 접근 확인
- [ ] structlog JSON 로그 포맷 검증
- [ ] 요청 ID 헤더 (X-Request-ID) 생성 및 추적 확인

---

*SPEC ID: SPEC-OPS-001*
*생성일: 2026-03-16*
*상태: completed*
