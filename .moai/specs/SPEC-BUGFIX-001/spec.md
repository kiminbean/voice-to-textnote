# SPEC-BUGFIX-001: 테스트 불일치 및 린트 오류 수정

## 개요

기존 구현 코드가 변경되었으나 테스트가 업데이트되지 않아 발생한 11개 백엔드 실패, 1개 Flutter 실패, 47개 린트 오류를 수정한다.

## 요구사항 (EARS Format)

### REQ-BF-001: Summary Schema max_tokens 기본값 동기화
- **When** SummaryCreateRequest가 max_tokens 없이 생성될 때
- **Then** 기본값은 4096이어야 한다 (기존 2000에서 변경됨)
- **Rationale**: backend/schemas/summary.py에서 기본값이 4096으로 변경되었으나 테스트 미반영

### REQ-BF-002: Redis 캐시 TTL 동기화
- **When** DB에서 Redis 캐시를 복원할 때
- **Then** TTL은 settings.cache_ttl_seconds(604800, 7일)를 사용해야 한다
- **Rationale**: config.py에서 TTL이 86400→604800으로 변경되었으나 테스트 미반영

### REQ-BF-003: STT 모델명 테스트 수정
- **When** WhisperEngine 인스턴스의 model_name을 조회할 때
- **Then** 'whisper'를 포함해야 한다 (large 조건 제거)
- **Rationale**: 모델이 whisper-large-v3-turbo → whisper-small-mlx로 변경됨

### REQ-BF-004: 화자 분리 테스트 WAV 픽스처 수정
- **When** 화자 분리 엔진/태스크 테스트에서 WAV 파일을 생성할 때
- **Then** 유효한 WAV 포맷이거나 오디오 처리를 적절히 모킹해야 한다
- **Rationale**: b"\x00" * 100은 유효한 WAV가 아니어서 soundfile/ffmpeg 오류 발생

### REQ-BF-005: Flutter result_screen 필터 테스트 수정
- **When** 액션 아이템 탭에서 필터 칩을 탭할 때
- **Then** 위젯 히트 테스트가 정상 동작해야 한다
- **Rationale**: 탭 오프셋이 잘못 계산되어 다른 위젯을 탭하는 문제

### REQ-BF-006: Ruff import 정렬
- **When** ruff check를 실행할 때
- **Then** 0개의 오류가 발생해야 한다
- **Rationale**: 47개 I001 import 정렬 오류

## 영향 범위

### 수정 대상 파일
- backend/tests/unit/test_summary_schemas.py (REQ-BF-001)
- backend/tests/unit/test_result_fallback.py (REQ-BF-002)
- backend/tests/unit/test_stt_engine.py (REQ-BF-003)
- backend/tests/unit/test_diarization_engine.py (REQ-BF-004)
- backend/tests/unit/test_diarization_task.py (REQ-BF-004)
- client/test/screens/result_screen_test.dart (REQ-BF-005)
- backend/**/*.py (REQ-BF-006, ruff --fix)

## 수락 기준
- [ ] 백엔드 테스트 전체 통과 (0 failures)
- [ ] Flutter 테스트 전체 통과 (0 failures)
- [ ] ruff check 0 errors
- [ ] flutter analyze 0 issues
- [ ] 커버리지 94%+ 유지
