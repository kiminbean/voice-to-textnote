"""Voiceprint metadata helpers for diarization results."""

from backend.ml.speaker_embedding_engine import SpeakerEmbeddingEngine
from backend.pipeline.speaker_matcher import SpeakerSegment
from backend.workers.tasks.diarization_task import _apply_voiceprint_matches


def test_apply_voiceprint_matches_adds_identified_names_to_result():
    result = {
        "segments": [{"speaker_id": "SPEAKER_03", "start": 0.0, "end": 1.0}],
        "speakers": [{"speaker_id": "SPEAKER_03", "total_speaking_time": 1.0}],
    }
    voiceprints = {
        "SPEAKER_03": {
            "speaker_id": "SPEAKER_03",
            "embedding": [1.0, 0.0, 0.0],
            "embedding_backend": "test",
        }
    }
    matches = {
        "SPEAKER_03": {
            "speaker_profile_id": "profile-001",
            "display_name": "영자",
            "similarity": 0.93,
        }
    }

    _apply_voiceprint_matches(result, voiceprints, matches)

    assert result["voiceprints"] == voiceprints
    assert result["speakers"][0]["identified_speaker_name"] == "영자"
    assert result["speakers"][0]["voiceprint_similarity"] == 0.93
    assert result["segments"][0]["identified_speaker_profile_id"] == "profile-001"


def test_extract_for_speakers_skips_short_voiceprint_sample(tmp_path, monkeypatch):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"not decoded in this test")
    engine = SpeakerEmbeddingEngine()
    calls = []

    def fake_extract_embedding(*args, **kwargs):
        calls.append((args, kwargs))
        return [1.0, 0.0, 0.0], "test"

    monkeypatch.setattr(engine, "extract_embedding", fake_extract_embedding)

    result = engine.extract_for_speakers(
        audio_path,
        [SpeakerSegment("SPEAKER_01", 0.0, 3.0)],
        min_seconds_per_speaker=8.0,
    )

    assert result == {}
    assert calls == []
