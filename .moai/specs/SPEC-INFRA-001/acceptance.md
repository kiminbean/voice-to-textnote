# SPEC-INFRA-001 인수 조건

## AC-1: PR 워크플로우 실행
- **Given** .github/workflows/ci.yml 존재
- **When** PR 생성/업데이트 시
- **Then** pytest + ruff + 커버리지 자동 실행

## AC-2: 커버리지 게이트
- **Given** 커버리지 85% 미만 코드
- **When** PR CI 실행 시
- **Then** 워크플로우 실패

## AC-3: Docker 빌드
- **Given** main push 시
- **When** build.yml 실행
- **Then** Docker 이미지 ghcr.io에 push

## AC-4: Dependabot
- **Given** dependabot.yml 존재
- **When** 주간 스캔 시
- **Then** 취약 의존성 자동 PR
