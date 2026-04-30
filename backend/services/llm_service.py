"""
LLM Service — Groq → Gemini → honest error.

FIXED:
- Model changed from llama3-70b-8192 → llama-3.3-70b-versatile (current Groq model)
- Added explicit dotenv load in case module is imported before main.py runs
- Added model fallback list so if one model is deprecated, next one is tried
- Better error logging showing exact HTTP status and message from Groq
"""
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

# Ensure .env is loaded even if this module is imported standalone (e.g. tests)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import httpx

logger = logging.getLogger(__name__)

GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "").strip()

# ── Groq model priority list ──────────────────────────────────────────────────
# Try models in order; first one that works wins.
# llama-3.3-70b-versatile is the current recommended model on Groq playground.
GROQ_MODELS = [
    "llama-3.3-70b-versatile",     # Current — matches Groq playground
    "llama3-70b-8192",             # Older alias (may still work)
    "llama-3.1-70b-versatile",     # Previous version
    "llama3-8b-8192",              # Fallback to smaller model
]

GEMINI_MODEL = "gemini-1.5-flash"

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a senior DevOps engineer and AI assistant helping users \
deploy and debug applications on Google Cloud Platform.

PERSONALITY:
- Conversational, helpful, and precise — like a knowledgeable colleague.
- Ask follow-up questions naturally when information is missing.
- Never show a static list of capabilities unless explicitly asked.
- Answer general questions (e.g. "What is Docker?") directly and helpfully.

DEPLOYMENT FLOW:
- If user wants to deploy but hasn't given a GitHub URL, ask for it naturally.
- Once you have a GitHub URL, confirm the plan and proceed.
- If deployment fails, explain the exact error clearly.

INTENT TYPES (pick the best fit):
  deploy_request   — wants to deploy, no repo URL yet
  deploy_with_repo — has provided a GitHub URL
  rollback         — wants to revert an app to previous version
  status           — asking about system or service health
  logs             — wants recent logs or error traces
  incident         — asking about active incidents or alerts
  root_cause       — asking why something failed (RCA)
  fix              — wants auto-remediation applied
  general          — anything else (questions, greetings, explanations)

RESPONSE FORMAT — always return valid JSON:
{
  "intent":         "<intent type>",
  "summary":        "<one-line description of what you understood>",
  "response":       "<your natural language reply in Markdown>",
  "app_name":       "<extracted app/service name, or null>",
  "repo_url":       "<full GitHub URL if user provided one, else null>",
  "version":        "<version tag if mentioned, else null>",
  "needs_input":    <true if you need more info from the user, else false>,
  "missing_fields": ["<any fields still needed>"]
}"""


async def call_llm(message: str, history: List[Dict[str, str]] = []) -> Dict[str, Any]:
    """Try Groq → Gemini → honest error message. Never silently fails."""

    # Reload keys in case .env was updated after import
    groq_key   = os.getenv("GROQ_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

    if not groq_key and not gemini_key:
        logger.error("No LLM API key configured (GROQ_API_KEY and GEMINI_API_KEY are both empty)")
        return _no_llm_response()

    if groq_key:
        result = await _call_groq(message, history, groq_key)
        if result:
            return result
        logger.error("All Groq models failed — trying Gemini next")

    if gemini_key:
        result = await _call_gemini(message, history, gemini_key)
        if result:
            return result
        logger.error("Gemini also failed")

    return _llm_error_response()


# ── Groq ──────────────────────────────────────────────────────────────────────

async def _call_groq(message: str, history: List[Dict], api_key: str) -> Optional[Dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in history[-10:]:
        role = turn.get("role", "user")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": str(turn["content"])})
    messages.append({"role": "user", "content": message})

    # Try each model in priority order
    for model in GROQ_MODELS:
        result = await _groq_request(messages, model, api_key)
        if result is not None:
            logger.info("✅ Groq success: model=%s intent=%s", model, result.get("intent"))
            return result

    return None


async def _groq_request(messages: List[Dict], model: str, api_key: str) -> Optional[Dict]:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.4,
                    "max_tokens": 1024,
                    "response_format": {"type": "json_object"},
                },
            )

            if resp.status_code == 404:
                logger.warning("Groq model not found: %s — trying next", model)
                return None

            if resp.status_code == 429:
                logger.error("Groq rate limit hit for model %s", model)
                return None

            if resp.status_code != 200:
                logger.error("Groq HTTP %s for model %s: %s",
                             resp.status_code, model, resp.text[:300])
                return None

            raw     = resp.json()["choices"][0]["message"]["content"]
            parsed  = json.loads(raw)
            return _normalize(parsed)

    except json.JSONDecodeError as exc:
        logger.error("Groq returned invalid JSON for model %s: %s", model, exc)
        return None
    except httpx.ConnectError:
        logger.error("Cannot connect to Groq API — check network")
        return None
    except Exception as exc:  # noqa: BLE001
        logger.error("Groq unexpected error (model=%s): %s", model, exc)
        return None


# ── Gemini ─────────────────────────────────────────────────────────────────────

async def _call_gemini(message: str, history: List[Dict], api_key: str) -> Optional[Dict]:
    turns = ""
    for turn in history[-8:]:
        role = "User" if turn.get("role") == "user" else "Assistant"
        turns += f"{role}: {turn['content']}\n"

    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"{turns}"
        f"User: {message}\n\n"
        "Respond ONLY with a JSON object matching the schema above. No markdown fences."
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
                params={"key": api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.4,
                        "maxOutputTokens": 1024,
                        "responseMimeType": "application/json",
                    },
                },
            )

            if resp.status_code != 200:
                logger.error("Gemini HTTP %s: %s", resp.status_code, resp.text[:300])
                return None

            data = resp.json()
            raw  = data["candidates"][0]["content"]["parts"][0]["text"]
            raw  = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            return _normalize(json.loads(raw))

    except json.JSONDecodeError as exc:
        logger.error("Gemini returned invalid JSON: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.error("Gemini error: %s", exc)
        return None


# ── Response builders ──────────────────────────────────────────────────────────

def _no_llm_response() -> Dict[str, Any]:
    return {
        "intent":   "general",
        "summary":  "LLM not configured",
        "response": (
            "⚠️ **LLM not configured.**\n\n"
            "I need an API key to respond intelligently.\n\n"
            "**Quick fix:**\n"
            "1. Get a free key at https://console.groq.com\n"
            "2. Add it to `backend/.env`:\n"
            "   ```\n"
            "   GROQ_API_KEY=gsk_...\n"
            "   ```\n"
            "3. Restart the server: `uvicorn main:app --reload`"
        ),
        "app_name": None, "repo_url": None, "version": None,
        "needs_input": False, "missing_fields": [],
    }


def _llm_error_response() -> Dict[str, Any]:
    return {
        "intent":   "general",
        "summary":  "LLM temporarily unavailable",
        "response": (
            "⚠️ **AI backend temporarily unavailable.**\n\n"
            "Both Groq and Gemini returned errors. "
            "Check the backend logs for details:\n"
            "```bash\n"
            "uvicorn main:app --reload  # watch the terminal output\n"
            "```\n\n"
            "Common causes:\n"
            "- Invalid or expired API key\n"
            "- Rate limit exceeded\n"
            "- Network connectivity issue"
        ),
        "app_name": None, "repo_url": None, "version": None,
        "needs_input": False, "missing_fields": [],
    }


def _normalize(data: Dict) -> Dict:
    data.setdefault("intent",        "general")
    data.setdefault("summary",       "")
    data.setdefault("response",      "")
    data.setdefault("app_name",      None)
    data.setdefault("repo_url",      None)
    data.setdefault("version",       None)
    data.setdefault("needs_input",   False)
    data.setdefault("missing_fields", [])

    # Extract repo URL from response text if LLM forgot to put it in the field
    if not data["repo_url"]:
        data["repo_url"] = extract_github_url(data.get("response", ""))

    return data


def extract_github_url(text: str) -> Optional[str]:
    m = re.search(r"https?://github\.com/[^\s\"'<>)\]]+", text or "")
    return m.group(0).rstrip("/.,)") if m else None