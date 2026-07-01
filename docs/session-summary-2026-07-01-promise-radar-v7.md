# Session Summary: Promise Radar v7

**Date**: 2026-07-01
**Scope**: Promise Radar 고도화 우선순위 1-7 추가 구현

## Implemented

- Learning Loop v2
  - `completed`, `delayed`, `changed`, `dismissed` 상태별 threshold를 별도 계산한다.
  - `learning_feedback.predicted_status`를 저장해 특정 상태의 오판만 해당 상태 threshold에 반영한다.

- Autopilot Preview Before Confirm
  - `POST /api/v1/promise-radar/autopilot/{task_id}/preview`
  - `POST /api/v1/promise-radar/ledger/{entry_id}/autopilot-confirm`
  - Flutter `자동 판정` 버튼은 즉시 적용하지 않고 미리보기 sheet를 보여준다.
  - 사용자가 `맞음`을 누른 후보만 원장 상태가 변경된다.

- Accuracy Golden Set
  - `backend/tests/fixtures/promise_radar_accuracy_cases.json`을 24개 fixture로 확대했다.
  - 현재 evaluator 결과는 24/24, accuracy 1.0이다.

- Owner/Speaker Alias Graph
  - learning profile에 `owner_aliases`를 추가했다.
  - ledger owner, speaker label, speaker profile id, assigned user id, evidence speaker를 alias graph로 묶는다.
  - 담당자 추천은 `기수님` 같은 한국어 호칭 alias를 정규화한다.

- Evidence Pack Snapshot
  - Autopilot assessment에 `evidence_pack`을 포함한다.
  - 적용/확정 event에 matched text, marker hits, source evidence, similarity, confidence factors, captured_at을 저장한다.

- Promise Conflict Detection
  - 완료/지연 또는 완료/취소 신호가 동시에 발견되면 `conflict_detected=true`로 표시하고 자동 적용하지 않는다.

- Google Tasks Integration
  - `external-task` provider에 `google_tasks`를 추가했다.
  - dry-run은 `tasks.googleapis.com` endpoint/payload를 반환한다.
  - 실제 전송은 OAuth access token과 `https://www.googleapis.com/auth/tasks` scope가 필요하다.

## Regression Prevention

- Autopilot UI must remain preview-first; do not restore one-click mutation in Result screen.
- Weak or conflicting evidence must not mutate ledger state automatically.
- External OAuth tokens must not be written to ledger events or docs.
- Accuracy fixture count should not shrink; add cases when changing marker or conflict rules.

## Verification Commands

- `.venv/bin/ruff check backend/schemas/promise_radar.py backend/services/promise_radar_service.py backend/app/api/v1/minutes/promise_radar.py backend/tests/unit/test_promise_radar_service.py backend/scripts/evaluate_promise_radar_accuracy.py`
- `.venv/bin/pytest backend/tests/unit/test_promise_radar_service.py -q --no-cov`
- `python backend/scripts/evaluate_promise_radar_accuracy.py`
- `cd client && flutter analyze lib/models/promise_radar.dart lib/services/promise_radar_api.dart lib/screens/result_screen.dart test/models/promise_radar_test.dart test/screens/result_screen_test.dart`
- `cd client && flutter test test/models/promise_radar_test.dart test/screens/result_screen_test.dart`
