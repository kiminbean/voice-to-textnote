"""
cleanup_task 단위 테스트
SPEC-RETENTION-001: Celery Beat 데이터 정리 태스크
"""

from unittest.mock import MagicMock, patch


class TestCleanupExpiredData:
    """만료 데이터 정리 태스크 검증"""

    def test_cleanup_expired_data_returns_cleanup_counts(self, tmp_path):
        """DB/임시 파일 정리 결과를 합쳐 반환"""
        from backend.workers.tasks.cleanup_task import cleanup_expired_data

        session = MagicMock()
        session_context = MagicMock()
        session_context.__enter__.return_value = session

        with (
            patch("backend.db.sync_engine.get_sync_session", return_value=session_context),
            patch(
                "backend.services.retention.cleanup_expired_results", return_value=7
            ) as db_cleanup,
            patch(
                "backend.services.retention.cleanup_temp_files", return_value=(3, 4096)
            ) as file_cleanup,
            patch("backend.app.config.settings") as mock_settings,
        ):
            mock_settings.data_retention_days = 45
            mock_settings.temp_dir = tmp_path
            mock_settings.temp_file_retention_hours = 6

            result = cleanup_expired_data.run()

        assert result == {
            "db_deleted": 7,
            "files_deleted": 3,
            "freed_bytes": 4096,
        }
        db_cleanup.assert_called_once_with(session, 45)
        file_cleanup.assert_called_once_with(tmp_path, 6)
        session_context.__enter__.assert_called_once()
        session_context.__exit__.assert_called_once()

    def test_cleanup_expired_data_handles_empty_cleanup(self, tmp_path):
        """삭제할 데이터가 없어도 0 카운트 반환"""
        from backend.workers.tasks.cleanup_task import cleanup_expired_data

        session_context = MagicMock()
        session_context.__enter__.return_value = MagicMock()

        with (
            patch("backend.db.sync_engine.get_sync_session", return_value=session_context),
            patch("backend.services.retention.cleanup_expired_results", return_value=0),
            patch("backend.services.retention.cleanup_temp_files", return_value=(0, 0)),
            patch("backend.app.config.settings") as mock_settings,
        ):
            mock_settings.data_retention_days = 30
            mock_settings.temp_dir = tmp_path
            mock_settings.temp_file_retention_hours = 24

            result = cleanup_expired_data.run()

        assert result["db_deleted"] == 0
        assert result["files_deleted"] == 0
        assert result["freed_bytes"] == 0

    def test_cleanup_task_is_registered_with_expected_name(self):
        """Celery Beat 스케줄이 참조하는 태스크 이름 유지"""
        from backend.workers.tasks.cleanup_task import cleanup_expired_data

        assert cleanup_expired_data.name == "cleanup_expired_data"
