"""
SQLite Database Service
"""
import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Tests override this via TEST_DB_PATH env var (set in conftest.py before import)
DB_PATH = Path(os.getenv("TEST_DB_PATH", "./data/copilot.db"))


def get_conn() -> sqlite3.Connection:
    # Only create parent dir for the real DB, not temp test files
    if "TEST_DB_PATH" not in os.environ:
        DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS deployments (
            id          TEXT PRIMARY KEY,
            app_name    TEXT NOT NULL,
            version     TEXT NOT NULL,
            environment TEXT NOT NULL,
            status      TEXT NOT NULL,
            stages      TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            completed_at TEXT,
            triggered_by TEXT DEFAULT 'user',
            error_message TEXT
        );

        CREATE TABLE IF NOT EXISTS logs (
            id          TEXT PRIMARY KEY,
            timestamp   TEXT NOT NULL,
            level       TEXT NOT NULL,
            service     TEXT NOT NULL,
            message     TEXT NOT NULL,
            metadata    TEXT DEFAULT '{}'
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

        CREATE TABLE IF NOT EXISTS chat_sessions (
            id          TEXT PRIMARY KEY,
            session_id  TEXT NOT NULL,
            role        TEXT NOT NULL,
            content     TEXT NOT NULL,
            agent       TEXT,
            timestamp   TEXT NOT NULL
        );
    """)

    conn.commit()
    conn.close()
    logger.info("Database tables ready")

    _seed_sample_data()


def _seed_sample_data():
    """Seed realistic sample data for demo."""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM logs")
    if cur.fetchone()[0] > 0:
        conn.close()
        return

    import uuid
    from datetime import timedelta

    now = datetime.utcnow()

    sample_logs = [
        ("INFO",     "api-gateway",     "Request processed: POST /api/deploy [200] 142ms"),
        ("INFO",     "auth-service",    "JWT token validated for user: admin@devops.io"),
        ("WARN",     "payment-service", "Response time elevated: 892ms (threshold: 500ms)"),
        ("ERROR",    "payment-service", "Database connection timeout after 30s retries"),
        ("INFO",     "deploy-agent",    "Build pipeline started: myapp v2.4.1"),
        ("INFO",     "deploy-agent",    "Docker image built successfully: myapp:2.4.1"),
        ("INFO",     "deploy-agent",    "Unit tests passed: 247/247"),
        ("ERROR",    "deploy-agent",    "Integration test failed: TestCheckoutFlow - assertion error"),
        ("WARN",     "monitoring",      "CPU usage spike detected: payment-service 87%"),
        ("CRITICAL", "incident-agent",  "Service degradation detected: payment-service error rate 23%"),
        ("INFO",     "fix-agent",       "Auto-scaling triggered: payment-service replicas 2→4"),
        ("INFO",     "api-gateway",     "Health check: all services nominal"),
        ("INFO",     "auth-service",    "OAuth2 callback successful for github integration"),
        ("WARN",     "database",        "Slow query detected: SELECT * FROM orders (2.3s)"),
        ("INFO",     "deploy-agent",    "Rollback initiated: payment-service v2.3.9→v2.3.8"),
    ]

    for i, (level, service, message) in enumerate(sample_logs):
        ts = (now - timedelta(minutes=len(sample_logs) - i)).isoformat()
        cur.execute(
            "INSERT INTO logs VALUES (?,?,?,?,?,?)",
            (str(uuid.uuid4()), ts, level, service, message, "{}"),
        )

    stages_success = json.dumps([
        {"name": "Build",  "status": "success", "duration_seconds": 47},
        {"name": "Test",   "status": "success", "duration_seconds": 123},
        {"name": "Deploy", "status": "success", "duration_seconds": 34},
    ])
    stages_failed = json.dumps([
        {"name": "Build",  "status": "success", "duration_seconds": 52},
        {"name": "Test",   "status": "failed",  "duration_seconds": 89},
        {"name": "Deploy", "status": "pending", "duration_seconds": None},
    ])

    cur.execute("INSERT INTO deployments VALUES (?,?,?,?,?,?,?,?,?,?)", (
        "dep-001", "myapp", "v2.4.0", "production", "success",
        stages_success,
        (now - timedelta(hours=3)).isoformat(),
        (now - timedelta(hours=2, minutes=57)).isoformat(),
        "user", None,
    ))
    cur.execute("INSERT INTO deployments VALUES (?,?,?,?,?,?,?,?,?,?)", (
        "dep-002", "payment-service", "v2.4.1", "production", "failed",
        stages_failed,
        (now - timedelta(hours=1)).isoformat(),
        (now - timedelta(minutes=50)).isoformat(),
        "CI/CD", "Integration test TestCheckoutFlow failed",
    ))

    cur.execute("INSERT INTO incidents VALUES (?,?,?,?,?,?,?,?,?,?)", (
        "inc-001",
        "Payment Service Degradation",
        "high", "investigating", "payment-service",
        "Error rate spiked to 23% following v2.4.1 deployment failure.",
        "Integration test regression in checkout flow introduced in v2.4.1",
        None,
        (now - timedelta(minutes=55)).isoformat(),
        None,
    ))

    conn.commit()
    conn.close()
    logger.info("Sample data seeded")


# ── CRUD Helpers ──────────────────────────────────────────────────────────────

def save_deployment(dep: dict):
    conn = get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO deployments
           VALUES (:id,:app_name,:version,:environment,:status,:stages,
                   :created_at,:completed_at,:triggered_by,:error_message)""",
        dep,
    )
    conn.commit()
    conn.close()


def get_deployments(limit: int = 20) -> List[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM deployments ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_logs(limit: int = 100, level: Optional[str] = None) -> List[dict]:
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


def save_log(entry: dict):
    conn = get_conn()
    conn.execute(
        "INSERT INTO logs VALUES (:id,:timestamp,:level,:service,:message,:metadata)",
        entry,
    )
    conn.commit()
    conn.close()


def get_incidents(status: Optional[str] = None) -> List[dict]:
    conn = get_conn()
    if status:
        rows = conn.execute(
            "SELECT * FROM incidents WHERE status=? ORDER BY created_at DESC", (status,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM incidents ORDER BY created_at DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_incident(inc: dict):
    conn = get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO incidents
           VALUES (:id,:title,:severity,:status,:service,:description,
                   :root_cause,:fix_applied,:created_at,:resolved_at)""",
        inc,
    )
    conn.commit()
    conn.close()