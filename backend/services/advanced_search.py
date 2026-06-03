"""
고급 검색 서비스
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import redis.asyncio as aioredis
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_redis_client
from backend.db.models import TaskResult
from backend.schemas.advanced_search import (
    AdvancedSearchRequest,
    SearchAnalytics,
    SearchFilter,
    SearchResultItem,
)


class AdvancedSearchService:
    """고급 검색 서비스"""
    
    def __init__(self):
        self.redis_client = None
        
    async def initialize(self, redis_client: aioredis.Redis):
        """Redis 클라이언트 초기화"""
        self.redis_client = redis_client
        
    async def search_advanced(
        self, 
        request: AdvancedSearchRequest, 
        db: AsyncSession
    ) -> Tuple[List[SearchResultItem], Dict[str, Any], SearchAnalytics]:
        """고급 검색 실행"""
        start_time = time.time()
        
        # 검색 쿼리 생성
        query = select(TaskResult)
        
        # 기본 조건: 검색 쿼리 매칭
        search_conditions = []
        
        # 내용 검색 (간단한 텍스트 검색 - 실제로는 FTS5를 사용해야 함)
        if request.query:
            search_conditions.append(
                or_(
                    TaskResult.content.ilike(f"%{request.query}%"),
                    TaskResult.summary.ilike(f"%{request.query}%")
                )
            )
        
        # 날짜 필터
        if request.filters.start_date:
            search_conditions.append(TaskResult.created_at >= request.filters.start_date)
            
        if request.filters.end_date:
            search_conditions.append(TaskResult.created_at <= request.filters.end_date)
        
        # 화자 필터
        if request.filters.speaker_ids:
            # TaskResult.speakers가 JSON 필드라고 가정
            # 실제로는 JSONB 쿼리를 사용해야 함
            search_conditions.append(
                TaskResult.speakers.op('?|')(request.filters.speaker_ids)
            )
        
        # 콘텐츠 유형 필터
        if request.filters.content_types:
            search_conditions.append(TaskResult.task_type.in_(request.filters.content_types))
        
        # 태그 필터
        if request.filters.tags:
            # TaskResult.tags가 JSON 필드라고 가정
            search_conditions.append(
                TaskResult.tags.op('?|')(request.filters.tags)
            )
        
        # 단어 수 필터
        if request.filters.min_word_count:
            search_conditions.append(TaskResult.word_count >= request.filters.min_word_count)
            
        if request.filters.max_word_count:
            search_conditions.append(TaskResult.word_count <= request.filters.max_word_count)
        
        # 모든 조건 결합
        if search_conditions:
            query = query.where(and_(*search_conditions))
        
        # 정렬
        if request.sort_by == "date":
            order_column = TaskResult.created_at
        elif request.sort_by == "speaker":
            order_column = TaskResult.speakers  # 실제로는 JSON 필드 정렬 필요
        elif request.sort_by == "word_count":
            order_column = TaskResult.word_count
        else:  # relevance
            order_column = TaskResult.created_at  # 기본값
        
        if request.sort_order == "desc":
            query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column.asc())
        
        # 페이징
        offset = (request.page - 1) * request.page_size
        query = query.offset(offset).limit(request.page_size)
        
        # 검색 실행
        result = await db.execute(query)
        task_results = result.scalars().all()
        
        # 결과 변환
        search_results = []
        for task in task_results:
            search_result = SearchResultItem(
                id=str(task.id),
                task_id=task.task_id,
                title=task.title or f"회의록 - {task.created_at.strftime('%Y-%m-%d %H:%M')}",
                content=self._extract_content_preview(task),
                content_type=task.task_type or "minutes",
                speaker_ids=task.speakers or [],
                word_count=task.word_count or 0,
                tags=task.tags or [],
                created_at=task.created_at,
                relevance_score=self._calculate_relevance(task, request.query),
                highlights=self._extract_highlights(task, request.query)
            )
            search_results.append(search_result)
        
        # 분석 데이터 생성
        analytics = await self._generate_analytics(db, request, search_results)
        
        # 페이지네이션 정보
        pagination = {
            "page": request.page,
            "page_size": request.page_size,
            "total_results": len(search_results),
            "has_next": len(search_results) == request.page_size
        }
        
        search_time_ms = (time.time() - start_time) * 1000
        
        # 검색 기록 저장 (Redis)
        if self.redis_client:
            await self._save_search_history(request, search_time_ms)
        
        return search_results, pagination, analytics
    
    def _extract_content_preview(self, task: TaskResult) -> str:
        """내용 미리 추출"""
        if task.summary:
            return task.summary[:200] + "..." if len(task.summary) > 200 else task.summary
        elif task.content:
            return task.content[:200] + "..." if len(task.content) > 200 else task.content
        return "내용 없음"
    
    def _calculate_relevance(self, task: TaskResult, query: str) -> float:
        """관련도 점수 계산 (간단한 구현)"""
        score = 0.5  # 기본 점수
        
        if query.lower() in (task.title or "").lower():
            score += 0.3
            
        if query.lower() in (task.summary or "").lower():
            score += 0.2
            
        if query.lower() in (task.content or "").lower():
            score += 0.1
            
        return min(score, 1.0)
    
    def _extract_highlights(self, task: TaskResult, query: str) -> List[str]:
        """하이라이트 추출 (간단한 구현)"""
        highlights = []
        
        # 제목에서 하이라이트
        if task.title and query.lower() in task.title.lower():
            highlights.append(task.title)
        
        # 요약에서 하이라이트
        if task.summary and query.lower() in task.summary.lower():
            # 쿼리를 중심으로 앞뒤 50자씩 추출
            pos = task.summary.lower().find(query.lower())
            if pos != -1:
                start = max(0, pos - 50)
                end = min(len(task.summary), pos + len(query) + 50)
                highlight = task.summary[start:end]
                highlights.append(highlight)
        
        return highlights[:3]  # 최대 3개
    
    async def _generate_analytics(
        self, 
        db: AsyncSession, 
        request: AdvancedSearchRequest,
        results: List[SearchResultItem]
    ) -> SearchAnalytics:
        """검색 분석 생성"""
        
        # 타입별 분포
        type_distribution = {}
        for result in results:
            type_distribution[result.content_type] = type_distribution.get(result.content_type, 0) + 1
        
        # 화자별 분포  
        speaker_distribution = {}
        for result in results:
            for speaker_id in result.speaker_ids:
                speaker_distribution[speaker_id] = speaker_distribution.get(speaker_id, 0) + 1
        
        # 인기 태그
        tag_counts = {}
        for result in results:
            for tag in result.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        popular_tags = [
            {"tag": tag, "count": count}
            for tag, count in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        
        # 평균 단어 수
        avg_word_count = sum(result.word_count for result in results) / len(results) if results else 0
        
        # 검색 트렌드 (간단한 구현)
        search_trends = [
            {"period": "last_week", "searches": 150},
            {"period": "last_month", "searches": 450},
            {"period": "last_year", "searches": 1200}
        ]
        
        return SearchAnalytics(
            total_results=len(results),
            search_time_ms=100.0,  # 실제로는 측정된 시간 사용
            distribution_by_type=type_distribution,
            distribution_by_speaker=speaker_distribution,
            popular_tags=popular_tags,
            average_word_count=avg_word_count,
            search_trends=search_trends
        )
    
    async def _save_search_history(
        self, 
        request: AdvancedSearchRequest, 
        search_time_ms: float
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
            "filters": request.filters.dict(),
            "result_count": 0,  # 실제 결과 수는 이후에 업데이트
            "search_time_ms": search_time_ms,
            "created_at": datetime.utcnow().isoformat(),
            "is_saved": False
        }
        
        # Redis에 저장 (TTL: 30일)
        await self.redis_client.setex(
            f"search_history:{history_id}",
            30 * 24 * 60 * 60,  # 30 days TTL
            str(history_data)
        )
        
        # 최근 검색 기록 목록에 추가 (최대 100개)
        recent_key = "search_history:recent"
        await self.redis_client.lpush(recent_key, history_id)
        await self.redis_client.ltrim(recent_key, 0, 99)  # 최대 100개 유지
    
    async def get_search_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """최근 검색 기록 조회"""
        if not self.redis_client:
            return []
            
        recent_key = "search_history:recent"
        history_ids = await self.redis_client.lrange(recent_key, 0, limit - 1)
        
        history = []
        for history_id in history_ids:
            data = await self.redis_client.get(f"search_history:{history_id}")
            if data:
                history.append(eval(data))  # 실제로는 json.loads 사용
        
        return history