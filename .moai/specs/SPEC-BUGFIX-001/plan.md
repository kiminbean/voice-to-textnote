# SPEC-BUGFIX-001: Implementation Plan

## Overview

기존 구현 코드가 변경되었으나 테스트가 업데이트되지 않아 발생한 11개 백엔드 테스트 실패, 1개 Flutter 테스트 실패, 47개 린트 오류를 일괄 수정.

## Implementation Status: COMPLETED (2026-06-02)

## Technology Stack

| Component | Technology | Tool |
|-----------|-----------|------|
| Backend Tests | pytest | venv/bin/python -m pytest |
| Flutter Tests | flutter test | Flutter SDK |
| Linting (Python) | ruff | ruff check / ruff --fix |
| Linting (Flutter) | flutter analyze | Flutter SDK |

## Task Decomposition

### Task 1: Summary Schema 동기화 (REQ-BF-001)
- **File**: `backend/tests/unit/test_summary_schemas.py`
- **Status**: COMPLETED
- max_tokens 기본값 2000 → 4096 동기화

### Task 2: Redis 캐시 TTL 동기화 (REQ-BF-002)
- **File**: `backend/tests/unit/test_result_fallback.py`
- **Status**: COMPLETED
- TTL 86400 → 604800 (7일) 동기화

### Task 3: STT 모델명 테스트 수정 (REQ-BF-003)
- **File**: `backend/tests/unit/test_stt_engine.py`
- **Status**: COMPLETED
- whisper-large-v3-turbo → whisper-small-mlx 반영

### Task 4: 화자 분리 WAV 픽스처 수정 (REQ-BF-004)
- **Files**: `backend/tests/unit/test_diarization_engine.py`, `backend/tests/unit/test_diarization_task.py`
- **Status**: COMPLETED
- b"\x00" * 100 → 유효한 WAV 포맷으로 수정

### Task 5: Flutter result_screen 필터 테스트 수정 (REQ-BF-005)
- **File**: `client/test/screens/result_screen_test.dart`
- **Status**: COMPLETED
- 탭 오프셋 계산 수정

### Task 6: Ruff import 정렬 (REQ-BF-006)
- **Files**: `backend/**/*.py` (47개 파일)
- **Status**: COMPLETED
- `ruff --fix`로 I001 오류 47건 자동 수정

## Risk Analysis

| Risk | Impact | Mitigation | Status |
|------|--------|------------|--------|
| 테스트 수정이 실제 동작 변경 | High | 테스트 값만 변경, 프로덕션 코드 미수정 | Resolved |
| ruff --fix가 의도치 않은 변경 | Medium | 변경사항 리뷰 후 커밋 | Resolved |
| Flutter 위젯 테스트 좌표 오차 | Medium | 올바른 탭 오프셋 재계산 | Resolved |

## Results

- Backend tests: 393 passed, 0 failures
- Flutter tests: 37 passed, 0 failures
- ruff check: 0 errors
- flutter analyze: 0 issues
- Coverage: 97.76%

---

*Plan Version: 1.0.0*
*Last Updated: 2026-06-03*
