# SPEC-GUEST-001 Acceptance Criteria

## 검증 방법
본 문서는 spec.md의 REQ-GUEST-* 요구사항이 코드와 테스트로 충족되었는지 추적한다.

## Acceptance Criteria

### REQ-GUEST-001: Guest 세션 생성 API
- 상태: MET
- 증거: backend/app/api/v1/auth/auth.py — POST `/api/v1/auth/guest` 엔드포인트. guest_session_id (UUID v4) + guest_token (JWT, "guest:" 접두사, HS256, 24h 만료) 반환. Redis `guest:session:{id}` 저장 (TTL 24h)

### REQ-GUEST-002: 인증 미들웨어 Guest 허용
- 상태: MET
- 증거: backend/app/middleware/auth.py — "guest:" 접두사 토큰 감지, JWT 검증, Redis 세션 존재 확인, `request.state.is_guest` / `request.state.guest_session_id` 설정. 만료/미존재 시 401

### REQ-GUEST-003: Guest 데이터 Redis TTL 24시간
- 상태: MET
- 증거: backend/app/middleware/auth.py + backend/services/retention.py — Guest 사용자 Redis 결과 (task:status, task:result, task:dia:*, task:min:*, task:sum:*) 24h TTL 적용. 기존 인증 사용자는 7일 유지

### REQ-GUEST-004: Guest 데이터 DB 보존 24시간
- 상태: MET
- 증거: backend/services/retention.py — task_results 테이블 is_guest 플래그, cleanup_expired_data 태스크에서 is_guest=True AND created_at < 24h 레코드 삭제

### REQ-GUEST-005: Flutter 게스트 시작 버튼
- 상태: MET
- 증거: client/lib/screens/login_screen.dart — "게스트로 시작 (24시간 저장)" 버튼. client/lib/services/auth_api.dart — createGuestSession(). client/lib/providers/auth_provider.dart — startAsGuest(), isGuest 상태

### REQ-GUEST-006: Guest 만료 안내 배너
- 상태: MET
- 증거: client/lib/screens/home_screen.dart — Guest 모드 시 상단 안내 배너 ("게스트 모드 — 데이터가 24시간 후 삭제됩니다"), 회원가입 바로가기 링크. 일반 인증 사용자에게는 미표시
