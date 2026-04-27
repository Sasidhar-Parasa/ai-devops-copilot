"""
Logs Router
"""
import logging
from typing import Optional
from fastapi import APIRouter, Query
from services.database import get_logs

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/logs")
async def fetch_logs(
    limit: int = Query(50, ge=1, le=500),
    level: Optional[str] = Query(None, description="Filter by log level"),
    service: Optional[str] = Query(None, description="Filter by service name"),
):
    """Fetch system logs with optional filters."""
    logs = get_logs(limit=limit, level=level)
    if service:
        logs = [entry for entry in logs if entry["service"] == service]

    errors = [entry for entry in logs if entry["level"] in ("ERROR", "CRITICAL")]
    error_rate = (len(errors) / len(logs) * 100) if logs else 0

    return {
        "logs": logs,
        "total": len(logs),
        "has_errors": len(errors) > 0,
        "error_rate": round(error_rate, 2),
    }