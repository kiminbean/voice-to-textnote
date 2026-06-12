"""
키워드 검색 및 추천 API 스키마
"""

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class SortOption(str, Enum):
    """정렬 옵션"""
    relevance = "relevance"
    frequency = "frequency"
    newest = "newest"
    oldest = "oldest"


class KeywordSearchFilter(BaseModel):
    """키워드 검색 필터"""
    
    # 날짜 필터
    date_from: Optional[datetime] = Field(None, description="시작 날짜")
    date_to: Optional[datetime] = Field(None, description="종료 날짜")
    
    # 문서 유형 필터
    task_types: Optional[List[str]] = Field(
        default=None,
        description="검색할 문서 유형 목록 (예: ['minutes', 'summary'])"
    )
    
    # 화자 필터
    speakers: Optional[List[str]] = Field(
        default=None,
        description="특정 화자의 키워드만 검색"
    )
    
    # 키워드 속성 필터
    has_action_items: Optional[bool] = Field(
        None,
        description="액션 아이템이 포함된 문서만 검색"
    )
    has_decisions: Optional[bool] = Field(
        None,
        description="의사결정이 포함된 문서만 검색"
    )
    has_issues: Optional[bool] = Field(
        None,
        description="이슈/문제점이 포함된 문서만 검색"
    )
    
    # 키워드 유형 필터
    exact_match: Optional[bool] = Field(
        default=False,
        description="정확한 일치만 검색"
    )
    include_variations: Optional[bool] = Field(
        default=True,
        description="변형어 포함 (예: '개발' -> '개발자', '개발하기')"
    )


class KeywordHit(BaseModel):
    """키워드 검색 결과 한 건"""
    
    task_id: str = Field(..., description="작업 ID")
    task_type: str = Field(..., description="작업 유형")
    title: str = Field(..., description="문서 제목")
    
    # 키워드 위치 정보
    positions: List[int] = Field(..., description="키워드 시작 위치 인덱스 목록")
    context_before: List[str] = Field(..., description="키워드 앞 문맥")
    context_after: List[str] = Field(..., description="키워드 뒷 문맥")
    
    # 문서 정보
    created_at: datetime = Field(..., description="작성 시간")
    speakers: List[str] = Field(default_factory=list, description="화자 목록")
    duration: Optional[float] = Field(None, description="오디오 길이 (초)")
    
    # 메타 정보
    relevance_score: float = Field(..., description="관련도 점수 (0.0-1.0)")
    frequency: int = Field(..., description="문서 내 출현 횟수")
    has_highlights: bool = Field(default=False, description="하이라이트 포함 여부")


class KeywordSearchResponse(BaseModel):
    """키워드 검색 응답"""
    
    keywords: List[str] = Field(..., description="검색된 키워드 목록")
    total_hits: int = Field(..., description="전체 검색 결과 수")
    total_documents: int = Field(..., description="검색된 문서 수")
    
    # 검색 결과
    results: List[KeywordHit] = Field(..., description="검색 결과 목록")
    
    # 페이지 정보
    page: int = Field(..., description="현재 페이지")
    page_size: int = Field(..., description="페이지당 항목 수")
    total_pages: int = Field(..., description="전체 페이지 수")
    
    # 검색 시간
    search_time_ms: float = Field(..., description="검색 소요 시간 (ms)")
    
    # 통계 정보
    keyword_stats: dict[str, Any] = Field(default_factory=dict, description="키워드별 통계")


class KeywordSuggestion(BaseModel):
    """추천 키워드 한 건"""
    
    keyword: str = Field(..., description="추천 키워드")
    score: float = Field(..., description="추천 점수 (0.0-1.0)")
    frequency: int = Field(..., description="전체 빈도")
    context_examples: List[str] = Field(default_factory=list, description="문맥 예시")
    synonyms: List[str] = Field(default_factory=list, description="동의어 목록")
    related_keywords: List[str] = Field(default_factory=list, description="관련 키워드")


class KeywordSuggestResponse(BaseModel):
    """키워드 추천 응답"""
    
    original_context: str = Field(..., description="원본 문맥")
    suggestions: List[KeywordSuggestion] = Field(..., description="추천 키워드 목록")
    
    # 추천 기준
    recommendation_type: str = Field(..., description="추천 유형 (frequency, context, similarity)")
    context_keywords: List[str] = Field(default_factory=list, description="문맥에서 추출된 키워드")
    
    # 통계
    total_suggestions: int = Field(..., description="총 추천 개수")
    search_time_ms: float = Field(..., description="추천 생성 시간 (ms)")


class KeywordFrequency(BaseModel):
    """키워드 빈도 정보"""
    
    keyword: str = Field(..., description="키워드")
    frequency: int = Field(..., description="출현 횟수")
    documents: int = Field(..., description="포함된 문서 수")
    trend: Optional[float] = Field(None, description="트렌드 (변화율)")


class KeywordStatsResponse(BaseModel):
    """키워드 통계 응답"""
    
    # 기간 정보
    period_start: datetime = Field(..., description="통계 시작 시간")
    period_end: datetime = Field(..., description="통계 종료 시간")
    
    # 상위 키워드
    top_keywords: List[KeywordFrequency] = Field(..., description="상위 키워드 목록")
    
    # 전체 통계
    total_keywords: int = Field(..., description="전체 고유 키워드 수")
    total_occurrences: int = Field(..., description="전체 키워드 발생 횟수")
    avg_keywords_per_document: float = Field(..., description="문서당 평균 키워드 수")
    
    # 트렌드 데이터 (선택적)
    trends: Optional[dict[str, List[Any]]] = Field(None, description="키워드 트렌드 데이터")
    
    # 카테고리별 통계
    category_stats: Optional[dict[str, Any]] = Field(None, description="카테고리별 통계")