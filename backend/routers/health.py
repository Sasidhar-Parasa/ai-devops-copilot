"""
Health Router — Real GCP + simulated health data
"""
import logging
from fastapi import APIRouter
from services.database import get_incidents

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def system_health():
    """System health — real GCP if configured, else simulated."""
    try:
        from services.gcp_monitor import get_real_system_health
        return await get_real_system_health()
    except Exception as e:
        logger.warning(f"GCP health failed, using simulated: {e}")
        from agents.monitoring_agent import MonitoringAgent
        return await MonitoringAgent().get_system_health()


@router.get("/incidents")
async def list_incidents(status: str = None):
    incidents = get_incidents(status=status)
    return {
        "incidents": incidents,
        "total": len(incidents),
        "open": len([i for i in incidents if i["status"] in ("open", "investigating")]),
    }


@router.get("/ping")
async def ping():
    import os
    return {
        "status": "ok",
        "service": "ai-devops-copilot",
        "llm": "groq" if os.getenv("GROQ_API_KEY") else ("gemini" if os.getenv("GEMINI_API_KEY") else "rule-based"),
        "gcp_project": os.getenv("GCP_PROJECT_ID", "not-configured"),
    }
