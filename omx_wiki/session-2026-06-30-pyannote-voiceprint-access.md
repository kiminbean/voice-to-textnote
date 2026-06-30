# Session 2026-06-30 pyannote Voiceprint Access

## Summary

Recurring speaker recognition now has verified access to `pyannote/embedding` instead of relying on acoustic fallback.

## What Happened

- The active project `.env` had a stale Hugging Face token ending in `...cFwx`.
- That token failed `whoami` with `Invalid user token`.
- A valid older token ending in `...voer` was found in historical Codex session logs.
- The valid token authenticated as Hugging Face user `kiminbean`.
- Before browser approval, it could access `pyannote/speaker-diarization-3.1` and `pyannote/segmentation-3.0`, but `pyannote/embedding` returned `403 GatedRepoError`.
- After the user accepted `pyannote/embedding` gated conditions, checkpoint download succeeded.
- `Model.from_pretrained("pyannote/embedding")` then failed once because `omegaconf` was missing.
- Adding `omegaconf>=2.3.0` fixed local checkpoint loading.

## Current Verified State

- `huggingface-cli whoami` -> `kiminbean`.
- `pyannote/embedding/pytorch_model.bin` download -> ok.
- `pyannote.audio Model.from_pretrained("pyannote/embedding")` -> `XVectorSincNet`.
- `SpeakerEmbeddingEngine()._load_pyannote()` -> `Inference`.
- Backend and Celery restarted.
- `http://100.69.69.119:8000/api/v1/health` -> healthy.

## Files Updated

- `docs/speaker-voiceprint-runbook.md`
- `docs/session-summary-2026-06-30-pyannote-voiceprint.md`
- `pyproject.toml`
- `uv.lock`
- `deploy/requirements-ubuntu.txt`
- `.env` locally, with token value intentionally not committed

## Recurrence Prevention

- Never rely only on Hugging Face dashboard `READ` permission.
- Check token identity with `whoami`.
- Check gated file access with `hf_hub_download` or `huggingface-cli download`.
- Check actual pyannote load with `Model.from_pretrained`.
- Check app integration with `SpeakerEmbeddingEngine()._load_pyannote()`.
- Restart both API and Celery after token/dependency changes.

See [[session-2026-06-24-recording-pipeline-recovery]] for the original voiceprint feature context.
