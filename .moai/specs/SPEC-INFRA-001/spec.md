---
id: SPEC-INFRA-001
version: "1.0.0"
status: completed
created: 2026-03-16
updated: 2026-03-16
author: kisoo
priority: P1
issue_number: 0
---

# SPEC-INFRA-001: CI/CD 파이프라인 - GitHub Actions 자동화

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-03-16 | 초안 작성 | kisoo |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| CI/CD | GitHub Actions |
| 런타임 | Python >= 3.11 |
| 테스트 | pytest >= 8.0, coverage |
| 린팅 | ruff |
| 컨테이너 | Docker, Docker Compose |

---

## 2. 가정 (Assumptions)

- GitHub 리포지토리에 push/PR 이벤트로 워크플로우가 트리거된다.
- GitHub Actions 러너에서 Redis 서비스 컨테이너를 사용할 수 있다.
- Python 의존성은 pyproject.toml로 관리된다.
- 테스트는 Redis 서비스가 필요하므로 서비스 컨테이너로 제공한다.
- Flutter 클라이언트 CI는 별도 워크플로우로 분리한다.

---

## 3. 요구사항 (Requirements)

### 모듈 1: PR 워크플로우

**[REQ-INFRA-001] [이벤트 기반]** WHEN Pull Request가 생성 또는 업데이트 THEN 테스트, 린팅, 타입 체크를 자동으로 실행해야 한다.

**[REQ-INFRA-002] [유비쿼터스]** 테스트 실행 시 Redis 서비스 컨테이너를 제공하여 통합 테스트를 포함한 전체 테스트 스위트를 실행해야 한다.

**[REQ-INFRA-003] [유비쿼터스]** 테스트 커버리지를 측정하고 85% 미만이면 워크플로우를 실패시켜야 한다.

**[REQ-INFRA-004] [유비쿼터스]** ruff를 사용한 린팅 검사를 실행하고 오류 시 워크플로우를 실패시켜야 한다.

### 모듈 2: 메인 브랜치 워크플로우

**[REQ-INFRA-005] [이벤트 기반]** WHEN main 브랜치에 push THEN 전체 테스트 + Docker 이미지 빌드를 실행해야 한다.

**[REQ-INFRA-006] [이벤트 기반]** WHEN Docker 이미지 빌드 성공 THEN 이미지를 GitHub Container Registry(ghcr.io)에 push해야 한다.

### 모듈 3: 의존성 보안

**[REQ-INFRA-007] [유비쿼터스]** Dependabot으로 Python 의존성 보안 취약점을 주간 자동 스캔해야 한다.

---

## 4. 인수 조건 (Acceptance Criteria)

### AC-1: PR 워크플로우 실행
- **Given** GitHub Actions 워크플로우가 설정된 상태에서
- **When** PR을 생성하면
- **Then** 테스트, 린팅, 커버리지 검사가 자동 실행된다

### AC-2: 커버리지 게이트
- **Given** 커버리지 임계값이 85%로 설정된 상태에서
- **When** 테스트 커버리지가 85% 미만이면
- **Then** 워크플로우가 실패한다

### AC-3: Docker 빌드
- **Given** main 브랜치에 push된 상태에서
- **When** CI 파이프라인이 실행되면
- **Then** Docker 이미지가 빌드되고 ghcr.io에 push된다

### AC-4: Dependabot 설정
- **Given** .github/dependabot.yml이 존재하면
- **When** 매주 스캔이 실행되면
- **Then** 취약한 의존성에 대해 자동 PR이 생성된다

---

## 5. 기술 접근 방식

### 파일 구조

```
.github/
├── workflows/
│   ├── ci.yml              # PR 워크플로우 (테스트, 린팅, 커버리지)
│   └── build.yml           # 메인 브랜치 빌드 + Docker push
├── dependabot.yml          # 의존성 보안 스캔
```

---

## Implementation Notes

### 구현 현황

**구현 날짜**: 2026-06-02

**진행 상태**: partially completed

### 구현된 기능

**완료됨**:
- GitHub Actions 워크플로우 (.github/workflows/ci.yml, build.yml)
- CI 파이프라인: pytest, ruff lint, coverage report
- Dependabot 설정 (의존성 보안 스캔)
- Docker 이미지 빌드 및 push (build.yml)

**부분 구현 (검증 필요)**:
- PR 머지 시 자동 테스트 실행
- 커버리지 리포트 Codecov/Codecov 연동
- Docker Hub/GitHub Container Registry 배포
- 환경 변수 주입 및 관리

**미구현**:
- 스테이징/프로덕션 환경 분리 배포
- 롤백 절차 (자동/수동)
- 알림 시스템 (Slack, 이메일)

### 추가 작업 필요

**검증 대상**:
- [ ] PR 생성 시 CI 워크플로우 자동 트리거 확인
- [ ] 테스트 실패 시 PR 블록 동작 확인
- [ ] Docker 이미지 빌드 성공 및 Container Registry push 확인

---

*SPEC ID: SPEC-INFRA-001*
*생성일: 2026-03-16*
*상태: completed*
