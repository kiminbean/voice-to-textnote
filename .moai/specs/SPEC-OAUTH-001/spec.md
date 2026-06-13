---
id: SPEC-OAUTH-001
version: "1.0.0"
status: completed
created: "2026-06-13"
updated: "2026-06-13"
author: MoAI
priority: medium
issue_number: 0
---

# SPEC-OAUTH-001: Google/Apple 소셜 로그인 및 계정 연동

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-06-13 | 기존 구현 문서화 | MoAI |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 런타임 | Python >= 3.11, FastAPI >= 0.135.1 |
| 데이터베이스 | PostgreSQL / SQLite (SQLAlchemy async) |
| 인증 | JWT (HS256, Access 15분 + Refresh 7일 Rotation) |
| 외부 ID 제공자 | Google Sign-In, Apple Sign-In |

---

## 2. 요구사항 (Requirements)

### 모듈 1: 소셜 로그인

**[REQ-OAUTH-001] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/auth/google 요청(id_token 포함) THEN 시스템은 Google ID token을 검증(verify_google_token)하고, 신규 사용자면 자동 가입, 기존 사용자면 로그인 처리 후 JWT 토큰 쌍을 반환해야 한다.

**[REQ-OAUTH-002] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/auth/apple 요청(id_token 포함) THEN 시스템은 Apple ID token을 검증(verify_apple_token)하고, 신규 사용자면 자동 가입, 기존 사용자면 로그인 처리 후 JWT 토큰 쌍을 반환해야 한다. display_name은 요청 본문에서 선택적으로 제공할 수 있다.

**[REQ-OAUTH-003] [원치 않는 행동]** 시스템은 ID token 검증 실패 시 401 Unauthorized를 반환해야 한다.

### 모듈 2: 소셜 계정 연동/해제

**[REQ-OAUTH-004] [이벤트 기반]** WHEN 인증된 사용자가 POST /api/v1/auth/link/{provider} 요청 THEN 시스템은 기존 계정에 소셜 제공자(google, apple)를 연동하고 갱신된 사용자 정보를 반환해야 한다.

**[REQ-OAUTH-005] [이벤트 기반]** WHEN 인증된 사용자가 DELETE /api/v1/auth/link/{provider} 요청 THEN 시스템은 소셜 제공자 연동을 해제하고 갱신된 사용자 정보를 반환해야 한다.

**[REQ-OAUTH-006] [원치 않는 행동]** 시스템은 provider가 "google" 또는 "apple"이 아니면 400 Bad Request를 반환해야 한다.

---

## 3. 스키마

| 스키마 | 설명 |
|--------|------|
| GoogleLoginRequest | id_token: str |
| AppleLoginRequest | id_token: str, display_name: str (선택) |
| LinkProviderRequest | id_token: str |
| TokenResponse | access_token: str, refresh_token: str |
| UserResponse | id, email, display_name, is_active, created_at, provider, avatar_url |

---

## 4. 추적성 (Traceability)

| 요구사항 ID | 엔드포인트 |
|-------------|-----------|
| REQ-OAUTH-001 | POST /api/v1/auth/google |
| REQ-OAUTH-002 | POST /api/v1/auth/apple |
| REQ-OAUTH-003 | (401 에러 케이스) |
| REQ-OAUTH-004 | POST /api/v1/auth/link/{provider} |
| REQ-OAUTH-005 | DELETE /api/v1/auth/link/{provider} |
| REQ-OAUTH-006 | (400 에러 케이스) |

---

## 5. 구현 노트

- 구현 파일: `backend/app/api/v1/auth/auth.py`
- OAuth 서비스: `backend/services/oauth_service.py` (verify_google_token, verify_apple_token)
- 인증 서비스: `backend/services/auth_service.py` (social_login_or_register, link_provider, unlink_provider)
- 스키마: `backend/schemas/auth.py`
- 사용자 모델: `backend/db/auth_models.py` (User.provider, User.provider_id 필드)
- 연관: SPEC-TEAM-001 (JWT Auth), SPEC-GUEST-001 (Guest Mode)
