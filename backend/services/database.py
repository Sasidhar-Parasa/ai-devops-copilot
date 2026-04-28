"""
SQLite Database Service — stores only real deployments, no seeded demo data.
"""
import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("TEST_DB_PATH", "./data/copilot.db"))


def get_conn() -> sqlite3.Connection:
    if "TEST_DB_PATH" not in os.environ:
        DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS deployments (
            id            TEXT PRIMARY KEY,
            app_name      TEXT NOT NULL,
            version       TEXT NOT NULL,
            environment   TEXT NOT NULL DEFAULT 'production',
            status        TEXT NOT NULL,
            stages        TEXT NOT NULL DEFAULT '[]',
            created_at    TEXT NOT NULL,
            completed_at  TEXT,
            triggered_by  TEXT DEFAULT 'user',
            error_message TEXT,
            service_url   TEXT DEFAULT '',
            repo_url      TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS logs (
            id        TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            level     TEXT NOT NULL,
            service   TEXT NOT NULL,
            message   TEXT NOT NULL,
            metadata  TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS incidents (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            severity    TEXT NOT NULL,
            status      TEXT NOT NULL,
            service     TEXT NOT NULL,
            description TEXT NOT NULL,
            root_cause  TEXT,
            fix_applied TEXT,
            created_at  TEXT NOT NULL,
            resolved_at TEXT
        );
    """)
    conn.commit()
    conn.close()
    logger.info("Database ready: %s", DB_PATH)


# ── Deployments ────────────────────────────────────────────────────────────────

def save_deployment(dep: Dict[str, Any]):
    dep.setdefault("service_url", "")
    dep.setdefault("repo_url", "")
    conn = get_conn()
    # Add columns if they didn't exist before
    try:
        conn.execute("ALTER TABLE deployments ADD COLUMN service_url TEXT DEFAULT ''")
        conn.commit()
    except Exception:  # noqa: BLE001
        pass
    try:
        conn.execute("ALTER TABLE deployments ADD COLUMN repo_url TEXT DEFAULT ''")
        conn.commit()
    except Exception:  # noqa: BLE001
        pass

    conn.execute(
        """INSERT OR REPLACE INTO deployments
           (id, app_name, version, environment, status, stages,
            created_at, completed_at, triggered_by, error_message, service_url, repo_url)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            dep["id"], dep["app_name"], dep["version"],
            dep.get("environment", "production"), dep["status"],
            dep.get("stages", "[]"),
            dep["created_at"], dep.get("completed_at"),
            dep.get("triggered_by", "user"), dep.get("error_message"),
            dep.get("service_url", ""), dep.get("repo_url", ""),
        ),
    )
    conn.commit()
    conn.close()


def get_deployments(limit: int = 20) -> List[Dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM deployments ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    result = []
    for row in rows:
        d = dict(row)
        if isinstance(d.get("stages"), str):
            try:
                d["stages"] = json.loads(d["stages"])
            except Exception:  # noqa: BLE001
                d["stages"] = []
        result.append(d)
    return result


# ── Logs (from real Cloud Run — written on deploy events) ──────────────────────

def append_log(level: str, service: str, message: str):
    import uuid
    conn = get_conn()
    conn.execute(
        "INSERT INTO logs VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), datetime.utcnow().isoformat(), level, service, message, "{}"),
    )
    conn.commit()
    conn.close()


def get_logs(limit: int = 100, level: Optional[str] = None) -> List[Dict]:
    conn = get_conn()
    if level:
        rows = conn.execute(
            "SELECT * FROM logs WHERE level=? ORDER BY timestamp DESC LIMIT ?",
            (level.upper(), limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM logs ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_log(entry: Dict):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO logs VALUES (:id,:timestamp,:level,:service,:message,:metadata)",
        entry,
    )
    conn.commit()
    conn.close()


# ── Incidents ──────────────────────────────────────────────────────────────────

def get_incidents(status: Optional[str] = None) -> List[Dict]:
    conn = get_conn()
    if status:
        rows = conn.execute(
            "SELECT * FROM incidents WHERE status=? ORDER BY created_at DESC", (status,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM incidents ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_incident(inc: Dict):
    conn = get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO incidents
           VALUES (:id,:title,:severity,:status,:service,:description,
                   :root_cause,:fix_applied,:created_at,:resolved_at)""",
        inc,
    )
    conn.commit()
    conn.close()
