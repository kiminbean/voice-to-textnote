"""
TASK-002: Alembic Migration 테스트

DeviceToken 테이블 migration의 유효성 검증
"""


class TestDeviceTokenMigration:
    """DeviceToken migration 테스트"""

    def test_migration_file_exists(self):
        """Migration 파일이 존재하는지 검증"""
        from pathlib import Path

        migration_file = (
            Path(__file__).parent.parent.parent
            / "alembic"
            / "versions"
            / "002_add_device_tokens.py"
        )
        assert migration_file.exists(), f"Migration file not found: {migration_file}"

    def test_migration_has_upgrade_downgrade(self):
        """Migration 파일에 upgrade와 downgrade 함수가 있는지 검증"""
        import importlib.util
        import sys
        from pathlib import Path

        migration_file = (
            Path(__file__).parent.parent.parent
            / "alembic"
            / "versions"
            / "002_add_device_tokens.py"
        )

        # 모듈 로드
        spec = importlib.util.spec_from_file_location("migration", str(migration_file))
        module = importlib.util.module_from_spec(spec)
        sys.modules["migration"] = module
        spec.loader.exec_module(module)

        # 함수 존재 확인
        assert hasattr(module, "upgrade"), "Migration must have upgrade() function"
        assert hasattr(module, "downgrade"), "Migration must have downgrade() function"

        # revision 정보 확인
        assert hasattr(module, "revision"), "Migration must have revision"
        assert hasattr(module, "down_revision"), "Migration must have down_revision"
        assert module.revision == "002_add_device_tokens"
        assert module.down_revision == "001"

    def test_migration_upgrade_creates_table(self):
        """Migration upgrade가 device_tokens 테이블을 생성하는지 검증 (구조 검증)"""
        from pathlib import Path

        migration_file = (
            Path(__file__).parent.parent.parent
            / "alembic"
            / "versions"
            / "002_add_device_tokens.py"
        )

        content = migration_file.read_text()

        # upgrade 함수에서 create_table 호출 확인
        assert "op.create_table" in content, "Upgrade must create table"
        assert "'device_tokens'" in content, "Table name must be device_tokens"
        assert "op.create_index" in content, "Upgrade must create indexes"
        assert "ix_device_tokens_user_id" in content, "Must create user_id index"
        assert "ix_device_tokens_fcm_token" in content, "Must create fcm_token index"

    def test_migration_downgrade_drops_table(self):
        """Migration downgrade가 device_tokens 테이블을 삭제하는지 검증"""
        from pathlib import Path

        migration_file = (
            Path(__file__).parent.parent.parent
            / "alembic"
            / "versions"
            / "002_add_device_tokens.py"
        )

        content = migration_file.read_text()

        # downgrade 함수에서 drop_table 호출 확인
        assert "op.drop_table" in content, "Downgrade must drop table"
        assert "op.drop_index" in content, "Downgrade must drop indexes"
