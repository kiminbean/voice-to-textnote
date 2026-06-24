"""Recommend a voiceprint similarity threshold from stored task results.

Usage:
    python -m backend.scripts.tune_voiceprint_threshold

The script compares stored diarization voiceprints. Same speaker labels are
treated as positive pairs, different labels as negative pairs. This is a tuning
aid, not a substitute for manually checking real recordings.
"""

from __future__ import annotations

from itertools import combinations
from statistics import mean

from sqlalchemy import select

from backend.db.models import TaskResult
from backend.db.sync_engine import get_sync_session
from backend.ml.speaker_embedding_engine import cosine_similarity


def _iter_voiceprints() -> list[tuple[str, str, list[float]]]:
    items: list[tuple[str, str, list[float]]] = []
    with get_sync_session() as session:
        rows = session.execute(
            select(TaskResult).where(TaskResult.status == "completed")
        ).scalars()
        for task in rows:
            data = task.result_data if isinstance(task.result_data, dict) else {}
            voiceprints = data.get("voiceprints")
            if not isinstance(voiceprints, dict):
                continue
            for speaker_label, payload in voiceprints.items():
                if not isinstance(payload, dict):
                    continue
                embedding = payload.get("embedding")
                if isinstance(embedding, list):
                    items.append((task.task_id, str(speaker_label), [float(v) for v in embedding]))
    return items


def main() -> None:
    voiceprints = _iter_voiceprints()
    positives: list[float] = []
    negatives: list[float] = []

    for left, right in combinations(voiceprints, 2):
        left_task, left_label, left_embedding = left
        right_task, right_label, right_embedding = right
        if left_task == right_task:
            continue
        score = cosine_similarity(left_embedding, right_embedding)
        if left_label == right_label:
            positives.append(score)
        else:
            negatives.append(score)

    print(f"voiceprints={len(voiceprints)} positive_pairs={len(positives)} negative_pairs={len(negatives)}")
    if not positives or not negatives:
        print("recommendation=insufficient-data")
        return

    min_positive = min(positives)
    max_negative = max(negatives)
    recommended = max(0.0, min(1.0, (min_positive + max_negative) / 2))
    print(
        f"positive_avg={mean(positives):.4f} positive_min={min_positive:.4f} "
        f"negative_avg={mean(negatives):.4f} negative_max={max_negative:.4f}"
    )
    print(f"recommendation={recommended:.4f}")


if __name__ == "__main__":
    main()
