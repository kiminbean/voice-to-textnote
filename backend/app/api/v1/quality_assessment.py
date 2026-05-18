"""
SPEC-QUALITY-001: 회의록 품질 평가 및 개선 제안 API

엔드포인트:
- GET /api/v1/quality/{task_id} - 기존 회의록 품질 평가
- POST /api/v1/quality/{task_id}/assess - 새로운 품질 평가 요청
- GET /api/v1/quality/{task_id}/improvements - 개선 제안 조회
"""

import json
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.dependencies import get_db_session, get_redis_client
from backend.db.models import Task, MeetingMinutes
from backend.schemas.quality import (
    QualityAssessmentRequest,
    QualityAssessmentResponse,
    QualityImprovementResponse,
    QualityScore,
    QualityIssue,
    ImprovementSuggestion,
)
from backend.services.quality_service import QualityService
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/quality", tags=["quality"])

# QualityService 인스턴스 (재사용)
_service = QualityService()


@router.get(
    "/{task_id}",
    response_model=QualityAssessmentResponse,
    responses={404: {"description": "회의 데이터 없음"}},
)
async def get_quality_assessment(
    task_id: str,
    include_details: bool = Query(
        default=True,
        description="세부 평가 항목 포함 여부"
    ),
    db: AsyncSession = Depends(get_db_session),
) -> QualityAssessmentResponse:
    """
    SPEC-QUALITY-001: 기존 회의록 품질 평가 조회
    
    저장된 회의록에 대해 품질 평가를 수행하고 결과를 반환합니다.
    """
    try:
        # Task 확인
        task_result = await db.execute(select(Task).where(Task.id == task_id))
        task = task_result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=404,
                detail=f"Task not found: {task_id}"
            )
        
        # MeetingMinutes 확인
        minutes_result = await db.execute(
            select(MeetingMinutes).where(MeetingMinutes.task_id == task_id)
        )
        minutes = minutes_result.scalar_one_or_none()
        
        if not minutes:
            raise HTTPException(
                status_code=404,
                detail=f"Meeting minutes not found for task: {task_id}"
            )
        
        # 품질 평가 수행
        assessment = await _service.assess_minutes(
            task_id=task_id,
            meeting_content=minutes.content,
            meeting_title=minutes.title or "",
            include_details=include_details,
            db=db
        )
        
        return assessment
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quality assessment failed for task {task_id}", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"품질 평가 중 오류가 발생했습니다: {str(e)}"
        )


@router.post(
    "/{task_id}/assess",
    response_model=QualityAssessmentResponse,
    responses={404: {"description": "회의 데이터 없음"}},
)
async def request_quality_assessment(
    task_id: str,
    payload: QualityAssessmentRequest,
    db: AsyncSession = Depends(get_db_session),
) -> QualityAssessmentResponse:
    """
    SPEC-QUALITY-002: 새로운 품질 평가 요청
    
    지정된 회의록에 대해 새로운 품질 평가를 수행합니다.
    평가 기준을 커스터마이징할 수 있습니다.
    """
    try:
        # Task 확인
        task_result = await db.execute(select(Task).where(Task.id == task_id))
        task = task_result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=404,
                detail=f"Task not found: {task_id}"
            )
        
        # MeetingMinutes 확인
        minutes_result = await db.execute(
            select(MeetingMinutes).where(MeetingMinutes.task_id == task_id)
        )
        minutes = minutes_result.scalar_one_or_none()
        
        if not minutes:
            raise HTTPException(
                status_code=404,
                detail=f"Meeting minutes not found for task: {task_id}"
            )
        
        # 커스텀 평가 기반으로 품질 평가 수행
        assessment = await _service.assess_minutes(
            task_id=task_id,
            meeting_content=minutes.content,
            meeting_title=minutes.title or "",
            custom_criteria=payload.criteria,
            assessment_focus=payload.assessment_focus,
            db=db
        )
        
        return assessment
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Custom quality assessment failed for task {task_id}", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"품질 평가 중 오류가 발생했습니다: {str(e)}"
        )


@router.get(
    "/{task_id}/improvements",
    response_model=QualityImprovementResponse,
    responses={404: {"description": "회의 데이터 없음"}},
)
async def get_improvement_suggestions(
    task_id: str,
    improvement_type: Optional[str] = Query(
        default="all",
        description="개선 제안 유형 (structure, content, clarity, completeness, all)"
    ),
    priority: Optional[str] = Query(
        default="high",
        description="우선순위 (high, medium, low)"
    ),
    db: AsyncSession = Depends(get_db_session),
) -> QualityImprovementResponse:
    """
    SPEC-QUALITY-003: 개선 제안 조회
    
    회의록 개선을 위한 구체적인 제안을 제공합니다.
    """
    try:
        # Task 확인
        task_result = await db.execute(select(Task).where(Task.id == task_id))
        task = task_result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=404,
                detail=f"Task not found: {task_id}"
            )
        
        # 개선 제안 가져오기
        improvements = await _service.get_improvement_suggestions(
            task_id=task_id,
            improvement_type=improvement_type,
            priority=priority,
            db=db
        )
        
        return QualityImprovementResponse(
            task_id=task_id,
            improvements=improvements,
            suggested_actions=await _service.generate_action_plan(improvements),
            total_improvements=len(improvements)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Improvement suggestions failed for task {task_id}", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"개선 제안 생성 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """품질 평가 시스템 상태 확인"""
    return {
        "status": "healthy",
        "service": "quality_assessment",
        "version": "1.0.0"
    }