# Promise Radar v19 Session Summary — 2026-07-02

This supersedes the v18 baseline. Older v6-v18 notes are historical records; use this file and `docs/promise-radar-e2e-evidence-2026-07-02-v19-summary.json` as the current Promise Radar reference.

## Baseline

- Accuracy set: `backend/tests/fixtures/promise_radar_accuracy_cases.json` has 1089 total cases.
- Real meeting/audio/transcript-derived labels: 1022 cases.
- Hard negatives: 70 cases.
- Public source coverage: 24 manifest entries, including YouTube-derived public meeting material and Hugging Face MeetingBank/QMSum transcript-derived labels.
- Accuracy evaluator: 1089/1089 correct, accuracy 1.0.
- Extraction recall fixture: 50 expected, 50 matched, recall 1.0.
- Command Center gate: `target_case_count=1000`, v15/v16/v17/v19 contracts passed in `backend/scripts/generate_promise_radar_e2e_evidence.py`.

## v19 Changes

- Added 240 public transcript-derived labels from Hugging Face MeetingBank and QMSum samples.
- Added hard-negative and public-source counts to the accuracy report contract.
- Added production-signal, hard-negative, and owner-identity review fields to Learning Loop insights.
- Added SLA due-today and push readiness fields to Daily/Weekly Digest.
- Added identity cluster and owner alias review counts to Promise Memory Graph.
- Added app redirect URI, PKCE, tasklist selection, OAuth UX readiness, and token-exchange readiness to the Google Tasks OAuth guide.
- Updated Flutter models and Command Center UI chips for the new v19 backend contract.
- Added Android device gate evidence for the connected Redmi Note 9 Pro.
- Mitigated the iOS 26.5 ProMotion launch crash observed in XCUITest by setting `CADisableMinimumFrameDurationOnPhone=false`.
- Added iOS UI-test token clearing and result deeplink auth bypass so stale guest Authorization headers do not hide Promise Radar test meetings behind 404.

## Verification

- `python backend/scripts/evaluate_promise_radar_accuracy.py --report --target-real-cases 1000`
  - Result: 1089 cases, 1089 correct, accuracy 1.0, 1022 real labels, 70 hard negatives, 24 public sources.
- `python backend/scripts/audit_promise_radar_accuracy_set.py --target-real-cases 1000`
  - Result: valid, 1089 total, 1022 real labels, target 1000, 0 errors.
- `python backend/scripts/evaluate_promise_radar_extraction.py --target-cases 50 --min-recall 0.95`
  - Result: 50/50 matched, recall 1.0.
- `.venv/bin/python -m pytest backend/tests/unit/test_promise_radar_service.py backend/tests/unit/test_promise_radar_route_registration.py -q --no-cov`
  - Result: 22 passed.
- `flutter analyze ...`
  - Result: No issues found.
- `flutter test test/models/promise_radar_test.dart test/screens/login_screen_guest_test.dart`
  - Result: 14 passed.
- `python3 client/scripts/verify_promise_radar_device_gate.py --serial 76aadc20 --evidence-out docs/release-e2e-artifacts/promise_radar_android_device_gate_v19.json`
  - Result: PASS, Promise Radar tab visible, 12 tabs, staging URL guard passed.
- `backend/scripts/generate_promise_radar_e2e_evidence.py --base-url http://127.0.0.1:8000/api/v1 --output .cache/promise-radar-e2e-v19-check.json`
  - Result: `overall_pass=true`.
- `xcodebuild test ... testIosPromiseRadarEvidence`
  - Result: latest rerun was interrupted by Xcode preflight because the physical iPhone was locked (`Unlock Inbean의 iPhone to Continue`). Earlier run reached the Promise Radar tab and exposed the stale guest-token 404 path that v19 now mitigates in app startup/router code.

## Recurrence Prevention

- Do not lower the v19 release gate below 1000 real labels without an explicit product decision.
- Do not commit raw `.cache/promise-radar-*` dataset/audio/device output; keep only sanitized summaries under `docs/`.
- For iOS Promise Radar UI tests, do not force guest login before opening a hardcoded result deeplink. A fresh guest token will not own older seeded meetings and will correctly produce 404.
- For iPhone 17 Pro / iOS 26.5 physical-device XCUITest, keep `CADisableMinimumFrameDurationOnPhone=false` unless Flutter upstream ProMotion VSync crash fixes are verified on device.
- If Promise Radar says “약속 레이더를 불러올 수 없습니다,” check server audit logs for 401/404 first, then verify whether the app sent a stale `Authorization: Bearer guest:...` header.
