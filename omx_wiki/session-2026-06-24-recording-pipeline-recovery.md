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
- Transcript segments retain `speaker_id`, overlay saved `/speakers` profile names, and prompt default `Speaker N` labels for real names.

## Speaker Name Reuse

- Minutes generation loads authenticated users' global `SpeakerProfile` names before falling back to automatic `Speaker N` labels.
- Renaming a default speaker in the meeting transcript saves a global profile so later transcript loads can show the saved name.
- Saved speakers count toward automatic numbering; a saved `SPEAKER_00=영자` does not cause the next unnamed speaker to restart at `Speaker 1`.
- The transcript tab now automatically opens the real-name prompt when default `Speaker N` labels remain, so users do not have to discover the rename flow by tapping the label. Manual tap-to-rename remains available.

## Voiceprint Speaker Matching

- Diarization now extracts per-speaker voiceprint embeddings from the recorded audio and stores them on the DIA task result.
- When a user corrects `Speaker N` to a real name in the meeting screen, the client sends the current task id and speaker label; the server follows the minutes task to its DIA task and enrolls that voiceprint into the global speaker voice profile.
- The automatic prompt path and manual tap path share the same save/enrollment API call.
- Future recordings compare fresh speaker embeddings against saved global voiceprints. If cosine similarity passes `SPEAKER_VOICEPRINT_SIMILARITY_THRESHOLD`, the saved display name is applied even if the new diarization label is `Speaker 3` or another automatic label.
- Speaker save responses now expose enrollment status so the app can tell the user whether both name and voice information were saved or only the name was saved.
- The transcript tab runs one opportunistic backfill call to connect older name-only global speaker profiles to historical DIA voiceprints.
- Voiceprint-matched speakers show a `추정됨` badge and correction tooltip to reduce silent false-positive risk.
- `backend/scripts/tune_voiceprint_threshold.py` analyzes stored voiceprint pairs and prints a recommended threshold when enough real recordings exist.
- The backend prefers `pyannote/embedding`; if model loading fails because the Hugging Face token or model access is unavailable, it falls back to local acoustic embedding so the pipeline stays functional.
- 2026-06-30 update: `pyannote/embedding` access is now verified for Hugging Face user `kiminbean` with the active token ending in `...voer`. `Model.from_pretrained("pyannote/embedding")` loads as `XVectorSincNet`, and `SpeakerEmbeddingEngine()._load_pyannote()` returns `Inference`.
- 2026-06-30 update: `omegaconf>=2.3.0` is required for the pyannote embedding checkpoint and is now pinned in project and deployment dependencies.
- Existing global speaker names that were saved before this change are backfilled when historical matching voiceprints exist; otherwise the user must correct/save that speaker once from a recording that contains DIA voiceprints.
- Voiceprint-matched names now override stale saved label names in the result provider, so an older saved `SPEAKER_00` label cannot hide a fresh `identified_speaker_name` acoustic match.

## Alembic and Local DB Recovery

- Restored missing migration `003_add_search_guest`.
- Connected `004_unique_minutes_versions_task_version.py` after `003_add_search_guest`.
- Made `005_add_team_sharing_policy.py` safe when `sharing_policy` already exists.
- Repaired the local SQLite DB with `alembic upgrade head` after backup.
- Deleted orphan `meeting_ownership` rows that referenced missing users.
- Verified local DB:
  - `PRAGMA integrity_check` -> `ok`
  - `PRAGMA foreign_key_check` -> clean
  - `alembic_version` -> `005_add_team_sharing_policy`

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
- Voiceprint tests: `68 passed` across speaker APIs, voice service, minutes worker, and DIA voiceprint matching.
- Voiceprint smoke: acoustic fallback produced 48-dimensional embeddings; same segment similarity `1.0`, different segment similarity `0.7555`.
- pyannote embedding access recovery: `huggingface-cli whoami` -> `kiminbean`; `pyannote/embedding/pytorch_model.bin` download -> ok; `SpeakerEmbeddingEngine()._load_pyannote()` -> `Inference`; backend/Celery health at `100.69.69.119:8000` -> healthy.
- Automatic speaker-name prompt UI: `flutter test test/screens/result_screen_test.dart` -> `30 passed`; `flutter analyze` -> no issues.
- Voiceprint improvement pass: backend speaker voice tests -> `40 passed`; Flutter result/provider/widget tests -> `46 passed`; threshold tuning script -> `recommendation=insufficient-data` on current local DB.
- Stale-name regression: reproduced `Expected: 영자 Actual: 철수`; fixed and re-ran the targeted Flutter test successfully.
- Broader Flutter validation after the stale-name fix: `47 passed`; `flutter analyze` clean.
- Alembic/DB repair validation: backend selected tests `85 passed`; backend ruff clean; temp SQLite `alembic upgrade head` succeeded; local DB integrity/FK checks clean.
- Commits pushed: `5253fd6 Identify recurring speakers by voiceprint`, `f987bb4 Prompt for real speaker names automatically`, `52e4413 Close voiceprint feedback loops`, `1f3fb44 Prefer voiceprint names over stale labels`, `a93304e Restore missing Alembic guest revision`.

## iPhone Build

- Device: `Inbean의 iPhone`
- Device id: `00008150-000239020C08401C`
- Command: `flutter run --release -d 00008150-000239020C08401C --dart-define=ENV=staging --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1`
- Signing team: `4NJ9JSQFW9`
- Release build installed and launched successfully.
- Frontend-required release build is already installed. The latest Alembic/DB-only repair does not require another iPhone build.

## Known Follow-ups

- Real-world voiceprint quality still depends on audio quality, speech length, overlap, embedding backend, and threshold data.
- Tone analysis may still fail on `librosa.core` import, but this no longer breaks DIA/minutes status.
- External LLM rate limiting can still fail mind-map/study/sales generation; the app now handles timing/race conditions, not upstream quota exhaustion.
