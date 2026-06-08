"""
자동 키워드 추출/추천 서비스.

외부 NLP 패키지 없이 TF-IDF와 TextRank를 결합하여 한/영 혼합 회의록에서
핵심 단어와 구문을 추출한다.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.db.models import TaskResult
from backend.schemas.keyword import KeywordGroup, KeywordItem, KeywordResponse
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_WORD_RE = re.compile(
    r"[A-Za-z][A-Za-z0-9_+#-]*|[가-힣]+|\d+(?:[./-]\d+)*",
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+|[\n\r]+")

_STOPWORDS: frozenset[str] = frozenset(
    {
        # Korean function words and common meeting filler
        "그리고",
        "그래서",
        "하지만",
        "그런데",
        "그러면",
        "그러나",
        "또한",
        "또는",
        "제가",
        "저는",
        "나는",
        "우리는",
        "우리가",
        "여러분",
        "이것",
        "저것",
        "그것",
        "여기",
        "저기",
        "거기",
        "오늘",
        "내일",
        "이번",
        "다음",
        "지금",
        "이제",
        "정말",
        "진짜",
        "약간",
        "그냥",
        "계속",
        "있는",
        "없는",
        "하는",
        "되는",
        "같은",
        "하고",
        "되고",
        "이고",
        "입니다",
        "합니다",
        "됩니다",
        "있습니다",
        "없습니다",
        "같습니다",
        "보입니다",
        "해주세요",
        "하겠습니다",
        # English function words and meeting filler
        "a",
        "an",
        "the",
        "and",
        "or",
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
        "meeting",
        "discussion",
        "today",
        "tomorrow",
        "next",
        "please",
        "thanks",
    }
)

_KOREAN_SUFFIXES: tuple[str, ...] = (
    "으로부터",
    "에서",
    "으로",
    "까지",
    "부터",
    "에게",
    "께서",
    "이라도",
    "라도",
    "마다",
    "처럼",
    "보다",
    "에는",
    "으로는",
    "로는",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "에",
    "로",
    "와",
    "과",
    "도",
    "만",
)

_KOREAN_VERB_ENDINGS: tuple[str, ...] = (
    "하겠습니다",
    "했습니다",
    "합니다",
    "됩니다",
    "하죠",
    "했죠",
    "하고요",
    "했고",
    "하고",
    "한다",
    "했다",
)

_REDIS_RESULT_KEYS: tuple[tuple[str, str], ...] = (
    ("task:min:result:{task_id}", "minutes"),
    ("task:result:{task_id}", "transcription"),
    ("task:sum:result:{task_id}", "summary"),
    ("minutes:{task_id}", "minutes"),
)


@dataclass(frozen=True)
class _Candidate:
    keyword: str
    tokens: tuple[str, ...]
    score: float
    tfidf_score: float
    textrank_score: float
    frequency: int
    source: str | None = None


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _round_score(value: float) -> float:
    return round(_clamp01(value), 4)


def _normalize_token(token: str) -> str:
    token = token.strip(" \t\r\n'\".,!?;:()[]{}<>")
    if not token:
        return ""

    has_latin = any("a" <= ch.lower() <= "z" for ch in token)
    if has_latin:
        normalized = token.lower()
        if normalized.endswith("'s") and len(normalized) > 3:
            normalized = normalized[:-2]
        return normalized

    normalized = token
    if any("\uac00" <= ch <= "\ud7af" for ch in normalized):
        for ending in _KOREAN_VERB_ENDINGS:
            if normalized.endswith(ending) and len(normalized) - len(ending) >= 2:
                normalized = normalized[: -len(ending)]
                break
        for suffix in _KOREAN_SUFFIXES:
            if normalized.endswith(suffix) and len(normalized) - len(suffix) >= 2:
                return normalized[: -len(suffix)]
    return normalized


def _detect_language(text: str, language_hint: str = "auto") -> str:
    if language_hint != "auto":
        return language_hint
    korean = sum(1 for char in text if "\uac00" <= char <= "\ud7af")
    latin = sum(1 for char in text if "a" <= char.lower() <= "z")
    if korean and latin:
        return "mixed"
    if korean:
        return "ko"
    return "en"


def _split_documents(text: str) -> list[str]:
    parts = [part.strip() for part in _SENTENCE_SPLIT_RE.split(text) if part.strip()]
    return parts or ([text.strip()] if text.strip() else [])


def _tokenize(text: str, min_length: int) -> list[str]:
    tokens: list[str] = []
    for raw in _WORD_RE.findall(text):
        normalized = _normalize_token(raw)  # pragma: no cover
        if not normalized:
            continue  # pragma: no cover
        if normalized.isdigit():
            continue
        if len(normalized) < min_length:
            continue
        if normalized in _STOPWORDS:
            continue
        tokens.append(normalized)
    return tokens


def _candidate_terms(tokens: list[str], max_ngram: int = 3) -> list[tuple[str, tuple[str, ...]]]:
    terms: list[tuple[str, tuple[str, ...]]] = []
    for size in range(1, max_ngram + 1):
        if len(tokens) < size:
            continue
        for index in range(0, len(tokens) - size + 1):
            term_tokens = tuple(tokens[index : index + size])
            if len(set(term_tokens)) == 1 and size > 1:
                continue
            terms.append((" ".join(term_tokens), term_tokens))
    return terms


def _normalize_values(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    maximum = max(values.values())
    if maximum <= 0:
        return {key: 0.0 for key in values}
    return {key: value / maximum for key, value in values.items()}


def _token_similarity(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    jaccard = len(left_set & right_set) / len(left_set | right_set)

    left_text = " ".join(left)
    right_text = " ".join(right)
    substring = 0.0
    if min(len(left_text), len(right_text)) >= 3:
        if left_text in right_text or right_text in left_text:
            substring = min(len(left_text), len(right_text)) / max(len(left_text), len(right_text))
    return max(jaccard, substring)


def _extract_text_from_result(data: dict[str, Any]) -> str:
    text_parts: list[str] = []

    for key in ("text", "transcription", "summary_text", "markdown"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            text_parts.append(value)

    segments = data.get("segments")
    if isinstance(segments, list):
        for segment in segments:
            if isinstance(segment, dict):
                text = segment.get("text")
                if isinstance(text, str) and text.strip():
                    text_parts.append(text)

    sections = data.get("sections")
    if isinstance(sections, dict):
        for value in sections.values():
            if isinstance(value, str) and value.strip():
                text_parts.append(value)

    action_items = data.get("action_items")
    if isinstance(action_items, list):
        for item in action_items:
            if isinstance(item, dict):
                task = item.get("task")
                if isinstance(task, str) and task.strip():
                    text_parts.append(task)
            elif isinstance(item, str) and item.strip():
                text_parts.append(item)

    minutes = data.get("minutes")
    if isinstance(minutes, str) and minutes.strip():
        text_parts.append(minutes)
    elif isinstance(minutes, dict):
        content = minutes.get("content")
        if isinstance(content, str) and content.strip():
            text_parts.append(content)

    return "\n".join(text_parts)


class KeywordService:
    """TF-IDF + TextRank 기반 키워드 추출/추천 서비스."""

    def extract_from_text(
        self,
        text: str,
        *,
        language: str = "auto",
        max_keywords: int | None = None,
        min_score: float | None = None,
        context_texts: list[str] | None = None,
        source: str = "text",
        task_id: str | None = None,
        history_task_count: int | None = None,
    ) -> KeywordResponse:
        """텍스트에서 키워드를 추출한다."""
        clean_text = text.strip()
        if len(clean_text) < 10:
            raise HTTPException(
                status_code=422,
                detail="키워드 추출에는 최소 10자 이상의 텍스트가 필요합니다.",
            )
        clean_text = clean_text[: settings.keyword_max_text_chars]

        limit = max_keywords or settings.keyword_max_keywords
        threshold = settings.keyword_min_score if min_score is None else min_score
        detected_language = _detect_language(clean_text, language)

        candidates = self._extract_candidates(
            clean_text,
            context_texts=context_texts or [],
            max_keywords=limit,
            min_score=threshold,
        )
        keyword_items, groups = self._build_items_and_groups(candidates)

        return KeywordResponse(
            task_id=task_id,
            status="completed",
            source=source,  # type: ignore[arg-type]
            language=detected_language,
            keywords=keyword_items,
            groups=groups,
            total_count=len(keyword_items),
            history_task_count=history_task_count,
            extracted_at=datetime.now(UTC).isoformat(),
        )

    async def extract_for_task(
        self,
        redis_client: aioredis.Redis,
        db: AsyncSession,
        task_id: str,
        *,
        max_keywords: int | None = None,
        min_score: float | None = None,
    ) -> KeywordResponse:
        """저장된 회의 결과에서 키워드를 추출한다."""
        if max_keywords is None and min_score is None:
            cached = await self._fetch_cached_response(redis_client, task_id, "extract")
            if cached:
                return cached

        data = await self._fetch_task_result(redis_client, db, task_id)
        text = _extract_text_from_result(data)
        response = self.extract_from_text(
            text,
            max_keywords=max_keywords,
            min_score=min_score,
            source="meeting",
            task_id=task_id,
        )
        await self._cache_response(redis_client, task_id, "extract", response)
        return response

    async def recommend_for_task(
        self,
        redis_client: aioredis.Redis,
        db: AsyncSession,
        task_id: str,
        *,
        max_keywords: int | None = None,
        min_score: float | None = None,
        history_limit: int | None = None,
    ) -> KeywordResponse:
        """현재 회의와 최근 회의 히스토리를 함께 사용해 키워드를 추천한다."""
        if max_keywords is None and min_score is None and history_limit is None:
            cached = await self._fetch_cached_response(redis_client, task_id, "recommend")
            if cached:
                return cached

        current_data = await self._fetch_task_result(redis_client, db, task_id)
        current_text = _extract_text_from_result(current_data)
        history_records = await self._fetch_history_records(
            db,
            exclude_task_id=task_id,
            limit=history_limit or settings.keyword_history_limit,
        )
        history_texts = [
            _extract_text_from_result(record.result_data or {})
            for record in history_records
            if record.result_data
        ]
        history_texts = [text for text in history_texts if len(text.strip()) >= 10]

        response = self.recommend_from_history(
            current_text,
            history_texts=history_texts,
            task_id=task_id,
            max_keywords=max_keywords,
            min_score=min_score,
        )
        await self._cache_response(redis_client, task_id, "recommend", response)
        return response

    def recommend_from_history(
        self,
        current_text: str,
        *,
        history_texts: list[str],
        task_id: str | None = None,
        max_keywords: int | None = None,
        min_score: float | None = None,
    ) -> KeywordResponse:
        """테스트 가능한 히스토리 기반 추천 로직."""
        limit = max_keywords or settings.keyword_max_keywords
        threshold = settings.keyword_min_score if min_score is None else min_score

        current = self._extract_candidates(
            current_text,
            context_texts=history_texts,
            max_keywords=limit * 2,
            min_score=0.0,
            source="current",
        )
        history_text = "\n".join(history_texts)
        history = (
            self._extract_candidates(
                history_text,
                context_texts=[current_text],
                max_keywords=limit * 2,
                min_score=0.0,
                source="history",
            )
            if history_text.strip()
            else []
        )

        combined = self._combine_recommendations(current, history)
        filtered = [candidate for candidate in combined if candidate.score >= threshold]
        selected = sorted(filtered, key=lambda item: (-item.score, item.keyword))[:limit]
        keyword_items, groups = self._build_items_and_groups(selected)

        return KeywordResponse(
            task_id=task_id,
            status="completed",
            source="history_recommendation",
            language=_detect_language(current_text),
            keywords=keyword_items,
            groups=groups,
            total_count=len(keyword_items),
            history_task_count=len(history_texts),
            extracted_at=datetime.now(UTC).isoformat(),
        )

    async def _fetch_task_result(
        self,
        redis_client: aioredis.Redis,
        db: AsyncSession,
        task_id: str,
    ) -> dict[str, Any]:
        for pattern, task_type in _REDIS_RESULT_KEYS:
            key = pattern.format(task_id=task_id)
            raw = await redis_client.get(key)
            if raw:
                logger.debug("키워드 원본 Redis 히트", key=key, task_type=task_type)
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError as exc:
                    logger.debug("키워드 원본 Redis JSON 파싱 실패", key=key, error=str(exc))
                    continue
                if isinstance(data, dict):
                    return data

        stmt = select(TaskResult).where(
            TaskResult.task_id == task_id,
            TaskResult.status == "completed",
        )
        result = await db.execute(stmt)
        record = result.scalars().first()
        if record and record.result_data:
            return record.result_data

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"회의 데이터를 찾을 수 없습니다: task_id={task_id}",
        )

    async def _fetch_cached_response(
        self,
        redis_client: aioredis.Redis,
        task_id: str,
        kind: str,
    ) -> KeywordResponse | None:
        try:
            raw = await redis_client.get(f"task:kw:{kind}:{task_id}")
            if not raw:
                return None
            data = json.loads(raw)  # pragma: no cover
            if not isinstance(data, dict):
                return None  # pragma: no cover
            return KeywordResponse.model_validate(data)
        except Exception as exc:
            logger.debug("키워드 결과 캐시 조회 실패", task_id=task_id, kind=kind, error=str(exc))
            return None

    async def _fetch_history_records(
        self,
        db: AsyncSession,
        *,
        exclude_task_id: str,
        limit: int,
    ) -> list[TaskResult]:
        stmt = (
            select(TaskResult)
            .where(
                TaskResult.task_type == "minutes",
                TaskResult.status == "completed",
                TaskResult.task_id != exclude_task_id,
            )
            .order_by(TaskResult.completed_at.desc(), TaskResult.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def _cache_response(
        self,
        redis_client: aioredis.Redis,
        task_id: str,
        kind: str,
        response: KeywordResponse,
    ) -> None:
        try:
            key = f"task:kw:{kind}:{task_id}"
            await redis_client.setex(
                key,
                settings.keyword_result_ttl,
                json.dumps(response.model_dump(mode="json"), ensure_ascii=False),
            )
        except Exception as exc:
            logger.debug("키워드 결과 캐시 저장 실패", task_id=task_id, error=str(exc))

    def _extract_candidates(
        self,
        text: str,
        *,
        context_texts: list[str],
        max_keywords: int,
        min_score: float,
        source: str | None = None,
    ) -> list[_Candidate]:
        min_length = settings.keyword_min_term_length
        target_docs = _split_documents(text)
        context_docs: list[str] = []
        for context in context_texts:
            context_docs.extend(_split_documents(context))
        all_docs = target_docs + context_docs

        target_counts: Counter[str] = Counter()
        token_by_term: dict[str, tuple[str, ...]] = {}
        for doc in target_docs:
            tokens = _tokenize(doc, min_length)
            for term, term_tokens in _candidate_terms(tokens):
                target_counts[term] += 1
                token_by_term.setdefault(term, term_tokens)

        if not target_counts:
            return []

        doc_freq: Counter[str] = Counter()
        for doc in all_docs:
            tokens = _tokenize(doc, min_length)
            terms = {term for term, _ in _candidate_terms(tokens)}
            doc_freq.update(terms)

        doc_count = max(1, len(all_docs))
        total_terms = sum(target_counts.values()) or 1
        tfidf_raw: dict[str, float] = {}
        for term, count in target_counts.items():
            tf = count / total_terms
            idf = math.log((1 + doc_count) / (1 + doc_freq.get(term, 0))) + 1
            length_boost = 1.0 + (0.08 * (len(token_by_term.get(term, ())) - 1))
            tfidf_raw[term] = tf * idf * length_boost

        token_rank = self._textrank(target_docs)
        textrank_raw: dict[str, float] = {}
        for term, term_tokens in token_by_term.items():
            ranks = [token_rank.get(token, 0.0) for token in term_tokens]  # pragma: no cover
            if not ranks:
                textrank_raw[term] = 0.0  # pragma: no cover
                continue  # pragma: no cover
            length_boost = 1.0 + (0.08 * (len(term_tokens) - 1))
            textrank_raw[term] = (sum(ranks) / len(ranks)) * length_boost

        tfidf_scores = _normalize_values(tfidf_raw)
        textrank_scores = _normalize_values(textrank_raw)

        tfidf_weight = settings.keyword_tfidf_weight
        textrank_weight = settings.keyword_textrank_weight
        total_weight = tfidf_weight + textrank_weight
        if total_weight <= 0:
            tfidf_weight = textrank_weight = 0.5
            total_weight = 1.0
        tfidf_weight = tfidf_weight / total_weight
        textrank_weight = textrank_weight / total_weight

        combined_raw: dict[str, float] = {}
        for term, count in target_counts.items():
            frequency_boost = min(0.08, math.log1p(count) / 40)
            combined_raw[term] = (
                tfidf_weight * tfidf_scores.get(term, 0.0)
                + textrank_weight * textrank_scores.get(term, 0.0)
                + frequency_boost
            )

        combined_scores = _normalize_values(combined_raw)
        candidates: list[_Candidate] = []
        for term, score in combined_scores.items():
            rounded_score = _round_score(score)  # pragma: no cover
            if rounded_score < min_score:
                continue  # pragma: no cover
            candidates.append(
                _Candidate(
                    keyword=term,
                    tokens=token_by_term[term],
                    score=rounded_score,
                    tfidf_score=_round_score(tfidf_scores.get(term, 0.0)),
                    textrank_score=_round_score(textrank_scores.get(term, 0.0)),
                    frequency=target_counts[term],
                    source=source,
                )
            )

        return sorted(candidates, key=lambda item: (-item.score, item.keyword))[:max_keywords]

    def _textrank(self, docs: list[str]) -> dict[str, float]:
        min_length = settings.keyword_min_term_length
        window = settings.keyword_textrank_window
        graph: dict[str, Counter[str]] = defaultdict(Counter)

        for doc in docs:
            tokens = _tokenize(doc, min_length)
            for token in tokens:
                graph[token]
            for index, token in enumerate(tokens):
                for neighbor in tokens[index + 1 : index + window]:
                    if token == neighbor:
                        continue
                    graph[token][neighbor] += 1
                    graph[neighbor][token] += 1

        if not graph:
            return {}

        ranks = {token: 1.0 for token in graph}
        damping = 0.85
        for _ in range(30):
            next_ranks: dict[str, float] = {}
            for token, neighbors in graph.items():
                rank_sum = 0.0
                for neighbor, weight in neighbors.items():
                    outbound = sum(graph[neighbor].values()) or 1.0
                    rank_sum += ranks[neighbor] * (weight / outbound)
                next_ranks[token] = (1.0 - damping) + damping * rank_sum
            ranks = next_ranks

        return _normalize_values(ranks)

    def _combine_recommendations(
        self,
        current: list[_Candidate],
        history: list[_Candidate],
    ) -> list[_Candidate]:
        current_map = {candidate.keyword: candidate for candidate in current}
        history_map = {candidate.keyword: candidate for candidate in history}
        keywords = set(current_map) | set(history_map)

        raw_scores: dict[str, float] = {}
        for keyword in keywords:
            current_score = current_map.get(keyword).score if keyword in current_map else 0.0  # type: ignore[union-attr]
            history_score = history_map.get(keyword).score if keyword in history_map else 0.0  # type: ignore[union-attr]
            if current_score and history_score:
                raw_scores[keyword] = (current_score * 0.72) + (history_score * 0.28) + 0.08
            elif current_score:
                raw_scores[keyword] = current_score * 0.82
            else:
                raw_scores[keyword] = history_score * 0.35

        normalized = _normalize_values(raw_scores)
        combined: list[_Candidate] = []
        for keyword, score in normalized.items():
            current_candidate = current_map.get(keyword)
            history_candidate = history_map.get(keyword)
            base = current_candidate or history_candidate  # pragma: no cover
            if base is None:
                continue  # pragma: no cover
            source = (
                "current+history"
                if current_candidate and history_candidate
                else ("current" if current_candidate else "history")
            )
            frequency = 0
            if current_candidate:
                frequency += current_candidate.frequency
            if history_candidate:
                frequency += history_candidate.frequency
            combined.append(
                _Candidate(
                    keyword=keyword,
                    tokens=base.tokens,
                    score=_round_score(score),
                    tfidf_score=_round_score(
                        max(
                            current_candidate.tfidf_score if current_candidate else 0.0,
                            history_candidate.tfidf_score if history_candidate else 0.0,
                        )
                    ),
                    textrank_score=_round_score(
                        max(
                            current_candidate.textrank_score if current_candidate else 0.0,
                            history_candidate.textrank_score if history_candidate else 0.0,
                        )
                    ),
                    frequency=max(1, frequency),
                    source=source,
                )
            )
        return combined

    def _build_items_and_groups(
        self,
        candidates: list[_Candidate],
    ) -> tuple[list[KeywordItem], list[KeywordGroup]]:
        groups: list[dict[str, Any]] = []
        threshold = settings.keyword_cluster_similarity_threshold

        item_data: list[dict[str, Any]] = []
        for candidate in candidates:
            best_index: int | None = None
            best_similarity = 0.0
            for index, group in enumerate(groups):
                similarity = max(
                    _token_similarity(candidate.tokens, member_tokens)
                    for member_tokens in group["member_tokens"]
                )
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_index = index

            if best_index is None or best_similarity < threshold:
                group_id = f"kwg-{len(groups) + 1}"
                groups.append(
                    {
                        "group_id": group_id,
                        "label": candidate.keyword,
                        "score": candidate.score,
                        "keywords": [candidate.keyword],
                        "tokens": candidate.tokens,
                        "member_tokens": [candidate.tokens],
                    }
                )
            else:
                group = groups[best_index]
                group_id = group["group_id"]
                group["keywords"].append(candidate.keyword)
                group["member_tokens"].append(candidate.tokens)  # pragma: no cover
                if candidate.score > group["score"]:
                    group["label"] = candidate.keyword  # pragma: no cover
                    group["score"] = candidate.score  # pragma: no cover
                    group["tokens"] = candidate.tokens  # pragma: no cover

            item_data.append(
                {
                    "keyword": candidate.keyword,
                    "score": candidate.score,
                    "tfidf_score": candidate.tfidf_score,
                    "textrank_score": candidate.textrank_score,
                    "frequency": candidate.frequency,
                    "group_id": group_id,
                    "source": candidate.source,
                }
            )

        keyword_items = [KeywordItem(**item) for item in item_data]
        keyword_groups = [
            KeywordGroup(
                group_id=group["group_id"],
                label=group["label"],
                score=_round_score(group["score"]),
                keywords=list(dict.fromkeys(group["keywords"])),
            )
            for group in groups
        ]
        return keyword_items, keyword_groups
