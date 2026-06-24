# 2026-06-24 Recording Pipeline Recovery

## Summary

Fixed a chain of production-like local issues around authenticated meeting history, recording pipeline status polling, result screen rendering, derived AI tabs, local Tailscale deployment, and iPhone release installation.

## Server

- Current local API server address: `http://100.69.69.119:8000/api/v1`
- `100.69.69.119` is the current Mac's Tailscale IP for this project, not a separate SSH host.
- Runtime tmux session: `voice-to-textnote-server`
- Windows:
  - `api`: Uvicorn on `0.0.0.0:8000`
  - `worker`: Celery worker with concurrency 3

## Backend Fixes

- Shared task access checks were applied to derived endpoints.
- Worker status updates now preserve ownership and parent task context through `backend/workers/tasks/status_context.py`.
- `has_task_access()` now falls back to parent task ids in payloads for derived task access.
- Tone task failures no longer publish generic DIA task SSE failure events by default.

## Client Fixes

- Speaker segment time now renders as a time range when `end` is available.
- Mind-map provider retries short-lived status 404 after task creation.
- Study Pack and Sales Contact Brief creation requests use a 2-minute receive timeout.

## Representative Recovered Tasks

- Earlier recovered meeting:
  - STT: `69e8d8f3-912c-4ed6-a38b-735c13f6d4d2`
  - DIA: `1c76d5bd-67e3-4a43-95b3-ff84651e2828`
  - Minutes: `095d6819-aea9-4de4-9d8b-661185d6a7b7`
- Current checked meeting:
  - STT: `436cc0fb-620b-4197-b176-6a8d92ed405a`
  - DIA: `e8af438e-71e6-4838-8c6c-edde06375106`
  - Minutes: `792b00d7-8c36-46f5-97df-d22b34d37db9`
  - Summary: `e39e7170-302a-4632-910a-0f3aaf182ddf`
  - Mind map: `41f3a50b-03f2-41e7-8450-1e1da4b2869f`

## Verification

- Backend worker/status tests: `43 passed`, then broader set `138 passed`
- Backend dependency/status tests: `34 passed`
- Backend ruff checks: clean
- Flutter result/service/provider tests: all passed
- Flutter analyze: no issues found
- API health at `100.69.69.119:8000`: healthy
- Study Pack, Sales Contact Brief, and Mind Map APIs returned `200 OK` for the current checked meeting.

## iPhone Build

- Device: `Inbean의 iPhone`
- Device id: `00008150-000239020C08401C`
- Command: `flutter run --release -d 00008150-000239020C08401C`
- Signing team: `4NJ9JSQFW9`
- Release build installed and launched successfully.

## Known Follow-ups

- Local Alembic state still references missing revision `003_add_search_guest`; local SQLite was patched directly for `sharing_policy`.
- Tone analysis may still fail on `librosa.core` import, but this no longer breaks DIA/minutes status.
- External LLM rate limiting can still fail mind-map/study/sales generation; the app now handles timing/race conditions, not upstream quota exhaustion.
