"""
키워드 검색 및 추출 서비스 - 비즈니스 로직

SPEC-KEYWORD-SEARCH-001: 고급 키워드 검색 서비스
SPEC-KEYWORD-SEARCH-002: 자동 키워드 추천 및 통계
"""

import re
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, func, text

from backend.db.models import TaskResult
from backend.schemas.keyword import (
    KeywordHit,
    KeywordSearchFilter,
    KeywordSearchResponse,
    KeywordSuggestion,
    KeywordSuggestResponse,
    KeywordStatsResponse,
    KeywordFrequency,
    SortOption
)


@dataclass
class KeywordSearchResult:
    """키워드 검색 결과 데이터"""
    task_id: str
    task_type: str
    title: str
    content: str
    created_at: datetime
    speakers: List[str]
    positions: List[int]
    frequency: int
    relevance_score: float


class KeywordService:
    """키워드 검색 및 추천 서비스"""
    
    def __init__(self):
        # 한글 및 영문 키워드 추출 패턴
        self.korean_pattern = re.compile(
            r'[가-힣ㄱ-ㅎㅏ-ㅣ]+|\b[A-Za-z]{2,}\b|\b\d{2,}\b',
            re.IGNORECASE
        )
        
        # 불용어 목록 (확장 가능)
        self.stop_words = {
            '그리고', '그러나', '또한', '때문에', '이러한', '모든', '우리', '저희',
            '것', '이', '그', '저', '수', '때', '경우', '문제', '방법', '과정',
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of',
            'that', 'this', 'with', 'have', 'has', 'are', 'is', 'was', 'were'
        }
    
    def _extract_keywords(self, text: str, include_variations: bool = True) -> List[str]:
        """텍스트에서 키워드 추출"""
        if not text:
            return []
        
        # 기본 키워드 추출
        keywords = []
        for match in self.korean_pattern.finditer(text):
            word = match.group().lower()
            if len(word) >= 2 and word not in self.stop_words:
                keywords.append(word)
        
        # 변형어 생성 (예: '개발' -> '개발자', '개발하기')
        if include_variations:
            variations = self._generate_variations(keywords)
            keywords.extend(variations)
        
        return list(set(keywords))  # 중복 제거
    
    def _generate_variations(self, keywords: List[str]) -> List[str]:
        """키워드 변형어 생성"""
        variations = []
        
        for keyword in keywords:
            # 명사화 (추가 가능)
            if not keyword.endswith('기'):
                variations.append(f"{keyword}기")
            
            # 집합형 추가
            if not keyword.endswith('들'):
                variations.append(f"{keyword}들")
            
            # 형용사/동사적 변형
            if len(keyword) >= 3:
                variations.append(f"{keyword}하는")
                variations.append(f"{keyword}된")
        
        return variations
    
    def _calculate_relevance_score(
        self, 
        keyword: str, 
        text_content: str, 
        title: str,
        frequency: int,
        is_exact_match: bool = False
    ) -> float:
        """키워드 관련도 점수 계산"""
        
        # 기본 점수
        score = 0.0
        
        # 제목에서 일치할 경우 높은 점수
        if keyword.lower() in title.lower():
            score += 0.4
        
        # 정확한 일치 추가 점수
        if is_exact_match:
            score += 0.2
        
        # 빈도 기반 점수 (로그 스케일)
        score += min(0.3, math.log(frequency + 1) / 5)
        
        # 텍스트 길이 대비 비율
        text_length = len(text_content)
        if text_length > 0:
            frequency_ratio = frequency / text_length
            score += min(0.1, frequency_ratio * 1000)
        
        return min(1.0, score)
    
    async def search_keywords(
        self,
        session: AsyncSession,
        keywords: List[str],
        filter: KeywordSearchFilter,
        page: int,
        page_size: int,
        sort: SortOption
    ) -> KeywordSearchResponse:
        """키워드 검색 메인 메서드"""
        
        # 검색 시작 시간
        start_time = datetime.utcnow()
        
        # 기본 쿼리
        query = session.query(TaskResult)
        
        # 날짜 필터 적용
        if filter.date_from and filter.date_to:
            query = query.filter(
                and_(
                    TaskResult.created_at >= filter.date_from,
                    TaskResult.created_at <= filter.date_to
                )
            )
        elif filter.date_from:
            query = query.filter(TaskResult.created_at >= filter.date_from)
        elif filter.date_to:
            query = query.filter(TaskResult.created_at <= filter.date_to)
        
        # 작업 유형 필터 적용
        if filter.task_types:
            query = query.filter(TaskResult.task_type.in_(filter.task_types))
        
        # 결과 조회
        task_results = await session.execute(query.order_by(TaskResult.created_at.desc()))
        task_results = task_results.scalars().all()
        
        # 검색 및 결과 처리
        search_results = []
        total_hits = 0
        
        for result in task_results:
            result_data = result.result_data or {}
            content = self._extract_text_from_result(result_data)
            
            if not content:
                continue
            
            # 현재 결과에서 키워드 검색
            result_hits = self._search_in_text(
                keywords=keywords,
                text=content,
                result=result,
                filter=filter
            )
            
            if result_hits:
                search_results.extend(result_hits)
                total_hits += len(result_hits)
        
        # 정렬
        search_results = self._sort_search_results(search_results, sort)
        
        # 페이지네이션
        total_pages = (total_hits + page_size - 1) // page_size
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_results = search_results[start_idx:end_idx]
        
        # 키워드 통계 계산
        keyword_stats = self._calculate_keyword_stats(search_results, keywords)
        
        # 응답 생성
        search_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return KeywordSearchResponse(
            keywords=keywords,
            total_hits=total_hits,
            total_documents=len(set(r.task_id for r in paginated_results)),
            results=paginated_results,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            search_time_ms=search_time_ms,
            keyword_stats=keyword_stats
        )
    
    def _extract_text_from_result(self, result_data: Dict[str, Any]) -> str:
        """결과 데이터에서 텍스트 추출"""
        text_parts = []
        
        # minutes content
        if 'minutes' in result_data:
            minutes = result_data['minutes']
            if isinstance(minutes, dict):
                text_parts.append(minutes.get('content', ''))
                text_parts.append(minutes.get('summary', ''))
            elif isinstance(minutes, str):
                text_parts.append(minutes)
        
        # summary content
        if 'summary' in result_data:
            summary = result_data['summary']
            if isinstance(summary, str):
                text_parts.append(summary)
            elif isinstance(summary, dict):
                text_parts.append(summary.get('content', ''))
                text_parts.append(summary.get('summary', ''))
        
        # transcription content
        if 'transcription' in result_data:
            transcription = result_data['transcription']
            if isinstance(transcription, dict):
                segments = transcription.get('segments', [])
                for segment in segments:
                    if 'text' in segment:
                        text_parts.append(segment['text'])
        
        # keywords/tags
        if 'keywords' in result_data:
            keywords = result_data['keywords']
            if isinstance(keywords, list):
                text_parts.extend(str(kw) for kw in keywords)
        
        return ' '.join(text_parts)
    
    def _search_in_text(
        self,
        keywords: List[str],
        text: str,
        result,
        filter: KeywordSearchFilter
    ) -> List[KeywordHit]:
        """텍스트 내에서 키워드 검색"""
        hits = []
        
        # 키워드별 위치 찾기
        for keyword in keywords:
            keyword_positions = []
            
            # 정확한 일치 검색
            start_pos = 0
            while True:
                pos = text.lower().find(keyword.lower(), start_pos)
                if pos == -1:
                    break
                
                keyword_positions.append(pos)
                start_pos = pos + 1
            
            if not keyword_positions:
                continue
            
            # 컨텍스트 추출
            contexts = []
            for pos in keyword_positions[:5]:  # 최대 5개 컨텍스트
                start = max(0, pos - 100)
                end = min(len(text), pos + len(keyword) + 100)
                context = text[start:end]
                
                # 키워드 강조
                highlighted = context.replace(
                    keyword, 
                    f"**{keyword}**", 
                    1
                )
                contexts.append({
                    'full_text': context,
                    'highlighted': highlighted,
                    'position': pos
                })
            
            # 관련도 점수 계산
            relevance_score = self._calculate_relevance_score(
                keyword=keyword,
                text_content=text,
                title=result.task_id,
                frequency=len(keyword_positions),
                is_exact_match=filter.exact_match
            )
            
            hit = KeywordHit(
                task_id=result.task_id,
                task_type=result.task_type,
                title=result.task_id,
                positions=keyword_positions,
                context_before=[c['full_text'] for c in contexts],
                context_after=[c['full_text'] for c in contexts],
                created_at=result.created_at,
                speakers=[],  # TODO: 화자 정보 추출
                duration=None,
                relevance_score=relevance_score,
                frequency=len(keyword_positions),
                has_highlights=False
            )
            hits.append(hit)
        
        return hits
    
    def _sort_search_results(self, results: List[KeywordHit], sort: SortOption) -> List[KeywordHit]:
        """검색 결과 정렬"""
        if sort == SortOption.relevance:
            return sorted(results, key=lambda x: x.relevance_score, reverse=True)
        elif sort == SortOption.frequency:
            return sorted(results, key=lambda x: x.frequency, reverse=True)
        elif sort == SortOption.newest:
            return sorted(results, key=lambda x: x.created_at, reverse=True)
        elif sort == SortOption.oldest:
            return sorted(results, key=lambda x: x.created_at)
        else:
            return results
    
    def _calculate_keyword_stats(
        self, 
        results: List[KeywordHit], 
        keywords: List[str]
    ) -> Dict[str, Any]:
        """키워드 통계 계산"""
        stats = {}
        
        for keyword in keywords:
            keyword_results = [r for r in results if keyword in r.title.lower() or any(keyword.lower() in pos.lower() for pos in r.positions)]
            
            stats[keyword] = {
                'total_hits': len(keyword_results),
                'total_documents': len(set(r.task_id for r in keyword_results)),
                'avg_relevance': sum(r.relevance_score for r in keyword_results) / len(keyword_results) if keyword_results else 0,
                'avg_frequency': sum(r.frequency for r in keyword_results) / len(keyword_results) if keyword_results else 0
            }
        
        return stats
    
    async def suggest_keywords(
        self,
        session: AsyncSession,
        context: str,
        limit: int,
        include_synonyms: bool
    ) -> KeywordSuggestResponse:
        """키워드 추천 생성"""
        
        start_time = datetime.utcnow()
        
        # 문맥에서 키워드 추출
        context_keywords = self._extract_keywords(context)
        
        # DB에서 관련 키워드 조회 (임시 구현)
        # 실제로는 미리 인덱싱된 키워드 데이터를 조회해야 함
        frequency_data = await self._get_keyword_frequency(session)
        
        # 추천 점수 계산
        suggestions = []
        for keyword, freq in frequency_data.items():
            if keyword in context_keywords:
                continue  # 이미 문맥에 있는 키워드
                
            # 점수 계산: 빈도 + 문맥 유사도
            score = min(1.0, freq['frequency'] / 100)  # 정규화
            
            if include_synonyms:
                # 동의어 추가 (임시)
                synonyms = self._find_synonyms(keyword)
            else:
                synonyms = []
            
            suggestion = KeywordSuggestion(
                keyword=keyword,
                score=score,
                frequency=freq['frequency'],
                context_examples=[],  # TODO: 문맥 예시 추출
                synonyms=synonyms,
                related_keywords=self._find_related_keywords(keyword)
            )
            suggestions.append(suggestion)
        
        # 점수순 정렬 및 개수 제한
        suggestions = sorted(suggestions, key=lambda x: x.score, reverse=True)[:limit]
        
        search_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return KeywordSuggestResponse(
            original_context=context,
            suggestions=suggestions,
            recommendation_type="frequency",
            context_keywords=context_keywords,
            total_suggestions=len(suggestions),
            search_time_ms=search_time_ms
        )
    
    async def get_keyword_stats(
        self,
        session: AsyncSession,
        start_date: datetime,
        end_date: datetime,
        top_n: int,
        include_trends: bool
    ) -> KeywordStatsResponse:
        """키워드 통계 조회"""
        
        # 키워드 빈도 데이터 조회
        frequency_data = await self._get_keyword_frequency(
            session, 
            start_date=start_date, 
            end_date=end_date
        )
        
        # 상위 N개 키워드 선택
        sorted_keywords = sorted(
            frequency_data.items(),
            key=lambda x: x[1]['frequency'],
            reverse=True
        )[:top_n]
        
        top_keywords = [
            KeywordFrequency(
                keyword=k,
                frequency=v['frequency'],
                documents=v['documents'],
                trend=v.get('trend')
            )
            for k, v in sorted_keywords
        ]
        
        # 전체 통계 계산
        total_keywords = len(frequency_data)
        total_occurrences = sum(v['frequency'] for v in frequency_data.values())
        avg_keywords_per_document = total_occurrences / 100 if total_occurrences > 0 else 0  # TODO: 실제 문서 수로 계산
        
        return KeywordStatsResponse(
            period_start=start_date,
            period_end=end_date,
            top_keywords=top_keywords,
            total_keywords=total_keywords,
            total_occurrences=total_occurrences,
            avg_keywords_per_document=avg_keywords_per_document,
            trends={},  # TODO: 트렌드 데이터 추가
            category_stats={}  # TODO: 카테고리별 통계 추가
        )
    
    async def _get_keyword_frequency(
        self,
        session: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """키워드 빈도 데이터 조회 (임시 구현)"""
        # 실제 구현에서는 DB FTS5 쿼리 또는 사전 인덱스된 데이터 사용
        
        frequency_data = {}
        
        # 최근 데이터 샘플링
        query = session.query(TaskResult)
        if start_date and end_date:
            query = query.filter(
                and_(
                    TaskResult.created_at >= start_date,
                    TaskResult.created_at <= end_date
                )
            )
        
        results = await session.execute(query.limit(100))
        results = results.scalars().all()
        
        # 키워드 추출 및 빈도 계산
        keyword_counter = Counter()
        document_keywords = defaultdict(set)
        
        for result in results:
            content = self._extract_text_from_result(result.result_data or {})
            keywords = self._extract_keywords(content)
            
            for keyword in keywords:
                keyword_counter[keyword] += 1
                document_keywords[keyword].add(result.task_id)
        
        # 데이터 변환
        for keyword, count in keyword_counter.items():
            frequency_data[keyword] = {
                'frequency': count,
                'documents': len(document_keywords[keyword]),
                'trend': None  # TODO: 트렌드 계산
            }
        
        return frequency_data
    
    def _find_synonyms(self, keyword: str) -> List[str]:
        """동의어 검색 (임시 구현)"""
        # 실제 구현에서는 동의어 사전 또는 NLP 모델 사용
        synonym_map = {
            '개발': ['프로그래밍', '코딩', '구현'],
            '설계': ['기획', '플래닝', '아키텍처'],
            '테스트': ['검증', '확인', '검사'],
            '의사결정': ['결정', '선택', '판단']
        }
        
        return synonym_map.get(keyword, [])
    
    def _find_related_keywords(self, keyword: str) -> List[str]:
        """관련 키워드 검색 (임시 구현)"""
        # 실제 구현에서는 키워드 네트워크 또는 임베딩 사용
        related_map = {
            '개발': ['프로그래밍', '소스코드', '버그', '기능'],
            '회의': ['발언', '논의', '결정', '액션아이템'],
            '프로젝트': ['일정', '기간', '예산', '팀원']
        }
        
        return related_map.get(keyword, [])