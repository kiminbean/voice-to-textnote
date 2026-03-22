# SPEC-TEAM-001: 팀 협업 및 권한 관리 - 실행 계획

## 개발 방법론: TDD (Test-Driven Development)

모든 Phase에서 RED -> GREEN -> REFACTOR 사이클을 따른다.

---

## Phase 1: 사용자 모델 및 인증 기반 (REQ-TEAM-001)

### 목표
JWT 기반 사용자 등록/로그인/토큰 관리 시스템 구축

### 작업 항목

**1.1 DB 모델 생성**
- RED: users, refresh_tokens 테이블 모델 테스트 작성
- GREEN: SQLAlchemy 모델 구현 (`backend/db/models.py`)
- Alembic 마이그레이션 파일 생성/적용

**1.2 인증 유틸리티**
- RED: 비밀번호 해싱/검증, JWT 생성/검증 테스트 작성
- GREEN: `backend/app/auth/` 모듈 구현 (password.py, jwt.py)
- 설정 추가: JWT_SECRET, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS

**1.3 인증 API 엔드포인트**
- RED: /auth/register, /auth/login, /auth/refresh, /auth/logout, /auth/me 테스트 작성
- GREEN: `backend/app/api/v1/auth.py` 라우터 구현
- 스키마: `backend/schemas/auth.py` (RegisterRequest, LoginRequest, TokenResponse 등)

**1.4 인증 미들웨어 통합**
- RED: JWT Bearer Token 검증 + API Key 폴백 테스트 작성
- GREEN: `verify_auth` 의존성 함수 구현 (기존 verify_api_key와 공존)
- 기존 라우터에 verify_auth 적용 (하위 호환성 유지)

### 산출물
- 5개 인증 API 엔드포인트
- users, refresh_tokens 테이블
- JWT + API Key 이중 인증 미들웨어

---

## Phase 2: 팀 모델 및 CRUD API (REQ-TEAM-002)

### 목표
팀 생성/조회/수정/삭제 기능 구현

### 작업 항목

**2.1 DB 모델 생성**
- RED: teams, team_members 테이블 모델 테스트 작성
- GREEN: SQLAlchemy 모델 구현
- Alembic 마이그레이션

**2.2 팀 CRUD API**
- RED: POST/GET/PUT/DELETE /teams 테스트 작성
- GREEN: `backend/app/api/v1/teams.py` 라우터 구현
- 스키마: `backend/schemas/team.py` (TeamCreate, TeamResponse, TeamListResponse 등)

**2.3 팀 생성자 자동 admin 등록**
- RED: 팀 생성 시 생성자가 admin으로 등록되는 테스트
- GREEN: 팀 생성 로직에 자동 멤버 등록 추가

### 산출물
- 5개 팀 CRUD API 엔드포인트
- teams, team_members 테이블

---

## Phase 3: 팀 멤버 관리 및 권한 (REQ-TEAM-003, REQ-TEAM-004)

### 목표
멤버 초대/제거/역할 변경 + 역할 기반 권한 검증

### 작업 항목

**3.1 권한 검증 의존성**
- RED: admin/member/viewer 역할별 접근 제어 테스트
- GREEN: `backend/app/auth/permissions.py` (require_team_role 의존성)

**3.2 멤버 관리 API**
- RED: POST/GET/PUT/DELETE /teams/{id}/members 테스트
- GREEN: 라우터에 멤버 관리 엔드포인트 추가
- 스키마: InviteMemberRequest, MemberResponse, UpdateRoleRequest

**3.3 엣지 케이스 처리**
- RED: 마지막 admin 제거 불가, 자기 역할 변경 불가, 미가입 이메일 초대 오류 테스트
- GREEN: 비즈니스 로직에 검증 규칙 추가

### 산출물
- 4개 멤버 관리 API 엔드포인트
- 역할 기반 권한 검증 시스템

---

## Phase 4: 회의록 소유권 및 팀 공유 (REQ-TEAM-005)

### 목표
회의록에 소유자를 지정하고 팀 단위 공유 기능 구현

### 작업 항목

**4.1 DB 모델 생성**
- RED: meeting_ownership 테이블 모델 테스트
- GREEN: SQLAlchemy 모델 구현
- Alembic 마이그레이션

**4.2 소유권 자동 할당**
- RED: 인증된 사용자가 파이프라인 실행 시 소유권 자동 생성 테스트
- GREEN: 기존 파이프라인 엔드포인트에 소유권 생성 로직 추가

**4.3 회의록 공유/조회 API**
- RED: POST/DELETE /meetings/{id}/share, GET /meetings/mine, GET /teams/{id}/meetings 테스트
- GREEN: `backend/app/api/v1/meetings.py` 라우터 구현
- audit_logs에 user_id 컬럼 추가 마이그레이션

**4.4 접근 권한 필터링**
- RED: 팀 멤버만 공유된 회의록 조회 가능 테스트
- GREEN: 기존 history API에 소유권/팀 기반 필터링 추가

### 산출물
- 4개 회의록 공유 API 엔드포인트
- meeting_ownership 테이블
- 기존 API에 소유권 기반 필터링 적용

---

## Phase 5: Flutter 인증 UI (REQ-TEAM-007)

### 목표
Flutter 로그인/회원가입 화면 및 토큰 관리 구현

### 작업 항목

**5.1 인증 서비스 및 모델**
- RED: AuthService, User 모델 단위 테스트
- GREEN: `client/lib/services/auth_service.dart`, `client/lib/models/user.dart` 구현
- flutter_secure_storage로 토큰 저장

**5.2 Dio 인터셉터 업데이트**
- RED: Authorization 헤더 자동 주입, 토큰 자동 갱신 테스트
- GREEN: api_client.dart에 AuthInterceptor 추가
- 401 응답 시 Refresh Token으로 자동 재시도

**5.3 로그인/회원가입 화면**
- RED: 위젯 테스트 (입력 검증, 버튼 동작)
- GREEN: LoginScreen, RegisterScreen 위젯 구현
- Riverpod AuthProvider (로그인 상태 관리)

**5.4 인증 플로우 통합**
- RED: 앱 시작 시 토큰 확인 -> 로그인/메인 화면 분기 테스트
- GREEN: go_router에 인증 가드 추가
- 자동 로그인 (저장된 토큰 유효 시)

### 산출물
- LoginScreen, RegisterScreen 2개 화면
- AuthService, AuthProvider
- 자동 토큰 관리 인터셉터

---

## Phase 6: Flutter 팀 관리 UI (REQ-TEAM-006)

### 목표
팀 목록, 팀 상세/설정, 회의록 공유 UI 구현

### 작업 항목

**6.1 팀 서비스 및 모델**
- RED: TeamService, Team/TeamMember 모델 단위 테스트
- GREEN: `client/lib/services/team_service.dart`, `client/lib/models/team.dart` 구현

**6.2 팀 목록 화면**
- RED: 위젯 테스트 (팀 목록 표시, FAB 동작)
- GREEN: TeamListScreen 구현
- Riverpod TeamProvider

**6.3 팀 상세/설정 화면**
- RED: 위젯 테스트 (멤버 목록, 역할 뱃지, 초대 다이얼로그)
- GREEN: TeamDetailScreen 구현
- admin 전용 설정 영역 (역할에 따라 조건부 표시)

**6.4 회의록 공유 다이얼로그**
- RED: 위젯 테스트 (팀 선택, 공유 상태 토글)
- GREEN: ShareMeetingDialog 구현
- 결과 화면에 "팀 공유" 버튼 추가

### 산출물
- TeamListScreen, TeamDetailScreen 2개 화면
- ShareMeetingDialog 1개 다이얼로그
- TeamService, TeamProvider

---

## Phase 7: 통합 테스트 및 마무리

### 목표
전체 플로우 E2E 검증 및 문서화

### 작업 항목

**7.1 백엔드 통합 테스트**
- 회원가입 -> 로그인 -> 팀 생성 -> 멤버 초대 -> 회의록 생성 -> 팀 공유 전체 플로우
- 권한 위반 시나리오 (viewer가 공유 시도 등)

**7.2 Flutter 통합 테스트**
- 로그인 -> 메인 화면 -> 팀 관리 -> 녹음 -> 결과 공유 플로우

**7.3 보안 검증**
- JWT 만료 처리 검증
- Refresh Token Rotation 검증
- 권한 에스컬레이션 시도 차단 검증

**7.4 문서화**
- API 문서 업데이트 (OpenAPI/Swagger)
- product.md 업데이트
- SPEC sync

### 산출물
- E2E 테스트 스위트
- 보안 검증 결과
- 업데이트된 문서

---

## 의존성 그래프

```
Phase 1 (인증 기반)
  ├── Phase 2 (팀 CRUD) ─── Phase 3 (멤버/권한)
  │                              │
  │                              ├── Phase 4 (소유권/공유)
  │                              │
  ├── Phase 5 (Flutter 인증) ─── Phase 6 (Flutter 팀 UI)
  │                                        │
  └────────────────────────────── Phase 7 (통합/마무리)
```

- Phase 1은 모든 Phase의 선행 조건
- Phase 2-3은 순차 실행 (팀이 있어야 멤버 관리 가능)
- Phase 4는 Phase 3 이후 (권한 시스템 필요)
- Phase 5는 Phase 1 이후 (인증 API 필요)
- Phase 5-6은 순차 실행 (인증이 있어야 팀 UI 가능)
- Phase 7은 모든 Phase 완료 후

**병렬 실행 가능 조합:**
- Phase 2 + Phase 5 (백엔드 팀 CRUD와 Flutter 인증을 동시에)
- Phase 3 + Phase 5 (백엔드 권한과 Flutter 인증을 동시에)

---

## 리스크 분석

| 리스크 | 확률 | 영향도 | 대응 전략 |
|--------|------|--------|----------|
| JWT Secret 유출 | 낮음 | 높음 | 환경 변수 관리, .env에 저장, git 미추적 |
| Refresh Token 탈취 | 중간 | 높음 | Token Rotation + 단일 디바이스 세션 제한 |
| DB 마이그레이션 실패 | 낮음 | 높음 | 마이그레이션 전 백업, 롤백 스크립트 준비 |
| 기존 API Key 호환성 깨짐 | 중간 | 중간 | 이중 인증 방식으로 점진적 전환 |
| Flutter 토큰 저장소 접근 실패 | 낮음 | 중간 | fallback으로 메모리 내 토큰 유지 (앱 재시작 시 재로그인) |
| 팀 멤버 수 급증 시 성능 | 낮음 | 중간 | MVP는 팀당 50명 제한, 인덱스 최적화 |

---

## 예상 일정

| Phase | 소요 시간 | 누적 |
|-------|----------|------|
| Phase 1: 인증 기반 | 2일 | 2일 |
| Phase 2: 팀 CRUD | 1일 | 3일 |
| Phase 3: 멤버/권한 | 1.5일 | 4.5일 |
| Phase 4: 소유권/공유 | 1.5일 | 6일 |
| Phase 5: Flutter 인증 | 2일 | 8일 |
| Phase 6: Flutter 팀 UI | 2일 | 10일 |
| Phase 7: 통합/마무리 | 2일 | 12일 |
| **합계** | **12일** | |
