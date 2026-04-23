"""
Monitoring Agent – Fetches logs, metrics, and system health
"""
import logging
import random
from datetime import datetime
from typing import Any, Dict

from services.database import get_logs, get_incidents

logger = logging.getLogger(__name__)

SERVICES = [
    "api-gateway",
    "auth-service",
    "payment-service",
    "myapp",
    "database",
]


class MonitoringAgent:
    async def run(self) -> Dict[str, Any]:
        logs = get_logs(limit=50)
        errors = [l for l in logs if l["level"] in ("ERROR", "CRITICAL")]
        warnings = [l for l in logs if l["level"] == "WARN"]

        total = len(logs)
        error_rate = (len(errors) / total * 100) if total else 0

        return {
            "log_count": total,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "error_rate": round(error_rate, 2),
            "recent_errors": errors[:5],
            "recent_logs": logs[:10],
        }

    async def get_system_health(self) -> Dict[str, Any]:
        incidents = get_incidents(status="open")
        incidents += get_incidents(status="investigating")

        services = []
        for svc in SERVICES:
            # Degrade payment-service if there's an active incident
            is_degraded = svc == "payment-service" and len(incidents) > 0
            status = "degraded" if is_degraded else "healthy"
            cpu = random.uniform(60, 90) if is_degraded else random.uniform(15, 45)
            mem = random.uniform(70, 85) if is_degraded else random.uniform(30, 60)
            err_rate = random.uniform(15, 25) if is_degraded else random.uniform(0, 1.5)
            latency = random.uniform(800, 1200) if is_degraded else random.uniform(40, 120)

            services.append({
                "service": svc,
                "status": status,
                "uptime_pct": round(random.uniform(97, 99.9) if not is_degraded else random.uniform(88, 95), 2),
                "cpu_pct": round(cpu, 1),
                "memory_pct": round(mem, 1),
                "request_rate": round(random.uniform(100, 500), 1),
                "error_rate": round(err_rate, 2),
                "latency_p99_ms": round(latency, 1),
            })

        overall = "degraded" if any(s["status"] == "degraded" for s in services) else "healthy"

        return {
            "overall": overall,
            "services": services,
            "active_incidents": len(incidents),
            "deployments_today": 3,
            "success_rate": round(random.uniform(85, 99), 1),
            "timestamp": datetime.utcnow().isoformat(),
        }
