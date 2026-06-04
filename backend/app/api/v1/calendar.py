"""
SPEC-CAL-001: 캘린더 통합 API
SPEC-REFACTOR-001: 서비스 계층 분리 + 에러 헬퍼 마이그레이션

엔드포인트:
- POST /api/v1/calendar/events/{task_id}
  회의록에서 캘린더 이벤트 생성 (미팅 일정, 참가자, 액션 아이템 포함)
- GET /api/v1/calendar/events/{task_id}
  생성된 캘린더 이벤트 조회
- DELETE /api/v1/calendar/events/{task_id}
  생성된 캘린더 이벤트 삭제
"""

from fastapi import APIRouter, Depends, Query, status

from backend.app.dependencies import get_db_session, get_redis_client
from backend.app.errors import not_found, unprocessable
from backend.schemas.calendar import CalendarEvent, CalendarEventResponse
from backend.services.calendar_service import CalendarService

router = APIRouter(prefix="/calendar", tags=["calendar"])

# 지원되는 캘린더 서비스
SUPPORTED_CALENDARS = CalendarService.SUPPORTED_CALENDARS


# --- 의존성 주입 ---


def get_calendar_service() -> CalendarService:
    """CalendarService 인스턴스 제공 (FastAPI Depends)"""
    return CalendarService()


# --- 엔드포인트 ---


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
    redis_client=Depends(get_redis_client),
    db=Depends(get_db_session),
    svc: CalendarService = Depends(get_calendar_service),
) -> CalendarEventResponse:
    """
    회의록에서 캘린더 이벤트 생성

    1. 회의록 데이터 조회
    2. 미팅 정보 추출 (참가자, 액션 아이템, 지속 시간 등)
    3. 캘린더 이벤트 생성
    4. 이벤트 저장 및 반환
    """
    if calendar_type not in SUPPORTED_CALENDARS:
        unprocessable(
            f"지원하지 않는 캘린더 타입: {calendar_type}. 지원 타입: {SUPPORTED_CALENDARS}"
        )

    event = await svc.create_and_save_event(redis_client, db, task_id, calendar_type)

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
    redis_client=Depends(get_redis_client),
    svc: CalendarService = Depends(get_calendar_service),
) -> CalendarEventResponse:
    """생성된 캘린더 이벤트 조회"""
    event_data = await svc.get_event(redis_client, task_id)
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
    redis_client=Depends(get_redis_client),
    svc: CalendarService = Depends(get_calendar_service),
) -> dict:
    """생성된 캘린더 이벤트 삭제"""
    await svc.delete_event(redis_client, task_id)

    return {
        "success": True,
        "message": "캘린더 이벤트가 삭제되었습니다.",
    }
