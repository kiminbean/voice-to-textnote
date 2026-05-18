"""
OpenAI 클라이언트 유틸리티
"""

import os
from typing import Optional
from openai import AsyncOpenAI
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def get_openai_client() -> AsyncOpenAI:
    """
    OpenAI 클라이언트 인스턴스를 반환합니다.
    
    Returns:
        AsyncOpenAI: OpenAI 클라이언트 인스턴스
    """
    # 환경 변수에서 API 키 가져오기
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        logger.warning("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다. 품질 평가 기능이 제한됩니다.")
        # 개발 환경을 위한 기본 설정 (실제 프로덕션에서는 API 키 필수)
        return AsyncOpenAI(
            api_key="dummy-key",
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        )
    
    try:
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        )
        logger.info("OpenAI 클라이언트가 성공적으로 초기화되었습니다.")
        return client
    except Exception as e:
        logger.error(f"OpenAI 클라이언트 초기화 실패: {str(e)}")
        # 실패 시 대체 클라이언트 반환
        return AsyncOpenAI(
            api_key="dummy-key",
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        )


# 전역 클라이언트 인스턴스
_openai_client = None


def get_cached_openai_client() -> AsyncOpenAI:
    """
    캐시된 OpenAI 클라이언트 인스턴스를 반환합니다.
    
    Returns:
        AsyncOpenAI: OpenAI 클라이언트 인스턴스
    """
    global _openai_client
    if _openai_client is None:
        _openai_client = get_openai_client()
    return _openai_client