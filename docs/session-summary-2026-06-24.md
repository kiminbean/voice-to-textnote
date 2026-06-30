# 세션 요약 — 2026-06-24

## 개요

이 세션에서는 로그인 사용자 기록/처리 흐름의 소유권 연결 문제, 녹음 후 회의록 생성 404, 회의 내용 시간 표시 혼동, 마인드맵/영업/학습 탭 로딩 실패, 로컬 Tailscale 서버 배포, USB 연결 iPhone 릴리스 빌드 설치를 처리했습니다.

현재 로컬 서버 주소는 `100.69.69.119:8000`이며, 이 주소는 이 프로젝트를 실행 중인 Mac의 Tailscale 주소입니다.

---

## 1. 로그인 사용자 기록 및 task 접근권한

### 문제

`t@test.com`으로 로그인했는데 이전 녹음/회의록 기록이 없다고 표시되거나, 처리 중인 task를 조회할 때 404가 발생했습니다.

### 원인

로그인/게스트 task의 소유권이 Redis payload, `task_results`, `meeting_ownership` 사이에서 일관되게 이어져야 하는데 일부 파생 엔드포인트가 공통 접근권한 확인을 사용하지 않았습니다.

### 해결

공통 task 접근권한 확인 헬퍼를 파생 계열에 적용하고, 소유자/팀/게스트 세션 기준으로 접근을 확인하도록 정리했습니다.

### 커밋

`5f4f850` — `Enforce shared task access checks across derived endpoints`

---

## 2. 녹음 후 회의록 생성 중 404

### 증상

녹음 완료 후 앱에서 “회의록 작성중 서버 처리 중 오류가 발생했습니다(404)”가 표시됐습니다.

### 원인

API가 처음 만든 Redis status에는 `user_id`, `guest_session_id`, 부모 task id가 들어갔지만, Celery 워커가 진행률을 업데이트하면서 `created_at`만 보존하고 접근권한 메타데이터를 지웠습니다.

DB 영속 저장이 끝나기 전 짧은 구간에 앱이 status를 조회하면 `require_task_access()`가 소유권을 판단하지 못해 404를 반환했습니다.

### 해결

- `backend/workers/tasks/status_context.py` 추가
- STT/DIA/회의록/요약/감정/톤/마인드맵 워커 status 갱신 시 기존 접근권한/부모 task 메타데이터 보존
- `tone_task` 실패가 DIA SSE 스트림 실패로 오인되지 않도록 기본 이벤트 발행을 차단
- 방금 실패한 녹음은 수동으로 회의록 생성 복구

### 복구된 task

- STT: `69e8d8f3-912c-4ed6-a38b-735c13f6d4d2`
- DIA: `1c76d5bd-67e3-4a43-95b3-ff84651e2828`
- 회의록: `095d6819-aea9-4de4-9d8b-661185d6a7b7`

### 검증

- `.venv/bin/python -m pytest backend/tests/unit/test_worker_status_context.py backend/tests/unit/test_tone_task.py backend/tests/unit/test_diarization_task_v2.py -q --no-cov` → `43 passed`
- 관련 확장 테스트 → `138 passed`
- `ruff check ...` → `All checks passed!`

---

## 3. 회의 내용 시간 표시

### 증상

회의 내용 페이지에서 `Speaker 1` 바로 아래 시간이 항상 `0:00`으로 표시됐습니다.

### 원인

해당 값은 녹음 총 시간이 아니라 발화 segment의 시작 시각이었습니다. 첫 발화는 보통 `0.3초`처럼 녹음 시작 직후라 `0:00`으로 표시되는 것이었습니다.

### 해결

시작 시간만 표시하지 않고 발화 구간을 표시하도록 변경했습니다.

예: `0:00` → `0:00 - 1:01`

### 변경 파일

- `client/lib/widgets/speaker_segment.dart`
- `client/lib/screens/result_screen.dart`
- `client/test/widgets/speaker_segment_test.dart`

### 검증

- `flutter test test/widgets/speaker_segment_test.dart` → `All tests passed`
- `flutter test test/providers/result_provider_test.dart test/widgets/speaker_segment_test.dart test/screens/result_screen_test.dart` → `41 passed`
- `flutter analyze ...` → `No issues found`

---

## 4. 마인드맵/영업/학습 탭 “다시 시도”

### 증상

회의록은 표시되지만 마인드맵, 영업, 학습 탭에서 “불러올 수 없습니다 / 다시 시도”가 표시됐습니다.

### 원인

원인은 두 갈래였습니다.

1. 마인드맵
   - `POST /summaries/{summary_task_id}/mind-map` 직후 앱이 status를 너무 빨리 조회했습니다.
   - 파생 마인드맵 task 자체에는 아직 DB ownership row가 없고 payload에도 직접 `user_id`가 없어서 status 조회가 404로 떨어졌습니다.
   - 나중에 생성은 완료됐지만 앱은 이미 오류 UI로 전환됐습니다.

2. 영업/학습
   - 첫 `GET`은 캐시 없음이므로 404가 정상입니다.
   - 앱 provider가 404를 보고 `POST` 생성으로 fallback하는 구조였지만, 실제 생성이 약 34~35초 걸렸습니다.
   - 일반 API timeout 30초를 넘어 UI가 오류로 바뀔 수 있었습니다.

### 해결

- `backend/app/dependencies.py`
  - payload에 `summary_task_id`, `minutes_task_id`, `diarization_task_id`, `stt_task_id`, `source_task_id`가 있으면 부모 task 접근권한을 fallback으로 확인
- `client/lib/providers/result_provider.dart`
  - 마인드맵 생성 직후 status 404를 짧은 race로 보고 최대 5회 재시도
- `client/lib/services/study_pack_api.dart`
  - 학습팩 생성 요청 receive timeout을 2분으로 설정
- `client/lib/services/sales_contact_brief_api.dart`
  - 영업 브리프 생성 요청 receive timeout을 2분으로 설정

### 검증

- Backend:
  - `.venv/bin/python -m pytest backend/tests/unit/test_dependencies.py backend/tests/unit/test_worker_status_context.py -q --no-cov` → `34 passed`
  - `ruff check backend/app/dependencies.py backend/tests/unit/test_dependencies.py backend/workers/tasks/status_context.py` → `All checks passed!`
- Flutter:
  - `flutter test test/providers/result_provider_test.dart test/providers/study_pack_provider_test.dart test/providers/sales_contact_brief_provider_test.dart test/services/study_pack_api_test.dart test/services/sales_contact_brief_api_test.dart` → `All tests passed`
  - `flutter analyze ...` → `No issues found`
- 실제 API 확인:
  - `GET /api/v1/minutes/792b00d7-8c36-46f5-97df-d22b34d37db9/study-pack?mode=lecture` → `200 OK`
  - `GET /api/v1/minutes/792b00d7-8c36-46f5-97df-d22b34d37db9/sales-contact-brief` → `200 OK`
  - `GET /api/v1/summaries/mind-map/41f3a50b-03f2-41e7-8450-1e1da4b2869f/status` → `200 OK`
  - `GET /api/v1/summaries/mind-map/41f3a50b-03f2-41e7-8450-1e1da4b2869f` → `200 OK`

---

## 5. 화자 이름 저장 및 다음 회의 자동 표시

### 요구

회의 내용에서 `Speaker 1`, `Speaker 2`처럼 표시되는 기본 이름을 `영자`, `철수`처럼 실제 이름으로 수정하면, 다음 회의에서도 저장된 이름을 자동 표시해야 합니다. 또한 기본 `Speaker N` 이름을 그대로 두지 않고 이름 입력을 유도해야 합니다.

### 해결

- 회의록 생성 워커가 로그인 사용자의 전역 `SpeakerProfile` 이름을 읽어 `MinutesFormatter`에 자동 적용합니다.
- 저장된 이름이 적용된 화자도 등장 순서에 포함해, `SPEAKER_00=영자` 이후 미등록 `SPEAKER_01`은 `Speaker 2`로 표시됩니다.
- 앱의 transcript provider가 `speaker_id`를 유지하고, 서버의 `/speakers` 프로필 이름을 `speaker_id` 기준으로 오버레이합니다.
- 회의 내용 탭에서 기본 `Speaker N`이 남아 있으면 자동으로 “이 화자의 이름을 알려주세요” 다이얼로그를 띄워 실제 이름 입력을 유도합니다.
- 사용자가 자동 안내를 닫았거나 나중에 다시 수정하려는 경우를 위해 기존 speaker label 탭 수정 흐름도 유지합니다.
- 입력한 이름은 전역 화자 프로필로 저장되어 이후 같은 사용자 계정의 회의록 표시명에 재사용됩니다.

### 추가 해결: 목소리 자체를 기억하는 화자 식별

- diarization 결과에서 화자별 voiceprint embedding을 추출해 DIA task result의 `voiceprints`에 저장합니다.
- 회의 내용 화면의 자동 이름 입력 UI 또는 수동 speaker label 탭 수정으로 `Speaker N`을 실제 이름으로 저장하면 앱이 현재 minutes task id와 speaker label을 `/speakers` API에 함께 보내고, 서버가 연결된 DIA task의 voiceprint를 전역 `SpeakerVoiceProfile.features.voiceprint`에 등록합니다.
- 이후 녹음에서는 새 diarization label이 `Speaker 1`, `Speaker 2`, `Speaker 3`처럼 달라도 저장된 전역 voiceprint와 cosine similarity를 비교해 임계값 이상이면 저장된 실제 이름을 회의록에 적용합니다.
- embedding backend는 `pyannote/embedding`을 우선 사용하고, Hugging Face 토큰/모델 접근 문제로 로드 실패 시 로컬 acoustic embedding fallback으로 계속 동작합니다.

### 운영상 주의사항

- 기존에 이름만 저장된 전역 화자 프로필은 회의 내용 탭 진입 시 `POST /api/v1/speakers/voiceprints/backfill`로 과거 DIA voiceprint 연결을 1회 자동 시도합니다. 과거 task에 같은 speaker label voiceprint가 없으면 이후 한 번은 해당 화자의 이름을 회의 화면에서 다시 수정/저장해야 voiceprint enrollment가 됩니다.
- 실제 현장 정확도는 발화 길이, 잡음, 마이크 품질, 화자 겹침, embedding backend에 영향을 받습니다. 운영 품질은 `HUGGINGFACE_TOKEN`으로 pyannote embedding 모델을 활성화했을 때 더 안정적입니다.

### 추가 개선: 상태 표시, backfill, 오인식 방지, threshold 튜닝

- `/speakers` create/update 응답에 `voiceprint_enrollment_status`, `voiceprint_sample_count`를 추가해 앱이 저장 결과를 구분합니다.
- 앱 snackbar는 “화자 이름과 목소리 정보를 저장했습니다”와 “화자 이름은 저장했지만 목소리 샘플은 부족합니다”를 구분해 표시합니다.
- voiceprint 자동 매칭된 transcript speaker는 `추정됨` 배지와 tooltip을 표시해 오인식 가능성을 사용자에게 알리고, tap-to-rename 보정 흐름을 유지합니다.
- `POST /api/v1/speakers/voiceprints/backfill`로 기존 이름-only 전역 화자 프로필을 과거 DIA voiceprint에서 보강합니다.
- `python -m backend.scripts.tune_voiceprint_threshold` 운영 스크립트로 실제 저장 voiceprint pair를 분석해 threshold 추천값을 계산합니다.
- 2026-06-30 업데이트: 기본 voiceprint similarity threshold를 `0.82`로 올렸고, 자동 매칭/저장/백필용 최소 발화 길이 `8초`를 적용했습니다. 짧은 샘플은 voiceprint 평균에 누적하지 않습니다.
- 2026-06-30 업데이트: Hugging Face gated 모델 접근 활성화 절차와 검증 명령은 `docs/speaker-voiceprint-runbook.md`를 기준으로 관리합니다.
- 2026-06-30 업데이트: 과거 로그에서 유효한 `kiminbean` Hugging Face 토큰(`...voer`)을 복구해 active `.env`에 적용했고, 사용자가 `pyannote/embedding` gated 조건에 동의한 뒤 checkpoint 다운로드와 `Model.from_pretrained("pyannote/embedding")` 로드가 성공했습니다. 누락 의존성 `omegaconf>=2.3.0`도 프로젝트/배포 의존성에 추가했습니다.
- 2026-06-30 재발 방지: 토큰 `READ` 표시만 보지 말고 `whoami`, `pyannote/embedding/pytorch_model.bin` 다운로드, `SpeakerEmbeddingEngine()._load_pyannote()` 로드를 모두 확인해야 합니다. 자세한 절차는 `docs/session-summary-2026-06-30-pyannote-voiceprint.md`와 `docs/speaker-voiceprint-runbook.md`에 있습니다.

### 변경 파일

- `backend/workers/tasks/minutes_task.py`
- `backend/pipeline/minutes_formatter.py`
- `backend/db/speaker_models.py`
- `backend/tests/unit/test_minutes_task.py`
- `client/lib/providers/result_provider.dart`
- `client/lib/screens/result_screen.dart`
- `client/test/providers/result_provider_test.dart`
- `client/test/screens/result_screen_test.dart`

### 검증

- `.venv/bin/python -m pytest backend/tests/unit/test_minutes_task.py backend/tests/unit/test_minutes_formatter.py backend/tests/unit/test_speakers_api.py -q --no-cov` → `51 passed`
- `ruff check backend/workers/tasks/minutes_task.py backend/pipeline/minutes_formatter.py backend/db/speaker_models.py backend/tests/unit/test_minutes_task.py` → `All checks passed!`
- `flutter test test/providers/result_provider_test.dart test/screens/result_screen_test.dart` → `42 passed`
- `flutter analyze` → `No issues found`

---

## 6. 로컬 서버 배포

### 서버

`100.69.69.119`는 별도 원격 서버가 아니라 현재 Mac의 Tailscale 주소입니다.

### 실행 방식

tmux 세션 `voice-to-textnote-server`로 API와 Celery worker를 실행했습니다.

```bash
tmux new-session -d -s voice-to-textnote-server -n api \
  'cd /Users/ibkim/Projects/voice-to-textnote && env STT_BACKEND=faster_whisper WHISPER_MODEL=mlx-community/whisper-small-mlx HUGGINGFACE_TOKEN= .venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 2>&1 | tee -a logs/backend.log'

tmux new-window -t voice-to-textnote-server -n worker \
  'cd /Users/ibkim/Projects/voice-to-textnote && env STT_BACKEND=faster_whisper .venv/bin/celery -A backend.workers.celery_app worker --loglevel=info --concurrency=3 2>&1 | tee -a logs/celery.log'
```

### 검증

`curl http://100.69.69.119:8000/api/v1/health`:

- API healthy
- Redis healthy
- Celery worker healthy
- ffmpeg available

---

## 7. iPhone 릴리스 빌드

### 대상

- Device: `Inbean의 iPhone`
- Device id: `00008150-000239020C08401C`
- iOS: `26.5.1`

### 실행

```bash
cd client
flutter run --release -d 00008150-000239020C08401C --dart-define=ENV=staging --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1
```

### 결과

- 자동 서명 팀: `4NJ9JSQFW9`
- Release build 성공
- iPhone 설치 및 실행 성공
- 화자 이름 저장/재사용 변경 후에도 release build를 다시 설치했습니다.
- 이후 `flutter run` 로컬 연결 프로세스는 정리했고, 설치된 release 앱은 iPhone에 남아 있습니다.

---

## 이번 화자 이름 작업 변경 묶음

### Backend

- `backend/db/speaker_models.py`
- `backend/pipeline/minutes_formatter.py`
- `backend/workers/tasks/minutes_task.py`
- `backend/tests/unit/test_minutes_task.py`

### Client

- `client/lib/screens/result_screen.dart`
- `client/lib/providers/result_provider.dart`
- `client/test/providers/result_provider_test.dart`
- `client/test/screens/result_screen_test.dart`

## 이번 목소리 기억 작업 변경 묶음

### Backend

- `backend/ml/speaker_embedding_engine.py`
- `backend/services/speaker_voice_service.py`
- `backend/workers/tasks/diarization_task.py`
- `backend/workers/tasks/minutes_task.py`
- `backend/app/api/v1/collaboration/speakers.py`
- `backend/schemas/speaker.py`
- `backend/tests/unit/test_speaker_voice_service.py`
- `backend/tests/unit/test_speakers_voice_api.py`
- `backend/tests/unit/test_minutes_task.py`
- `backend/tests/unit/test_diarization_voiceprint.py`

### Client

- `client/lib/models/speaker_profile.dart`
- `client/lib/screens/result_screen.dart`
- `client/test/screens/result_screen_test.dart`

### 검증

- `ruff check ...` → `All checks passed!`
- `.venv/bin/python -m pytest backend/tests/unit/test_speakers_api.py backend/tests/unit/test_speakers_voice_api.py backend/tests/unit/test_speaker_voice_service.py backend/tests/unit/test_minutes_task.py backend/tests/unit/test_diarization_voiceprint.py -q --no-cov` → `68 passed`
- `flutter test test/screens/result_screen_test.dart test/providers/result_provider_test.dart` → `42 passed`
- `flutter test test/screens/result_screen_test.dart` → `30 passed`
- `flutter test test/screens/result_screen_test.dart test/providers/result_provider_test.dart test/widgets/speaker_segment_test.dart` → `46 passed`
- `flutter analyze` → `No issues found`
- `.venv/bin/python -m pytest backend/tests/unit/test_speaker_voice_service.py backend/tests/unit/test_speakers_voice_api.py -q --no-cov` → `40 passed`
- `python -m backend.scripts.tune_voiceprint_threshold` → `voiceprints=0`, `recommendation=insufficient-data`
- acoustic voiceprint smoke → `{'backend': 'acoustic', 'dims': 48, 'same': 1.0, 'different': 0.7555}`
- `5253fd6 Identify recurring speakers by voiceprint`, `f987bb4 Prompt for real speaker names automatically` pushed to `origin/main`.

### 후속 수정: 화자 이름 우선순위와 Alembic/DB 복구

- voiceprint로 식별된 `identified_speaker_name`이 오래된 저장 label 이름보다 우선 적용되도록 `result_provider.dart`를 수정했습니다.
- 재현된 증상: 테스트에서 `Expected: 영자 Actual: 철수`로, 실제 voiceprint 매칭 이름이 과거 label 이름에 의해 가려졌습니다.
- 누락된 Alembic revision `003_add_search_guest`를 복원하고 `004_unique_minutes_versions_task_version.py`의 `down_revision`을 연결했습니다.
- `005_add_team_sharing_policy.py`는 `sharing_policy` 컬럼이 이미 존재하는 SQLite DB에서도 upgrade가 중단되지 않도록 idempotent 처리했습니다.
- 로컬 `voice_to_textnote.db`는 백업 후 `alembic upgrade head`를 완료했고, orphan `meeting_ownership` FK row를 제거했습니다.
- 최종 DB 상태: `PRAGMA integrity_check` → `ok`, `PRAGMA foreign_key_check` → clean, `alembic_version` → `005_add_team_sharing_policy`.
- 검증: stale-name targeted Flutter test pass, Flutter 관련 전체 테스트 `47 passed`, `flutter analyze` clean, 백엔드 선택 테스트 `85 passed`, backend ruff clean, 임시 SQLite `alembic upgrade head` 성공.
- Commits: `1f3fb44 Prefer voiceprint names over stale labels`, `a93304e Restore missing Alembic guest revision`.
- iPhone 상태: frontend speaker prompt/voiceprint UI 변경 후 release build는 이미 설치 완료. 이후 Alembic/DB-only 수정은 iPhone 재빌드가 필요하지 않습니다.

### Docs

- `docs/session-summary-2026-06-24.md`
- `progress.txt`
- `client/progress.txt`

## 남은 주의사항

- Alembic local DB migration 문제는 `003_add_search_guest` 복원과 local DB upgrade로 해결했습니다. 현재 local DB는 head `005_add_team_sharing_policy`이며 integrity/FK check가 통과합니다.
- 톤 분석은 `librosa.core` import 오류로 실패할 수 있지만, tone 실패가 DIA/회의록 pipeline 실패로 오염되지 않도록 이벤트 발행을 분리했습니다.
- 학습/영업/마인드맵은 LLM API rate limit 또는 긴 응답 시간의 영향을 받습니다. 앱은 생성 시간을 견디도록 보강했지만, 외부 API 429는 재시도 후에도 실패할 수 있습니다.
