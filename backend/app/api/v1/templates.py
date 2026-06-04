"""
회의록 양식 관리 API 엔드포인트
REQ-TMPL-001: POST /api/v1/templates - 양식 파일 업로드 (PDF/DOCX, 최대 10MB)
REQ-TMPL-003: GET /api/v1/templates - 목록 조회
REQ-TMPL-003: GET /api/v1/templates/{template_id} - 상세 조회
REQ-TMPL-003: DELETE /api/v1/templates/{template_id} - 삭제
"""

import json
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from backend.app.config import settings
from backend.app.errors import internal_server_error, not_found, unprocessable
from backend.app.dependencies import get_redis_client
from backend.pipeline.template_parser import TemplateParser
from backend.schemas.template import TemplateDetail, TemplateListItem, TemplateUploadResponse
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/templates", tags=["templates"])

# 지원 파일 형식
_SUPPORTED_FORMATS = {"docx", "pdf"}
_SUPPORTED_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/pdf",
    "application/octet-stream",  # 일부 클라이언트의 generic MIME type 허용
}
# 최대 파일 크기: 10MB
_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# Redis 메타데이터 TTL (24시간)
_TEMPLATE_REDIS_TTL = 86400


def _get_file_extension(filename: str) -> str:
    """파일 확장자 반환 (소문자)"""
    return Path(filename).suffix.lstrip(".").lower()


def _validate_file(filename: str, file_size: int) -> tuple[bool, str]:
    """
    파일 형식 및 크기 검증.

    Returns:
        (is_valid, error_message)
    """
    ext = _get_file_extension(filename)
    if ext not in _SUPPORTED_FORMATS:
        return False, f"지원하지 않는 파일 형식: .{ext}. PDF 또는 DOCX만 허용됩니다."
    if file_size > _MAX_FILE_SIZE_BYTES:
        return False, f"파일 크기 초과: {file_size} bytes. 최대 10MB까지 허용됩니다."
    return True, ""


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=TemplateUploadResponse,
    responses={
        422: {"description": "파일 검증 실패 (형식 불일치 또는 크기 초과)"},
    },
)
async def upload_template(
    file: UploadFile = File(..., description="회의록 양식 파일 (PDF 또는 DOCX, 최대 10MB)"),
    name: str | None = Form(default=None, description="양식 이름 (없으면 파일명 사용)"),
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> TemplateUploadResponse:
    """
    회의록 양식 파일 업로드 및 구조 파싱
    POST /api/v1/templates
    """
    filename = file.filename or "unknown"

    # --- 파일 내용 읽기 ---
    raw_content = await file.read()
    file_size = len(raw_content)

    # --- 파일 검증 (형식 + 크기) ---
    is_valid, error_msg = _validate_file(filename, file_size)
    if not is_valid:
        unprocessable(error_msg)

    # --- 이름 결정 (없으면 파일명 사용) ---
    template_name = name or Path(filename).stem

    # --- 파일 저장 ---
    template_id = str(uuid.uuid4())
    file_ext = _get_file_extension(filename)
    template_dir = settings.templates_dir / template_id
    template_dir.mkdir(parents=True, exist_ok=True)
    saved_file_path = template_dir / f"original.{file_ext}"

    saved_file_path.write_bytes(raw_content)
    logger.info(
        "양식 파일 저장 완료",
        template_id=template_id,
        file_path=str(saved_file_path),
        file_size=file_size,
    )

    # --- 구조 파싱 ---
    parser = TemplateParser()
    structure = parser.extract_structure(saved_file_path, file_ext)

    # 구조도 파일로 저장
    structure_path = template_dir / "structure.json"
    structure_path.write_text(json.dumps(structure, ensure_ascii=False))

    # --- Redis 메타데이터 저장 ---
    now = datetime.now(UTC).isoformat()
    metadata = {
        "template_id": template_id,
        "name": template_name,
        "format": file_ext,
        "created_at": now,
        "structure": structure,
    }
    redis_key = f"template:{template_id}"
    await redis_client.setex(redis_key, _TEMPLATE_REDIS_TTL, json.dumps(metadata))

    logger.info(
        "양식 업로드 완료",
        template_id=template_id,
        name=template_name,
        format=file_ext,
    )

    return TemplateUploadResponse(
        template_id=template_id,
        name=template_name,
        format=file_ext,
        structure=structure,
        created_at=now,
    )


@router.get(
    "",
    response_model=list[TemplateListItem],
)
async def list_templates(
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> list[TemplateListItem]:
    """
    저장된 양식 목록 조회
    GET /api/v1/templates
    """
    # Redis에서 template:* 키 조회
    keys = await redis_client.keys("template:*")
    items: list[TemplateListItem] = []

    for key in keys:
        raw = await redis_client.get(key)
        if raw is None:
            continue
        try:
            meta = json.loads(raw)
            items.append(
                TemplateListItem(
                    template_id=meta["template_id"],
                    name=meta["name"],
                    format=meta["format"],
                    created_at=meta["created_at"],
                )
            )
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("양식 메타데이터 파싱 실패", key=key, error=str(exc))

    # 생성 시각 역순으로 정렬
    items.sort(key=lambda x: x.created_at, reverse=True)

    return items


@router.get(
    "/{template_id}",
    response_model=TemplateDetail,
    responses={404: {"description": "양식 없음"}},
)
async def get_template(
    template_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> TemplateDetail:
    """
    양식 상세 조회 (구조 포함)
    GET /api/v1/templates/{template_id}
    """
    redis_key = f"template:{template_id}"
    raw = await redis_client.get(redis_key)

    if raw is None:
        not_found(f"양식을 찾을 수 없습니다: template_id={template_id}")

    try:
        meta = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("양식 메타데이터 파싱 실패", template_id=template_id, error=str(exc))
        internal_server_error("양식 데이터 파싱 오류")

    return TemplateDetail(
        template_id=meta["template_id"],
        name=meta["name"],
        format=meta["format"],
        structure=meta.get("structure", {}),
        created_at=meta["created_at"],
    )


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "양식 없음"}},
)
async def delete_template(
    template_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> None:
    """
    양식 삭제 (파일 + Redis 메타데이터)
    DELETE /api/v1/templates/{template_id}
    """
    redis_key = f"template:{template_id}"
    raw = await redis_client.get(redis_key)

    if raw is None:
        not_found(f"양식을 찾을 수 없습니다: template_id={template_id}")

    # Redis 키 삭제
    await redis_client.delete(redis_key)

    # 파일 디렉토리 삭제 (존재하면)
    template_dir = settings.templates_dir / template_id
    if template_dir.exists():
        shutil.rmtree(str(template_dir))
        logger.info("양식 파일 디렉토리 삭제", template_id=template_id)

    logger.info("양식 삭제 완료", template_id=template_id)
