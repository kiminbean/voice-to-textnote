# SPEC-TECHDEBT-001 Acceptance Criteria

## AC-001: datetime.utcnow 제거
- 상태: MET
- 증거: `grep -rn "datetime\.utcnow\(\)" backend/` → 0건 (38곳 → 0)

## AC-002: Pydantic Config 마이그레이션
- 상태: MET
- 증거: `grep -rn "class Config:" backend/app/schemas/` → 0건 (5개 → 0)
- 5개 클래스 전부 `model_config = ConfigDict(from_attributes=True)` 사용

## AC-003: asyncio.get_event_loop 제거
- 상태: MET
- 증거: `grep -rn "get_event_loop" backend/` → 0건 (3곳 → 0)

## AC-004: pytest-asyncio 설정
- 상태: MET
- 증거: `pyproject.toml`에 `asyncio_default_fixture_loop_scope = "function"` 추가

## AC-005: 전체 게이트 유지
- 상태: MET
- ruff: 0 errors
- mypy: 0 errors
- pytest: 3374 passed
