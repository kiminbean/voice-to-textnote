# Promise Radar v11

## Summary

Promise Radar now has an offline fixture/source audit gate, confidence-bucket accuracy reporting, stricter Evidence Lock v2 auto-apply rules, and a richer Autopilot Review Queue diff preview.

## Decisions

- Fixture quality is gated by `backend/scripts/audit_promise_radar_accuracy_set.py`.
- Real-meeting label target remains 100+; current evidence is 112 real labels out of 172 total fixture cases.
- Due-date-only delayed guesses are still predicted, but Evidence Lock v2 prevents automatic status application unless marker-backed current-meeting evidence exists.
- iPhone private staging release builds must keep using `ENV=staging` and `API_BASE_URL=http://100.69.69.119:8000/api/v1`.

## Verification

- `python backend/scripts/audit_promise_radar_accuracy_set.py --target-real-cases 100` -> passed, 172 total, 112 real labels.
- `python backend/scripts/evaluate_promise_radar_accuracy.py --report --target-real-cases 100` -> below_target false, confidence buckets emitted.
- `.venv/bin/pytest backend/tests/unit/test_promise_radar_service.py -q --no-cov` -> 12 passed.
