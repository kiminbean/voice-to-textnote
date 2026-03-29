---
id: SPEC-GUEST-001
version: "1.1.0"
status: completed
created: "2026-03-29"
updated: "2026-03-29"
author: kisoo
priority: high
issue_number: 0
---

## HISTORY

| Date | Version | Author | Change |
|------|---------|--------|--------|
| 2026-03-29 | 1.0.0 | kisoo | 초기 작성 |

---

# SPEC-GUEST-001: Guest 모드 (24시간 임시 저장)

## 1. 개요

### 현재 상태

- JWT 기반 인증 시스템 (SPEC-TEAM-001)
- 미인증 사용자는 로그인 화면으로 리다이렉트
- 데이터 보존: Redis TTL 7일, DB 30일
- 앱 사용을 위해 반드시 회원가입/로그인 필요

### 목적

회원가입 없이 즉시 앱을 사용할 수 있는 Guest 모드를 제공한다. Guest 사용자의 녹음 및 회의록 결과는 24시간 동안만 저장되고 자동 삭제된다.

### 범위

**포함:**
- Backend: Guest 세션 생성 API, guest 전용 Redis TTL (24h)
- Backend: 인증 미들웨어에 guest 세션 허용 로직 추가
- Backend: Guest 데이터 자동 정리 (기존 cleanup 태스크 확장)
- Flutter: 로그인 화면에 "게스트로 시작" 버튼 추가
- Flutter: 게스트 세션 로컬 관리 + 24시간 만료 안내 배너

**제외:**
- Guest → 회원 전환 시 데이터 마이그레이션 (Phase 2)
- Guest 사용 횟수/용량 제한 (Phase 2)
- Guest 전용 워터마크/제한 UI (Phase 2)

---

## 2. EARS 요구사항

### REQ-GUEST-001: Guest 세션 생성 API (Ubiquitous)

**The system shall** POST `/api/v1/auth/guest` 엔드포인트를 제공하여 인증 없이 guest 세션을 생성하고, guest_session_id와 guest_token을 반환한다.

- 요청 본문 없음 (비인증 엔드포인트)
- 응답: `{ guest_session_id: str, guest_token: str, expires_at: datetime }`
- guest_session_id: UUID v4
- guest_token: "guest:" 접두사 + guest_session_id를 HS256으로 서명한 JWT (24시간 만료)
- guest_session_id를 Redis에 저장: `guest:session:{id}` (TTL 24시간)

### REQ-GUEST-002: 인증 미들웨어 Guest 허용 (Ubiquitous)

**The system shall** 기존 API Key 인증 미들웨어에서 guest_token도 유효한 인증으로 허용한다.

- Authorization: Bearer guest:xxx 형태의 토큰 감지
- JWT 검증 후 guest_session_id 추출
- Redis에서 guest:session:{id} 존재 여부 확인
- 유효하면 요청 진행, 만료/미존재면 401 반환
- request.state.is_guest = True 설정 (후속 핸들러에서 참조 가능)
- request.state.guest_session_id = id 설정

### REQ-GUEST-003: Guest 데이터 Redis TTL 24시간 (Event-Driven)

**When** guest 사용자가 파이프라인을 실행하면, **the system shall** 해당 작업의 Redis 결과에 24시간 TTL을 적용한다.

- 기존 인증 사용자: Redis TTL 7일 (기존 동작 유지)
- Guest 사용자: Redis TTL 86400초 (24시간)
- 적용 대상: task:status, task:result, task:dia:*, task:min:*, task:sum:*
- Guest 세션 만료 후에는 결과 조회 시 404 반환

### REQ-GUEST-004: Guest 데이터 DB 보존 24시간 (Ubiquitous)

**The system shall** guest 사용자가 생성한 DB 레코드에 `is_guest=True` 플래그를 설정하고, 기존 cleanup 태스크에서 24시간 이상 된 guest 레코드를 삭제한다.

- task_results 테이블에 `is_guest` (Boolean, default False) 컬럼 추가
- `guest_session_id` (String, nullable) 컬럼 추가
- cleanup_expired_data 태스크에서 is_guest=True AND created_at < 24h 전 레코드 삭제

### REQ-GUEST-005: Flutter 게스트 시작 버튼 (Event-Driven)

**When** 사용자가 로그인 화면에서 "게스트로 시작" 버튼을 탭하면, **the system shall** guest 세션 API를 호출하고 홈 화면으로 이동한다.

- 로그인 화면 하단에 "게스트로 시작 (24시간 저장)" 텍스트 버튼 추가
- POST /api/v1/auth/guest 호출
- guest_token을 SharedPreferences에 저장
- AuthState를 guest 모드로 설정 (isGuest=true)
- 홈 화면으로 리다이렉트

### REQ-GUEST-006: Guest 만료 안내 배너 (State-Driven)

**While** guest 모드로 로그인된 상태이면, **the system shall** 홈 화면 상단에 "게스트 모드 — 데이터가 24시간 후 삭제됩니다" 안내 배너를 표시한다.

- MaterialBanner 또는 Container 위젯으로 표시
- 회원가입 바로가기 링크 포함
- 일반 인증 사용자에게는 표시하지 않음

---

## 3. 수정 대상 파일

### Backend

| 파일 | 변경 유형 | 설명 |
|------|----------|------|
| `backend/app/api/v1/auth.py` | 수정 | POST /api/v1/auth/guest 엔드포인트 추가 |
| `backend/app/middleware/auth.py` | 수정 | guest_token 검증 로직 추가 |
| `backend/app/config.py` | 수정 | guest_session_ttl_hours 설정 추가 |
| `backend/db/models.py` | 수정 | task_results에 is_guest, guest_session_id 컬럼 추가 |
| `backend/services/retention.py` | 수정 | guest 데이터 24h 정리 로직 추가 |
| `backend/schemas/auth.py` | 수정 | GuestSessionResponse 스키마 추가 |

### Flutter

| 파일 | 변경 유형 | 설명 |
|------|----------|------|
| `client/lib/providers/auth_provider.dart` | 수정 | isGuest 상태, startAsGuest() 메서드 |
| `client/lib/services/auth_api.dart` | 수정 | createGuestSession() 메서드 |
| `client/lib/screens/login_screen.dart` | 수정 | 게스트 시작 버튼 추가 |
| `client/lib/screens/home_screen.dart` | 수정 | Guest 모드 안내 배너 |
| `client/lib/router/app_router.dart` | 수정 | guest 인증도 허용 |

---

## 4. 기술 제약

- Guest 토큰은 JWT 형식이지만 "guest:" 접두사로 일반 JWT와 구분
- Guest 세션은 서버 측 Redis로만 관리 (DB 테이블 불필요)
- 기존 인증 사용자의 데이터 보존 정책(7일/30일)에 영향 없음
- Alembic 마이그레이션 필요 (task_results 컬럼 추가)
