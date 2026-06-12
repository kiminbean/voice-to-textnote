"""
회의록 내보내기 API - PDF/DOCX 변환 다운로드

SPEC-EXPORT-001: 회의록 내보내기 API
- GET /export/minutes/{task_id} - 회의록 PDF/DOCX 다운로드
- POST /export/batch - 배치 내보내기 요청
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db_session
from backend.app.errors import not_found, unprocessable
from backend.db.models import TaskResult
from backend.schemas.export import ExportRequest, ExportResponse, ExportFormat
from backend.services.export_service import ExportService

router = APIRouter(tags=["export"])


def get_export_service() -> ExportService:
    """ExportService 인스턴스 제공 (FastAPI Depends)"""
    return ExportService()


@router.get("/export/minutes/{task_id}", response_model=Dict[str, Any])
async def export_meeting_minutes(
    task_id: str,
    format: ExportFormat = Query(default=ExportFormat.pdf, description="내보내기 형식"),
    include_summary: bool = Query(default=True, description="요약 포함 여부"),
    include_action_items: bool = Query(default=True, description="액션 아이템 포함 여부"),
    include_audio_analysis: bool = Query(default=False, description="오디오 분석 포함 여부"),
    db: AsyncSession = Depends(get_db_session),
    svc: ExportService = Depends(get_export_service),
) -> Dict[str, Any]:
    """
    SPEC-EXPORT-001: 단일 회의록 내보내기
    
    지정된 회의록을 PDF 또는 DOCX 형식으로 내보냅니다.
    
    - task_id: 내보낼 회의록 ID
    - format: 내보내기 형식 (pdf, docx)
    - include_summary: 요약 내용 포함 여부
    - include_action_items: 액션 아이템 포함 여부  
    - include_audio_analysis: 오디오 분석 포함 여부
    """
    # 작업 결과 조회
    result = await session.get(TaskResult, task_id)
    if not result:
        not_found(f"회의록을 찾을 수 없습니다: {task_id}")
    
    if result.status != "completed":
        unprocessable(f"회의록 처리가 완료되지 않았습니다: {task_id}")
    
    # 내보내기 파일 생성
    export_file = await svc.export_meeting(
        task_result=result,
        format=format,
        include_summary=include_summary,
        include_action_items=include_action_items,
        include_audio_analysis=include_audio_analysis
    )
    
    return FileResponse(
        path=export_file.path,
        filename=export_file.filename,
        media_type=export_file.media_type,
        headers={"Content-Disposition": f"attachment; filename={export_file.filename}"}
    )


@router.post("/export/batch", response_model=ExportResponse)
async def export_batch_meetings(
    request: ExportRequest,
    db: AsyncSession = Depends(get_db_session),
    svc: ExportService = Depends(get_export_service),
) -> ExportResponse:
    """
    SPEC-EXPORT-001: 배치 회의록 내보내기
    
    여러 회의록을 한 번에 내보내는 요청을 처리합니다.
    
    - task_ids: 내보낼 회의록 ID 목록
    - format: 내보내기 형식
    - filters: 필터 조건
    """
    # 유효성 검증
    if not request.task_ids:
        unprocessable("내보낼 회의록 ID 목록이 필요합니다.")
    
    if len(request.task_ids) > 50:
        unprocessable("최대 50개의 회의록만 내보낼 수 있습니다.")
    
    # 작업 결과 조회
    task_results = []
    for task_id in request.task_ids:
        result = await session.get(TaskResult, task_id)
        if not result:
            not_found(f"회의록을 찾을 수 없습니다: {task_id}")
        
        if result.status != "completed":
            unprocessable(f"회의록 처리가 완료되지 않았습니다: {task_id}")
        
        task_results.append(result)
    
    # 비동기 내보내기 실행
    export_files = await svc.export_batch_meetings(
        task_results=task_results,
        format=request.format,
        filters=request.filters
    )
    
    return ExportResponse(
        request_id=f"batch_export_{datetime.utcnow().timestamp()}",
        total_requested=len(request.task_ids),
        total_success=len(export_files),
        total_failed=len(request.task_ids) - len(export_files),
        export_files=export_files,
        created_at=datetime.utcnow()
    )


@router.get("/export/templates")
async def get_export_templates(
    format: ExportFormat = Query(default=ExportFormat.pdf, description="템플릿 대상 형식"),
    db: AsyncSession = Depends(get_db_session),
    svc: ExportService = Depends(get_export_service),
) -> Dict[str, Any]:
    """
    내보내기 템플릿 조회 API
    
    지원되는 내보내기 템플릿 목록을 반환합니다.
    """
    templates = await svc.get_export_templates(format=format)
    
    return {
        "format": format.value,
        "templates": templates,
        "available": True
    }