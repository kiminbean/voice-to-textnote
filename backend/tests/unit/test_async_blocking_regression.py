"""
SPEC-BUGFIX-002 REQ-BF2-001: asyncio.to_thread 회귀 테스트.

7개 엔드포인트에서 CPU-bound/blocking 작업이 asyncio.to_thread로 감싸져 있는지
AST 기반으로 정적 검사한다. 실수로 to_thread가 제거되면 즉시 CI가 실패한다.
"""
import ast
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _function_uses_to_thread(file_path: Path, function_name: str) -> bool:
    """지정한 async function이 asyncio.to_thread 또는 run_in_executor를 사용하는지 AST로 검사."""
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))

    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == function_name:
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    func = child.func
                    if isinstance(func, ast.Attribute):
                        if func.attr in ("to_thread", "run_in_executor"):
                            return True
                        if func.attr == "thread" and isinstance(func.value, ast.Name):
                            if func.value.id == "asyncio":
                                return True
                    elif isinstance(func, ast.Name) and func.id == "to_thread":
                        return True
            return False
    pytest.fail(f"Function '{function_name}' not found in {file_path}")


class TestTranscriptionAsyncBlocking:
    """transcription 엔드포인트의 blocking 호출 회귀 방지."""

    def test_upload_transcription_uses_to_thread_for_duration_check(self):
        f = BACKEND_ROOT / "app" / "api" / "v1" / "transcription" / "transcription.py"
        assert _function_uses_to_thread(f, "upload_transcription")

    def test_batch_upload_uses_to_thread_for_duration_check(self):
        f = BACKEND_ROOT / "app" / "api" / "v1" / "transcription" / "batch.py"
        assert _function_uses_to_thread(f, "upload_batch_transcription")


class TestAudioAnalysisAsyncBlocking:
    """audio_analysis 엔드포인트의 librosa 분석 회귀 방지."""

    def test_analyze_audio_file_uses_to_thread(self):
        f = BACKEND_ROOT / "app" / "api" / "v1" / "audio" / "audio_analysis.py"
        assert _function_uses_to_thread(f, "analyze_audio_file")


class TestExportAsyncBlocking:
    """export 엔드포인트의 PDF/DOCX 생성 회귀 방지."""

    def test_export_pdf_uses_to_thread(self):
        f = BACKEND_ROOT / "app" / "api" / "v1" / "admin" / "export.py"
        assert _function_uses_to_thread(f, "export_pdf")

    def test_export_docx_uses_to_thread(self):
        f = BACKEND_ROOT / "app" / "api" / "v1" / "admin" / "export.py"
        assert _function_uses_to_thread(f, "export_docx")


class TestTemplatesAsyncBlocking:
    """templates 엔드포인트의 구조 파싱 회귀 방지."""

    def test_upload_template_uses_to_thread_for_structure_parsing(self):
        f = BACKEND_ROOT / "app" / "api" / "v1" / "admin" / "templates.py"
        assert _function_uses_to_thread(f, "upload_template")


class TestPushServiceAsyncBlocking:
    """push_service의 FCM 전송 회귀 방지 (MOCK 모드가 아닐 때)."""

    def test_send_push_uses_to_thread(self):
        f = BACKEND_ROOT / "services" / "push_service.py"
        assert _function_uses_to_thread(f, "send_push")

    def test_send_multicast_uses_to_thread(self):
        f = BACKEND_ROOT / "services" / "push_service.py"
        assert _function_uses_to_thread(f, "send_multicast")
