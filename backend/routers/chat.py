"""
Chat Router — Main conversational AI endpoint.
"""
import logging

from fastapi import APIRouter, HTTPException

from models.schemas import ChatRequest, ChatResponse
from agents.coordinator import CoordinatorAgent

logger = logging.getLogger(__name__)
router = APIRouter()
coordinator = CoordinatorAgent()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Routes natural language through the multi-agent system."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    logger.info("[CHAT] session=%s msg=%r", request.session_id, request.message[:80])
    response = await coordinator.process(request)
    logger.info("[CHAT] intent=%s agents=%d", response.intent, len(response.agents_used))
    return response


@router.get("/session/{session_id}")
async def get_session_info(session_id: str):
    """Get current session state."""
    from services.session_manager import get_session
    session = get_session(session_id)
    return {
        "session_id": session_id,
        "pending_intent": session.get("pending_intent"),
        "pending_app_name": session.get("pending_app_name"),
        "has_pending_deploy": session.get("pending_intent") == "deploy_request",
    }
