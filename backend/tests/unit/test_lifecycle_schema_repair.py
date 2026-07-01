from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, create_engine, inspect

from backend.app.lifecycle import _repair_sqlite_auth_schema, _repair_sqlite_promise_ledger_schema


def test_repair_sqlite_auth_schema_adds_oauth_columns(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    metadata = MetaData()
    Table(
        "users",
        metadata,
        Column("id", String, primary_key=True),
        Column("email", String, nullable=False),
        Column("password_hash", String, nullable=False),
        Column("display_name", String, nullable=False),
    )
    metadata.create_all(engine)

    with engine.begin() as conn:
        _repair_sqlite_auth_schema(conn)

    with engine.connect() as conn:
        columns = {column["name"] for column in inspect(conn).get_columns("users")}

    assert {"provider", "provider_id", "avatar_url"}.issubset(columns)


def test_repair_sqlite_auth_schema_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    metadata = MetaData()
    Table(
        "users",
        metadata,
        Column("id", String, primary_key=True),
        Column("email", String, nullable=False),
        Column("password_hash", String, nullable=False),
        Column("display_name", String, nullable=False),
    )
    metadata.create_all(engine)

    with engine.begin() as conn:
        _repair_sqlite_auth_schema(conn)
        _repair_sqlite_auth_schema(conn)

    with engine.connect() as conn:
        columns = [column["name"] for column in inspect(conn).get_columns("users")]

    assert columns.count("provider") == 1


def test_repair_sqlite_promise_ledger_schema_adds_v4_columns_and_indexes(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    metadata = MetaData()
    Table(
        "promise_ledger_entries",
        metadata,
        Column("id", String, primary_key=True),
        Column("owner_id", String),
        Column("guest_session_id", String),
        Column("source_task_id", String, nullable=False),
        Column("last_source_task_id", String, nullable=False),
        Column("canonical_key", String, nullable=False),
        Column("canonical_text", String, nullable=False),
        Column("text", String, nullable=False),
        Column("status", String, nullable=False),
        Column("priority", String, nullable=False),
        Column("risk_level", String, nullable=False),
        Column("confidence", Integer, nullable=False),
        Column("occurrences", Integer, nullable=False),
        Column("first_seen_at", DateTime, nullable=False),
        Column("last_seen_at", DateTime, nullable=False),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
    )
    metadata.create_all(engine)

    with engine.begin() as conn:
        _repair_sqlite_promise_ledger_schema(conn)
        _repair_sqlite_promise_ledger_schema(conn)

    with engine.connect() as conn:
        columns = [column["name"] for column in inspect(conn).get_columns("promise_ledger_entries")]
        indexes = {index["name"] for index in inspect(conn).get_indexes("promise_ledger_entries")}

    assert columns.count("team_id") == 1
    assert columns.count("assigned_user_id") == 1
    assert columns.count("notification_sent_at") == 1
    assert "ix_promise_ledger_team_status" in indexes
