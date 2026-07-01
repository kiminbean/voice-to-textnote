# Session Summary: Promise Radar v6

**Date**: 2026-07-01
**Scope**: Promise Radar 고도화 우선순위 1-7 일괄 구현

## Implemented

- Promise Learning Loop
  - `learning_feedback` ledger event 저장
  - 사용자/팀/게스트 scope별 learning profile 계산
  - false positive가 늘면 Autopilot 자동 적용 threshold를 상향 조정
  - Flutter Result 화면 `오판` 버튼으로 피드백 저장

- Promise Timeline
  - `GET /api/v1/promise-radar/ledger/{entry_id}/timeline`
  - 감지, 수정, Autopilot, 사용자 피드백, 병합/분리, 캘린더, 푸시, 외부 전송 이벤트를 운영자용 label로 변환
  - Flutter Result 화면 `타임라인` bottom sheet 추가

- Pre-Meeting Promise Brief
  - `GET /api/v1/promise-radar/briefing/pre-meeting`
  - 녹음 시작 전 화면에 미해결 약속/질문/준비 점수 표시

- Daily/Weekly Promise Digest
  - `GET /api/v1/promise-radar/digest?cadence=daily|weekly`
  - Home Promise Radar 카드에 Daily Digest 라인 표시

- Evidence Lock
  - Autopilot 자동 적용 전 matched text, source evidence, similarity, confidence factors를 확인
  - 근거가 약하면 assessment는 보여주지만 ledger 상태를 자동 변경하지 않음

- External Work Tool Integration
  - 1차 대상은 Slack
  - `POST /api/v1/promise-radar/ledger/{entry_id}/external-task`
  - 기본 dry-run은 payload 생성/복사만 수행
  - 실제 전송은 `PROMISE_RADAR_SLACK_WEBHOOK_URL` 설정 필요

- Promise Radar Accuracy Set
  - `backend/tests/fixtures/promise_radar_accuracy_cases.json`
  - `backend/scripts/evaluate_promise_radar_accuracy.py`
  - 현재 fixture 6건 기준 accuracy 1.0

## Regression Prevention

- Promise Radar service unit test now covers learning feedback, timeline, pre-meeting brief, digest, Slack dry-run, Evidence Lock, and accuracy evaluation.
- Flutter model test now parses v6 response/request types.
- Do not expand strict release E2E required scenario keys without updating readiness constants, evidence examples, scaffold JSON, and release-readiness tests in the same change.
- Do not bypass Evidence Lock to make Autopilot look more aggressive; weak evidence must remain a visible assessment only.

## Verification Commands

- `.venv/bin/pytest backend/tests/unit/test_promise_radar_service.py -q --no-cov`
- `python backend/scripts/evaluate_promise_radar_accuracy.py`
- `cd client && flutter test test/models/promise_radar_test.dart`
- `cd client && flutter analyze lib/models/promise_radar.dart lib/services/promise_radar_api.dart lib/providers/result_provider.dart lib/screens/result_screen.dart lib/screens/recording_screen.dart lib/screens/home_screen.dart test/models/promise_radar_test.dart`
