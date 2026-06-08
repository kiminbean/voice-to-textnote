"""
실시간 자막 생성 API - 회의의 접근성 향상을 위한 실시간 자막 생성 기능

SPEC-CAPTION-001: 실시간 오디오 스트림 기반 자막 생성
SPEC-CAPTION-002: 자막 형식 및 위치 지원 (WebVTT, SRT)
SPEC-CAPTION-003: 자막 생성 상태 실시간 스트리밍
"""

import asyncio
from datetime import datetime

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse

from backend.app.api.dependencies import get_current_user
from backend.db.caption_models import CaptionSegment, CaptionSession
from backend.schemas.caption import (
    CaptionCreateRequest,
    CaptionResponse,
    CaptionSessionResponse,
    CaptionStatus,
    WebVTTResponse,
)
from backend.services.caption_service import CaptionService
from backend.services.streaming_service import StreamingService
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/captions", tags=["captions"])


class CaptionSessionManager:
    """실시간 자막 세션 관리"""

    def __init__(self):
        self.active_sessions: dict[str, CaptionSession] = {}
        self.lock = asyncio.Lock()

    async def create_session(self, meeting_id: str, user_id: str) -> CaptionSession:
        """새로운 자막 생성 세션 생성"""
        async with self.lock:
            session = CaptionSession(
                session_id=f"caption_{meeting_id}_{datetime.now().timestamp()}",
                meeting_id=meeting_id,
                user_id=user_id,
                status=CaptionStatus.ACTIVE,
                created_at=datetime.now(),
                segments=[]
            )
            self.active_sessions[session.session_id] = session  # type: ignore[index]
            logger.info("새로운 자막 세션 생성", session_id=session.session_id, meeting_id=meeting_id)
            return session

    async def get_session(self, session_id: str) -> CaptionSession | None:
        """세션 조회"""
        return self.active_sessions.get(session_id)

    async def update_segment(self, session_id: str, segment: CaptionSegment) -> bool:
        """세gment 업데이트"""
        async with self.lock:
            session = self.active_sessions.get(session_id)
            if not session:
                return False

            session.segments.append(segment)
            session.updated_at = datetime.now()  # type: ignore[assignment]
            return True

    async def close_session(self, session_id: str):
        """세션 종료"""
        async with self.lock:
            if session_id in self.active_sessions:
                session = self.active_sessions[session_id]
                session.status = CaptionStatus.COMPLETED  # type: ignore[assignment]
                session.updated_at = datetime.now()  # type: ignore[assignment]
                logger.info("자막 세션 종료", session_id=session_id)
                del self.active_sessions[session_id]


# 전역 세션 관리자
session_manager = CaptionSessionManager()


@router.post("/sessions", response_model=CaptionSessionResponse)
async def create_caption_session(
    meeting_id: str = Query(..., description="회의 ID"),
    user: dict = Depends(get_current_user),
    caption_service: CaptionService = Depends(CaptionService)
):
    """새로운 자막 생성 세션 시작"""
    try:
        session = await session_manager.create_session(meeting_id, user["user_id"])

        # DB에 세션 저장
        await caption_service.save_session(session)

        return CaptionSessionResponse(
            session_id=session.session_id,
            meeting_id=session.meeting_id,
            user_id=session.user_id,
            status=session.status,
            created_at=session.created_at,
            segment_count=len(session.segments)
        )
    except Exception as e:
        logger.error("자막 세션 생성 실패", error=str(e))
        raise HTTPException(status_code=500, detail="자막 세션 생성 실패")


@router.get("/sessions/{session_id}", response_model=CaptionSessionResponse)
async def get_caption_session(
    session_id: str,
    user: dict = Depends(get_current_user),
    caption_service: CaptionService = Depends(CaptionService)
):
    """자막 세션 정보 조회"""
    session = await session_manager.get_session(session_id)
    if not session:
        # DB에서 조회
        session = await caption_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="자막 세션을 찾을 수 없습니다")

    return CaptionSessionResponse(
        session_id=session.session_id,
        meeting_id=session.meeting_id,
        user_id=session.user_id,
        status=session.status,
        created_at=session.created_at,
        segment_count=len(session.segments)
    )


@router.websocket("/stream/{session_id}")
async def websocket_caption_stream(
    websocket: WebSocket,
    session_id: str,
    user: dict = Depends(get_current_user)
):
    """WebSocket을 통한 실시간 자막 스트리밍"""
    await websocket.accept()

    try:
        session = await session_manager.get_session(session_id)
        if not session:
            await websocket.close(code=4004, reason="세션을 찾을 수 없습니다")
            return

        _streaming_service = StreamingService()  # noqa: F841

        while True:
            try:
                # 클라이언트로부터 오디오 데이터 수신 (현재는 더미 데이터)
                data = await websocket.receive_text()

                # 실제 구현에서는 오디오 데이터를 STT 엔진으로 처리
                # 여기서는 더미 응답을 보냄
                segment = CaptionSegment(
                    index=len(session.segments),
                    text=f"[더미 자막] {data}",
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    confidence=0.95,
                    speaker_id="unknown"
                )

                # 세션 업데이트
                await session_manager.update_segment(session_id, segment)

                # 클라이언트로 자막 전송
                await websocket.send_json({
                    "type": "caption_segment",
                    "data": segment.dict()
                })

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error("자막 스트리밍 오류", error=str(e))
                await websocket.close(code=4005, reason="스트리밍 오류")
                break

    except Exception as e:
        logger.error("WebSocket 연결 오류", error=str(e))
        await websocket.close(code=4003, reason="연결 오류")


@router.post("/generate", response_model=CaptionResponse)
async def generate_captions(
    request: CaptionCreateRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    caption_service: CaptionService = Depends(CaptionService)
):
    """자막 생성 (비동기)"""
    try:
        # 비동기 작업으로 자막 생성 시작
        task_id = await caption_service.create_caption_task(
            meeting_id=request.meeting_id,
            audio_url=request.audio_url,
            user_id=user["user_id"],
            language=request.language,
            format=request.format
        )

        return CaptionResponse(
            task_id=task_id,
            status=CaptionStatus.PENDING,
            message="자막 생성이 시작되었습니다"
        )
    except Exception as e:
        logger.error("자막 생성 실패", error=str(e))
        raise HTTPException(status_code=500, detail="자막 생성 실패")


@router.get("/export/{task_id}", response_model=WebVTTResponse | str)
async def export_captions(
    task_id: str,
    format: str = Query("vtt", description="출력 형식 (vtt, srt, json)"),
    user: dict = Depends(get_current_user),
    caption_service: CaptionService = Depends(CaptionService)
):
    """생성된 자막 내보내기"""
    try:
        caption_data = await caption_service.get_caption(task_id)
        if not caption_data:
            raise HTTPException(status_code=404, detail="자막을 찾을 수 없습니다")

        if format == "vtt":
            return WebVTTResponse(
                content=caption_service.generate_vtt(caption_data),
                filename=f"captions_{task_id}.vtt"
            )
        elif format == "srt":
            srt_content = caption_service.generate_srt(caption_data)
            return StreamingResponse(
                iter([srt_content]),
                media_type="text/plain",
                headers={"Content-Disposition": f"attachment; filename=captions_{task_id}.srt"}
            )
        elif format == "json":
            return caption_data
        else:
            raise HTTPException(status_code=400, detail="지원하지 않는 형식입니다")

    except Exception as e:
        logger.error("자막 내보내기 실패", error=str(e))
        raise HTTPException(status_code=500, detail="자막 내보내기 실패")


@router.get("/sessions/{session_id}/segments", response_model=list[CaptionSegment])
async def get_caption_segments(
    session_id: str,
    user: dict = Depends(get_current_user),
    caption_service: CaptionService = Depends(CaptionService)
):
    """세gment별 자막 조회"""
    session = await session_manager.get_session(session_id)
    if not session:
        # DB에서 조회
        session = await caption_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="자막 세션을 찾을 수 없습니다")

    return session.segments


@router.delete("/sessions/{session_id}")
async def delete_caption_session(
    session_id: str,
    user: dict = Depends(get_current_user),
    caption_service: CaptionService = Depends(CaptionService)
):
    """자막 세션 삭제"""
    try:
        await session_manager.close_session(session_id)
        await caption_service.delete_session(session_id)
        return {"message": "자막 세션이 삭제되었습니다"}
    except Exception as e:
        logger.error("자막 세션 삭제 실패", error=str(e))
        raise HTTPException(status_code=500, detail="자막 세션 삭제 실패")
