"""
TASK-002: Alembic Migration 테스트

DeviceToken 테이블 migration의 유효성 검증
"""

import os
import sqlite3
import subprocess
import sys


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

    def test_device_id_migration_adds_lookup_column(self):
        """003 migration이 device_id 컬럼과 조회 인덱스를 추가하는지 검증"""
        from pathlib import Path

        migration_file = (
            Path(__file__).parent.parent.parent
            / "alembic"
            / "versions"
            / "003_add_device_id_to_device_tokens.py"
        )

        assert migration_file.exists(), f"Migration file not found: {migration_file}"
        content = migration_file.read_text()

        assert 'revision: str = "003_add_device_id_to_device_tokens"' in content
        assert 'down_revision: str | None = "002_add_device_tokens"' in content
        assert "op.add_column" in content
        assert '"device_id"' in content
        assert "ix_device_tokens_user_device_id" in content
        assert "op.drop_column" in content

    def test_alembic_upgrade_head_creates_device_id_schema(self, tmp_path):
        """alembic upgrade head가 device_id 컬럼과 조회 인덱스를 실제 생성한다."""
        from pathlib import Path

        repo_root = Path(__file__).parent.parent.parent
        db_path = tmp_path / "alembic-device-token.sqlite"
        env = {
            **os.environ,
            "DATABASE_URL": f"sqlite+aiosqlite:///{db_path}",
        }

        completed = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=repo_root,
            env=env,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        assert completed.returncode == 0, completed.stdout

        with sqlite3.connect(db_path) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(device_tokens)")}
            indexes = {row[1] for row in connection.execute("PRAGMA index_list(device_tokens)")}
            version = connection.execute("SELECT version_num FROM alembic_version").fetchone()

        assert "device_id" in columns
        assert "ix_device_tokens_device_id" in indexes
        assert "ix_device_tokens_user_device_id" in indexes
        assert version is not None
        assert "003_add_device_id_to_device_tokens" in version[0] or version[0].startswith("004")
