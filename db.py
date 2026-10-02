"""SQLite-backed storage for locker occupancy and the action audit log.

This is the server's single source of truth for who has what package where —
the frontend no longer keeps its own authoritative copy in localStorage.
"""
import sqlite3
import threading
from datetime import datetime, timezone

import config

_lock = threading.Lock()


def get_connection():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _lock, get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bays (
                id INTEGER PRIMARY KEY,
                occupied INTEGER NOT NULL DEFAULT 0,
                customer_email TEXT,
                pickup_code TEXT,
                code_created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL
            )
        """)
        # Idempotent: adds any bays missing up to NUM_LOCKERS without
        # touching existing rows, so bumping the locker count for a bigger
        # site is just a config change.
        conn.executemany(
            "INSERT OR IGNORE INTO bays (id, occupied) VALUES (?, 0)",
            [(i,) for i in range(1, config.NUM_LOCKERS + 1)],
        )
        conn.commit()


def log_event(level, message):
    with _lock, get_connection() as conn:
        conn.execute(
            "INSERT INTO events (ts, level, message) VALUES (?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), level, message),
        )
        conn.commit()


def get_all_bays():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM bays ORDER BY id").fetchall()
        return [dict(row) for row in rows]


def get_bay(bay_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM bays WHERE id = ?", (bay_id,)).fetchone()
        return dict(row) if row else None


def get_bay_by_code(code):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM bays WHERE pickup_code = ? AND occupied = 1", (code,)
        ).fetchone()
        return dict(row) if row else None


def stage_deposit(bay_id, email, pickup_code):
    """Records a pending deposit (door opened, not yet confirmed closed)."""
    with _lock, get_connection() as conn:
        conn.execute(
            "UPDATE bays SET customer_email = ?, pickup_code = ?, code_created_at = ? WHERE id = ?",
            (email, pickup_code, datetime.now(timezone.utc).isoformat(), bay_id),
        )
        conn.commit()


def confirm_deposit(bay_id):
    """Marks a staged deposit as occupied once the door is confirmed closed."""
    with _lock, get_connection() as conn:
        conn.execute("UPDATE bays SET occupied = 1 WHERE id = ?", (bay_id,))
        conn.commit()


def clear_bay(bay_id):
    with _lock, get_connection() as conn:
        conn.execute(
            "UPDATE bays SET occupied = 0, customer_email = NULL, pickup_code = NULL, code_created_at = NULL WHERE id = ?",
            (bay_id,),
        )
        conn.commit()
