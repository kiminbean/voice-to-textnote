# SPEC-REFACTOR-001 — Tasks (Plan Iteration 2)

> 범위: Scope A(테스트 회귀 수정) → Scope B(Phase 3 DI 완료). Phase 4(라우터 그룹핑)는 **연기(deferred)**.
> 검증 환경: `cd backend && ../venv/bin/python -m pytest ...` (venv = `backend/../venv/bin/python`). 회귀 식별 시 `-o addopts=""`로 커버리지 게이트 비활성화.
> import 접두사: `backend.`

---

## Phase A — 테스트 회귀 수정 (먼저 수행, 그린 테스트 해제)

### A-1 — audio_preprocess: 광역 except의 VoiceNoteError 전파

- **id**: TASK-A1
- **req**: REQ-RM-A1
- **대상 파일**: `backend/app/api/v1/audio_preprocess.py` (업로드 루프 ~line 131-142)
- **변경**: `except Exception` 블록 **이전에** `except VoiceNoteError: raise` 추가. 즉 `try` 직후 도메인 예외(`request_entity_too_large` 등 413/400)를 먼저 재전파하고, 그 다음 일반 예외만 `bad_request`로 처리.
  - import 확인: `from backend.app.exceptions import VoiceNoteError` (또는 `backend.app.errors`에서 노출되는 베이스) 존재 여부 확인 후 없으면 추가.
- **검증**: `cd backend && ../venv/bin/python -m pytest -o addopts="" tests/unit/test_audio_preprocess_api.py::TestPreprocessEndpoint::test_file_too_large_returns_413 tests/unit/test_audio_preprocess_v2.py::TestUploadFailure::test_upload_read_failure_returns_400 "tests/unit/test_remaining_coverage.py::TestAudioPreprocessRemaining"` → passed

### A-2 — transcription: VoiceNoteError import 누락

- **id**: TASK-A2
- **req**: REQ-RM-A3
- **대상 파일**: `backend/app/api/v1/transcription.py` (line 150 `except VoiceNoteError:` 참조)
- **변경**: 파일 상단 import 블록(line 18-30 영역)에 `from backend.app.exceptions import VoiceNoteError` 추가.
- **검증**: `cd backend && ../venv/bin/python -m pytest -o addopts="" tests/unit/test_transcription_api.py::TestUploadTranscription::test_upload_corrupted_audio tests/integration/test_api.py::TestScenario7CorruptedFile::test_corrupted_file_upload_returns_422` → passed

### A-3 — batch: audio read error 처리

- **id**: TASK-A3
- **req**: REQ-RM-A3
- **대상 파일**: `backend/app/api/v1/batch.py` (및 연관 transcription 경로). `test_audio_read_error_marked_failed`가 A-2 수정으로 해소되는지 우선 확인, 미해소 시 batch 라우터의 예외 처리/응답 형식 개별 수정.
- **검증**: `cd backend && ../venv/bin/python -m pytest -o addopts="" tests/unit/test_batch_api.py::TestUploadBatch::test_audio_read_error_marked_failed` → passed

### A-4 — summary 통합 테스트: 예외 핸들러 등록

- **id**: TASK-A4
- **req**: REQ-RM-A2
- **대상 파일**: `backend/tests/integration/test_summary_api.py` (`sum_client` 픽스처, line 96-146; `app = FastAPI()` line 107)
- **변경**: 픽스처에서 라우터 등록 후 `register_exception_handlers(app)` 호출 추가 (`from backend.app.error_handlers import register_exception_handlers`). 이로써 `VoiceNoteError` → `{"error_code","message","request_id"}` 변환.
- **검증**: `cd backend && ../venv/bin/python -m pytest -o addopts="" tests/integration/test_summary_api.py` → 0 failed

### A-5 — sentiment / rate_limit 404·429 개별 재확인

- **id**: TASK-A5
- **req**: REQ-RM-A2
- **대상 파일**: `backend/app/api/v1/sentiment.py`(not_found 경로 ~line 120), `backend/app/api/v1/*`(rate limit 응답 형식), 필요 시 해당 테스트 픽스처.
- **주의(모호성)**: `test_sentiment_api_extra.py`는 production app(`backend.app.main`)을 사용 → 핸들러는 이미 등록됨. 따라서 404 실패는 라우터 경로/테스트 mock 설정에서 개별 원인 재확인 필요(spec 7.5 참조).
- **검증**: `cd backend && ../venv/bin/python -m pytest -o addopts="" tests/unit/test_sentiment_api_extra.py::TestSentimentAPI::test_get_sentiment_result_not_found tests/unit/test_rate_limit.py::TestRateLimitExceeded::test_rate_limit_response_body_format` → passed

### A-6 — 전체 스위트 그린 게이트

- **id**: TASK-A6
- **req**: REQ-RM-A4
- **변경**: 없음(검증 단계). 잔여 실패 발견 시 해당 카테고리 태스크로 회귀하여 수정.
- **검증**: `cd backend && ../venv/bin/python -m pytest tests/ --ignore=tests/e2e/test_pipeline_e2e.py` → 0 failed
- **참고**: `tests/e2e/test_pipeline_e2e.py` 9건(이벤트 루프 환경 이슈)은 이번 Scope 제외(spec 7.5).

---

## Phase B — Phase 3 의존성 주입 완료 (Scope A 그린 이후)

> 공통 패턴: 각 파일에 `def get_<name>_service() -> XxxService: return XxxService()` provider 추가 → 엔드포인트에 `svc: XxxService = Depends(get_<name>_service)` 주입 → 모듈 레벨 싱글톤 삭제. 서비스 메서드 시그니처(첫 파라미터 `session: AsyncSession`)는 불변(REQ-RM-B2).
> 참조 구현: `backend/app/api/v1/calendar.py:30 get_calendar_service()`.
> 각 태스크 검증: 해당 파일 테스트 + `grep -n "_service = .*Service()" <파일>` → 0.

### B-1 — auth.py

- **id**: TASK-B1 / **req**: REQ-RM-B1
- **변경**: `_auth_service = AuthService()` → `get_auth_service` provider + Depends.
- **검증**: `pytest -o addopts="" tests/unit/test_auth_*` ; `grep -n "_service = .*Service()" app/api/v1/auth.py` → 0

### B-2 — tags.py

- **id**: TASK-B2 / **req**: REQ-RM-B1
- **변경**: `_service = TagService()` → `get_tag_service` + Depends.
- **검증**: `pytest -o addopts="" tests/unit/test_tags_*` ; grep → 0

### B-3 — bookmarks.py

- **id**: TASK-B3 / **req**: REQ-RM-B1
- **변경**: `_service = BookmarkService()` → `get_bookmark_service` + Depends.
- **검증**: `pytest -o addopts="" tests/unit/test_bookmark*` ; grep → 0

### B-4 — search.py / advanced_search.py

- **id**: TASK-B4 / **req**: REQ-RM-B1
- **변경**: `search.py` `_service = SearchService()` → `get_search_service`; `advanced_search.py` `_service = AdvancedSearchService()` → `get_advanced_search_service`.
- **검증**: `pytest -o addopts="" tests/unit/test_search* tests/unit/test_advanced_search*` ; grep 두 파일 → 0

### B-5 — speakers.py (2건)

- **id**: TASK-B5 / **req**: REQ-RM-B1
- **변경**: `_service = SpeakerService()` → `get_speaker_service`; `_voice_service = SpeakerVoiceService()` → `get_speaker_voice_service`.
- **검증**: `pytest -o addopts="" tests/unit/test_speaker*` ; grep → 0

### B-6 — teams.py / meetings.py (공유 MeetingShareService)

- **id**: TASK-B6 / **req**: REQ-RM-B1
- **변경**: `meetings.py` `_meeting_service = MeetingShareService()` → `get_meeting_share_service`; `teams.py` `_team_service = TeamService()` → `get_team_service`, `_meeting_service = MeetingShareService()` → `get_meeting_share_service`(동일 provider 재사용 가능).
- **검증**: `pytest -o addopts="" tests/unit/test_team* tests/unit/test_meeting*` ; grep 두 파일 → 0

### B-7 — webhooks.py

- **id**: TASK-B7 / **req**: REQ-RM-B1
- **변경**: `_service = WebhookService()` → `get_webhook_service`.
- **검증**: `pytest -o addopts="" tests/unit/test_webhook*` ; grep → 0

### B-8 — versions.py

- **id**: TASK-B8 / **req**: REQ-RM-B1
- **변경**: `_service = VersionService()` → `get_version_service`.
- **검증**: `pytest -o addopts="" tests/unit/test_version*` ; grep → 0

### B-9 — vocabulary.py + transcription.py (함수 스코프)

- **id**: TASK-B9 / **req**: REQ-RM-B1
- **변경**: `vocabulary.py` `_service = VocabularyService()` → `get_vocabulary_service`. `transcription.py:67` `vocab_service = VocabularyService()`(함수 스코프)도 `get_vocabulary_service` provider + Depends로 전환(공유 provider 재사용). 조건부 사용(`vocabulary_id` 존재 시)이므로 주입은 항상 받되 분기 내에서만 메서드 호출.
- **검증**: `pytest -o addopts="" tests/unit/test_vocabulary* tests/unit/test_transcription*` ; `grep -rn "_service = .*Service()" app/api/v1/vocabulary.py app/api/v1/transcription.py` → 0

### B-10 — qa.py

- **id**: TASK-B10 / **req**: REQ-RM-B1
- **변경**: `_service = QAService()` → `get_qa_service`.
- **검증**: `pytest -o addopts="" tests/unit/test_qa_*` ; grep → 0

### B-11 — history.py

- **id**: TASK-B11 / **req**: REQ-RM-B1
- **변경**: `_service = ResultService()` → `get_result_service`.
- **검증**: `pytest -o addopts="" tests/unit/test_history*` ; grep → 0

### B-12 — keywords.py

- **id**: TASK-B12 / **req**: REQ-RM-B1
- **변경**: `_service = KeywordService()` → `get_keyword_service`.
- **검증**: `pytest -o addopts="" tests/unit/test_keyword*` ; grep → 0

### B-13 — statistics.py / dashboard.py / enhanced_statistics.py

- **id**: TASK-B13 / **req**: REQ-RM-B1
- **변경**: `statistics.py` `_service = StatisticsService()` → `get_statistics_service`; `dashboard.py` `_service = StatisticsService()` → `get_statistics_service`(공유 가능); `enhanced_statistics.py` `_service = EnhancedStatisticsService()` → `get_enhanced_statistics_service`.
- **검증**: `pytest -o addopts="" tests/unit/test_statistics* tests/unit/test_dashboard* tests/unit/test_enhanced*` ; grep 세 파일 → 0

### B-14 — quality_assessment.py

- **id**: TASK-B14 / **req**: REQ-RM-B1
- **변경**: `_service = QualityService()` → `get_quality_service`.
- **검증**: `pytest -o addopts="" tests/unit/test_quality*` ; grep → 0

### B-15 — Scope B 글로벌 게이트

- **id**: TASK-B15 / **req**: REQ-RM-B3, REQ-RM-A4
- **변경**: 없음(검증).
- **검증**:
  - `grep -rn "_service = .*Service()" backend/app/api/v1/ | wc -l` → **0**
  - `cd backend && ../venv/bin/python -m pytest tests/ --ignore=tests/e2e/test_pipeline_e2e.py` → **0 failed**

---

## 후속 완료 상태

- **Phase 4 (REQ-ROUTE-001~003)**: SPEC-REFACTOR-002와 2026-06-14 재검증으로 완료. flat 라우터 0건, `registry.py` SSOT, `main.py` registry 루프 유지.
- **e2e 이벤트 루프 이슈 (9건)**: 2026-06-14 현재 재현 안 됨. `tests/e2e/test_pipeline_e2e.py` 포함 전체 suite `3323 passed, 16 skipped`.

---

## 실행 순서 요약

1. Phase A 전체(TASK-A1 → A6): 회귀 수정 후 전체 그린 확인.
2. Phase B(TASK-B1 → B15): 파일 그룹별 DI 전환, 각 단계마다 해당 테스트 + grep 검증.
3. 최종 게이트(TASK-B15): grep 0건 + 전체 스위트 0 failed.
