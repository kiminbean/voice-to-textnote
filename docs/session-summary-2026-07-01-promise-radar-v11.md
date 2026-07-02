# Promise Radar v11 Session Summary

> Superseded: Promise Radar v19 is the current baseline as of 2026-07-02. Keep this file as historical context and use docs/session-summary-2026-07-02-promise-radar-v19.md for current counts, gates, and recurrence-prevention notes.

> Current baseline note: v11 counts are preserved as session history. The latest Promise Radar baseline is v18 in `docs/session-summary-2026-07-02-promise-radar-v18.md`: 849 total accuracy cases, 782 real-meeting/audio-derived labels, evaluator accuracy 1.0, extraction recall 50/50, Google Tasks OAuth callback/token exchange, preview-only Autopilot default, Live Promise Coach recording surface, and Command Center `target_case_count=700`.

## Scope

- Added an offline accuracy-set audit gate for Promise Radar fixture labels and YouTube source provenance.
- Kept the real-meeting target at 100+ labels and verified the current set has 172 total cases and 112 real-meeting labels.
- Added confidence-bucket accuracy to the backend report so Autopilot thresholds can be tuned from observed calibration instead of guesswork.
- Strengthened Evidence Lock v2: automatic status application now requires a sufficiently long matched text, enough tokens, source evidence, confidence factors, similarity, and marker hits for terminal status changes.
- Added Review Queue diff preview in Flutter: visible/actionable counts, evidence-locked count, weak-evidence count, high-risk count, due count, and status-change distribution before bulk confirmation.
- Added accuracy report UI sections for warnings, confidence buckets, coverage, and source quality.

## New Commands

```bash
python backend/scripts/audit_promise_radar_accuracy_set.py --target-real-cases 100
python backend/scripts/audit_promise_radar_accuracy_set.py \
  --target-real-cases 100 \
  --rebuild-plan-output /tmp/promise-radar-rebuild-plan.json
python backend/scripts/evaluate_promise_radar_accuracy.py --report --target-real-cases 100
```

## Recurrence Prevention

- Do not edit `backend/tests/fixtures/promise_radar_accuracy_cases.json` without running the audit script.
- If adding real meeting labels, update `backend/tests/fixtures/promise_radar_real_meeting_sources.json` with source URL, Creative Commons license evidence, verification command, rebuild commands, and golden case IDs or prefix.
- Keep extracted subtitles/audio in `.cache/promise-radar-*`; do not commit cache files.
- Treat due-date-only delayed detection as Review Queue material unless there is marker-backed evidence in the current meeting text.
- Before release-device validation, build iOS staging with:

```bash
flutter build ios --release \
  --dart-define=ENV=staging \
  --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1
```

## Verification

- `python backend/scripts/audit_promise_radar_accuracy_set.py --target-real-cases 100`
  - passed: `true`, case_count: `172`, real_case_count: `112`, rebuild_plan: `9`
- `python backend/scripts/evaluate_promise_radar_accuracy.py --report --target-real-cases 100`
  - case_count: `172`, real_meeting_case_count: `112`, below_target: `false`, quality_warnings: `4`
- `.venv/bin/pytest backend/tests/unit/test_promise_radar_service.py -q --no-cov`
  - `12 passed`
- `flutter build ios --release --dart-define=ENV=staging --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1`
  - `✓ Built build/ios/iphoneos/Runner.app (38.3MB)`
- `xcrun devicectl device install app --device 00008150-000239020C08401C build/ios/iphoneos/Runner.app`
  - installed `com.voicetextnote.app`
- `xcrun devicectl device process launch --device 00008150-000239020C08401C com.voicetextnote.app`
  - launched `com.voicetextnote.app`
- `strings build/ios/iphoneos/Runner.app/Frameworks/App.framework/App | rg '100\.69\.69\.119|api\.voicetextnote'`
  - found `http://100.69.69.119:8000/api/v1`; no production host match was emitted.
