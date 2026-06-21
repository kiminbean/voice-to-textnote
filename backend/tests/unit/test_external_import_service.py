import sys
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.schemas.external_import import (
    ExternalImportSourceType,
    ExternalTextImportRequest,
    ExternalTextImportResponse,
)
from backend.services.document_import_service import DocumentImportService
from backend.services.external_import_service import (
    ExternalImportService,
    ExternalImportValidationError,
)


@pytest.mark.asyncio
async def test_import_text_persists_minutes_result_and_caches_for_existing_flow():
    service = ExternalImportService()
    db = AsyncMock()
    redis = AsyncMock()
    db.run_sync = AsyncMock()
    db.commit = AsyncMock()
    payload = ExternalTextImportRequest(
        source_url="https://youtu.be/example123",
        title="제품 데모 영상",
        content="첫 번째 문단입니다.\n\n두 번째 문단에서는 고객 피드백과 다음 단계를 설명합니다.",
    )

    with patch(
        "backend.services.external_import_service.ResultService.save_result",
        new_callable=AsyncMock,
    ) as save_result:
        response = await service.import_text(payload, db, redis)

    assert response.task_id.startswith("ext-")
    assert response.status == "completed"
    assert response.source_type == ExternalImportSourceType.YOUTUBE
    assert response.result_url == f"/api/v1/minutes/{response.task_id}"
    assert response.search_indexed is True

    saved_kwargs = save_result.await_args.kwargs
    result_data = saved_kwargs["result_data"]
    assert saved_kwargs["task_type"] == "minutes"
    assert saved_kwargs["status"] == "completed"
    assert saved_kwargs["input_metadata"]["source"] == "external_import"
    assert result_data["source"]["type"] == "youtube"
    assert result_data["segments"][0]["speaker_name"] == "외부 소스"
    assert "고객 피드백" in result_data["segments"][0]["text"]
    assert "원본: https://youtu.be/example123" in result_data["markdown"]
    assert redis.setex.await_count == 2
    assert db.run_sync.await_count == 2
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_import_text_reports_search_index_best_effort_failure():
    service = ExternalImportService()
    db = AsyncMock()
    redis = AsyncMock()
    db.run_sync = AsyncMock(side_effect=RuntimeError("fts unavailable"))
    db.rollback = AsyncMock()
    payload = ExternalTextImportRequest(
        source_url="https://example.com/transcript",
        title="외부 기사",
        content="검색 인덱스 실패와 무관하게 가져오기 결과는 저장되어야 합니다.",
    )

    with patch(
        "backend.services.external_import_service.ResultService.save_result",
        new_callable=AsyncMock,
    ):
        response = await service.import_text(payload, db, redis)

    assert response.search_indexed is False
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_import_text_applies_default_team_policy_for_authenticated_owner():
    service = ExternalImportService()
    db = AsyncMock()
    redis = AsyncMock()
    db.run_sync = AsyncMock()
    db.commit = AsyncMock()
    owner_id = uuid.uuid4()
    payload = ExternalTextImportRequest(
        source_url="https://example.com/transcript",
        title="팀 기본 공유 회의",
        content="팀 기본 공유 정책을 적용할 만큼 충분한 외부 transcript 본문입니다.",
    )

    with (
        patch(
            "backend.services.external_import_service.ResultService.save_result",
            new_callable=AsyncMock,
        ),
        patch(
            "backend.services.external_import_service.MeetingShareService"
        ) as share_service_cls,
    ):
        share_service = share_service_cls.return_value
        shared_team_id = uuid.uuid4()
        share_service.apply_default_team_sharing_policy = AsyncMock(
            return_value=[shared_team_id]
        )
        response = await service.import_text(payload, db, redis, owner_id=owner_id)

    share_service.apply_default_team_sharing_policy.assert_awaited_once_with(
        session=db,
        task_id=response.task_id,
        owner_id=owner_id,
    )
    assert response.shared_team_ids == [str(shared_team_id)]


def test_normalize_content_rejects_empty_import_text():
    service = ExternalImportService()

    with pytest.raises(ExternalImportValidationError):
        if not service._normalize_content(" \n\t "):
            raise ExternalImportValidationError("가져올 본문이 비어 있습니다.")


@pytest.mark.asyncio
async def test_import_text_rejects_whitespace_after_normalization():
    service = ExternalImportService()

    with pytest.raises(ExternalImportValidationError, match="본문"):
        await service.import_text(
            SimpleNamespace(content=" \n\t "),
            AsyncMock(),
            AsyncMock(),
        )


def test_resolve_source_type_respects_explicit_non_web_type():
    service = ExternalImportService()

    assert (
        service._resolve_source_type(
            "https://example.com/video",
            ExternalImportSourceType.PODCAST,
        )
        == ExternalImportSourceType.PODCAST
    )


@pytest.mark.asyncio
async def test_import_document_extracts_text_and_reuses_external_import_pipeline():
    external_service = AsyncMock()
    external_service.import_text = AsyncMock(
        return_value=ExternalTextImportResponse(
            task_id="ext-doc-001",
            status="completed",
            title="강의 자료",
            source_url="https://local.voicetextnote/imports/documents/lecture.pdf",
            source_type=ExternalImportSourceType.DOCUMENT,
            language="ko",
            result_url="/api/v1/minutes/ext-doc-001",
            search_indexed=True,
        )
    )
    service = DocumentImportService(external_service)
    service._extract_text = (
        lambda file_type, content: " 첫 문단 \n\n 두 번째 문단과 핵심 개념 및 복습 질문 "
    )

    response = await service.import_document(
        filename="lecture.pdf",
        content=b"%PDF fake",
        title="강의 자료",
        language="ko",
        db=AsyncMock(),
        redis_client=AsyncMock(),
        owner_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
    )

    assert response.task_id == "ext-doc-001"
    assert response.source_type == ExternalImportSourceType.DOCUMENT
    assert response.file_name == "lecture.pdf"
    assert response.file_type == "pdf"
    assert response.extracted_characters == len("첫 문단\n두 번째 문단과 핵심 개념 및 복습 질문")
    payload = external_service.import_text.await_args.args[0]
    assert payload.title == "강의 자료"
    assert payload.content == "첫 문단\n두 번째 문단과 핵심 개념 및 복습 질문"
    assert payload.source_type == ExternalImportSourceType.DOCUMENT
    assert external_service.import_text.await_args.kwargs["owner_id"] == uuid.UUID(
        "00000000-0000-0000-0000-000000000001"
    )


@pytest.mark.asyncio
async def test_import_document_uses_filename_as_default_title():
    external_service = AsyncMock()
    external_service.import_text = AsyncMock(
        return_value=ExternalTextImportResponse(
            task_id="ext-doc-002",
            status="completed",
            title="meeting-notes",
            source_url="https://local.voicetextnote/imports/documents/meeting-notes.docx",
            source_type=ExternalImportSourceType.DOCUMENT,
            language="en",
            result_url="/api/v1/minutes/ext-doc-002",
            search_indexed=True,
        )
    )
    service = DocumentImportService(external_service)
    service._extract_text = lambda file_type, content: "Meeting notes with enough text"

    await service.import_document(
        filename="meeting-notes.docx",
        content=b"PK\x03\x04 fake",
        title=None,
        language="en",
        db=AsyncMock(),
        redis_client=AsyncMock(),
    )

    payload = external_service.import_text.await_args.args[0]
    assert payload.title == "meeting-notes"


def test_import_document_rejects_image_until_ocr_engine_is_available():
    service = DocumentImportService()

    service._validate_document(
        filename="whiteboard.png",
        file_type="png",
        content=b"\x89PNG\r\n\x1a\n",
    )


@pytest.mark.asyncio
async def test_import_document_extracts_image_ocr_text_and_reuses_pipeline():
    external_service = AsyncMock()
    external_service.import_text = AsyncMock(
        return_value=ExternalTextImportResponse(
            task_id="ext-img-001",
            status="completed",
            title="화이트보드",
            source_url="https://local.voicetextnote/imports/documents/whiteboard.png",
            source_type=ExternalImportSourceType.DOCUMENT,
            language="ko",
            result_url="/api/v1/minutes/ext-img-001",
            search_indexed=True,
        )
    )
    service = DocumentImportService(external_service)
    service._extract_image_text = lambda content: "화이트보드 OCR 텍스트와 결정 사항"

    response = await service.import_document(
        filename="whiteboard.png",
        content=b"\x89PNG\r\n\x1a\nfake image",
        title=None,
        language="ko",
        db=AsyncMock(),
        redis_client=AsyncMock(),
    )

    assert response.task_id == "ext-img-001"
    assert response.file_type == "png"
    assert response.extracted_characters == len("화이트보드 OCR 텍스트와 결정 사항")
    payload = external_service.import_text.await_args.args[0]
    assert payload.title == "whiteboard"
    assert payload.content == "화이트보드 OCR 텍스트와 결정 사항"
    assert payload.source_type == ExternalImportSourceType.DOCUMENT


def test_extract_image_text_reports_missing_optional_ocr_runtime(monkeypatch):
    service = DocumentImportService()
    monkeypatch.setitem(sys.modules, "PIL", None)
    monkeypatch.setitem(sys.modules, "pytesseract", None)

    with pytest.raises(ExternalImportValidationError, match="이미지 OCR"):
        service._extract_image_text(b"\x89PNG\r\n\x1a\nfake image")


def test_extract_image_text_uses_optional_ocr_runtime(monkeypatch):
    service = DocumentImportService()
    fake_image = MagicMock()
    fake_image.__enter__.return_value = fake_image
    fake_image.__exit__.return_value = False
    image_module = MagicMock()
    image_module.open.return_value = fake_image
    pytesseract = MagicMock()
    pytesseract.image_to_string.return_value = "OCR 텍스트"
    monkeypatch.setitem(sys.modules, "PIL", SimpleNamespace(Image=image_module))
    monkeypatch.setitem(sys.modules, "pytesseract", pytesseract)

    assert service._extract_image_text(b"\x89PNG\r\n\x1a\nfake image") == "OCR 텍스트"
    image_module.open.assert_called_once()
    pytesseract.image_to_string.assert_called_once_with(fake_image, lang="kor+eng")


def test_extract_image_text_reports_ocr_runtime_failure(monkeypatch):
    service = DocumentImportService()
    image_module = MagicMock()
    image_module.open.side_effect = RuntimeError("broken image")
    monkeypatch.setitem(sys.modules, "PIL", SimpleNamespace(Image=image_module))
    monkeypatch.setitem(sys.modules, "pytesseract", MagicMock())

    with pytest.raises(ExternalImportValidationError, match="이미지 OCR 텍스트 추출"):
        service._extract_image_text(b"\x89PNG\r\n\x1a\nfake image")


def test_import_document_rejects_magic_byte_mismatch():
    service = DocumentImportService()

    with pytest.raises(ExternalImportValidationError, match="시그니처"):
        service._validate_document(
            filename="not-a-pdf.pdf",
            file_type="pdf",
            content=b"not a pdf",
        )


def test_import_document_rejects_missing_filename_empty_and_large_content():
    service = DocumentImportService()

    with pytest.raises(ExternalImportValidationError, match="파일명"):
        service._validate_document(filename="", file_type="", content=b"data")

    with pytest.raises(ExternalImportValidationError, match="빈 문서"):
        service._validate_document(filename="empty.pdf", file_type="pdf", content=b"")

    with pytest.raises(ExternalImportValidationError, match="20MB"):
        service._validate_document(
            filename="large.pdf",
            file_type="pdf",
            content=b"x" * (20 * 1024 * 1024 + 1),
        )


def test_import_document_rejects_unsupported_document_type():
    service = DocumentImportService()

    with pytest.raises(ExternalImportValidationError, match="PDF, DOCX 또는 이미지"):
        service._validate_document(
            filename="notes.txt",
            file_type="txt",
            content=b"plain text",
        )


def test_import_document_extract_text_dispatches_supported_types():
    service = DocumentImportService()
    service._extract_pdf_text = lambda content: "pdf text"
    service._extract_docx_text = lambda content: "docx text"

    assert service._extract_text("pdf", b"pdf") == "pdf text"
    assert service._extract_text("docx", b"docx") == "docx text"

    with pytest.raises(ExternalImportValidationError, match="지원하지 않는"):
        service._extract_text("txt", b"text")


def test_extract_pdf_text_reads_all_pages(monkeypatch):
    service = DocumentImportService()
    page_one = MagicMock()
    page_one.extract_text.return_value = "첫 페이지"
    page_two = MagicMock()
    page_two.extract_text.return_value = ""
    page_three = MagicMock()
    page_three.extract_text.return_value = "세 번째 페이지"
    pdf = MagicMock()
    pdf.pages = [page_one, page_two, page_three]
    pdf.__enter__.return_value = pdf
    pdf.__exit__.return_value = False
    pdfplumber = MagicMock()
    pdfplumber.open.return_value = pdf
    monkeypatch.setitem(sys.modules, "pdfplumber", pdfplumber)

    assert service._extract_pdf_text(b"%PDF fake") == "첫 페이지\n세 번째 페이지"
    pdfplumber.open.assert_called_once()


def test_extract_pdf_text_reports_missing_dependency(monkeypatch):
    service = DocumentImportService()
    monkeypatch.setitem(sys.modules, "pdfplumber", None)

    with pytest.raises(ExternalImportValidationError, match="PDF 텍스트 추출 기능"):
        service._extract_pdf_text(b"%PDF fake")


def test_extract_pdf_text_reports_parser_failure(monkeypatch):
    service = DocumentImportService()
    pdfplumber = MagicMock()
    pdfplumber.open.side_effect = RuntimeError("broken")
    monkeypatch.setitem(sys.modules, "pdfplumber", pdfplumber)

    with pytest.raises(ExternalImportValidationError, match="PDF 텍스트 추출에 실패"):
        service._extract_pdf_text(b"%PDF fake")


def test_extract_docx_text_reads_paragraphs_and_tables(monkeypatch):
    service = DocumentImportService()
    fake_document = SimpleNamespace(
        paragraphs=[SimpleNamespace(text="본문 1"), SimpleNamespace(text="본문 2")],
        tables=[
            SimpleNamespace(
                rows=[
                    SimpleNamespace(
                        cells=[SimpleNamespace(text="표 제목"), SimpleNamespace(text="표 값")]
                    )
                ]
            )
        ],
    )
    docx_module = MagicMock()
    docx_module.Document.return_value = fake_document
    monkeypatch.setitem(sys.modules, "docx", docx_module)

    assert service._extract_docx_text(b"PK\x03\x04 fake") == "본문 1\n본문 2\n표 제목\n표 값"


def test_extract_docx_text_reports_missing_dependency(monkeypatch):
    service = DocumentImportService()
    monkeypatch.setitem(sys.modules, "docx", None)

    with pytest.raises(ExternalImportValidationError, match="DOCX 텍스트 추출 기능"):
        service._extract_docx_text(b"PK\x03\x04 fake")


def test_extract_docx_text_reports_parser_failure(monkeypatch):
    service = DocumentImportService()
    docx_module = MagicMock()
    docx_module.Document.side_effect = RuntimeError("broken")
    monkeypatch.setitem(sys.modules, "docx", docx_module)

    with pytest.raises(ExternalImportValidationError, match="DOCX 텍스트 추출에 실패"):
        service._extract_docx_text(b"PK\x03\x04 fake")


@pytest.mark.asyncio
async def test_import_document_rejects_short_extracted_text():
    service = DocumentImportService(AsyncMock())
    service._extract_text = lambda file_type, content: "짧음"

    with pytest.raises(ExternalImportValidationError, match="충분히"):
        await service.import_document(
            filename="short.pdf",
            content=b"%PDF fake",
            title="짧은 문서",
            language="ko",
            db=AsyncMock(),
            redis_client=AsyncMock(),
        )
