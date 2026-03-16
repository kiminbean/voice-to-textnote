# SPEC-INFRA-001 구현 계획

## 구현 순서

### Task 1: PR 워크플로우 (.github/workflows/ci.yml)
- Python 3.11 설정
- Redis 서비스 컨테이너
- pytest 실행 (커버리지 포함)
- ruff 린팅
- 커버리지 85% 게이트

### Task 2: 메인 브랜치 빌드 (.github/workflows/build.yml)
- 테스트 실행
- Docker 이미지 빌드
- ghcr.io push

### Task 3: Dependabot 설정 (.github/dependabot.yml)
- pip 생태계 주간 스캔
- 자동 PR 생성

## 리스크

- GitHub Actions에서 mlx-whisper/pyannote 모델 로드 불가 → 모델 의존 테스트 mock 처리
- Redis 서비스 컨테이너 초기화 시간 → health check 추가
