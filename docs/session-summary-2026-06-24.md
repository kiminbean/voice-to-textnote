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

## 5. 로컬 서버 배포

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

## 6. iPhone 릴리스 빌드

### 대상

- Device: `Inbean의 iPhone`
- Device id: `00008150-000239020C08401C`
- iOS: `26.5.1`

### 실행

```bash
cd client
flutter run --release -d 00008150-000239020C08401C
```

### 결과

- 자동 서명 팀: `4NJ9JSQFW9`
- Release build 성공
- iPhone 설치 및 실행 성공
- 이후 `flutter run` 로컬 연결 프로세스는 정리했고, 설치된 release 앱은 iPhone에 남아 있습니다.

---

## 현재 미커밋 변경 묶음

### Backend

- `backend/app/dependencies.py`
- `backend/workers/tasks/status_context.py`
- `backend/workers/tasks/transcription_task.py`
- `backend/workers/tasks/diarization_task.py`
- `backend/workers/tasks/minutes_task.py`
- `backend/workers/tasks/summary_task.py`
- `backend/workers/tasks/sentiment_task.py`
- `backend/workers/tasks/tone_task.py`
- `backend/workers/tasks/mind_map_task.py`
- `backend/tests/unit/test_dependencies.py`
- `backend/tests/unit/test_worker_status_context.py`
- `backend/tests/unit/test_tone_task.py`

### Client

- `client/lib/widgets/speaker_segment.dart`
- `client/lib/screens/result_screen.dart`
- `client/lib/providers/result_provider.dart`
- `client/lib/services/study_pack_api.dart`
- `client/lib/services/sales_contact_brief_api.dart`
- `client/test/widgets/speaker_segment_test.dart`
- `client/test/providers/result_provider_test.dart`
- `client/test/services/study_pack_api_test.dart`
- `client/test/services/sales_contact_brief_api_test.dart`

### Runtime state

- `.omx/metrics.json`
- `.omx/state/tmux-hook-state.json`

---

## 남은 주의사항

- Alembic local DB migration은 현재 `alembic_version`이 repo에 없는 `003_add_search_guest`를 가리켜 `alembic upgrade head`가 실패합니다. 이번 세션에서는 `sharing_policy` 컬럼을 SQLite에 직접 추가해 로컬 서버를 복구했습니다.
- 톤 분석은 `librosa.core` import 오류로 실패할 수 있지만, tone 실패가 DIA/회의록 pipeline 실패로 오염되지 않도록 이벤트 발행을 분리했습니다.
- 학습/영업/마인드맵은 LLM API rate limit 또는 긴 응답 시간의 영향을 받습니다. 앱은 생성 시간을 견디도록 보강했지만, 외부 API 429는 재시도 후에도 실패할 수 있습니다.
