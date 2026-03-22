# SPEC-TEAM-001: 팀 협업 및 권한 관리 - 리서치 문서

## 1. 현재 아키텍처 분석

### 1.1 인증 시스템 현황

**현재 방식: 정적 API Key 인증**

- `backend/app/middleware/auth.py`에서 `X-API-Key` 헤더 기반 인증
- `settings.api_keys`에 쉼표로 구분된 API Key 목록 저장 (환경 변수)
- API Key가 비어있으면 개발 모드로 인증 비활성화 (REQ-SEC-004)
- 사용자 개념 없음 - 모든 API Key가 동등한 권한
- Flutter 클라이언트(`api_client.dart`)에 API Key 설정 없음 (현재 개발 모드)

**한계점:**
- 사용자 식별 불가 (누가 어떤 회의록을 생성했는지 추적 불가)
- 권한 분리 불가 (모든 키가 동일 권한)
- 팀/조직 개념 부재
- Key 탈취 시 전체 시스템 접근 가능 (세션 관리 없음)

### 1.2 데이터베이스 스키마 현황

**현재 테이블:**
- `task_results`: 작업 결과 저장 (task_id, task_type, status, result_data 등)
- `audit_logs`: HTTP 감사 로그 (request_id, method, path, status_code 등)

**사용자/팀 관련 테이블: 없음**
- `product.md`에 "팀 협업" 언급이 있으나 실제 DB 모델에 User/Team 테이블 미구현
- `task_results`에 `user_id` 또는 `team_id` 외래 키 없음
- 회의록 소유권 개념 부재

### 1.3 Flutter 클라이언트 현황

**현재 구조:**
- `Meeting` 모델: id, title, createdAt, status, duration, 각종 taskId (사용자/팀 필드 없음)
- `api_client.dart`: Dio 기반, API Key 인증 미구현 (개발 모드)
- `auth_service.dart`: 존재하지 않음 (파일 미생성)
- `user.dart`: 존재하지 않음 (파일 미생성)
- 로그인/회원가입 화면 없음

### 1.4 API 라우터 구조

**현재 엔드포인트 (`/api/v1/`):**
- transcription, diarization, minutes, summary (핵심 파이프라인)
- health (인증 불필요)
- stream (SSE 실시간)
- history (작업 이력)
- admin (데이터 보존 정책)
- templates (회의록 양식)

**인증 적용:** 모든 라우터에 `Depends(verify_api_key)` 의존성 주입 (health 제외)

---

## 2. 필요한 변경 범위

### 2.1 백엔드 변경

| 영역 | 현재 | 필요 | 변경 규모 |
|------|------|------|----------|
| 인증 | 정적 API Key | JWT + Refresh Token | 대규모 |
| DB 모델 | TaskResult, AuditLog | + User, Team, TeamMember, MeetingOwnership | 대규모 |
| 미들웨어 | verify_api_key | verify_jwt_token + 역할 기반 권한 | 중규모 |
| API | 없음 | /auth/*, /teams/*, /meetings/share | 대규모 |
| 스키마 | 없음 | UserSchema, TeamSchema, AuthSchema | 중규모 |
| 설정 | API_KEYS 환경변수 | JWT_SECRET, TOKEN_EXPIRY 등 | 소규모 |

### 2.2 Flutter 변경

| 영역 | 현재 | 필요 | 변경 규모 |
|------|------|------|----------|
| 모델 | Meeting만 | + User, Team, TeamMember | 중규모 |
| 서비스 | api_client만 | + AuthService, TeamService | 대규모 |
| 화면 | 4개 화면 | + 로그인, 회원가입, 팀 관리, 팀 설정 | 대규모 |
| 상태 관리 | MeetingProvider | + AuthProvider, TeamProvider | 중규모 |
| 토큰 관리 | 없음 | SecureStorage + 자동 갱신 | 중규모 |

---

## 3. 기술 선택지 분석

### 3.1 인증 방식 비교

| 방식 | 장점 | 단점 | MVP 적합성 |
|------|------|------|-----------|
| **JWT (Access + Refresh)** | Stateless, 확장성, 표준화 | Token 무효화 어려움, 구현 복잡도 | **적합 (추천)** |
| OAuth 2.0 / 소셜 로그인 | 사용자 편의, 보안 위임 | 외부 의존성, 구현 복잡, 오프라인 불가 | MVP 제외 |
| Session 기반 | 즉시 무효화 가능, 단순 | Stateful, 확장성 제한, Redis 부하 | 부적합 (이미 Redis 부하 높음) |
| Simple Token (DB 저장) | 구현 단순, 즉시 무효화 | 매 요청 DB 조회, 확장성 낮음 | 대안으로 고려 가능 |

**결론: JWT (Access + Refresh Token) 추천**
- 이유: 기존 API Key 방식과 유사한 Stateless 패턴, 프라이버시 중시 로컬 처리 철학과 부합
- Access Token: 15분 TTL (짧은 유효기간으로 탈취 위험 최소화)
- Refresh Token: 7일 TTL (DB 저장, 명시적 무효화 가능)

### 3.2 비밀번호 해싱

| 라이브러리 | 알고리즘 | 성능 (M1) | 보안 |
|-----------|---------|----------|------|
| **passlib[bcrypt]** | bcrypt | ~200ms/hash | 높음 (추천) |
| argon2-cffi | Argon2id | ~100ms/hash | 최고 |
| hashlib | SHA-256 | <1ms/hash | 부적합 |

**결론: passlib[bcrypt] 추천** (검증된 라이브러리, 충분한 보안)

### 3.3 JWT 라이브러리

| 라이브러리 | 유지보수 | 기능 | 크기 |
|-----------|---------|------|------|
| **python-jose[cryptography]** | 활발 | JWS, JWE, JWK | 중간 |
| PyJWT | 활발 | JWS만 | 작음 |

**결론: python-jose[cryptography] 추천** (FastAPI 공식 문서 권장)

### 3.4 Flutter 토큰 저장

| 방식 | iOS | Android | 보안 |
|------|-----|---------|------|
| **flutter_secure_storage** | Keychain | EncryptedSharedPreferences | 높음 (추천) |
| SharedPreferences | 평문 | 평문 | 부적합 |
| Hive (암호화) | AES | AES | 중간 |

**결론: flutter_secure_storage 추천** (플랫폼 네이티브 보안 저장소 활용)

---

## 4. 데이터 모델 설계 방향

### 4.1 새로운 테이블 설계

```
users
├── id (UUID, PK)
├── email (VARCHAR, UNIQUE, INDEX)
├── password_hash (VARCHAR)
├── display_name (VARCHAR)
├── is_active (BOOLEAN, DEFAULT true)
├── created_at (DATETIME)
└── updated_at (DATETIME)

teams
├── id (UUID, PK)
├── name (VARCHAR)
├── description (TEXT, NULLABLE)
├── created_by (UUID, FK -> users.id)
├── created_at (DATETIME)
└── updated_at (DATETIME)

team_members
├── id (UUID, PK)
├── team_id (UUID, FK -> teams.id)
├── user_id (UUID, FK -> users.id)
├── role (VARCHAR: 'admin' | 'member' | 'viewer')
├── invited_by (UUID, FK -> users.id, NULLABLE)
├── joined_at (DATETIME)
└── UNIQUE(team_id, user_id)

meeting_ownership (기존 task_results 확장)
├── id (UUID, PK)
├── task_id (VARCHAR, FK -> task_results.task_id)
├── owner_id (UUID, FK -> users.id)
├── team_id (UUID, FK -> teams.id, NULLABLE)
├── shared_at (DATETIME, NULLABLE)
└── created_at (DATETIME)

refresh_tokens
├── id (UUID, PK)
├── user_id (UUID, FK -> users.id)
├── token_hash (VARCHAR, INDEX)
├── expires_at (DATETIME)
├── is_revoked (BOOLEAN, DEFAULT false)
├── created_at (DATETIME)
└── device_info (VARCHAR, NULLABLE)
```

### 4.2 기존 테이블 영향

- `task_results`: 직접 변경하지 않고 `meeting_ownership`으로 연결
- `audit_logs`: `user_id` 컬럼 추가 (API Key 대신 사용자 추적)

---

## 5. 하위 호환성 분석

### 5.1 기존 API Key 인증과의 공존

- **Phase 1**: JWT 인증 추가, API Key 인증 유지 (둘 다 허용)
- **Phase 2**: 새 기능(팀/공유)은 JWT 전용
- **Phase 3**: API Key deprecation 공지 후 제거

### 5.2 기존 회의록 데이터 마이그레이션

- 기존 `task_results` 데이터에는 소유자 정보 없음
- 마이그레이션 전략: 기존 데이터는 "시스템" 소유로 처리, 관리자가 재할당 가능

---

## 6. 보안 고려사항

### 6.1 비밀번호 정책 (MVP)
- 최소 8자, 영문+숫자 조합
- bcrypt 해싱 (cost factor 12)

### 6.2 JWT 보안
- Access Token: HS256, 15분 만료
- Refresh Token: DB 저장 + 해시, 7일 만료
- Token Rotation: Refresh 사용 시 새 Refresh Token 발급

### 6.3 팀 권한 모델
- admin: 팀 설정 변경, 멤버 초대/제거, 모든 회의록 접근
- member: 회의록 생성/공유, 팀 내 회의록 조회
- viewer: 팀 내 회의록 조회만 가능

---

## 7. 범위 평가 (Scope Assessment)

### MVP 포함
- 이메일/비밀번호 기반 회원가입/로그인
- JWT Access + Refresh Token
- 팀 CRUD (생성, 조회, 수정, 삭제)
- 이메일 기반 멤버 초대 (앱 내)
- 역할 기반 권한 (admin/member/viewer)
- 회의록 팀 공유 (팀 선택하여 공유)
- Flutter 로그인/회원가입 UI
- Flutter 팀 관리 화면

### MVP 제외
- OAuth/소셜 로그인 (Google, Apple)
- 이메일 발송 (초대 알림)
- 댓글/코멘트 기능
- 실시간 공동 편집
- 문서별 세분화 권한 (팀 단위만)
- 프로필 이미지 업로드
- 비밀번호 찾기/재설정 (이메일 발송 필요)

### 예상 작업량
- 백엔드: 5-7일 (DB 모델 + API + 인증 + 권한)
- Flutter: 3-5일 (UI + 토큰 관리 + 상태 관리)
- 테스트: 2-3일 (단위 + 통합)
- 총 예상: 10-15일
