"""
키워드 검색 API 테스트
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from backend.app.main import app
from backend.services.keyword_service import KeywordService


class TestKeywordSearch:
    """키워드 검색 API 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.client = TestClient(app)
        self.keyword_service = KeywordService()
    
    @patch('backend.services.keyword_service.KeywordService.search_keywords')
    async def test_search_keywords_basic(self, mock_search):
        """기본 키워드 검색 테스트"""
        # Mock 설정
        mock_search.return_value = {
            "keywords": ["개발", "프로젝트"],
            "total_hits": 5,
            "total_documents": 3,
            "results": [
                {
                    "task_id": "test_task_1",
                    "task_type": "minutes",
                    "title": "테스트 회의록",
                    "positions": [100, 200],
                    "context_before": ["회의에서"],
                    "context_after": ["논의되었습니다"],
                    "created_at": "2026-06-12T10:00:00Z",
                    "speakers": ["user1"],
                    "duration": 1800.0,
                    "relevance_score": 0.8,
                    "frequency": 2,
                    "has_highlights": False
                }
            ],
            "page": 1,
            "page_size": 20,
            "total_pages": 1,
            "search_time_ms": 150.5,
            "keyword_stats": {
                "개발": {"total_hits": 3, "total_documents": 2, "avg_relevance": 0.7},
                "프로젝트": {"total_hits": 2, "total_documents": 1, "avg_relevance": 0.9}
            }
        }
        
        # 테스트 요청
        response = self.client.get("/api/v1/keywords/search?q=개발")
        
        # 응답 검증
        assert response.status_code == 200
        data = response.json()
        assert data["keywords"] == ["개발"]
        assert data["total_hits"] == 5
        assert data["total_documents"] == 3
        assert len(data["results"]) == 1
        assert data["results"][0]["task_id"] == "test_task_1"
    
    @patch('backend.services.keyword_service.KeywordService.search_keywords')
    async def test_search_keywords_empty_query(self, mock_search):
        """빈 쿼리 검색 테스트 (400 에러)"""
        response = self.client.get("/api/v1/keywords/search?q=")
        assert response.status_code == 422
    
    @patch('backend.services.keyword_service.KeywordService.suggest_keywords')
    async def test_suggest_keywords_basic(self, mock_suggest):
        """키워드 추천 테스트"""
        # Mock 설정
        mock_suggest.return_value = {
            "original_context": "회의에서 프로젝트 진행 상황에 대해 논의",
            "suggestions": [
                {
                    "keyword": "프로젝트",
                    "score": 0.9,
                    "frequency": 15,
                    "context_examples": ["회의에서 프로젝트 진행 상황", "프로젝트 계획 수립"],
                    "synonyms": ["계획", "기획"],
                    "related_keywords": ["개발", "팀", "일정"]
                }
            ],
            "recommendation_type": "frequency",
            "context_keywords": ["회의", "프로젝트", "진행"],
            "total_suggestions": 1,
            "search_time_ms": 45.2
        }
        
        # 테스트 요청
        response = self.client.get("/api/v1/keywords/suggest?context=회의에서 프로젝트")
        
        # 응답 검증
        assert response.status_code == 200
        data = response.json()
        assert data["original_context"] == "회의에서 프로젝트 진행 상황에 대해 논의"
        assert len(data["suggestions"]) == 1
        assert data["suggestions"][0]["keyword"] == "프로젝트"
        assert data["suggestions"][0]["score"] == 0.9
    
    @patch('backend.services.keyword_service.KeywordService.suggest_keywords')
    async def test_suggest_keywords_short_context(self, mock_suggest):
        """짧은 문맥 테스트 (400 에러)"""
        response = self.client.get("/api/v1/keywords/suggest?context=가")
        assert response.status_code == 422
    
    @patch('backend.services.keyword_service.KeywordService.get_keyword_stats')
    async def test_get_keyword_stats_basic(self, mock_stats):
        """키워드 통계 테스트"""
        # Mock 설정
        mock_stats.return_value = {
            "period_start": "2026-06-01T00:00:00Z",
            "period_end": "2026-06-12T00:00:00Z",
            "top_keywords": [
                {
                    "keyword": "프로젝트",
                    "frequency": 25,
                    "documents": 8,
                    "trend": 0.1
                },
                {
                    "keyword": "개발",
                    "frequency": 20,
                    "documents": 6,
                    "trend": -0.05
                }
            ],
            "total_keywords": 50,
            "total_occurrences": 150,
            "avg_keywords_per_document": 5.2,
            "trends": {},
            "category_stats": {}
        }
        
        # 테스트 요청
        response = self.client.get("/api/v1/keywords/stats?period=30d&top_n=5")
        
        # 응답 검증
        assert response.status_code == 200
        data = response.json()
        assert data["period_start"] == "2026-06-01T00:00:00Z"
        assert len(data["top_keywords"]) == 2
        assert data["top_keywords"][0]["keyword"] == "프로젝트"
        assert data["top_keywords"][0]["frequency"] == 25
        assert data["total_keywords"] == 50
        assert data["total_occurrences"] == 150