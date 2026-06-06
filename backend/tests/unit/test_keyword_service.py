"""
자동 키워드 추출 서비스 테스트.
"""

import json
from unittest.mock import AsyncMock

import pytest

from backend.services.keyword_service import KeywordService


class TestKeywordService:
    def test_extracts_mixed_korean_english_keywords(self):
        text = """
        프로젝트 일정 검토 회의에서 FastAPI 마이그레이션과 Redis 캐시 전략을 논의했습니다.
        FastAPI API 성능 개선, Redis 캐시 TTL 조정, 프로젝트 일정 리스크를 다시 확인했습니다.
        다음 회의에서는 API 성능 지표와 프로젝트 일정 변경안을 검토합니다.
        """

        response = KeywordService().extract_from_text(text, max_keywords=12, min_score=0.0)

        assert response.status == "completed"
        assert response.language == "mixed"
        assert response.total_count > 0
        assert response.groups
        assert all(0.0 <= item.score <= 1.0 for item in response.keywords)
        assert all(0.0 <= item.tfidf_score <= 1.0 for item in response.keywords)
        assert all(0.0 <= item.textrank_score <= 1.0 for item in response.keywords)

        keywords = {item.keyword for item in response.keywords}
        assert any("fastapi" in keyword for keyword in keywords)
        assert any("redis" in keyword for keyword in keywords)
        assert any("프로젝트" in keyword for keyword in keywords)

    def test_korean_particles_are_normalized_into_same_keyword(self):
        text = """
        일정은 중요합니다. 일정을 다시 검토합니다. 일정이 변경되면 공유합니다.
        프로젝트 일정 리스크와 일정 조정 방안을 논의합니다.
        """

        response = KeywordService().extract_from_text(text, max_keywords=8, min_score=0.0)

        schedule = next(item for item in response.keywords if item.keyword == "일정")
        assert schedule.frequency >= 4

    def test_groups_related_unigrams_and_phrases(self):
        text = """
        API gateway 설계를 검토했습니다. API gateway 배포 일정도 확인했습니다.
        API 성능과 gateway 장애 대응 계획을 다시 논의했습니다.
        """

        response = KeywordService().extract_from_text(text, max_keywords=10, min_score=0.0)

        grouped = [
            group
            for group in response.groups
            if "api" in group.keywords and any("api gateway" in kw for kw in group.keywords)
        ]
        assert grouped

    def test_history_recommendation_marks_sources(self):
        current_text = """
        이번 회의에서는 API 배포 일정과 프로젝트 리스크를 확인했습니다.
        다음 단계로 API 성능 지표를 공유합니다.
        """
        history_texts = [
            """
            지난 회의에서는 API 배포 전략, Redis 캐시 전략, 프로젝트 리스크를 논의했습니다.
            API 성능 지표와 Redis TTL 조정이 반복 이슈였습니다.
            """,
            """
            이전 회의에서 FastAPI 마이그레이션과 API gateway 안정화 계획을 정리했습니다.
            """,
        ]

        response = KeywordService().recommend_from_history(
            current_text,
            history_texts=history_texts,
            task_id="meeting-001",
            max_keywords=12,
            min_score=0.0,
        )

        assert response.source == "history_recommendation"
        assert response.task_id == "meeting-001"
        assert response.history_task_count == 2
        assert response.total_count > 0
        assert any(item.source == "current+history" for item in response.keywords)

    def test_short_text_rejected(self):
        with pytest.raises(Exception):
            KeywordService().extract_from_text("짧음")

    @pytest.mark.asyncio
    async def test_extract_for_task_returns_cached_keywords_without_db_lookup(self):
        service = KeywordService()
        cached = service.extract_from_text(
            "프로젝트 일정과 FastAPI API 성능 개선을 반복해서 논의했습니다.",
            max_keywords=5,
            min_score=0.0,
            source="meeting",
            task_id="cached-task",
        )
        redis_client = AsyncMock()
        redis_client.get.return_value = json.dumps(
            cached.model_dump(mode="json"), ensure_ascii=False
        )
        db = AsyncMock()

        response = await service.extract_for_task(redis_client, db, "cached-task")

        assert response.task_id == "cached-task"
        assert response.source == "meeting"
        assert response.total_count == cached.total_count
        db.execute.assert_not_called()
