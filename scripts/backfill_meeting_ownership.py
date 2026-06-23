#!/usr/bin/env python3
"""Backfill private meeting ownership rows for orphaned task results.

This is intentionally conservative: dry-run is the default, and write mode
requires either explicit task IDs or an explicit orphan-wide selector.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class Candidate:
    task_id: str
    task_type: str
    status: str
    created_at: str


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill meeting_ownership rows for task_results without private owners.",
    )
    parser.add_argument("--database", default="voice_to_textnote.db", help="SQLite DB path")
    parser.add_argument("--email", required=True, help="User email that should own the records")
    parser.add_argument("--task-id", action="append", default=[], help="Task ID to assign")
    parser.add_argument("--task-type", action="append", default=[], help="Task type filter")
    parser.add_argument("--status", action="append", default=[], help="Status filter")
    parser.add_argument("--created-from", help="Inclusive created_at lower bound")
    parser.add_argument("--created-to", help="Exclusive created_at upper bound")
    parser.add_argument("--limit", type=int, help="Maximum records to backfill")
    parser.add_argument(
        "--all-orphans",
        action="store_true",
        help="Allow selecting all orphaned results matching other filters",
    )
    parser.add_argument("--apply", action="store_true", help="Write ownership rows")
    return parser.parse_args(argv)


def validate_args(args: argparse.Namespace) -> None:
    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be greater than zero")
    if args.apply and not args.task_id and not args.all_orphans:
        raise ValueError("write mode requires --task-id or --all-orphans")
    if args.apply and args.all_orphans and not (
        args.task_type or args.status or args.created_from or args.created_to or args.limit
    ):
        raise ValueError("write mode with --all-orphans requires at least one narrowing filter")


def get_owner_id(conn: sqlite3.Connection, email: str) -> str:
    row = conn.execute(
        "select id from users where lower(email) = lower(?) and is_active = 1",
        (email,),
    ).fetchone()
    if row is None:
        raise ValueError(f"active user not found: {email}")
    return str(row[0])


def find_candidates(conn: sqlite3.Connection, args: argparse.Namespace) -> list[Candidate]:
    clauses = [
        "not exists ("
        "select 1 from meeting_ownership mo "
        "where mo.task_id = tr.task_id and mo.team_id is null"
        ")"
    ]
    params: list[object] = []
    if args.task_id:
        placeholders = ",".join("?" for _ in args.task_id)
        clauses.append(f"tr.task_id in ({placeholders})")
        params.extend(args.task_id)
    if args.task_type:
        placeholders = ",".join("?" for _ in args.task_type)
        clauses.append(f"tr.task_type in ({placeholders})")
        params.extend(args.task_type)
    if args.status:
        placeholders = ",".join("?" for _ in args.status)
        clauses.append(f"tr.status in ({placeholders})")
        params.extend(args.status)
    if args.created_from:
        clauses.append("tr.created_at >= ?")
        params.append(args.created_from)
    if args.created_to:
        clauses.append("tr.created_at < ?")
        params.append(args.created_to)

    sql = (
        "select tr.task_id, tr.task_type, tr.status, tr.created_at "
        "from task_results tr "
        f"where {' and '.join(clauses)} "
        "order by tr.created_at desc"
    )
    if args.limit is not None:
        sql += " limit ?"
        params.append(args.limit)

    rows = conn.execute(sql, params).fetchall()
    return [Candidate(*map(str, row)) for row in rows]


def apply_backfill(conn: sqlite3.Connection, owner_id: str, candidates: list[Candidate]) -> None:
    now = datetime.now(UTC).replace(tzinfo=None).isoformat(sep=" ")
    rows = [
        (uuid.uuid4().hex, candidate.task_id, owner_id, None, None, now)
        for candidate in candidates
    ]
    conn.executemany(
        "insert into meeting_ownership "
        "(id, task_id, owner_id, team_id, shared_at, created_at) "
        "values (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        validate_args(args)
        database_path = Path(args.database)
        if not database_path.exists():
            raise ValueError(f"database not found: {database_path}")
        conn = sqlite3.connect(database_path)
        try:
            owner_id = get_owner_id(conn, args.email)
            candidates = find_candidates(conn, args)
            print(f"owner={args.email} ({owner_id})")
            print(f"candidates={len(candidates)}")
            for candidate in candidates[:20]:
                print(
                    f"{candidate.task_id}\t{candidate.task_type}\t"
                    f"{candidate.status}\t{candidate.created_at}"
                )
            if len(candidates) > 20:
                print(f"... {len(candidates) - 20} more")
            if args.apply:
                apply_backfill(conn, owner_id, candidates)
                print(f"inserted={len(candidates)}")
            else:
                print("dry_run=true")
        finally:
            conn.close()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
