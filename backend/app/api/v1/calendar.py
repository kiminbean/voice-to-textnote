"""
SPEC-CAL-001: 캘린더 통합 API

엔드포인트:
- POST /api/v1/calendar/events/{task_id}
  회의록에서 캘린더 이벤트 생성 (미팅 일정, 참가자, 액션 아이템 포함)
- GET /api/v1/calendar/events/{task_id}
  생성된 캘린더 이벤트 조회
- DELETE /api/v1/calendar/events/{task_id}
  생성된 캘린더 이벤트 삭제
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db_session, get_redis_client
from backend.db.models import TaskResult
from backend.schemas.calendar import CalendarEvent, CalendarEventCreate, CalendarEventResponse

router = APIRouter(prefix="/calendar", tags=["calendar"])

# 지원되는 캘린더 서비스
SUPPORTED_CALENDARS = {"google", "outlook", "apple"}


async def _get_meeting_data(
    redis_client: aioredis.Redis, db: AsyncSession, task_id: str
) -> Optional[Dict[str, Any]]:
    """Redis 또는 DB에서 회의 데이터 조회"""
    # Redis 우선 조회
    redis_key = f"task:min:result:{task_id}"
    raw = await redis_client.get(redis_key)
    if raw:
        return json.loads(raw)
    
    # DB 폴백
    stmt = select(TaskResult).where(
        TaskResult.task_id == task_id,
        TaskResult.task_type == "minutes",
        TaskResult.status == "completed",
    )
    result = await db.execute(stmt)
    record = result.scalars().first()
    
    if record and record.result_data:
        return record.result_data
    
    return None


def _extract_meeting_info(meeting_data: Dict[str, Any]) -> Dict[str, Any]:
    """회의록에서 미팅 정보 추출"""
    segments = meeting_data.get("segments", [])
    
    # 기본 정보
    info = {
        "title": "회의록",
        "description": "",
        "participants": set(),
        "duration_minutes": 0,
        "action_items": [],
        "key_decisions": [],
        "date": datetime.now().date(),
        "start_time": "09:00",
        "location": "온라인 미팅",
    }
    
    # 발화자를 참가자로 추가
    for segment in segments:
        speaker = segment.get("speaker", "알 수 없음")
        info["participants"].add(speaker)
        
        # 액션 아이템 추출 (간단한 키워드 기반)
        text = segment.get("text", "")
        if any(keyword in text.lower() for keyword in ["할 일", "해야 할 것", "action", "todo", "task"]):
            info["action_items"].append(f"- {text.strip()}")
    
    # 참가자 리스트로 변환
    info["participants"] = list(info["participants"])
    
    # 총 지속 시간 계산
    if segments:
        first_start = segments[0].get("start", 0)
        last_end = segments[-1].get("end", 0)
        info["duration_minutes"] = int((last_end - first_start) / 60)
    
    return info


def _generate_calendar_event(meeting_info: Dict[str, Any]) -> CalendarEvent:
    """캘린더 이벤트 생성"""
    event_date = meeting_info["date"]
    start_time = datetime.strptime(meeting_info["start_time"], "%H:%M")
    end_time = start_time + timedelta(minutes=meeting_info["duration_minutes"])
    
    # 이벤트 설명 생성
    description_parts = [meeting_info["description"]]
    
    if meeting_info["action_items"]:
        description_parts.append("\n## 📋 액션 아이템")
        description_parts.extend(meeting_info["action_items"])
    
    if meeting_info["key_decisions"]:
        description_parts.append("\n## 🎯 주요 결정 사항")
        for i, decision in enumerate(meeting_info["key_decisions"], 1):
            description_parts.append(f"{i}. {decision}")
    
    if meeting_info["participants"]:
        description_parts.append(f"\n## 👥 참가자")
        description_parts.append(", ".join(meeting_info["participants"]))
    
    event_description = "\n".join(description_parts)
    
    return CalendarEvent(
        title=meeting_info["title"],
        description=event_description,
        start_datetime=datetime.combine(event_date, start_time.time()),
        end_datetime=datetime.combine(event_date, end_time.time()),
        location=meeting_info["location"],
        participants=meeting_info["participants"],
        action_items=meeting_info["action_items"],
        duration_minutes=meeting_info["duration_minutes"],
        calendar_type="google",  # 기본값
        status="confirmed",
    )


@router.post(
    "/events/{task_id}",
    response_model=CalendarEventResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "회의록 데이터를 찾을 수 없음"},
        422: {"description": "회의록 데이터 불완전"},
    },
)
async def create_calendar_event(
    task_id: str,
    calendar_type: str = Query(default="google", regex="|".join(SUPPORTED_CALENDARS)),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    db: AsyncSession = Depends(get_db_session),
) -> CalendarEventResponse:
    """
    회의록에서 캘린더 이벤트 생성
    
    1. 회의록 데이터 조회
    2. 미팅 정보 추출 (참가자, 액션 아이템, 지속 시간 등)
    3. 캘린더 이벤트 생성
    4. 이벤트 저장 및 반환
    """
    # 캘린더 타입 검증
    if calendar_type not in SUPPORTED_CALENDARS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"지원하지 않는 캘린더 타입: {calendar_type}. 지원 타입: {SUPPORTED_CALENDARS}",
        )
    
    # 회의록 데이터 조회
    meeting_data = await _get_meeting_data(redis_client, db, task_id)
    if meeting_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"회의록 데이터를 찾을 수 없습니다. (task_id: {task_id})",
        )
    
    # 회의 정보 추출
    meeting_info = _extract_meeting_info(meeting_data)
    
    # 캘린더 이벤트 생성
    event = _generate_calendar_event(meeting_info)
    event.calendar_type = calendar_type
    
    # 이벤트 저장 (Redis)
    event_key = f"calendar:event:{task_id}"
    event_data = event.model_dump()
    await redis_client.setex(event_key, 86400 * 7, json.dumps(event_data))  # 7일 보관
    
    logger = __import__("backend.utils.logger", fromlist=["get_logger"]).get_logger(__name__)
    logger.info("캘린더 이벤트 생성 완료", task_id=task_id, calendar_type=calendar_type)
    
    return CalendarEventResponse(
        success=True,
        message="캘린더 이벤트가 생성되었습니다.",
        event=event,
    )


@router.get(
    "/events/{task_id}",
    response_model=CalendarEventResponse,
    responses={
        404: {"description": "캘린더 이벤트를 찾을 수 없음"},
    },
)
async def get_calendar_event(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> CalendarEventResponse:
    """생성된 캘린더 이벤트 조회"""
    event_key = f"calendar:event:{task_id}"
    raw = await redis_client.get(event_key)
    
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"캘린더 이벤트를 찾을 수 없습니다. (task_id: {task_id})",
        )
    
    event_data = json.loads(raw)
    event = CalendarEvent(**event_data)
    
    return CalendarEventResponse(
        success=True,
        message="캘린더 이벤트를 조회했습니다.",
        event=event,
    )


@router.delete(
    "/events/{task_id}",
    response_model=dict,
    responses={
        404: {"description": "캘린더 이벤트를 찾을 수 없음"},
    },
)
async def delete_calendar_event(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> dict:
    """생성된 캘린더 이벤트 삭제"""
    event_key = f"calendar:event:{task_id}"
    result = await redis_client.delete(event_key)
    
    if result == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"캘린더 이벤트를 찾을 수 없습니다. (task_id: {task_id})",
        )
    
    return {
        "success": True,
        "message": "캘린더 이벤트가 삭제되었습니다.",
    }