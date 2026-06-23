import sqlite3

from scripts.backfill_meeting_ownership import main


def create_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        create table users (
            id char(32) primary key,
            email varchar(255) not null,
            is_active boolean not null,
            created_at datetime
        );
        create table task_results (
            id char(32) primary key,
            task_id varchar(255) not null,
            task_type varchar(50) not null,
            status varchar(20) not null,
            created_at datetime not null
        );
        create table meeting_ownership (
            id char(32) primary key,
            task_id varchar(255) not null,
            owner_id char(32) not null,
            team_id char(32),
            shared_at datetime,
            created_at datetime not null
        );
        """
    )
    conn.execute(
        "insert into users (id, email, is_active, created_at) values (?, ?, 1, ?)",
        ("8a27b69fd5e6487498d8cbd3fc716f9a", "t@test.com", "2026-06-22"),
    )
    conn.execute(
        "insert into task_results (id, task_id, task_type, status, created_at) "
        "values (?, ?, ?, ?, ?)",
        ("task-row-1", "task-1", "summary", "completed", "2026-06-22 10:00:00"),
    )
    conn.execute(
        "insert into task_results (id, task_id, task_type, status, created_at) "
        "values (?, ?, ?, ?, ?)",
        ("task-row-2", "task-2", "summary", "failed", "2026-06-22 11:00:00"),
    )
    conn.commit()
    conn.close()


def ownership_count(path):
    conn = sqlite3.connect(path)
    try:
        return conn.execute("select count(*) from meeting_ownership").fetchone()[0]
    finally:
        conn.close()


def test_backfill_defaults_to_dry_run(tmp_path, capsys):
    db_path = tmp_path / "app.db"
    create_db(db_path)

    result = main(
        [
            "--database",
            str(db_path),
            "--email",
            "t@test.com",
            "--task-id",
            "task-1",
        ]
    )

    assert result == 0
    assert ownership_count(db_path) == 0
    assert "dry_run=true" in capsys.readouterr().out


def test_backfill_apply_requires_explicit_selector(tmp_path, capsys):
    db_path = tmp_path / "app.db"
    create_db(db_path)

    result = main(["--database", str(db_path), "--email", "t@test.com", "--apply"])

    assert result == 2
    assert ownership_count(db_path) == 0
    assert "requires --task-id or --all-orphans" in capsys.readouterr().err


def test_backfill_applies_selected_orphan(tmp_path):
    db_path = tmp_path / "app.db"
    create_db(db_path)

    result = main(
        [
            "--database",
            str(db_path),
            "--email",
            "t@test.com",
            "--task-type",
            "summary",
            "--status",
            "completed",
            "--all-orphans",
            "--apply",
        ]
    )

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "select task_id, owner_id, team_id from meeting_ownership"
        ).fetchall()
    finally:
        conn.close()

    assert result == 0
    assert rows == [("task-1", "8a27b69fd5e6487498d8cbd3fc716f9a", None)]
