"""
Chat Router — Main conversational AI endpoint
Handles streaming responses for long-running deployments
"""
import json
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from models.schemas import ChatRequest, ChatResponse
from agents.coordinator import CoordinatorAgent

logger = logging.getLogger(__name__)
router = APIRouter()
coordinator = CoordinatorAgent()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main conversational endpoint.
    Routes natural language through the multi-agent system.
    """
    try:
        if not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        logger.info(f"[CHAT] session={request.session_id} msg={request.message[:80]!r}")
        response = await coordinator.process(request)
        logger.info(f"[CHAT] intent={response.intent} agents={len(response.agents_used)}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}")
async def get_session_info(session_id: str):
    """Get current session state (useful for frontend to show pending deploy context)."""
    from services.session_manager import get_session
    session = get_session(session_id)
    return {
        "session_id": session_id,
        "pending_intent": session.get("pending_intent"),
        "pending_app_name": session.get("pending_app_name"),
        "has_pending_deploy": session.get("pending_intent") == "deploy_request",
    }
