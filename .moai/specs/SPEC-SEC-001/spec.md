---
id: SPEC-SEC-001
version: "1.0.0"
status: completed
created: 2026-03-16
updated: 2026-03-16
author: kisoo
priority: P1
issue_number: 0
---

# SPEC-SEC-001: API 보안 - 인증 미들웨어 및 레이트 리미팅

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
| 인증 | python-jose[cryptography], passlib[bcrypt] |
| 레이트 리미팅 | slowapi >= 0.1.9 (pyrate-limiter 기반) |
| 캐싱 | Redis >= 7.0 (기존 인프라 활용) |
| 테스트 | pytest >= 8.0, httpx |

---

## 2. 가정 (Assumptions)

- 기존 FastAPI 앱 구조(backend/app/main.py)에 미들웨어를 추가하는 방식으로 구현한다.
- 초기 단계에서는 API Key 기반 인증을 사용하며, JWT는 향후 사용자 시스템 추가 시 도입한다.
- Redis가 이미 실행 중이며 레이트 리미팅 카운터 저장에 활용할 수 있다.
- 헬스체크 엔드포인트(/api/v1/health, /api/v1/health/model)는 인증 없이 접근 가능해야 한다.
- 로컬 전용 서비스이지만, 네트워크 내 다른 클라이언트의 무단 접근을 방지해야 한다.

---

## 3. 요구사항 (Requirements)

### 모듈 1: API Key 인증

**[REQ-SEC-001] [유비쿼터스]** 시스템은 항상 보호된 엔드포인트에 대해 `X-API-Key` 헤더 또는 `api_key` 쿼리 파라미터를 통한 인증을 요구해야 한다.

**[REQ-SEC-002] [이벤트 기반]** WHEN 클라이언트가 유효한 API Key 없이 보호된 엔드포인트에 접근 THEN 시스템은 HTTP 401 Unauthorized 응답을 반환해야 한다.

**[REQ-SEC-003] [이벤트 기반]** WHEN 유효한 API Key가 제공된 요청 THEN 시스템은 요청을 정상 처리하고 기존 엔드포인트 로직을 그대로 실행해야 한다.

**[REQ-SEC-004] [상태 기반]** IF API Key가 환경 변수(API_KEYS)로 설정되지 않은 경우 THEN 시스템은 인증을 비활성화하고 모든 요청을 허용해야 한다 (개발 모드).

**[REQ-SEC-005] [원치 않는 행동]** 시스템은 API Key를 로그에 평문으로 기록하지 않아야 한다.

### 모듈 2: 레이트 리미팅

**[REQ-SEC-006] [유비쿼터스]** 시스템은 항상 모든 API 엔드포인트에 IP 기반 레이트 리미팅을 적용해야 한다.

**[REQ-SEC-007] [이벤트 기반]** WHEN 클라이언트가 설정된 요청 제한(기본: 60회/분)을 초과 THEN 시스템은 HTTP 429 Too Many Requests 응답과 함께 Retry-After 헤더를 반환해야 한다.

**[REQ-SEC-008] [상태 기반]** IF Redis가 가용하지 않은 경우 THEN 레이트 리미팅은 인메모리 폴백으로 전환하여 서비스 가용성을 유지해야 한다.

### 모듈 3: CORS 강화

**[REQ-SEC-009] [유비쿼터스]** 시스템은 CORS allow_methods를 필요한 HTTP 메서드(GET, POST, DELETE)로만 제한해야 한다.

**[REQ-SEC-010] [유비쿼터스]** 시스템은 CORS allow_origins를 설정 가능한 출처 목록으로 관리해야 한다.

### 모듈 4: 보안 헤더

**[REQ-SEC-011] [유비쿼터스]** 시스템은 모든 응답에 보안 헤더(X-Content-Type-Options, X-Frame-Options, X-XSS-Protection)를 포함해야 한다.

### 모듈 5: 설정

**[REQ-SEC-012] [유비쿼터스]** 모든 보안 설정(API Key, 레이트 리미트, CORS 출처)은 환경 변수 또는 .env 파일로 관리되어야 한다.

---

## 4. 인수 조건 (Acceptance Criteria)

### AC-1: API Key 인증 작동
- **Given** API Key가 설정된 환경에서
- **When** 유효한 API Key로 POST /api/v1/transcriptions 요청 시
- **Then** HTTP 200/202 응답을 받는다

### AC-2: 미인증 접근 차단
- **Given** API Key가 설정된 환경에서
- **When** API Key 없이 POST /api/v1/transcriptions 요청 시
- **Then** HTTP 401 응답을 받는다

### AC-3: 헬스체크 공개 접근
- **Given** API Key가 설정된 환경에서
- **When** API Key 없이 GET /api/v1/health 요청 시
- **Then** HTTP 200 응답을 받는다

### AC-4: 레이트 리미팅 작동
- **Given** 레이트 리미트가 5회/분으로 설정된 환경에서
- **When** 동일 IP에서 6번째 요청 시
- **Then** HTTP 429 응답과 Retry-After 헤더를 받는다

### AC-5: 개발 모드 (인증 비활성)
- **Given** API_KEYS 환경 변수가 미설정된 상태에서
- **When** API Key 없이 요청 시
- **Then** 인증 없이 정상 처리된다

### AC-6: 보안 헤더 포함
- **Given** 서버가 실행 중일 때
- **When** 임의의 API 요청 시
- **Then** 응답에 X-Content-Type-Options, X-Frame-Options 헤더가 포함된다

---

## 5. 기술 접근 방식

### 구현 전략

1. **API Key 인증**: FastAPI Depends를 활용한 의존성 주입 방식
2. **레이트 리미팅**: slowapi 라이브러리로 IP 기반 리미팅 (Redis 백엔드)
3. **보안 헤더**: Starlette 미들웨어로 전역 적용
4. **CORS 강화**: 기존 CORSMiddleware 설정 업데이트

### 파일 구조

```
backend/
├── app/
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py           # API Key 인증 의존성
│   │   ├── rate_limit.py     # 레이트 리미팅 설정
│   │   └── security_headers.py  # 보안 헤더 미들웨어
│   ├── config.py             # 보안 설정 추가
│   └── main.py               # 미들웨어 등록
├── tests/
│   └── unit/
│       ├── test_auth_middleware.py
│       ├── test_rate_limit.py
│       └── test_security_headers.py
```
