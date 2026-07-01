# 2026-07-01 Promise Radar load failure fix

## Symptom

Existing meeting result screens showed "약속 레이더를 불러올 수 없습니다." The failing app request was:

```text
GET /api/v1/promise-radar/ff99d1f5-cb95-4fbc-8282-7860d03a96d4?limit=30 -> 404
```

## Root Cause

Two independent conditions combined:

1. The running FastAPI process was stale. `/openapi.json` exposed zero `/promise-radar` paths, while a fresh import of `backend.app.main.app` exposed the Promise Radar router.
2. Restarting with the full local `.env` tried to preload the pyannote diarization model during FastAPI startup. The process exited during that warm-up, so the stale process pattern could recur.

Some older summary/minutes rows also lacked `meeting_ownership` rows. Those rows fail access checks even when the route exists, so recent affected task IDs were backfilled after taking a SQLite backup.

## Fix Applied

- Added `MODEL_PRELOAD_ENABLED=false` support so the API server can start routes without STT/pyannote/tone warm-up.
- Updated local/mobile backend run commands to use `MODEL_PRELOAD_ENABLED=false`.
- Backfilled ownership for the recent affected task IDs owned by the authenticated Google account.

## Recurrence Guard

For iOS/Android device validation against the Tailscale backend, start FastAPI like this:

```bash
MODEL_PRELOAD_ENABLED=false STT_BACKEND=faster_whisper \
  .venv/bin/python -m uvicorn backend.app.main:app \
  --host 0.0.0.0 --port 8000 --loop asyncio --http h11
```

Then verify before opening the app:

```bash
curl -sS http://100.69.69.119:8000/openapi.json \
  | python -c 'import json,sys; print(sum("/promise-radar" in p for p in json.load(sys.stdin)["paths"]))'
```

The Promise Radar path count must be greater than zero.
