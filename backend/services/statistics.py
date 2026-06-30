"""
SPEC-STATS-001: 회의 통계 대시보드 서비스

TaskResult.result_data.segments 배열을 집계하여 화자별 통계와
키워드 빈도를 계산한다. 읽기 전용이며 저장소 구조를 변경하지 않는다.
"""

import json
import re
from collections import Counter
from typing import Any

import redis.asyncio as aioredis
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.db.models import TaskResult
from backend.schemas.statistics import KeywordStat, SpeakerStat, StatisticsResponse
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# 공백/문장부호로 토큰 분할 (한/영/숫자 모두 대응)
_TOKEN_SPLIT = re.compile(r"[\s\.,!?\[\]\(\)\"'“”‘’~·…:;／/\\\-—=+*#@`|<>]+")

# 통계에서 제외할 일반 기능어/조사/어미 (한국어 + 영어 기초)
_STOPWORDS: frozenset[str] = frozenset(
    {
        # 한국어 기능어
        "그리고",
        "그래서",
        "하지만",
        "그런데",
        "그러면",
        "그럼",
        "그러나",
        "또한",
        "또는",
        "저는",
        "제가",
        "너는",
        "나는",
        "우리는",
        "우리가",
        "여러분",
        "이것",
        "저것",
        "그것",
        "있습니다",
        "없습니다",
        "입니다",
        "합니다",
        "됩니다",
        "보입니다",
        "같습니다",
        "있는",
        "없는",
        "하는",
        "되는",
        "같은",
        "하고",
        "되고",
        "이고",
        "으로",
        "에서",
        "그리고요",
        "그러면",
        "진짜",
        "정말",
        "좀더",
        "이제",
        "여기",
        "저기",
        "거기",
        # 영어 기능어
        "the",
        "and",
        "but",
        "for",
        "with",
        "this",
        "that",
        "these",
        "those",
        "into",
        "from",
        "over",
        "under",
        "then",
        "than",
        "have",
        "has",
        "had",
        "are",
        "was",
        "were",
        "been",
        "being",
        "will",
        "would",
        "could",
        "should",
        "about",
        "after",
        "before",
        "while",
        "during",
        "between",
        "without",
    }
)

UNKNOWN_SPEAKER = "UNKNOWN"
_SPEAKER_ID_RE = re.compile(r"^SPEAKER[_\s-]?\d+$", re.IGNORECASE)
_DEFAULT_SPEAKER_RE = re.compile(r"^Speaker\s+\d+$", re.IGNORECASE)


def _clean_speaker_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def is_placeholder_speaker_name(name: str | None) -> bool:
    text = _clean_speaker_value(name)
    if text is None:
        return True
    normalized = text.upper()
    return (
        normalized in {"UNKNOWN", "UNKNOWN SPEAKER"}
        or text == "알 수 없음"
        or bool(_SPEAKER_ID_RE.fullmatch(text))
        or bool(_DEFAULT_SPEAKER_RE.fullmatch(text))
    )


def resolve_segment_speaker_key(segment: dict[str, Any]) -> str:
    """Return the stable identity used for speaker aggregation."""
    speaker_id = _clean_speaker_value(segment.get("speaker_id"))
    if speaker_id:
        return speaker_id

    speaker = _clean_speaker_value(segment.get("speaker"))
    if speaker and speaker.upper() not in {"UNKNOWN", "UNKNOWN SPEAKER"}:
        return speaker

    speaker_name = _clean_speaker_value(segment.get("speaker_name"))
    if speaker_name and not is_placeholder_speaker_name(speaker_name):
        return speaker_name

    identified_name = _clean_speaker_value(segment.get("identified_speaker_name"))
    if identified_name and not is_placeholder_speaker_name(identified_name):
        return identified_name

    return speaker_name or identified_name or speaker or UNKNOWN_SPEAKER


def resolve_segment_speaker_name(segment: dict[str, Any]) -> str:
    """Return the best display name available on a minutes segment."""
    identified_name = _clean_speaker_value(segment.get("identified_speaker_name"))
    if identified_name and not is_placeholder_speaker_name(identified_name):
        return identified_name

    speaker_name = _clean_speaker_value(segment.get("speaker_name"))
    if speaker_name and not is_placeholder_speaker_name(speaker_name):
        return speaker_name

    speaker = _clean_speaker_value(segment.get("speaker"))
    if speaker and not is_placeholder_speaker_name(speaker):
        return speaker

    speaker_id = _clean_speaker_value(segment.get("speaker_id"))
    if speaker_id:
        return speaker_id
    if speaker:
        return speaker
    if speaker_name:
        return speaker_name
    if identified_name:
        return identified_name
    return UNKNOWN_SPEAKER


def choose_speaker_display_name(current: str | None, candidate: str) -> str:
    if current is None:
        return candidate
    if is_placeholder_speaker_name(current) and not is_placeholder_speaker_name(candidate):
        return candidate
    return current


async def _fetch_minutes_result(
    redis_client: aioredis.Redis,
    db: AsyncSession,
    task_id: str,
) -> dict | None:
    """Redis 우선, DB 폴백으로 minutes 결과를 조회.

    export.py 의 _get_task_result 와 독립된 서비스 레이어 구현 (API 의존 제거).
    """
    redis_key = f"task:min:result:{task_id}"
    raw = await redis_client.get(redis_key)
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            # Redis 캐시가 손상되었을 때 DB로 폴백시키기 위해 None을 반환한다.
            logger.warning(
                "회의록 Redis 캐시 JSON 파싱 실패 — DB 폴백",
                task_id=task_id,
                error=str(exc),
            )

    stmt = select(TaskResult).where(
        TaskResult.task_id == task_id,
        TaskResult.task_type == "minutes",
        TaskResult.status == "completed",
    )
    result = await db.execute(stmt)
    record = result.scalars().first()
    if record and record.result_data:
        return record.result_data
    return None


class StatisticsService:
    """회의록 통계 계산기.

    의존성:
        - redis_client: Redis 캐시 조회용
        - db: DB 폴백용 (Redis 미스 시)
    """

    async def compute(
        self,
        redis_client: aioredis.Redis,
        db: AsyncSession,
        task_id: str,
        keyword_top_n: int | None = None,
        keyword_min_length: int | None = None,
    ) -> StatisticsResponse:
        """minutes 결과(task_id)로부터 통계를 계산하여 반환."""
        top_n = keyword_top_n or settings.statistics_keyword_top_n
        min_len = keyword_min_length or settings.statistics_keyword_min_length

        # 1) minutes 결과 조회 (Redis 우선, DB 폴백)
        data = await _fetch_minutes_result(redis_client, db, task_id)
        if data is None:
            raise HTTPException(
                status_code=404,
                detail=f"회의록 데이터를 찾을 수 없습니다: task_id={task_id}",
            )

        segments = data.get("segments") or []
        if not isinstance(segments, list) or not segments:
            # 세그먼트 없음 — 빈 통계 반환 (422 대신 200 + 빈값이 더 유용)
            return StatisticsResponse(
                task_id=task_id,
                total_segments=0,
                total_words=0,
                total_duration_seconds=0.0,
                unique_speakers=0,
                speakers=[],
                top_keywords=[],
            )

        return self._aggregate(
            task_id=task_id,
            segments=segments,
            top_n=top_n,
            min_len=min_len,
        )

    def _aggregate(
        self,
        task_id: str,
        segments: list[dict[str, Any]],
        top_n: int,
        min_len: int,
    ) -> StatisticsResponse:
        speaker_time: dict[str, float] = {}
        speaker_segments: dict[str, int] = {}
        speaker_words: dict[str, int] = {}
        speaker_names: dict[str, str] = {}
        keyword_counter: Counter[str] = Counter()

        total_duration = 0.0
        total_words = 0
        total_segments = 0

        for seg in segments:
            if not isinstance(seg, dict):
                continue  # pragma: no cover
            try:
                start = float(seg.get("start", 0) or 0)
                end = float(seg.get("end", 0) or 0)
            except (TypeError, ValueError):
                continue

            duration = max(0.0, end - start)
            text = str(seg.get("text") or "")
            speaker_key = resolve_segment_speaker_key(seg)
            speaker_name = resolve_segment_speaker_name(seg)
            speaker_names[speaker_key] = choose_speaker_display_name(
                speaker_names.get(speaker_key),
                speaker_name,
            )

            tokens = [t for t in _TOKEN_SPLIT.split(text) if t]
            word_count = len(tokens)

            speaker_time[speaker_key] = speaker_time.get(speaker_key, 0.0) + duration
            speaker_segments[speaker_key] = speaker_segments.get(speaker_key, 0) + 1
            speaker_words[speaker_key] = speaker_words.get(speaker_key, 0) + word_count

            for tok in tokens:
                lowered = tok.lower()
                if len(lowered) < min_len:
                    continue
                if lowered in _STOPWORDS:
                    continue
                keyword_counter[lowered] += 1

            total_duration += duration
            total_words += word_count
            total_segments += 1

        speakers: list[SpeakerStat] = []
        for speaker_key, t in sorted(speaker_time.items(), key=lambda kv: -kv[1]):
            ratio = (t / total_duration) if total_duration > 0 else 0.0
            speakers.append(
                SpeakerStat(
                    speaker=speaker_names.get(speaker_key, speaker_key),
                    speaking_time_seconds=round(t, 3),
                    speaking_ratio=round(ratio, 4),
                    segment_count=speaker_segments.get(speaker_key, 0),
                    word_count=speaker_words.get(speaker_key, 0),
                )
            )

        top = [KeywordStat(keyword=k, count=c) for k, c in keyword_counter.most_common(top_n)]

        return StatisticsResponse(
            task_id=task_id,
            total_segments=total_segments,
            total_words=total_words,
            total_duration_seconds=round(total_duration, 3),
            unique_speakers=len(speaker_time),
            speakers=speakers,
            top_keywords=top,
        )
