# SPEC-SEC-001 구현 계획

## 구현 순서

### Task 1: 설정 확장 (config.py)
- Settings 클래스에 보안 관련 필드 추가
- api_keys, rate_limit_per_minute, cors_origins 등
- .env.example 업데이트

### Task 2: API Key 인증 미들웨어
- backend/app/middleware/auth.py 생성
- FastAPI Depends 패턴으로 verify_api_key 구현
- 헬스체크 경로 제외 로직

### Task 3: 레이트 리미팅 미들웨어
- backend/app/middleware/rate_limit.py 생성
- slowapi 기반 IP별 레이트 리미팅
- Redis 백엔드, 인메모리 폴백

### Task 4: 보안 헤더 미들웨어
- backend/app/middleware/security_headers.py 생성
- X-Content-Type-Options, X-Frame-Options, X-XSS-Protection

### Task 5: CORS 강화
- main.py의 CORSMiddleware 설정 업데이트
- allow_methods 제한, 설정 가능한 origins

### Task 6: 통합 및 미들웨어 등록
- main.py에 미들웨어 통합
- 라우터에 인증 의존성 적용

## 의존성

- python-jose[cryptography]
- passlib[bcrypt]
- slowapi

## 리스크

- 기존 테스트가 인증 추가로 실패할 수 있음 → conftest.py에 인증 우회 픽스처 추가
- slowapi와 FastAPI 버전 호환성 확인 필요
