# Session Summary: Promise Radar v8

**Date**: 2026-07-01
**Scope**: Promise Radar 고도화 우선순위 1-7 추가 구현

## Implemented

- Real-meeting-style Accuracy Set 확대
  - `backend/tests/fixtures/promise_radar_accuracy_cases.json`을 24건에서 60건으로 확대했다.
  - 완료/지연/변경/제외/열림/충돌 사례를 한국어와 영어로 포함한다.
  - 현재 evaluator 결과는 60/60, accuracy 1.0이다.

- Autopilot Review Queue
  - `GET /api/v1/promise-radar/autopilot/{task_id}/review-queue`
  - 여러 자동 판정 후보를 `확정 대기 약속함`에서 한 번에 검토한다.
  - Flutter에서 `모두 맞음`, 개별 `맞음`, `거절`을 지원한다.

- Conflict Resolution UI/API
  - `POST /api/v1/promise-radar/ledger/{entry_id}/resolve-conflict`
  - 충돌 감지 항목은 자동 적용하지 않고 사용자가 완료/지연/변경/제외를 선택한다.
  - `분리`는 기존 split flow로 연결한다.

- Evidence Pack Viewer
  - Review Queue `근거` 버튼에서 matched text, marker hit, similarity, confidence factor, timestamp/source evidence를 보여준다.
  - Evidence Pack은 계속 ledger event에 snapshot으로 남긴다.

- Google Tasks OAuth UX
  - Result 화면 `Tasks` 버튼이 Google 계정 선택과 `https://www.googleapis.com/auth/tasks` scope 승인을 요청한다.
  - access token은 저장하지 않고 Google Tasks 전송 요청 1회에만 서버로 전달한다.

- Team Automation Policy
  - `GET|PUT /api/v1/promise-radar/automation-policy`
  - 정책은 `automation_policy_updated` ledger event로 저장된다.
  - 지원 모드: `safe_auto`, `preview_only`, `completed_only`, `manual_only`

- Scheduled Digest Push
  - `POST /api/v1/promise-radar/ledger/notifications/digest`
  - scheduler는 `PROMISE_RADAR_DIGEST_PUSH_ENABLED=true`일 때 due push tick 뒤 digest push도 실행한다.
  - `digest_notification_sent` event로 사용자/cadence/날짜 중복 발송을 방지한다.

## Regression Prevention

- Review Queue는 상태 변경 전용 UX다. Result 화면에서 원장 상태를 즉시 바꾸는 one-click Autopilot을 복원하지 않는다.
- Conflict는 감지만 하지 말고 사용자 해결 경로를 제공해야 한다.
- Evidence Pack Viewer는 marker hit와 matched text를 숨기면 안 된다. 신뢰도 설명의 핵심이다.
- Google Tasks OAuth access token은 저장하지 않는다.
- Accuracy fixture count는 60건 아래로 줄이지 않는다.
- Digest scheduler는 중복 발송 방지 event를 우회하지 않는다.

## Verification Commands

- `ruff check backend/schemas/promise_radar.py backend/services/promise_radar_service.py backend/app/api/v1/minutes/promise_radar.py backend/app/promise_radar_scheduler.py backend/tests/unit/test_promise_radar_service.py`
- `.venv/bin/python -m pytest backend/tests/unit/test_promise_radar_service.py -q --no-cov`
- `python backend/scripts/evaluate_promise_radar_accuracy.py`
- `cd client && flutter analyze lib/models/promise_radar.dart lib/services/promise_radar_api.dart lib/screens/result_screen.dart lib/providers/auth_provider.dart test/models/promise_radar_test.dart`
- `cd client && flutter test test/models/promise_radar_test.dart`
- `cd client && flutter test test/screens/result_screen_test.dart`
