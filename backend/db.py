"""SQLite persistence layer for PatchPilot runs and events.

Provides thread-safe storage so that all run history, execution statuses,
and traces survive backend restarts without requiring external database services.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional


class Database:
    def __init__(self, db_path: str | Path = "runs/runs.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    bug_id TEXT,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    completed_at REAL,
                    result_json TEXT,
                    error_message TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_run_id ON events(run_id)"
            )
            conn.commit()

    def create_run(self, run_id: str, bug_id: Optional[str], status: str = "pending") -> None:
        now = time.time()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO runs (run_id, bug_id, status, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, bug_id, status, now),
            )
            conn.commit()

    def update_run_status(
        self,
        run_id: str,
        status: str,
        result: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> None:
        now = time.time() if status in ("completed", "failed") else None
        result_json = json.dumps(result) if result is not None else None
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE runs
                SET status = ?, completed_at = COALESCE(?, completed_at),
                    result_json = COALESCE(?, result_json),
                    error_message = COALESCE(?, error_message)
                WHERE run_id = ?
                """,
                (status, now, result_json, error, run_id),
            )
            conn.commit()

    def add_event(self, run_id: str, event: dict[str, Any]) -> None:
        event_type = event.get("type", "unknown")
        timestamp = event.get("timestamp", time.time())
        payload_json = json.dumps(event)
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO events (run_id, event_type, timestamp, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, event_type, timestamp, payload_json),
            )
            conn.commit()

    def get_run(self, run_id: str) -> Optional[dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if row is None:
                return None
            return {
                "run_id": row["run_id"],
                "bug_id": row["bug_id"],
                "status": row["status"],
                "created_at": row["created_at"],
                "completed_at": row["completed_at"],
                "result": json.loads(row["result_json"]) if row["result_json"] else None,
                "error": row["error_message"],
            }

    def get_events(self, run_id: str) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM events WHERE run_id = ? ORDER BY id ASC", (run_id,)
            ).fetchall()
            return [json.loads(row["payload_json"]) for row in rows]

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [
                {
                    "run_id": row["run_id"],
                    "bug_id": row["bug_id"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "completed_at": row["completed_at"],
                    "result": json.loads(row["result_json"]) if row["result_json"] else None,
                    "error": row["error_message"],
                }
                for row in rows
            ]
