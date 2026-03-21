# SPEC-DOCKER-001 구현 계획

## Task 1: docker-compose.prod.yml
- nginx, api, worker, redis, postgres 5개 서비스
- healthcheck, depends_on, named volumes
- 환경 변수 파일 참조 (.env)

## Task 2: Nginx 설정 (nginx/nginx.conf)
- 리버스 프록시 → localhost:8000
- /metrics 내부 전용
- gzip 압축
- 500MB client_max_body_size
- SSL 구조 (주석 처리, 활성화 가이드)

## Task 3: 환경 변수 완성
- .env.example 업데이트 (누락 변수 추가)
- .env.production.example 생성

## 리스크
- Nginx SSL은 인증서 없이 테스트 불가 → HTTP 기본 + SSL 주석 제공
