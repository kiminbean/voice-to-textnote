"""
Advanced Audio Enhancement API 엔드포인트
AI 기반 오디오 향상 및 노이즈 제거
"""

import asyncio
import tempfile
import uuid
from pathlib import Path
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.dependencies import get_db_session, get_redis_client
from backend.app.errors import unprocessable
from backend.schemas.audio_enhancement import (
    AudioEnhancementRequest,
    AudioEnhancementResponse,
    AudioEnhancementStatus,
    EnhancementResult,
)
from backend.services.audio_enhancement_service import AudioEnhancementService

router = APIRouter(prefix="/enhance", tags=["audio-enhancement"])


def get_audio_enhancement_service() -> AudioEnhancementService:
    """AudioEnhancementService 인스턴스 제공"""
    return AudioEnhancementService()


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=AudioEnhancementResponse,
    responses={
        400: {"description": "잘못된 요청 파라미터"},
        422: {"description": "파일 검증 실패"},
    },
)
async def enhance_audio(
    enhancement_request: AudioEnhancementRequest,
    file: UploadFile = File(..., description="오디오 파일 (WAV, MP3, FLAC, M4A)"),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    svc: AudioEnhancementService = Depends(get_audio_enhancement_service),
) -> AudioEnhancementResponse:
    """
    AI 기반 오디오 향산 처리
    
    지원 형식: WAV, MP3, FLAC, M4A
    최대 크기: 100MB
    
    - 노이즈 제거 및 음향 향상
    - 음성 활동 검출 및 세분화
    - 품질 평가 및 점수 계산
    - 다양한 향상 옵션 지원
    """
    
    # 1. 파일 검증
    if not file.filename:
        unprocessable("파일이 제공되지 않았습니다.")
    
    filename = file.filename
    file_ext = Path(filename).suffix.lower()
    
    # 지원 형식 검증
    supported_formats = {".wav", ".mp3", ".flac", ".m4a"}
    if file_ext not in supported_formats:
        unprocessable(f"지원하지 않는 파일 형식: {file_ext}. WAV, MP3, FLAC, M4A만 허용됩니다.")
    
    # 파일 크기 검증 (100MB)
    file_size = 0
    contents = await file.read()
    file_size = len(contents)
    
    if file_size > 100 * 1024 * 1024:  # 100MB
        unprocessable(f"파일 크기 초과: {file_size} bytes. 최대 100MB까지 허용됩니다.")
    
    # 다시 읽기 위해 파일 포인터 초기화
    await file.seek(0)
    
    # 2. 임시 파일 저장
    with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as temp_file:
        temp_file.write(contents)
        temp_file_path = Path(temp_file.name)
    
    try:
        # 3. 작업 ID 생성
        task_id = str(uuid.uuid4())
        
        # 4. Redis에 작업 상태 저장
        task_status = {
            "task_id": task_id,
            "status": "processing",
            "enhancement_request": enhancement_request.model_dump(),
            "filename": filename,
            "file_size": file_size,
            "created_at": asyncio.get_event_loop().time(),
            "progress": 0.0,
            "current_step": "audio_processing"
        }
        
        redis_key = f"task:audio:enhance:{task_id}"
        await redis_client.setex(redis_key, 86400, task_status)  # 24시간 TTL
        
        # 5. 비동기 오디오 향상 처리 시작
        enhanced_result = await svc.enhance_audio(temp_file_path, enhancement_request)
        
        # 6. 결과 저장
        task_status.update({
            "status": "completed",
            "result": enhanced_result.model_dump(),
            "completed_at": asyncio.get_event_loop().time(),
            "progress": 100.0
        })
        
        await redis_client.setex(redis_key, 86400, task_status)
        
        # 7. 응답 생성
        return AudioEnhancementResponse(
            task_id=task_id,
            status="completed",
            request=enhancement_request,
            result=enhanced_result,
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
        
    finally:
        # 임시 파일 삭제
        if temp_file_path.exists():
            temp_file_path.unlink()


@router.get("/status/{task_id}", response_model=AudioEnhancementStatus)
async def get_enhancement_status(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> AudioEnhancementStatus:
    """
    오디오 향상 작업 상태 조회
    
    - 진행률 확인
    - 현재 처리 단계 조회
    - 오류 메시지 확인
    """
    
    redis_key = f"task:audio:enhance:{task_id}"
    raw_status = await redis_client.get(redis_key)
    
    if raw_status is None:
        raise ValueError(f"작업을 찾을 수 없습니다: {task_id}")
    
    try:
        status_data = eval(raw_status)  # JSON 문자열을 Python 딕셔너리로 변환
    except:
        raise ValueError("작업 상태 데이터 파싱 실패")
    
    return AudioEnhancementStatus(
        task_id=status_data["task_id"],
        status=status_data["status"],
        progress_percent=status_data.get("progress", 0.0),
        current_step=status_data.get("current_step", ""),
        estimated_remaining_seconds=status_data.get("estimated_remaining_seconds"),
        error_message=status_data.get("error_message")
    )


@router.get("/results/{task_id}", response_model=AudioEnhancementResponse)
async def get_enhancement_result(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> AudioEnhancementResponse:
    """
    오디오 향상 결과 조회
    
    - 최종 처리 결과
    - 품질 점수 정보
    - 세그먼트 정보
    - 향상된 파일 다운로드 링크
    """
    
    redis_key = f"task:audio:enhance:{task_id}"
    raw_status = await redis_client.get(redis_key)
    
    if raw_status is None:
        raise ValueError(f"작업을 찾을 수 없습니다: {task_id}")
    
    try:
        status_data = eval(raw_status)  # JSON 문자열을 Python 딕셔너리로 변환
    except:
        raise ValueError("작업 상태 데이터 파싱 실패")
    
    if status_data["status"] != "completed":
        raise ValueError(f"작업이 완료되지 않았습니다: {status_data['status']}")
    
    # EnhancementResult 객체 재구성
    result_data = status_data["result"]
    enhancement_request = AudioEnhancementRequest.model_validate(status_data["enhancement_request"])
    
    return AudioEnhancementResponse(
        task_id=status_data["task_id"],
        status=status_data["status"],
        request=enhancement_request,
        result=EnhancementResult.model_validate(result_data),
        created_at=status_data["created_at"],
        completed_at=status_data["completed_at"]
    )