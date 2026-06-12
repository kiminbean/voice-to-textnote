"""
내보내기 API 테스트
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from pathlib import Path

from backend.app.main import app
from backend.services.export_service import ExportService


class TestExportAPI:
    """내보내기 API 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.client = TestClient(app)
        self.export_service = ExportService()
    
    @patch('backend.services.export_service.ExportService.export_meeting')
    async def test_export_meeting_minutes_basic(self, mock_export):
        """기본 회의록 내보내기 테스트"""
        # Mock 설정
        mock_export.return_value = {
            "task_id": "test_task_1",
            "filename": "meeting_minutes_test_task_1_20240612_120000.pdf",
            "path": "/tmp/test_export.pdf",
            "size_bytes": 2048,
            "media_type": "application/pdf",
            "created_at": "2026-06-12T12:00:00Z",
            "format": "pdf",
            "title": "test_task_1",
            "page_count": 5,
            "word_count": 250
        }
        
        # 테스트 요청
        response = self.client.get("/api/v1/export/minutes/test_task_1?format=pdf")
        
        # 응답 검증
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["content-disposition"] == "attachment; filename=meeting_minutes_test_task_1_20240612_120000.pdf"
    
    @patch('backend.services.export_service.ExportService.export_meeting')
    async def test_export_meeting_minutes_not_found(self, mock_export):
        """존재하지 않는 회의록 내보내기 테스트"""
        response = self.client.get("/api/v1/export/minutes/nonexistent_task")
        assert response.status_code == 404
    
    @patch('backend.services.export_service.ExportService.export_meeting')
    async def test_export_meeting_minutes_invalid_format(self, mock_export):
        """지원하지 않는 형식 테스트"""
        response = self.client.get("/api/v1/export/minutes/test_task_1?format=txt")
        assert response.status_code == 422
    
    @patch('backend.services.export_service.ExportService.export_batch_meetings')
    async def test_export_batch_meetings_basic(self, mock_export):
        """배치 내보내기 테스트"""
        # Mock 설정
        mock_export.return_value = [
            {
                "task_id": "test_task_1",
                "filename": "meeting_minutes_test_task_1_20240612_120000.pdf",
                "path": "/tmp/test_export1.pdf",
                "size_bytes": 2048,
                "media_type": "application/pdf",
                "created_at": "2026-06-12T12:00:00Z",
                "format": "pdf",
                "title": "test_task_1",
                "page_count": 5,
                "word_count": 250
            },
            {
                "task_id": "test_task_2", 
                "filename": "meeting_minutes_test_task_2_20240612_120000.pdf",
                "path": "/tmp/test_export2.pdf",
                "size_bytes": 3072,
                "media_type": "application/pdf",
                "created_at": "2026-06-12T12:00:00Z",
                "format": "pdf",
                "title": "test_task_2",
                "page_count": 7,
                "word_count": 350
            }
        ]
        
        # 테스트 요청
        request_data = {
            "task_ids": ["test_task_1", "test_task_2"],
            "format": "pdf"
        }
        
        response = self.client.post("/api/v1/export/batch", json=request_data)
        
        # 응답 검증
        assert response.status_code == 200
        data = response.json()
        assert data["total_requested"] == 2
        assert data["total_success"] == 2
        assert data["total_failed"] == 0
        assert len(data["export_files"]) == 2
        assert data["export_files"][0]["task_id"] == "test_task_1"
    
    @patch('backend.services.export_service.ExportService.export_batch_meetings')
    async def test_export_batch_meetings_empty_request(self, mock_export):
        """빈 요청 테스트"""
        request_data = {
            "task_ids": [],
            "format": "pdf"
        }
        
        response = self.client.post("/api/v1/export/batch", json=request_data)
        assert response.status_code == 422
    
    @patch('backend.services.export_service.ExportService.export_batch_meetings')
    async def test_export_batch_meetings_too_many_tasks(self, mock_export):
        """과도한 작업 수 테스트"""
        # 51개 작업 ID 생성
        task_ids = [f"task_{i}" for i in range(51)]
        request_data = {
            "task_ids": task_ids,
            "format": "pdf"
        }
        
        response = self.client.post("/api/v1/export/batch", json=request_data)
        assert response.status_code == 422
    
    @patch('backend.services.export_service.ExportService.get_export_templates')
    async def test_get_export_templates(self, mock_templates):
        """내보내기 템플릿 조회 테스트"""
        # Mock 설정
        mock_templates.return_value = [
            {
                "id": "default",
                "name": "Default",
                "description": "PDF 형식의 default 템플릿",
                "sections": ["transcription", "summary", "action_items"],
                "styling": {
                    "font_family": "helvetica",
                    "font_size": 12,
                    "page_size": "A4"
                }
            }
        ]
        
        # 테스트 요청
        response = self.client.get("/api/v1/export/templates?format=pdf")
        
        # 응답 검증
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "pdf"
        assert len(data["templates"]) == 1
        assert data["templates"][0]["id"] == "default"
        assert data["available"] is True