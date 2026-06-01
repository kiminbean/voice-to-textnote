"""
오디오 파일 스트리밍 API
Phase 2 (REQ-AUDIO-001): 인앱 오디오 재생을 위한 엔드포인트
"""

import mimetypes

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from backend.app.config import settings

router = APIRouter()


@router.get(
    "/meetings/{task_id}/audio",
    summary="회의 오디오 파일 스트리밍",
    response_class=FileResponse,
)
async def get_meeting_audio(task_id: str) -> FileResponse:
    """업로드된 오디오 파일을 스트리밍한다.

    task_id에 해당하는 원본 오디오 파일을 반환한다.
    파일이 임시 보관 기간 이후 삭제된 경우 404를 반환한다.
    """
    # task_id 기반 파일 검색 (업로드 시 {task_id}{ext} 형식으로 저장됨)
    temp_dir = settings.temp_dir
    if not temp_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="오디오 파일을 찾을 수 없습니다",
        )

    # 지원 포맷 순서대로 검색
    for ext in (".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm"):
        candidate = temp_dir / f"{task_id}{ext}"
        if candidate.exists():
            content_type, _ = mimetypes.guess_type(str(candidate))
            return FileResponse(
                path=str(candidate),
                media_type=content_type or "application/octet-stream",
                filename=candidate.name,
            )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="오디오 파일이 만료되었거나 존재하지 않습니다",
    )
