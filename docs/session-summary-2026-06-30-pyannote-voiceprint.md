# Session Summary - 2026-06-30 pyannote Voiceprint Access Recovery

## Context

The app's recurring speaker recognition was designed to prefer `pyannote/embedding`, but recent real-device recordings still showed weak speaker separation. Logs and manual checks showed the worker was falling back to the local acoustic embedding path because `pyannote/embedding` could not be loaded.

## Root Causes

1. The active backend `.env` contained a stale Hugging Face token ending in `...cFwx`.
   - `huggingface_hub.login()` and `whoami` returned `Invalid user token`.
2. A valid older token ending in `...voer` existed only in historical Codex session logs, not in the active project `.env`.
   - The token authenticated as Hugging Face user `kiminbean`.
3. That valid token initially had access to:
   - `pyannote/speaker-diarization-3.1`
   - `pyannote/segmentation-3.0`
   - but not `pyannote/embedding`.
4. After the user accepted the `pyannote/embedding` gated-model conditions in the browser, file download worked but `Model.from_pretrained("pyannote/embedding")` failed because `omegaconf` was missing.

## Fixes Applied

- Replaced active `.env` `HUGGINGFACE_TOKEN` with the valid `kiminbean` token ending in `...voer`.
- Updated local Hugging Face CLI login cache for the same account.
- User accepted the `pyannote/embedding` gated-model conditions in the browser.
- Added `omegaconf>=2.3.0` to:
  - `pyproject.toml`
  - `uv.lock`
  - `deploy/requirements-ubuntu.txt`
- Restarted backend API and Celery worker after the token/dependency changes.

## Voiceprint Quality Changes In Same Workstream

- Default voiceprint similarity threshold: `0.82`.
- Minimum speaker speech duration for automatic matching: `8` seconds.
- Minimum speaker speech duration for enrollment/backfill: `8` seconds.
- Short voiceprints are not extracted or accumulated into running averages.
- Client `추정됨` tooltip now says automatic matches are tentative and should be saved/corrected by the user.

## Verification

```text
huggingface-cli whoami
=> kiminbean
```

```text
pyannote/embedding checkpoint download ok
pyannote/speaker-diarization-3.1/config.yaml: ok
pyannote/segmentation-3.0/pytorch_model.bin: ok
```

```text
pyannote embedding load ok: pyannote/embedding -> XVectorSincNet
speaker embedding inference loaded: Inference
```

```text
ruff check -> All checks passed
pytest voiceprint/diarization set -> 59 passed
health http://100.69.69.119:8000/api/v1/health -> healthy
```

## Recurrence Prevention

- Do not trust token names or Hugging Face dashboard `READ` alone. Always run `whoami`.
- Do not trust model metadata access alone. Always download `pyannote/embedding/pytorch_model.bin`.
- Do not stop after gated access is fixed. Always run `Model.from_pretrained("pyannote/embedding")`.
- If `ModuleNotFoundError: omegaconf` appears, the token is no longer the blocker; dependency sync is.
- Restart both API and Celery after token/dependency changes. Voiceprint extraction runs in Celery.
- Canonical runbook: `docs/speaker-voiceprint-runbook.md`.
