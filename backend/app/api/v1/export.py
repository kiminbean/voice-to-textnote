"""
SPEC-EXPORT-001: 회의록 PDF 내보내기 API

엔드포인트:
- GET /api/v1/export/pdf/{minutes_task_id}
  회의록 데이터를 PDF로 변환하여 파일로 다운로드합니다.
  선택적으로 summary_task_id를 지정하면 요약 섹션이 포함됩니다.
"""

import io
import json
import re

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db_session, get_redis_client
from backend.db.models import TaskResult
from backend.pipeline.docx_generator import MinutesDOCXGenerator
from backend.pipeline.pdf_generator import MinutesPDFGenerator
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["export"])

# @MX:NOTE: Content-Disposition 파일명에 허용할 문자(영숫자/대시/언더스코어/하이픈)만 통과.
# Reason: minutes_task_id가 URL 경로에서 들어오므로 CRLF·따옴표 인젝션을 막아야 함.
_FILENAME_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]")


def _safe_export_filename(task_id: str, extension: str) -> str:
    """헤더 인젝션 방지용 파일명 생성기.

    영숫자, 마침표, 대시, 언더스코어만 남기고 나머지를 제거한다.
    빈 문자열이 되면 'minutes'를 기본값으로 사용.
    """
    sanitized = _FILENAME_SAFE_RE.sub("", task_id)[:64] or "minutes"
    return f"minutes_{sanitized}.{extension}"


# ---------------------------------------------------------------------------
# 헬퍼 함수
# ---------------------------------------------------------------------------


async def _get_task_result(
    redis_client: aioredis.Redis,
    db: AsyncSession,
    type_prefix: str,
    task_id: str,
) -> dict | None:
    """
    Redis 우선 조회, 미스 시 DB 폴백으로 작업 결과 반환

    Args:
        redis_client: Redis 비동기 클라이언트
        db: SQLAlchemy 비동기 세션
        type_prefix: Redis 키 타입 접두사 ('min', 'sum')
        task_id: 조회할 작업 ID

    Returns:
        결과 dict 또는 None (없으면)
    """
    # Redis 조회
    redis_key = f"task:{type_prefix}:result:{task_id}"
    raw = await redis_client.get(redis_key)
    if raw:
        logger.debug("Redis 캐시 히트", key=redis_key)
        return json.loads(raw)

    # DB 폴백 - task_type 매핑
    task_type_map = {"min": "minutes", "sum": "summary"}
    task_type = task_type_map.get(type_prefix, type_prefix)

    stmt = select(TaskResult).where(
        TaskResult.task_id == task_id,
        TaskResult.task_type == task_type,
        TaskResult.status == "completed",
    )
    result = await db.execute(stmt)
    record = result.scalars().first()

    if record and record.result_data:
        logger.debug("DB 폴백 히트", task_id=task_id, task_type=task_type)
        return record.result_data

    return None


# ---------------------------------------------------------------------------
# 엔드포인트
# ---------------------------------------------------------------------------


@router.get(
    "/export/pdf/{minutes_task_id}",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "PDF 파일 다운로드",
        },
        404: {"description": "회의록 데이터를 찾을 수 없음"},
        422: {"description": "회의록 데이터 불완전 (segments 없음)"},
    },
    summary="회의록 PDF 내보내기",
    description=(
        "회의록 데이터를 PDF로 변환하여 반환합니다. "
        "summary_task_id를 지정하면 요약 섹션이 포함됩니다."
    ),
)
async def export_pdf(
    minutes_task_id: str,
    summary_task_id: str | None = Query(
        default=None,
        description="요약 태스크 ID (지정하면 요약 섹션 포함)",
    ),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    db: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """
    REQ-EXPORT-010~015: 회의록 PDF 다운로드

    1. Redis 우선으로 회의록 결과 조회 (미스 시 DB 폴백)
    2. summary_task_id가 있으면 요약 데이터도 조회
    3. PDF 생성 후 StreamingResponse로 반환
    """
    # 1. 회의록 데이터 조회
    minutes_data = await _get_task_result(redis_client, db, "min", minutes_task_id)
    if minutes_data is None:
        logger.warning("회의록 데이터 없음", task_id=minutes_task_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"회의록 데이터를 찾을 수 없습니다. (task_id: {minutes_task_id})",
        )

    # 2. 데이터 유효성 검증 (segments 필수)
    if not minutes_data.get("segments"):
        logger.warning("회의록 데이터 불완전 - segments 없음", task_id=minutes_task_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="회의록 데이터가 불완전합니다. segments가 없습니다.",
        )

    # 3. 요약 데이터 조회 (선택)
    summary_data: dict | None = None
    if summary_task_id:
        summary_data = await _get_task_result(redis_client, db, "sum", summary_task_id)
        if summary_data is None:
            logger.warning(
                "요약 데이터 없음 - 요약 없이 PDF 생성",
                summary_task_id=summary_task_id,
            )
            # 요약은 선택이므로 없어도 계속 진행

    # 4. PDF 생성
    try:
        generator = MinutesPDFGenerator()
        pdf_bytes = generator.generate(minutes_data, summary_data)
    except ValueError as e:
        logger.error("PDF 생성 실패 - 유효하지 않은 데이터", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error("PDF 생성 중 예기치 않은 오류", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF 생성 중 오류가 발생했습니다.",
        ) from e

    # 5. StreamingResponse 반환
    filename = _safe_export_filename(minutes_task_id, "pdf")
    logger.info(
        "PDF 생성 완료",
        task_id=minutes_task_id,
        size_bytes=len(pdf_bytes),
        include_summary=summary_data is not None,
    )

    return StreamingResponse(
        content=io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get(
    "/export/docx/{minutes_task_id}",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {}
            },
            "description": "DOCX 파일 다운로드",
        },
        404: {"description": "회의록 데이터를 찾을 수 없음"},
        422: {"description": "회의록 데이터 불완전 (segments 없음)"},
    },
    summary="회의록 DOCX 내보내기",
    description=(
        "회의록 데이터를 DOCX로 변환하여 반환합니다. "
        "summary_task_id를 지정하면 요약 섹션이 포함됩니다."
    ),
)
async def export_docx(
    minutes_task_id: str,
    summary_task_id: str | None = Query(
        default=None,
        description="요약 태스크 ID (지정하면 요약 섹션 포함)",
    ),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    db: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """
    SPEC-EXPORT-002: 회의록 DOCX 다운로드

    PDF와 동일한 데이터 소스에서 DOCX 포맷으로 내보냅니다.
    """
    # 1. 회의록 데이터 조회 (PDF 엔드포인트와 동일 로직)
    minutes_data = await _get_task_result(redis_client, db, "min", minutes_task_id)
    if minutes_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"회의록 데이터를 찾을 수 없습니다. (task_id: {minutes_task_id})",
        )

    if not minutes_data.get("segments"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="회의록 데이터가 불완전합니다. segments가 없습니다.",
        )

    # 2. 요약 데이터 조회 (선택)
    summary_data: dict | None = None
    if summary_task_id:
        summary_data = await _get_task_result(redis_client, db, "sum", summary_task_id)

    # 3. DOCX 생성
    try:
        generator = MinutesDOCXGenerator()
        docx_bytes = generator.generate(minutes_data, summary_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error("DOCX 생성 중 오류", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DOCX 생성 중 오류가 발생했습니다.",
        ) from e

    # 4. 응답
    filename = _safe_export_filename(minutes_task_id, "docx")
    logger.info(
        "DOCX 생성 완료",
        task_id=minutes_task_id,
        size_bytes=len(docx_bytes),
        include_summary=summary_data is not None,
    )

    return StreamingResponse(
        content=io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
