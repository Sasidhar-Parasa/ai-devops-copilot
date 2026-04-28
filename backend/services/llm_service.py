"""
LLM Service — Groq (llama3-70b-8192) → Gemini → minimal structural fallback.

Key rules:
- Every response goes through the LLM if a key is configured.
- Rule-based fallback is ONLY for when no LLM is configured at all.
- Conversation history (last 10 turns) is always passed for context.
- JSON is enforced via response_format so parsing never fails silently.
"""
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "").strip()
GROQ_MODEL     = "llama3-70b-8192"
GEMINI_MODEL   = "gemini-1.5-flash"

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
  "needs_input":    <true if you asked a follow-up question, else false>,
  "missing_fields": ["<any fields still needed, e.g. repo_url>"]
}

EXAMPLES:

User: "deploy my app"
→ {"intent":"deploy_request","response":"Sure! What's the GitHub URL of the repository you'd like to deploy?","needs_input":true,"missing_fields":["repo_url"],...}

User: "https://github.com/acme/api"
→ {"intent":"deploy_with_repo","response":"Got it — deploying **api** from `https://github.com/acme/api`. I'll clone the repo, validate the Dockerfile, build the image, and deploy to Cloud Run. Starting now...","repo_url":"https://github.com/acme/api","needs_input":false,...}

User: "What is a Dockerfile?"
→ {"intent":"general","response":"A Dockerfile is a text file containing instructions to build a Docker image...","needs_input":false,...}

User: "why did my last deploy fail?"
→ {"intent":"root_cause","response":"Let me check the recent deployment logs and error traces...","needs_input":false,...}
"""


async def call_llm(message: str, history: List[Dict[str, str]] = []) -> Dict[str, Any]:
    """
    Primary entry point. Tries Groq → Gemini → structural fallback.
    Always returns a dict with the required keys.
    """
    if not GROQ_API_KEY and not GEMINI_API_KEY:
        logger.error("No LLM configured — GROQ_API_KEY and GEMINI_API_KEY are both unset")
        return _no_llm_response()

    if GROQ_API_KEY:
        result = await _call_groq(message, history)
        if result:
            return result
        logger.error("Groq failed — trying Gemini")

    if GEMINI_API_KEY:
        result = await _call_gemini(message, history)
        if result:
            return result
        logger.error("Gemini also failed")

    # Both LLMs failed — return an honest error, not fake success
    return _llm_error_response()


# ── Groq ──────────────────────────────────────────────────────────────────────

async def _call_groq(message: str, history: List[Dict]) -> Optional[Dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in history[-10:]:
        role = turn.get("role", "user")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": turn["content"]})
    messages.append({"role": "user", "content": message})

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": messages,
                    "temperature": 0.4,
                    "max_tokens": 1024,
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
            parsed = json.loads(raw)
            parsed = _normalize(parsed)
            logger.info("Groq OK: intent=%s", parsed.get("intent"))
            return parsed
    except httpx.HTTPStatusError as exc:
        logger.error("Groq HTTP %s: %s", exc.response.status_code, exc.response.text[:300])
    except Exception as exc:  # noqa: BLE001
        logger.error("Groq error: %s", exc)
    return None


# ── Gemini ─────────────────────────────────────────────────────────────────────

async def _call_gemini(message: str, history: List[Dict]) -> Optional[Dict]:
    turns = ""
    for turn in history[-8:]:
        role = "User" if turn.get("role") == "user" else "Assistant"
        turns += f"{role}: {turn['content']}\n"

    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"{turns}"
        f"User: {message}\n\n"
        "Respond ONLY with a JSON object. No markdown fences."
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
                params={"key": GEMINI_API_KEY},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.4,
                        "maxOutputTokens": 1024,
                        "responseMimeType": "application/json",
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data["candidates"][0]["content"]["parts"][0]["text"]
            raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            parsed = _normalize(json.loads(raw))
            logger.info("Gemini OK: intent=%s", parsed.get("intent"))
            return parsed
    except httpx.HTTPStatusError as exc:
        logger.error("Gemini HTTP %s: %s", exc.response.status_code, exc.response.text[:300])
    except Exception as exc:  # noqa: BLE001
        logger.error("Gemini error: %s", exc)
    return None


# ── Response builders ──────────────────────────────────────────────────────────

def _no_llm_response() -> Dict[str, Any]:
    missing = []
    if not GROQ_API_KEY:
        missing.append("`GROQ_API_KEY`")
    if not GEMINI_API_KEY:
        missing.append("`GEMINI_API_KEY`")
    return {
        "intent": "general",
        "summary": "LLM not configured",
        "response": (
            f"⚠️ **LLM not configured.**\n\n"
            f"I need at least one API key to respond intelligently. "
            f"Please add {' or '.join(missing)} to your `.env` file and restart the server.\n\n"
            "**Free keys:**\n"
            "- Groq (recommended): https://console.groq.com\n"
            "- Gemini: https://aistudio.google.com"
        ),
        "app_name": None, "repo_url": None, "version": None,
        "needs_input": False, "missing_fields": [],
    }


def _llm_error_response() -> Dict[str, Any]:
    return {
        "intent": "general",
        "summary": "LLM temporarily unavailable",
        "response": (
            "⚠️ **I'm having trouble reaching the AI backend right now.**\n\n"
            "Both Groq and Gemini returned errors. This is usually a temporary issue. "
            "Please try again in a few seconds.\n\n"
            "If this persists, check your API keys are valid and have quota remaining."
        ),
        "app_name": None, "repo_url": None, "version": None,
        "needs_input": False, "missing_fields": [],
    }


def _normalize(data: Dict) -> Dict:
    """Ensure all expected keys exist with sensible defaults."""
    data.setdefault("intent", "general")
    data.setdefault("summary", "")
    data.setdefault("response", "")
    data.setdefault("app_name", None)
    data.setdefault("repo_url", None)
    data.setdefault("version", None)
    data.setdefault("needs_input", False)
    data.setdefault("missing_fields", [])

    # Validate and extract repo URL if LLM missed it
    if not data["repo_url"]:
        data["repo_url"] = extract_github_url(data.get("response", ""))

    return data


# ── Helpers ────────────────────────────────────────────────────────────────────

def extract_github_url(text: str) -> Optional[str]:
    m = re.search(r"https?://github\.com/[^\s\"'<>)\]]+", text)
    return m.group(0).rstrip("/.,)") if m else None
