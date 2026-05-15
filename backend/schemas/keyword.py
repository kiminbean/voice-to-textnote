"""
자동 키워드 추출/추천 스키마
SPEC-KEYWORD-001: TF-IDF + TextRank 기반 회의 키워드 추천
"""

from typing import Literal

from pydantic import BaseModel, Field

LanguageCode = Literal["auto", "ko", "en", "mixed"]
KeywordSource = Literal["text", "meeting", "history_recommendation"]


class KeywordExtractRequest(BaseModel):
    """POST /api/v1/keywords/extract 요청."""

    text: str = Field(
        ...,
        min_length=10,
        max_length=1000000,
        description="키워드를 추출할 회의 텍스트. 실제 분석 길이는 KEYWORD_MAX_TEXT_CHARS 설정을 따릅니다.",
    )
    language: LanguageCode = Field(
        default="auto",
        description="언어 힌트. auto는 한/영 혼합 여부를 자동 감지합니다.",
    )
    max_keywords: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="반환할 최대 키워드 수. 미지정 시 KEYWORD_MAX_KEYWORDS 사용",
    )
    min_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="최소 중요도 점수. 미지정 시 KEYWORD_MIN_SCORE 사용",
    )


class KeywordRecommendRequest(BaseModel):
    """POST /api/v1/keywords/{task_id}/recommend 요청."""

    max_keywords: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="반환할 최대 추천 키워드 수",
    )
    min_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="최소 추천 중요도 점수",
    )
    history_limit: int | None = Field(
        default=None,
        ge=1,
        le=200,
        description="참조할 최근 회의록 개수. 미지정 시 KEYWORD_HISTORY_LIMIT 사용",
    )


class KeywordItem(BaseModel):
    """개별 키워드."""

    keyword: str = Field(..., min_length=1, description="키워드 또는 핵심 구문")
    score: float = Field(..., ge=0.0, le=1.0, description="최종 중요도 점수")
    tfidf_score: float = Field(..., ge=0.0, le=1.0, description="정규화된 TF-IDF 점수")
    textrank_score: float = Field(..., ge=0.0, le=1.0, description="정규화된 TextRank 점수")
    frequency: int = Field(..., ge=1, description="분석 대상 텍스트 내 출현 횟수")
    group_id: str | None = Field(default=None, description="연관 키워드 그룹 ID")
    source: str | None = Field(
        default=None,
        description="추천 시 키워드 출처(current/history/current+history)",
    )


class KeywordGroup(BaseModel):
    """유사 키워드 묶음."""

    group_id: str = Field(..., description="키워드 그룹 ID")
    label: str = Field(..., description="그룹 대표 키워드")
    score: float = Field(..., ge=0.0, le=1.0, description="그룹 중요도 점수")
    keywords: list[str] = Field(default_factory=list, description="그룹에 속한 키워드")


class KeywordResponse(BaseModel):
    """키워드 추출/추천 응답."""

    task_id: str | None = Field(default=None, description="회의 task_id")
    status: str = Field(default="completed", description="처리 상태")
    source: KeywordSource = Field(..., description="키워드 생성 경로")
    language: str = Field(..., description="감지 또는 요청된 언어")
    keywords: list[KeywordItem] = Field(default_factory=list)
    groups: list[KeywordGroup] = Field(default_factory=list)
    total_count: int = Field(default=0, ge=0)
    history_task_count: int | None = Field(
        default=None,
        ge=0,
        description="추천에 사용한 과거 회의록 수",
    )
    extracted_at: str = Field(..., description="추출 시각 (ISO 8601)")
