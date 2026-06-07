"""
Templates API 단위 테스트
REQ-TMPL-001~004: 양식 업로드, 목록 조회, 상세 조회, 삭제
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import status

from backend.app.api.v1.admin.templates import (
    _validate_file,
    delete_template,
    get_template,
    list_templates,
    upload_template,
)
from backend.schemas.template import TemplateDetail, TemplateListItem, TemplateUploadResponse

# ---------------------------------------------------------------------------
# _validate_file 테스트
# ---------------------------------------------------------------------------


class TestValidateFile:
    """파일 검증 함수 테스트 스위트"""

    def test_supported_format_pdf(self):
        """PDF 형식 허용"""
        is_valid, error = _validate_file("document.pdf", 1024)
        assert is_valid is True
        assert error == ""

    def test_supported_format_docx(self):
        """DOCX 형식 허용"""
        is_valid, error = _validate_file("document.docx", 1024)
        assert is_valid is True
        assert error == ""

    def test_unsupported_format_exe(self):
        """지원하지 않는 형식 거부"""
        is_valid, error = _validate_file("malware.exe", 1024)
        assert is_valid is False
        assert "지원하지 않는 파일 형식" in error
        assert ".exe" in error

    def test_file_size_under_limit(self):
        """10MB 이하 파일 허용"""
        is_valid, error = _validate_file("document.pdf", 10 * 1024 * 1024 - 1)
        assert is_valid is True
        assert error == ""

    def test_file_size_exceeds_limit(self):
        """10MB 초과 파일 거부"""
        is_valid, error = _validate_file("document.pdf", 10 * 1024 * 1024 + 1)
        assert is_valid is False
        assert "파일 크기 초과" in error
        assert "10MB" in error


# ---------------------------------------------------------------------------
# upload_template 테스트
# ---------------------------------------------------------------------------


class TestUploadTemplate:
    """양식 업로드 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_upload_pdf_success(self, mock_redis_client, tmp_path, monkeypatch):
        """PDF 파일 업로드 성공"""
        from backend.app.config import settings

        # 테스트용 임시 디렉토리 설정
        test_templates_dir = tmp_path / "templates"
        test_templates_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(settings, "templates_dir", test_templates_dir)

        # Mock UploadFile 생성
        mock_file = MagicMock()
        mock_file.filename = "test_template.pdf"
        mock_file.content_type = "application/pdf"
        mock_pdf_content = b"%PDF-1.4 fake pdf content"

        # 비동기 read 메서드 모의
        async def mock_read():
            return mock_pdf_content

        mock_file.read = mock_read

        # TemplateParser mock
        mock_parser = MagicMock()
        mock_structure = {
            "sections": [{"title": "회의 제목", "level": 1}],
            "fields": {},
            "has_table": False,
            "raw_text_preview": "회의 제목",
        }
        mock_parser.extract_structure.return_value = mock_structure

        # Redis mock 설정
        mock_redis_client.setex.return_value = True

        # TemplateParser.patch로 주입
        import backend.app.api.v1.admin.templates as templates_module

        original_parser = templates_module.TemplateParser
        templates_module.TemplateParser = lambda: mock_parser

        try:
            response = await upload_template(
                file=mock_file, name="테스트 양식", redis_client=mock_redis_client
            )

            assert isinstance(response, TemplateUploadResponse)
            assert response.name == "테스트 양식"
            assert response.format == "pdf"
            assert response.structure == mock_structure
            assert response.template_id is not None
        finally:
            templates_module.TemplateParser = original_parser

    @pytest.mark.asyncio
    async def test_upload_unsupported_format(self, mock_redis_client):
        """지원하지 않는 형식 업로드 실패"""
        mock_file = MagicMock()
        mock_file.filename = "document.exe"
        mock_file.content_type = "application/octet-stream"

        async def mock_read():
            return b"fake content"

        mock_file.read = mock_read

        with pytest.raises(Exception) as exc_info:
            await upload_template(file=mock_file, redis_client=mock_redis_client)

        # HTTPException 확인
        assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "지원하지 않는 파일 형식" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_upload_file_too_large(self, mock_redis_client):
        """파일 크기 초과 업로드 실패"""
        mock_file = MagicMock()
        mock_file.filename = "large.pdf"
        mock_file.content_type = "application/pdf"
        large_content = b"x" * (10 * 1024 * 1024 + 1)

        async def mock_read():
            return large_content

        mock_file.read = mock_read

        with pytest.raises(Exception) as exc_info:
            await upload_template(file=mock_file, redis_client=mock_redis_client)

        assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "파일 크기 초과" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_upload_default_name_from_filename(
        self, mock_redis_client, tmp_path, monkeypatch
    ):
        """이름 미지정 시 파일명 사용"""
        from backend.app.config import settings

        test_templates_dir = tmp_path / "templates"
        test_templates_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(settings, "templates_dir", test_templates_dir)

        mock_file = MagicMock()
        mock_file.filename = "meeting_template.docx"
        mock_file.content_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

        async def mock_read():
            return b"fake docx"

        mock_file.read = mock_read

        mock_parser = MagicMock()
        mock_structure = {
            "sections": [],
            "fields": {},
            "has_table": False,
            "raw_text_preview": "",
        }
        mock_parser.extract_structure.return_value = mock_structure

        import backend.app.api.v1.admin.templates as templates_module

        original_parser = templates_module.TemplateParser
        templates_module.TemplateParser = lambda: mock_parser

        try:
            response = await upload_template(
                file=mock_file, name=None, redis_client=mock_redis_client
            )

            assert response.name == "meeting_template"
        finally:
            templates_module.TemplateParser = original_parser


# ---------------------------------------------------------------------------
# list_templates 테스트
# ---------------------------------------------------------------------------


class TestListTemplates:
    """양식 목록 조회 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_list_empty(self, mock_redis_client):
        """빈 목록 조회"""
        mock_redis_client.keys.return_value = []

        items = await list_templates(redis_client=mock_redis_client)

        assert items == []
        mock_redis_client.keys.assert_called_once_with("template:*")

    @pytest.mark.asyncio
    async def test_list_multiple_templates(self, mock_redis_client):
        """여러 양식 목록 조회"""
        now = datetime.now(UTC).isoformat()

        mock_redis_client.keys.return_value = [
            b"template:uuid1",
            b"template:uuid2",
        ]

        # Redis get mock 설정
        def mock_get(key: bytes):
            if b"uuid1" in key:
                return json.dumps(
                    {
                        "template_id": "uuid1",
                        "name": "첫 번째 양식",
                        "format": "pdf",
                        "created_at": now,
                    }
                ).encode()
            elif b"uuid2" in key:
                return json.dumps(
                    {
                        "template_id": "uuid2",
                        "name": "두 번째 양식",
                        "format": "docx",
                        "created_at": now,
                    }
                ).encode()
            return None

        mock_redis_client.get.side_effect = mock_get

        items = await list_templates(redis_client=mock_redis_client)

        assert len(items) == 2
        assert all(isinstance(item, TemplateListItem) for item in items)
        assert items[0].name == "첫 번째 양식"
        assert items[1].name == "두 번째 양식"

    @pytest.mark.asyncio
    async def test_list_sorted_by_created_at_desc(self, mock_redis_client):
        """생성일 역순 정렬"""
        now = datetime.now(UTC)
        earlier = now.replace(hour=0, minute=0, second=0, microsecond=0)
        later = now.replace(hour=12, minute=0, second=0, microsecond=0)

        mock_redis_client.keys.return_value = [b"template:uuid1", b"template:uuid2"]

        def mock_get(key: bytes):
            if b"uuid1" in key:
                return json.dumps(
                    {
                        "template_id": "uuid1",
                        "name": "이른 양식",
                        "format": "pdf",
                        "created_at": earlier.isoformat(),
                    }
                ).encode()
            elif b"uuid2" in key:
                return json.dumps(
                    {
                        "template_id": "uuid2",
                        "name": "늦은 양식",
                        "format": "docx",
                        "created_at": later.isoformat(),
                    }
                ).encode()
            return None

        mock_redis_client.get.side_effect = mock_get

        items = await list_templates(redis_client=mock_redis_client)

        # 나중에 생성된 것이 먼저
        assert items[0].template_id == "uuid2"
        assert items[1].template_id == "uuid1"

    @pytest.mark.asyncio
    async def test_list_skips_invalid_metadata(self, mock_redis_client):
        """잘못된 메타데이터는 건너뜀"""
        mock_redis_client.keys.return_value = [b"template:uuid1", b"template:uuid2"]

        def mock_get(key: bytes):
            if b"uuid1" in key:
                return b"invalid json{{{"
            elif b"uuid2" in key:
                return json.dumps(
                    {
                        "template_id": "uuid2",
                        "name": "유효한 양식",
                        "format": "pdf",
                        "created_at": datetime.now(UTC).isoformat(),
                    }
                ).encode()
            return None  # pragma: no cover

        mock_redis_client.get.side_effect = mock_get

        items = await list_templates(redis_client=mock_redis_client)

        assert len(items) == 1
        assert items[0].template_id == "uuid2"


# ---------------------------------------------------------------------------
# get_template 테스트
# ---------------------------------------------------------------------------


class TestGetTemplate:
    """양식 상세 조회 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_get_template_success(self, mock_redis_client):
        """양식 상세 조회 성공"""
        template_id = "test-uuid"
        now = datetime.now(UTC).isoformat()

        metadata = {
            "template_id": template_id,
            "name": "테스트 양식",
            "format": "pdf",
            "created_at": now,
            "structure": {
                "sections": [{"title": "회의 제목", "level": 1}],
                "fields": {},
                "has_table": False,
            },
        }

        mock_redis_client.get.return_value = json.dumps(metadata).encode()

        response = await get_template(template_id=template_id, redis_client=mock_redis_client)

        assert isinstance(response, TemplateDetail)
        assert response.template_id == template_id
        assert response.name == "테스트 양식"
        assert response.structure == metadata["structure"]
        mock_redis_client.get.assert_called_once_with(f"template:{template_id}")

    @pytest.mark.asyncio
    async def test_get_template_not_found(self, mock_redis_client):
        """존재하지 않는 양식 조회 실패"""
        mock_redis_client.get.return_value = None

        with pytest.raises(Exception) as exc_info:
            await get_template(template_id="nonexistent", redis_client=mock_redis_client)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "양식을 찾을 수 없습니다" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_get_template_invalid_json(self, mock_redis_client):
        """잘못된 JSON 데이터 처리"""
        mock_redis_client.get.return_value = b"invalid json"

        with pytest.raises(Exception) as exc_info:
            await get_template(template_id="bad-json", redis_client=mock_redis_client)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "파싱 오류" in exc_info.value.message


# ---------------------------------------------------------------------------
# delete_template 테스트
# ---------------------------------------------------------------------------


class TestDeleteTemplate:
    """양식 삭제 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_delete_template_success(self, mock_redis_client, tmp_path, monkeypatch):
        """양식 삭제 성공"""
        from backend.app.config import settings

        test_templates_dir = tmp_path / "templates"
        test_template_dir = test_templates_dir / "test-uuid"
        test_template_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(settings, "templates_dir", test_templates_dir)

        # 파일 생성
        (test_template_dir / "original.pdf").write_bytes(b"fake pdf")

        mock_redis_client.get.return_value = json.dumps(
            {
                "template_id": "test-uuid",
                "name": "테스트",
                "format": "pdf",
                "created_at": datetime.now(UTC).isoformat(),
            }
        ).encode()
        mock_redis_client.delete.return_value = 1

        await delete_template(template_id="test-uuid", redis_client=mock_redis_client)

        mock_redis_client.delete.assert_called_once_with("template:test-uuid")
        assert not test_template_dir.exists()

    @pytest.mark.asyncio
    async def test_delete_template_not_found(self, mock_redis_client):
        """존재하지 않는 양식 삭제 실패"""
        mock_redis_client.get.return_value = None

        with pytest.raises(Exception) as exc_info:
            await delete_template(template_id="nonexistent", redis_client=mock_redis_client)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "양식을 찾을 수 없습니다" in exc_info.value.message
        mock_redis_client.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_template_no_files(self, mock_redis_client, monkeypatch):
        """파일이 없는 경우 Redis만 삭제"""
        from backend.app.config import settings

        test_templates_dir = Path("/nonexistent/templates")
        monkeypatch.setattr(settings, "templates_dir", test_templates_dir)

        mock_redis_client.get.return_value = json.dumps(
            {
                "template_id": "no-files",
                "name": "파일 없음",
                "format": "pdf",
                "created_at": datetime.now(UTC).isoformat(),
            }
        ).encode()
        mock_redis_client.delete.return_value = 1

        await delete_template(template_id="no-files", redis_client=mock_redis_client)

        mock_redis_client.delete.assert_called_once()
