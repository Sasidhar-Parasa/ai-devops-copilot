"""
AI Service — backward-compat shim.
Delegates to llm_service.py (Groq → Gemini → rule-based).
Old callers of detect_intent_and_respond() keep working.
"""
from services.llm_service import call_llm, _rule_based as _rule_based_response

async def detect_intent_and_respond(message: str, history=None):
    """Legacy wrapper — routes to new llm_service."""
    return await call_llm(message, history or [])
