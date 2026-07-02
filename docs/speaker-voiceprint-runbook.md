# Speaker Voiceprint Runbook

Last updated: 2026-07-02

## Current Behavior

- Diarization uses `pyannote/speaker-diarization-community-1` first and falls back to `pyannote/speaker-diarization-3.1` if the primary model cannot be loaded.
- The Community-1 `exclusive_speaker_diarization` output is preferred when available, so STT segment matching receives one speaker label per time span.
- Automatic upload uses `DEFAULT_DIARIZATION_MAX_SPEAKERS=10` by default instead of the old hard-coded `max_speakers=4`.
- Long-recording chunk mode now forwards `num_speakers`, `min_speakers`, and `max_speakers` hints to each pyannote chunk and reuses stable local speaker labels across chunks when overlap matching has no evidence.
- Recurring speaker identification uses `pyannote/embedding` first.
- If `pyannote/embedding` cannot be loaded because the Hugging Face token or gated-model access is invalid, the server falls back to local acoustic embeddings so the app remains usable.
- Automatic matches are displayed as tentative in the client with the `추정됨` badge. A voiceprint is accumulated only when the user saves or updates a speaker name.
- Current verified production-local state on 2026-07-02:
  - Active backend token is the valid `kiminbean` Hugging Face token ending in `...voer`.
  - `pyannote/embedding`, `pyannote/speaker-diarization-community-1`, `pyannote/speaker-diarization-3.1`, and `pyannote/segmentation-3.0` gated file access are all approved.
  - `pyannote.audio Model.from_pretrained("pyannote/embedding")` loads successfully as `XVectorSincNet`.
  - `SpeakerEmbeddingEngine._load_pyannote()` loads `Inference`.
  - `omegaconf>=2.3.0` is required for the legacy pyannote embedding checkpoint and is pinned in `pyproject.toml`, `uv.lock`, and `deploy/requirements-ubuntu.txt`.

## Runtime Settings

Set these in the backend `.env` when you want explicit operational values. Code defaults match the values below.

```env
DIARIZATION_MODEL=pyannote/speaker-diarization-community-1
DIARIZATION_FALLBACK_MODEL=pyannote/speaker-diarization-3.1
DEFAULT_DIARIZATION_MAX_SPEAKERS=10
SPEAKER_EMBEDDING_MODEL=pyannote/embedding
SPEAKER_VOICEPRINT_SIMILARITY_THRESHOLD=0.82
SPEAKER_VOICEPRINT_MAX_SECONDS_PER_SPEAKER=30
SPEAKER_VOICEPRINT_MIN_MATCH_SECONDS=8
SPEAKER_VOICEPRINT_MIN_ENROLL_SECONDS=8
```

Tuning guidance:

- Raise `SPEAKER_VOICEPRINT_SIMILARITY_THRESHOLD` toward `0.85` when different people are being merged.
- Lower it toward `0.80` only when the same person often remains as `Speaker 1`, `Speaker 2`, etc.
- Raise `SPEAKER_VOICEPRINT_MIN_ENROLL_SECONDS` toward `10` for noisy rooms.
- Lower `DEFAULT_DIARIZATION_MAX_SPEAKERS` only for known small meetings; keep `10` for general team meetings because too-low values merge different speakers before voiceprint matching can help.
- Ask users to confirm the speaker name 3 to 5 times across clean recordings before relying on automatic identification.

## Hugging Face pyannote Access Activation

This project cannot complete gated-model access from code. The Hugging Face account owner must do it in the browser because Hugging Face gated models require a logged-in user to request access and share contact information.

Do not assume that a token with `READ` permission is sufficient. Three independent conditions must all be true:

- The token must authenticate with Hugging Face `whoami`.
- The same account must have accepted the gated model conditions.
- The local Python environment must include the checkpoint loader dependencies.

1. Log in to the Hugging Face account that owns the token used in backend `.env`.
2. Open `https://huggingface.co/settings/tokens`.
3. Create or verify a token with either:
   - `read` role, or
   - a production `fine-grained` token with read access to the required pyannote repositories.
4. Open `https://huggingface.co/pyannote/embedding`.
5. Click the access/conditions button and agree to share contact information.
6. Open `https://huggingface.co/pyannote/speaker-diarization-community-1`.
7. Agree to its user conditions.
8. Open `https://huggingface.co/pyannote/speaker-diarization-3.1`.
9. Agree to its user conditions. This is the configured fallback model.
10. Open `https://huggingface.co/pyannote/segmentation-3.0`.
11. Agree to its user conditions. This may be required by pyannote pipelines.
12. Put the token in backend `.env`:

```env
HUGGINGFACE_TOKEN=hf_xxx
```

13. Restart both backend API and Celery worker. `pyannote/embedding` is loaded inside the worker during voiceprint extraction, so restarting only the API is not enough.
14. Validate token identity without printing the token:

```bash
cd /Users/ibkim/Projects/voice-to-textnote
.venv/bin/python - <<'PY'
from backend.app.config import settings
from huggingface_hub import HfApi

who = HfApi().whoami(token=settings.huggingface_token.strip())
print(f"huggingface whoami ok: {who.get('name')}")
PY
```

15. Validate gated file access:

```bash
cd /Users/ibkim/Projects/voice-to-textnote
.venv/bin/python - <<'PY'
from backend.app.config import settings
from huggingface_hub import hf_hub_download

token = settings.huggingface_token.strip()
for repo, filename in [
    ("pyannote/embedding", "pytorch_model.bin"),
    ("pyannote/speaker-diarization-community-1", "config.yaml"),
    ("pyannote/speaker-diarization-3.1", "config.yaml"),
    ("pyannote/segmentation-3.0", "pytorch_model.bin"),
]:
    path = hf_hub_download(repo, filename, token=token)
    print(f"{repo}/{filename}: ok")
PY
```

16. Validate actual pyannote model loading:

```bash
cd /Users/ibkim/Projects/voice-to-textnote
.venv/bin/python - <<'PY'
from backend.app.config import settings
from pyannote.audio import Model, Pipeline

token = settings.huggingface_token or None
Model.from_pretrained(settings.speaker_embedding_model, token=token)
Pipeline.from_pretrained(settings.diarization_model, token=token)
Pipeline.from_pretrained(settings.diarization_fallback_model, token=token)
print("pyannote access ok")
PY
```

Expected result:

```text
pyannote access ok
```

If it fails with `401`, `GatedRepoError`, or a message saying access to `pyannote/embedding`, `pyannote/speaker-diarization-community-1`, or `pyannote/speaker-diarization-3.1` is restricted, the token exists but the account has not accepted the required gated-model conditions, the token is not from that account, or the token lacks read access.

## Recurrence Prevention Checklist

Run this checklist after any `.env`, dependency, server, worker, or model-access change.

1. Confirm `.env` has the intended masked token:

```bash
cd /Users/ibkim/Projects/voice-to-textnote
.venv/bin/python - <<'PY'
from backend.app.config import settings
token = settings.huggingface_token.strip()
print(f"HUGGINGFACE_TOKEN configured={bool(token)} suffix=...{token[-4:] if token else ''}")
PY
```

Expected current suffix:

```text
...voer
```

2. Confirm Hugging Face identity:

```bash
huggingface-cli whoami
```

Expected:

```text
kiminbean
```

3. Confirm `pyannote/embedding` file access:

```bash
huggingface-cli download pyannote/embedding pytorch_model.bin --local-dir /tmp/hf-pyannote-embedding-check --quiet
```

4. Confirm `omegaconf` is installed:

```bash
.venv/bin/python - <<'PY'
import omegaconf
print(f"omegaconf ok: {omegaconf.__version__}")
PY
```

5. Confirm the application embedding engine is not falling back:

```bash
.venv/bin/python - <<'PY'
from backend.ml.speaker_embedding_engine import SpeakerEmbeddingEngine

inference = SpeakerEmbeddingEngine()._load_pyannote()
print(f"speaker embedding inference loaded: {type(inference).__name__ if inference else None}")
PY
```

Expected:

```text
speaker embedding inference loaded: Inference
```

6. Restart both long-lived processes:

```bash
./scripts/install_backend_api_launch_agent.sh
tmux send-keys -t voice-to-textnote-celery:0 C-c
tmux send-keys -t voice-to-textnote-celery:0 \
  'cd /Users/ibkim/Projects/voice-to-textnote && STT_BACKEND=faster_whisper .venv/bin/celery -A backend.workers.celery_app worker --loglevel=info --pool=solo --concurrency=1 2>&1 | tee -a logs/celery.log' C-m
```

Restarting only the API is insufficient because voiceprint extraction runs inside Celery. For Mac mini private staging, the API is owned by LaunchAgent `com.voicetextnote.backend-api`; do not start a second temporary API server in tmux.

7. Confirm health:

```bash
curl -sS http://100.69.69.119:8000/api/v1/health
```

Expected:

```text
"status":"healthy"
```

## Failure Matrix

| Symptom | Meaning | Fix |
| --- | --- | --- |
| `Invalid user token` from `whoami` | `.env` token is revoked, malformed, or from a stale copy | Replace `HUGGINGFACE_TOKEN` with the valid `kiminbean` token; current known suffix is `...voer` |
| `403 GatedRepoError`, `not in the authorized list` | Token is valid, but the account has not accepted that model's gated conditions | Open the model page in the browser and accept/share contact info |
| `401 Unauthorized` on model file | Token missing, token not passed, or wrong token loaded by the process | Check `.env`, process restart, and `settings.huggingface_token` |
| `ModuleNotFoundError: No module named 'omegaconf'` | Gated access is fixed, but local checkpoint dependencies are incomplete | Install/sync `omegaconf>=2.3.0`; it is now pinned in project dependencies |
| Logs show Community-1 failed and 3.1 loaded | Primary model access or compatibility failed, but fallback protected diarization availability | Fix Community-1 access and restart API plus Celery; do not remove fallback until production recordings are verified |
| Logs show `speaker embedding model unavailable; acoustic fallback enabled` | Worker could not load `pyannote/embedding` | Run this checklist inside the same environment used by Celery, then restart Celery |

## Official References

- Hugging Face gated models: https://huggingface.co/docs/hub/models-gated
- Hugging Face user access tokens: https://huggingface.co/docs/hub/security-tokens
- pyannote embedding model card: https://huggingface.co/pyannote/embedding
- pyannote speaker diarization Community-1 model card: https://huggingface.co/pyannote/speaker-diarization-community-1
- pyannote speaker diarization 3.1 model card: https://huggingface.co/pyannote/speaker-diarization-3.1
- pyannote segmentation 3.0 model card: https://huggingface.co/pyannote/segmentation-3.0

## Verification Signals

After a restart and a new recording:

- Backend logs should show `speaker embedding model loaded` for `pyannote/embedding`.
- Diarization logs should show `pyannote/speaker-diarization-community-1` as the loaded model; 3.1 should appear only as fallback evidence after a primary load failure.
- Logs should not show `speaker embedding model unavailable; acoustic fallback enabled`.
- New diarization task results should include `voiceprints.*.embedding_backend = "pyannote"`.
- Client transcript speaker labels may show `추정됨` until the user confirms by saving the name.
