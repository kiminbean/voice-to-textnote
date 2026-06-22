from sqlalchemy import Column, MetaData, String, Table, create_engine, inspect

from backend.app.lifecycle import _repair_sqlite_auth_schema


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
