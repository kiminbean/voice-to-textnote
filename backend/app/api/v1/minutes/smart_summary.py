"""
Smart Summary Generation API 엔드포인트
다양한 모드로 회의록 스마트 요약 생성
"""

import asyncio
import uuid
from datetime import datetime
from pathlib import Path

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.dependencies import get_db_session, get_redis_client
from backend.app.exceptions import VoiceNoteError
from backend.db.models import TaskResult
from backend.schemas.smart_summary import (
    SmartSummaryResponse,
    SmartSummaryStatus,
    SummaryRequest,
    SummaryGenerationResult,
    MeetingType,
)
from backend.services.smart_summary_service import SmartSummaryService

router = APIRouter(prefix="/smart-summary", tags=["smart-summary"])


def get_smart_summary_service() -> SmartSummaryService:
    """SmartSummaryService 인스턴스 제공"""
    return SmartSummaryService()


@router.post(
    "/{minutes_task_id}",
    status_code=status.HTTP_201_CREATED,
    response_model=SmartSummaryResponse,
    responses={
        404: {"description": "회의록을 찾을 수 없습니다"},
        422: {"description": "요청 파라미터 오류"},
    },
)
async def create_smart_summary(
    minutes_task_id: str,
    request: SummaryRequest,
    db: AsyncSession = Depends(get_db_session),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    svc: SmartSummaryService = Depends(get_smart_summary_service),
) -> SmartSummaryResponse:
    """
    회의록 스마트 요약 생성
    
    - 다양한 요약 모드 지원 (executive, detailed, bullet-points 등)
    - 자동 회의 유형 감지
    - 감정 분석 포함 가능
    - 집중 영역 선택 가능
    - 대체 버전 생성 옵션
    
    ### 지원 모드
    - **executive**: 경영진 요약 (간결한 핵심 내용)
    - **detailed**: 상세 요약 (완전한 내용 포함)
    - **bullet_points**: 항목별 요약
    - **action_oriented**: 행동 중심 요약
    - **sentiment_focused**: 감정 분석 중심
    
    ### 집중 영역
    - **all**: 모든 내용
    - **decisions**: 결정 사항만
    - **action_items**: 실행 항목만
    - **sentiment**: 감정 분석만
    - **discussion**: 논의 내용만
    - **takeaways**: 핵심 요약만
    """
    
    # 1. 원본 회의록 데이터 조회
    stmt = select(TaskResult).where(
        TaskResult.task_id == minutes_task_id,
        TaskResult.task_type == "minutes",
        TaskResult.status == "completed"
    )
    result = await db.execute(stmt)
    task_record = result.scalars().first()
    
    if not task_record:
        raise VoiceNoteError(f"완료된 회의록을 찾을 수 없습니다: {minutes_task_id}")
    
    if not task_record.result_data:
        raise VoiceNoteError(f"회의록 데이터가 없습니다: {minutes_task_id}")
    
    # 2. 회의록 내용 추출
    result_data = task_record.result_data
    if "markdown" in result_data:
        content = result_data["markdown"]
    elif "text" in result_data:
        content = result_data["text"]
    else:
        # 세그먼트 결합
        segments = result_data.get("segments", [])
        content = "\n".join([seg.get("text", "") for seg in segments])
    
    if not content.strip():
        raise VoiceNoteError(f"회의록 내용이 비어있습니다: {minutes_task_id}")
    
    # 3. 요약 작업 ID 생성
    summary_task_id = str(uuid.uuid4())
    
    # 4. Redis에 작업 상태 저장
    task_status = {
        "task_id": summary_task_id,
        "status": "processing",
        "minutes_task_id": minutes_task_id,
        "summary_request": request.model_dump(),
        "content_length": len(content),
        "created_at": datetime.now().isoformat(),
        "progress": 0.0,
        "current_step": "analysis",
        "detected_meeting_type": None,
        "processing_time": 0.0
    }
    
    redis_key = f"task:summary:smart:{summary_task_id}"
    await redis_client.setex(redis_key, 86400, task_status)  # 24시간 TTL
    
    try:
        # 5. 비동기 스마트 요약 처리 시작
        summary_result = await svc.generate_smart_summary(content, request)
        
        # 6. 결과 저장
        task_status.update({
            "status": "completed",
            "result": summary_result.model_dump(),
            "detected_meeting_type": summary_result.meeting_detection.detected_type.value,
            "completed_at": datetime.now().isoformat(),
            "progress": 100.0
        })
        
        await redis_client.setex(redis_key, 86400, task_status)
        
        # 7. 응답 생성
        return SmartSummaryResponse(
            task_id=summary_task_id,
            status="completed",
            request=request,
            result=summary_result,
            detected_meeting_type=summary_result.meeting_detection.detected_type,
            created_at=task_status["created_at"],
            completed_at=task_status["completed_at"]
        )
        
    except Exception as e:
        # 오류 발생 시 상태 업데이트
        task_status.update({
            "status": "failed",
            "error_message": str(e)
        })
        await redis_client.setex(redis_key, 86400, task_status)
        
        # 재발생
        raise


@router.get("/status/{task_id}", response_model=SmartSummaryStatus)
async def get_smart_summary_status(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> SmartSummaryStatus:
    """
    스마트 요약 작업 상태 조회
    
    - 진행률 확인
    - 현재 처리 단계 조회
    - 감지된 회의 유형 확인
    - 오류 메시지 확인
    """
    
    redis_key = f"task:summary:smart:{task_id}"
    raw_status = await redis_client.get(redis_key)
    
    if raw_status is None:
        raise VoiceNoteError(f"요약 작업을 찾을 수 없습니다: {task_id}")
    
    try:
        status_data = eval(raw_status)  # JSON 문자열을 Python 딕셔너리로 변환
    except:
        raise VoiceNoteError("작업 상태 데이터 파싱 실패")
    
    return SmartSummaryStatus(
        task_id=status_data["task_id"],
        status=status_data["status"],
        progress_percent=status_data.get("progress", 0.0),
        current_step=status_data.get("current_step", ""),
        estimated_remaining_seconds=status_data.get("estimated_remaining_seconds"),
        error_message=status_data.get("error_message")
    )


@router.get("/results/{task_id}", response_model=SmartSummaryResponse)
async def get_smart_summary_result(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> SmartSummaryResponse:
    """
    스마트 요약 결과 조회
    
    - 최종 요약 결과
    - 감지된 회의 유형
    - 감정 분석 결과
    - 대체 버전 목록
    - 신뢰도 점수
    """
    
    redis_key = f"task:summary:smart:{task_id}"
    raw_status = await redis_client.get(redis_key)
    
    if raw_status is None:
        raise VoiceNoteError(f"요약 작업을 찾을 수 없습니다: {task_id}")
    
    try:
        status_data = eval(raw_status)  # JSON 문자열을 Python 딕셔너리로 변환
    except:
        raise VoiceNoteError("작업 상태 데이터 파싱 실패")
    
    if status_data["status"] != "completed":
        raise VoiceNoteError(f"요약 작업이 완료되지 않았습니다: {status_data['status']}")
    
    # SummaryRequest 객체 재구성
    request_data = status_data["summary_request"]
    summary_request = SummaryRequest.model_validate(request_data)
    
    # SummaryGenerationResult 객체 재구성
    result_data = status_data["result"]
    summary_result = SummaryGenerationResult.model_validate(result_data)
    
    return SmartSummaryResponse(
        task_id=status_data["task_id"],
        status=status_data["status"],
        request=summary_request,
        result=summary_result,
        detected_meeting_type=MeetingType(status_data["detected_meeting_type"]) if status_data.get("detected_meeting_type") else None,
        created_at=datetime.fromisoformat(status_data["created_at"]),
        completed_at=datetime.fromisoformat(status_data["completed_at"]) if status_data.get("completed_at") else None
    )


@router.get("/meeting-types")
async def get_available_meeting_types() -> dict:
    """지원하는 회의 유형 목록 조회"""
    from backend.schemas.smart_summary import MeetingType
    
    return {
        "meeting_types": [
            {
                "value": mt.value,
                "description": mt.description if hasattr(mt, 'description') else mt.value,
                "keywords": ["아이디어", "생각", "창의"]
            }
            for mt in MeetingType
        ]
    }