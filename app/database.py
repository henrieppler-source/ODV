from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from .config import DB_FILE, ensure_app_dir
from .models import HistoryEntry


def connect() -> sqlite3.Connection:
    ensure_app_dir()
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_display_name TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT NOT NULL,
                upload_id TEXT
            )
            """
        )
        conn.commit()


def add_history(entry: HistoryEntry) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO history (timestamp, user_display_name, action, details, upload_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (entry.timestamp, entry.user_display_name, entry.action, entry.details, entry.upload_id),
        )
        conn.commit()


def list_history(limit: int = 200) -> list[HistoryEntry]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT timestamp, user_display_name, action, details, upload_id
            FROM history
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        HistoryEntry(
            timestamp=row["timestamp"],
            user_display_name=row["user_display_name"],
            action=row["action"],
            details=row["details"],
            upload_id=row["upload_id"],
        )
        for row in rows
    ]
