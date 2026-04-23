"""
Incident Agent – Detects and triages anomalies
"""
import logging
import uuid
from datetime import datetime
from typing import Any, Dict

from services.database import get_incidents, save_incident

logger = logging.getLogger(__name__)


class IncidentAgent:
    async def run(self) -> Dict[str, Any]:
        incidents = get_incidents()
        open_incidents = [i for i in incidents if i["status"] in ("open", "investigating")]
        critical = [i for i in open_incidents if i["severity"] == "critical"]
        high = [i for i in open_incidents if i["severity"] == "high"]

        # Auto-detect new incidents from patterns
        from services.database import get_logs
        logs = get_logs(limit=20)
        errors = [l for l in logs if l["level"] in ("ERROR", "CRITICAL")]

        return {
            "incidents": incidents,
            "open_count": len(open_incidents),
            "critical_count": len(critical),
            "high_count": len(high),
            "recent_errors": errors[:3],
        }
