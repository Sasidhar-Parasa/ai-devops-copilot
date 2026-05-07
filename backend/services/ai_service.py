"""
AI Service — backward-compat shim.
Delegates to llm_service.py (Groq → Gemini → honest error).
"""
from services.llm_service import call_llm


async def detect_intent_and_respond(message: str, history=None):
    """Legacy wrapper — routes to new llm_service."""
    return await call_llm(message, history or [])
