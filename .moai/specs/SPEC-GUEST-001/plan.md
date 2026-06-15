# SPEC-GUEST-001 Plan (Retrospective)

## 개요
본 문서는 SPEC-GUEST-001 Guest 모드 (24시간 임시 저장) 구현 완료 후, as-built 기준으로 작성된 회고성 plan이다.

## 구현 범위

### Backend
- `backend/app/api/v1/auth/auth.py` — POST `/api/v1/auth/guest` 엔드포인트. guest_session_id (UUID v4) + guest_token (JWT, "guest:" 접두사, 24h 만료) 반환
- `backend/app/middleware/auth.py` — guest_token 검증 로직 추가. "guest:" 접두사 감지, JWT 검증, Redis `guest:session:{id}` 존재 확인, `request.state.is_guest` / `request.state.guest_session_id` 설정
- `backend/services/retention.py` — guest 데이터 24h 정리 로직. cleanup_expired_data 태스크에서 is_guest=True AND created_at < 24h 레코드 삭제
- `backend/schemas/auth.py` — GuestSessionResponse 스키마
- `backend/app/config.py` — guest_session_ttl_hours 설정

### Data Model
- task_results 테이블에 `is_guest` (Boolean, default False), `guest_session_id` (String, nullable) 컬럼 추가

### Flutter
- `client/lib/providers/auth_provider.dart` — isGuest 상태, startAsGuest() 메서드
- `client/lib/services/auth_api.dart` — createGuestSession() 메서드
- `client/lib/screens/login_screen.dart` — "게스트로 시작 (24시간 저장)" 버튼
- `client/lib/screens/home_screen.dart` — Guest 모드 안내 배너
- `client/lib/router/app_router.dart` — guest 인증 허용

## 기술 결정
- Guest 토큰은 JWT 형식이지만 "guest:" 접두사로 일반 JWT와 구분
- Guest 세션은 서버 측 Redis로만 관리 (DB 테이블 불필요)
- 기존 인증 사용자의 데이터 보존 정책(7일/30일)에 영향 없음

## 검증 결과
- Backend: 24 tests (auth/middleware/config/models/retention/schemas)
- Flutter: 13 tests (auth provider/api/service/login/home/router)
- Phase 2.5 Quality: Backend 811 passed, Flutter 190 passed, 0 regressions
