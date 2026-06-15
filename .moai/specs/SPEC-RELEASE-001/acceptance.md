# SPEC-RELEASE-001 Acceptance Criteria

## AC-001: verify_release_readiness.py --strict 통과
- 상태: PENDING (사용자 실행 필요)
- 조건: 11개 외부 환경 변수 설정 후 `0 errors`
- 코드 작업: 완료 (스크립트 이미 구축됨)

## AC-002: GitHub Actions strict gate 통과
- 상태: PENDING (사용자 실행 필요)
- 조건: self-hosted runner + Environment secrets 설정 후 workflow_dispatch PASS

## AC-003: README 상태 업데이트
- 상태: PENDING (AC-001 통과 후)
- 조건: `Production Ready v1.6.0`으로 변경

## AC-004: Git tag 생성
- 상태: PENDING (AC-002 통과 후)
- 조건: `git tag v1.6.0` + GitHub Release 게시

## AC-005: 전체 게이트 유지
- 상태: MET
- ruff: 0 errors
- mypy: 0 errors
- pytest: 3374 passed
- flutter analyze: No issues found!
- flutter test: 328 passed
