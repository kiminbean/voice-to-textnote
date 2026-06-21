"""Smart Summary Generation API 엔드포인트."""

import ast
import json
import uuid
from datetime import datetime
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db_session, get_redis_client
from backend.app.exceptions import VoiceNoteError
from backend.db.models import TaskResult
from backend.schemas.smart_summary import (
    MeetingType,
    SmartSummaryResponse,
    SmartSummaryStatus,
    SummaryGenerationResult,
    SummaryMode,
    SummaryRequest,
)
from backend.services.smart_summary_service import SmartSummaryService

router = APIRouter(prefix="/smart-summary", tags=["smart-summary"])


_SUMMARY_MODE_PRESETS = [
    {
        "value": SummaryMode.EXECUTIVE.value,
        "label": "경영진 요약",
        "description": "핵심 결정과 리스크를 짧게 정리합니다.",
    },
    {
        "value": SummaryMode.DETAILED.value,
        "label": "상세 요약",
        "description": "논의 맥락을 길게 보존합니다.",
    },
    {
        "value": SummaryMode.BULLET_POINTS.value,
        "label": "불릿 요약",
        "description": "긴 논의를 빠르게 훑는 항목형 요약입니다.",
    },
    {
        "value": SummaryMode.ACTION_ORIENTED.value,
        "label": "액션 중심",
        "description": "해야 할 일과 후속 조치를 우선합니다.",
    },
    {
        "value": SummaryMode.SENTIMENT_FOCUSED.value,
        "label": "감정 중심",
        "description": "회의 분위기와 감정 신호를 정리합니다.",
    },
    {
        "value": SummaryMode.LECTURE_NOTES.value,
        "label": "강의 노트",
        "description": "학습과 복습에 맞춘 노트 구조입니다.",
    },
    {
        "value": SummaryMode.SALES_FOLLOW_UP.value,
        "label": "영업 후속",
        "description": "고객 니즈와 다음 연락 액션을 정리합니다.",
    },
    {
        "value": SummaryMode.SERMON_NOTES.value,
        "label": "설교 노트",
        "description": "주제, 묵상 포인트, 적용을 분리합니다.",
    },
    {
        "value": SummaryMode.RESEARCH_INTERVIEW.value,
        "label": "리서치 인터뷰",
        "description": "관찰, 인사이트 후보, 후속 질문을 정리합니다.",
    },
    {
        "value": SummaryMode.DECISION_LOG.value,
        "label": "결정 로그",
        "description": "결정 사항만 추려 추적하기 쉽게 만듭니다.",
    },
    {
        "value": SummaryMode.ACTION_ONLY.value,
        "label": "액션만",
        "description": "실행 항목만 빠르게 추출합니다.",
    },
]


def get_smart_summary_service() -> SmartSummaryService:
    """SmartSummaryService 인스턴스 제공"""
    return SmartSummaryService()


@router.get("/modes")
async def get_available_summary_modes() -> dict[str, list[dict[str, str]]]:
    """사용자 선택 가능한 스마트 요약 모드 프리셋 목록."""
    return {"modes": _SUMMARY_MODE_PRESETS}


def _smart_summary_error(message: str, status_code: int = 400) -> VoiceNoteError:
    return VoiceNoteError(
        error_code="SMART_SUMMARY_ERROR",
        message=message,
        status_code=status_code,
    )


def _serialize_status(status_data: dict[str, Any]) -> str:
    return json.dumps(status_data, ensure_ascii=False)


def _parse_status(raw_status: bytes | str) -> dict[str, Any]:
    if isinstance(raw_status, bytes):
        raw_status = raw_status.decode("utf-8")
    try:
        parsed = json.loads(raw_status)
    except json.JSONDecodeError:
        parsed = ast.literal_eval(raw_status)
    if not isinstance(parsed, dict):
        raise ValueError("Smart summary status payload is not an object")
    return parsed


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
        TaskResult.status == "completed",
    )
    result = await db.execute(stmt)
    task_record = result.scalars().first()

    if not task_record:
        raise _smart_summary_error(
            f"완료된 회의록을 찾을 수 없습니다: {minutes_task_id}",
            status_code=404,
        )

    if not task_record.result_data:
        raise _smart_summary_error(f"회의록 데이터가 없습니다: {minutes_task_id}", status_code=422)

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
        raise _smart_summary_error(
            f"회의록 내용이 비어있습니다: {minutes_task_id}", status_code=422
        )

    # 3. 요약 작업 ID 생성
    summary_task_id = str(uuid.uuid4())

    # 4. Redis에 작업 상태 저장
    created_at = datetime.now()
    task_status: dict[str, Any] = {
        "task_id": summary_task_id,
        "status": "processing",
        "minutes_task_id": minutes_task_id,
        "summary_request": request.model_dump(mode="json"),
        "content_length": len(content),
        "created_at": created_at.isoformat(),
        "progress": 0.0,
        "current_step": "analysis",
        "detected_meeting_type": None,
        "processing_time": 0.0,
    }

    redis_key = f"task:summary:smart:{summary_task_id}"
    await redis_client.setex(redis_key, 86400, _serialize_status(task_status))  # 24시간 TTL

    try:
        # 5. 비동기 스마트 요약 처리 시작
        summary_result = await svc.generate_smart_summary(content, request)

        # 6. 결과 저장
        completed_at = datetime.now()
        task_status.update(
            {
                "status": "completed",
                "result": summary_result.model_dump(mode="json"),
                "detected_meeting_type": summary_result.meeting_detection.detected_type.value,
                "completed_at": completed_at.isoformat(),
                "progress": 100.0,
            }
        )

        await redis_client.setex(redis_key, 86400, _serialize_status(task_status))

        # 7. 응답 생성
        return SmartSummaryResponse(
            task_id=summary_task_id,
            status="completed",
            request=request,
            result=summary_result,
            detected_meeting_type=summary_result.meeting_detection.detected_type,
            created_at=created_at,
            completed_at=completed_at,
        )

    except Exception as e:
        # 오류 발생 시 상태 업데이트
        task_status.update({"status": "failed", "error_message": str(e)})
        await redis_client.setex(redis_key, 86400, _serialize_status(task_status))

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
        raise _smart_summary_error(f"요약 작업을 찾을 수 없습니다: {task_id}", status_code=404)

    try:
        status_data = _parse_status(raw_status)
    except Exception:
        raise _smart_summary_error("작업 상태 데이터 파싱 실패", status_code=422)

    return SmartSummaryStatus(
        task_id=status_data["task_id"],
        status=status_data["status"],
        progress_percent=status_data.get("progress", 0.0),
        current_step=status_data.get("current_step", ""),
        estimated_remaining_seconds=status_data.get("estimated_remaining_seconds"),
        error_message=status_data.get("error_message"),
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
        raise _smart_summary_error(f"요약 작업을 찾을 수 없습니다: {task_id}", status_code=404)

    try:
        status_data = _parse_status(raw_status)
    except Exception:
        raise _smart_summary_error("작업 상태 데이터 파싱 실패", status_code=422)

    if status_data["status"] != "completed":
        raise _smart_summary_error(
            f"요약 작업이 완료되지 않았습니다: {status_data['status']}",
            status_code=409,
        )

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
        detected_meeting_type=MeetingType(status_data["detected_meeting_type"])
        if status_data.get("detected_meeting_type")
        else None,
        created_at=datetime.fromisoformat(status_data["created_at"]),
        completed_at=datetime.fromisoformat(status_data["completed_at"])
        if status_data.get("completed_at")
        else None,
    )


@router.get("/meeting-types")
async def get_available_meeting_types() -> dict:
    """지원하는 회의 유형 목록 조회"""
    from backend.schemas.smart_summary import MeetingType

    return {
        "meeting_types": [
            {
                "value": mt.value,
                "description": mt.description if hasattr(mt, "description") else mt.value,
                "keywords": ["아이디어", "생각", "창의"],
            }
            for mt in MeetingType
        ]
    }
