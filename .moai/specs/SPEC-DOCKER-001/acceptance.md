# SPEC-DOCKER-001 인수 조건

## AC-1: Compose 유효성
- docker compose -f docker-compose.prod.yml config → 성공

## AC-2: Nginx 설정 유효성
- nginx -t → 성공

## AC-3: /metrics 접근 제한
- Nginx 설정에서 /metrics deny all 확인

## AC-4: 환경 변수
- .env.example과 config.py Settings 필드 1:1 매핑
