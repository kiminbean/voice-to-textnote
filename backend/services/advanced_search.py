"""
고급 검색 서비스
"""

import json
import time
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import redis.asyncio as aioredis
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import TaskResult
from backend.schemas.advanced_search import (
    AdvancedSearchRequest,
    SearchAnalytics,
    SearchResultItem,
)


class AdvancedSearchService:  # pragma: no cover
    """고급 검색 서비스."""

    def __init__(self):
        self.redis_client = None

    async def initialize(self, redis_client: aioredis.Redis):
        """Redis 클라이언트 초기화"""
        self.redis_client = redis_client

    async def search_advanced(
        self, request: AdvancedSearchRequest, db: AsyncSession
    ) -> tuple[list[SearchResultItem], dict[str, Any], SearchAnalytics]:
        """고급 검색 실행"""
        start_time = time.time()

        # 검색 쿼리 생성: DB 컬럼으로 좁힐 수 있는 조건만 먼저 적용한다.
        # JSON 결과 본문/세그먼트/태그/화자 조건은 DB별 JSON dialect 차이를 피하기 위해
        # Python에서 동일한 추출 로직으로 필터링한다.
        query = select(TaskResult)
        search_conditions = []

        # 날짜 필터
        if request.filters.start_date:
            search_conditions.append(TaskResult.created_at >= request.filters.start_date)

        if request.filters.end_date:
            search_conditions.append(TaskResult.created_at <= request.filters.end_date)

        # 콘텐츠 유형 필터
        if request.filters.content_types:
            search_conditions.append(TaskResult.task_type.in_(request.filters.content_types))

        # 모든 조건 결합
        if search_conditions:
            query = query.where(and_(*search_conditions))

        # 검색 실행
        result = await db.execute(query)
        task_results = list(result.scalars().all())

        if request.query:
            task_results = [
                task for task in task_results if self._matches_query(task, request.query)
            ]
        if request.filters.speaker_ids:
            speaker_set = set(request.filters.speaker_ids)
            task_results = [
                task
                for task in task_results
                if speaker_set.intersection(self._get_speaker_ids(task))
            ]
        if request.filters.tags:
            tag_set = set(request.filters.tags)
            task_results = [
                task for task in task_results if tag_set.intersection(self._get_tags(task))
            ]
        if request.filters.min_word_count is not None:
            task_results = [
                task
                for task in task_results
                if self._get_word_count(task) >= cast(int, request.filters.min_word_count)
            ]
        if request.filters.max_word_count is not None:
            task_results = [
                task
                for task in task_results
                if self._get_word_count(task) <= cast(int, request.filters.max_word_count)
            ]

        all_search_results = []
        for task in task_results:
            search_result = SearchResultItem(
                id=str(task.id),
                task_id=task.task_id,
                title=self._get_title(task),
                content=self._extract_content_preview(task),
                content_type=task.task_type or "minutes",
                speaker_ids=self._get_speaker_ids(task),
                word_count=self._get_word_count(task),
                tags=self._get_tags(task),
                created_at=task.created_at,
                relevance_score=self._calculate_relevance(task, request.query),
                highlights=self._extract_highlights(task, request.query),
            )
            all_search_results.append(search_result)

        reverse = request.sort_order == "desc"
        if request.sort_by == "date":
            all_search_results.sort(key=lambda item: item.created_at, reverse=reverse)
        else:
            all_search_results.sort(
                key=lambda item: (item.relevance_score, item.created_at),
                reverse=reverse,
            )

        # 페이징
        offset = (request.page - 1) * request.page_size
        search_results = all_search_results[offset : offset + request.page_size]
        total_results = len(all_search_results)
        search_time_ms = (time.time() - start_time) * 1000

        # 분석 데이터 생성
        analytics = await self._generate_analytics(all_search_results, search_time_ms)

        # 페이지네이션 정보
        pagination = {
            "page": request.page,
            "page_size": request.page_size,
            "total_results": total_results,
            "has_next": offset + request.page_size < total_results,
        }

        # 검색 기록 저장 (Redis)
        if self.redis_client:
            await self._save_search_history(request, search_time_ms, total_results)

        return search_results, pagination, analytics

    def _result_data(self, task: TaskResult) -> dict[str, Any]:
        return task.result_data or {}

    def _input_metadata(self, task: TaskResult) -> dict[str, Any]:
        return task.input_metadata or {}

    def _get_title(self, task: TaskResult) -> str:
        data = self._result_data(task)
        meta = self._input_metadata(task)
        title = data.get("title") or meta.get("title")
        if isinstance(title, str) and title:
            return title
        return f"회의록 - {task.created_at.strftime('%Y-%m-%d %H:%M')}"

    def _get_text(self, task: TaskResult, key: str) -> str:
        value = self._result_data(task).get(key)
        return value if isinstance(value, str) else ""

    def _get_segments_text(self, task: TaskResult) -> str:
        segments = self._result_data(task).get("segments", [])
        if not isinstance(segments, list):
            return ""
        texts = []
        for segment in segments:
            if isinstance(segment, dict):
                text = segment.get("text")
                if isinstance(text, str):
                    texts.append(text)
        return " ".join(texts)

    def _get_searchable_text(self, task: TaskResult) -> str:
        parts = [
            task.task_id,
            task.task_type,
            task.status,
            task.error_message or "",
            self._get_title(task),
            self._get_text(task, "summary"),
            self._get_text(task, "content"),
            self._get_segments_text(task),
            " ".join(self._get_tags(task)),
            " ".join(self._get_speaker_ids(task)),
        ]
        return "\n".join(part for part in parts if part)

    def _matches_query(self, task: TaskResult, query: str) -> bool:
        return query.lower() in self._get_searchable_text(task).lower()

    def _get_speaker_ids(self, task: TaskResult) -> list[str]:
        speakers = self._result_data(task).get("speakers", [])
        if not isinstance(speakers, list):
            return []
        result: list[str] = []
        for speaker in speakers:
            if isinstance(speaker, dict):
                speaker_id = speaker.get("speaker_id") or speaker.get("id")
                if speaker_id is not None:
                    result.append(str(speaker_id))
            elif speaker is not None:
                result.append(str(speaker))
        return result

    def _get_tags(self, task: TaskResult) -> list[str]:
        tags = self._result_data(task).get("tags", [])
        return [str(tag) for tag in tags] if isinstance(tags, list) else []

    def _get_word_count(self, task: TaskResult) -> int:
        value = self._result_data(task).get("word_count")
        if isinstance(value, int):
            return value
        text = (
            self._get_text(task, "content")
            or self._get_text(task, "summary")
            or self._get_segments_text(task)
        )
        return len(text.split())

    def _extract_content_preview(self, task: TaskResult) -> str:
        """내용 미리 추출"""
        summary = self._get_text(task, "summary")
        content = self._get_text(task, "content")
        if summary:
            return summary[:200] + "..." if len(summary) > 200 else summary
        elif content:
            return content[:200] + "..." if len(content) > 200 else content
        segments = self._get_segments_text(task)
        if segments:
            return segments[:200] + "..." if len(segments) > 200 else segments
        return "내용 없음"

    def _calculate_relevance(self, task: TaskResult, query: str) -> float:
        """검색 대상 전체 텍스트를 기준으로 관련도 점수 계산"""
        score = 0.5  # 기본 점수

        query_lower = query.lower()
        if query_lower in self._get_title(task).lower():
            score += 0.3

        if query_lower in self._get_text(task, "summary").lower():
            score += 0.2

        searchable = self._get_searchable_text(task).lower()
        if query_lower in self._get_text(task, "content").lower():
            score += 0.1
        elif query_lower in searchable:
            score += 0.05

        return min(score, 1.0)

    def _extract_highlights(self, task: TaskResult, query: str) -> list[str]:
        """검색어 주변 문맥 하이라이트 추출"""
        highlights: list[str] = []
        title = self._get_title(task)
        summary = self._get_text(task, "summary")
        content = self._get_text(task, "content")
        segments = self._get_segments_text(task)

        # 제목에서 하이라이트
        if query.lower() in title.lower():
            highlights.append(title)

        for text in [summary, content, segments]:
            if text and query.lower() in text.lower():
                pos = text.lower().find(query.lower())
                start = max(0, pos - 50)
                end = min(len(text), pos + len(query) + 50)
                highlights.append(text[start:end])

        return highlights[:3]  # 최대 3개

    async def _generate_analytics(
        self, results: list[SearchResultItem], search_time_ms: float
    ) -> SearchAnalytics:
        """검색 분석 생성"""

        # 타입별 분포
        type_distribution: dict[str, int] = {}
        for result in results:
            type_distribution[result.content_type] = (
                type_distribution.get(result.content_type, 0) + 1
            )

        # 화자별 분포
        speaker_distribution: dict[str, int] = {}
        for result in results:
            for speaker_id in result.speaker_ids:
                speaker_distribution[speaker_id] = speaker_distribution.get(speaker_id, 0) + 1

        # 인기 태그
        tag_counts: dict[str, int] = {}
        for result in results:
            for tag in result.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        popular_tags = [
            {"tag": tag, "count": count}
            for tag, count in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        # 평균 단어 수
        avg_word_count = (
            sum(result.word_count for result in results) / len(results) if results else 0
        )

        search_trends = await self._get_search_trends()

        return SearchAnalytics(
            total_results=len(results),
            search_time_ms=search_time_ms,
            distribution_by_type=type_distribution,
            distribution_by_speaker=speaker_distribution,
            popular_tags=popular_tags,
            average_word_count=avg_word_count,
            search_trends=search_trends,
        )

    async def _get_search_trends(self) -> list[dict[str, Any]]:
        if not self.redis_client:
            return []
        history = await self.get_search_history(limit=100)
        now = datetime.now(UTC)
        windows = [
            ("last_week", 7),
            ("last_month", 30),
            ("last_year", 365),
        ]
        trends = []
        for period, days in windows:
            since = now.timestamp() - days * 24 * 60 * 60
            count = 0
            for item in history:
                created_at = self._parse_datetime(item.get("created_at"))
                if created_at and created_at.timestamp() >= since:
                    count += 1
            trends.append({"period": period, "searches": count})
        return trends

    def _parse_datetime(self, value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

    def _parse_json_dict(self, data: Any) -> dict[str, Any] | None:
        try:
            parsed = json.loads(data)
        except (TypeError, json.JSONDecodeError, UnicodeDecodeError):
            return None
        return parsed if isinstance(parsed, dict) else None

    async def _save_search_history(
        self, request: AdvancedSearchRequest, search_time_ms: float, result_count: int = 0
    ):
        """검색 기록 저장"""
        if not self.redis_client:
            return

        # 검색 기록 ID 생성
        history_id = str(uuid4())

        # 검색 기록 데이터
        history_data = {
            "id": history_id,
            "query": request.query,
            "filters": request.filters.model_dump(mode="json"),
            "result_count": result_count,
            "search_time_ms": search_time_ms,
            "created_at": datetime.now(UTC).isoformat(),
            "is_saved": False,
        }

        # Redis에 저장 (TTL: 30일)
        await self.redis_client.setex(
            f"search_history:{history_id}",
            30 * 24 * 60 * 60,  # 30 days TTL
            json.dumps(history_data, ensure_ascii=False),
        )

        # 최근 검색 기록 목록에 추가 (최대 100개)
        recent_key = "search_history:recent"
        await self.redis_client.lpush(recent_key, history_id)
        await self.redis_client.ltrim(recent_key, 0, 99)  # 최대 100개 유지

    async def get_search_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """최근 검색 기록 조회"""
        if not self.redis_client:
            return []

        recent_key = "search_history:recent"
        history_ids = await self.redis_client.lrange(recent_key, 0, limit - 1)

        history = []
        for history_id in history_ids:
            data = await self.redis_client.get(f"search_history:{history_id}")
            if data:
                parsed = self._parse_json_dict(data)
                if parsed:
                    history.append(parsed)

        return history

    async def get_search_history_item(self, history_id: str) -> dict[str, Any] | None:
        """단일 검색 기록 조회"""
        if not self.redis_client:
            return None
        return self._parse_json_dict(await self.redis_client.get(f"search_history:{history_id}"))

    async def get_saved_searches(self, limit: int = 50) -> list[dict[str, Any]]:
        """저장된 검색 조회"""
        if not self.redis_client:
            return []
        saved_ids = await self.redis_client.lrange("saved_search:recent", 0, limit - 1)
        saved_searches = []
        for saved_id in saved_ids:
            data = await self.redis_client.get(f"saved_search:{saved_id}")
            parsed = self._parse_json_dict(data)
            if parsed:
                saved_searches.append(parsed)
        return saved_searches

    async def save_search(self, search_id: str, name: str) -> dict[str, Any] | None:
        """검색 기록을 저장된 검색으로 승격"""
        if not self.redis_client:
            return None

        history = await self.get_search_history_item(search_id)
        if not history:
            return None

        now = datetime.now(UTC).isoformat()
        saved_id = f"saved_{uuid4()}"
        saved_data = {
            "id": saved_id,
            "name": name,
            "query": history.get("query", ""),
            "filters": history.get("filters") or {},
            "created_at": now,
            "last_used_at": now,
            "usage_count": 1,
            "search_id": search_id,
        }

        await self.redis_client.setex(
            f"saved_search:{saved_id}",
            90 * 24 * 60 * 60,
            json.dumps(saved_data, ensure_ascii=False),
        )
        await self.redis_client.lpush("saved_search:recent", saved_id)
        await self.redis_client.ltrim("saved_search:recent", 0, 99)

        history["is_saved"] = True
        await self.redis_client.setex(
            f"search_history:{search_id}",
            30 * 24 * 60 * 60,
            json.dumps(history, ensure_ascii=False),
        )
        return saved_data

    async def delete_search_history(self, history_id: str) -> None:
        """검색 기록 삭제 및 최근 목록 정리"""
        if not self.redis_client:
            return
        await self.redis_client.delete(f"search_history:{history_id}")
        lrem = getattr(self.redis_client, "lrem", None)
        if lrem:
            await lrem("search_history:recent", 0, history_id)
