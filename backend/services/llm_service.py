"""
LLM Service — Groq (llama3-70b) → Gemini → Rule-based fallback
No OpenAI dependency. All free-tier providers.
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_MODEL     = "llama3-70b-8192"
GEMINI_MODEL   = "gemini-1.5-flash"

# ── System prompt for the DevOps Copilot ─────────────────────────────────────
SYSTEM_PROMPT = """You are an expert AI DevOps Copilot. You behave like GitHub Copilot for infrastructure.

CORE BEHAVIOUR RULES:
1. When a user asks to "deploy" something and hasn't provided a GitHub repo URL, ask for it conversationally.
2. When they provide a repo, acknowledge and confirm what you will do next.
3. Always be specific about what is missing before taking action.
4. Detect intent precisely from natural language.

INTENT TYPES (always return one of these):
- deploy_request   → user wants to deploy but hasn't given repo yet → ask for it
- deploy_with_repo → user provided a GitHub URL → proceed with deployment
- rollback         → user wants to rollback an app
- status           → user wants system/service health
- logs             → user wants to see logs
- incident         → user asking about alerts/incidents
- root_cause       → user asking why something failed
- fix              → user wants auto-remediation
- general          → anything else

CONVERSATIONAL EXAMPLES:
User: "deploy myapp"
→ intent: deploy_request, ask for GitHub repo URL

User: "deploy https://github.com/user/myapp"  
→ intent: deploy_with_repo, extract repo_url

User: "here's the repo: https://github.com/acme/api"
→ intent: deploy_with_repo, extract repo_url

ALWAYS respond in this exact JSON format:
{
  "intent": "<one of the intent types above>",
  "summary": "<one line of what you understood>",
  "response": "<your markdown response to the user — be conversational and helpful>",
  "app_name": "<extracted app name or null>",
  "repo_url": "<full GitHub URL if provided, else null>",
  "version": "<version tag if mentioned, else null>",
  "needs_input": true/false,
  "missing_fields": ["<list of what is still needed, e.g. repo_url>"]
}"""


async def call_llm(message: str, history: List[Dict[str, str]] = []) -> Dict[str, Any]:
    """Try Groq → Gemini → rule-based fallback."""
    if GROQ_API_KEY:
        result = await _call_groq(message, history)
        if result:
            return result

    if GEMINI_API_KEY:
        result = await _call_gemini(message, history)
        if result:
            return result

    logger.warning("No LLM available — using rule-based fallback")
    return _rule_based(message)


# ── Groq ─────────────────────────────────────────────────────────────────────

async def _call_groq(message: str, history: List[Dict]) -> Optional[Dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in history[-8:]:
        messages.append({"role": h["role"], "content": h["content"]})
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
                    "temperature": 0.2,
                    "max_tokens": 1024,
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            logger.info(f"Groq response: intent={parsed.get('intent')}")
            return parsed
    except Exception as e:
        logger.warning(f"Groq failed: {e}")
        return None


# ── Gemini ───────────────────────────────────────────────────────────────────

async def _call_gemini(message: str, history: List[Dict]) -> Optional[Dict]:
    # Build conversation for Gemini
    history_text = ""
    for h in history[-6:]:
        role = "User" if h["role"] == "user" else "Assistant"
        history_text += f"{role}: {h['content']}\n"

    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"{history_text}"
        f"User: {message}\n\n"
        "Respond ONLY with valid JSON matching the schema above."
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
                params={"key": GEMINI_API_KEY},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.2,
                        "maxOutputTokens": 1024,
                        "responseMimeType": "application/json",
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data["candidates"][0]["content"]["parts"][0]["text"]
            # Strip possible markdown fences
            raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            parsed = json.loads(raw)
            logger.info(f"Gemini response: intent={parsed.get('intent')}")
            return parsed
    except Exception as e:
        logger.warning(f"Gemini failed: {e}")
        return None


# ── Rule-based fallback ───────────────────────────────────────────────────────

def _rule_based(message: str) -> Dict[str, Any]:
    msg = message.lower().strip()
    repo_url = _extract_github_url(message)

    # Priority: RCA before deploy (avoid substring conflicts)
    if any(w in msg for w in ["why did", "why is", "root cause", "rca", "reason", "investigate"]):
        return _resp("root_cause", "Root cause analysis requested",
            "## \U0001f50d Root Cause Analysis\n\nAnalyzing failure signals...\n\n"
            "1. **Log correlation** — matching error spikes with deploys\n"
            "2. **Metric diff** — comparing before/after\n"
            "3. **Change audit** — what changed recently?\n\nReport incoming...")

    if any(w in msg for w in ["rollback", "revert", "undo"]):
        app = _extract_app(msg)
        return _resp("rollback", f"Rolling back {app}",
            f"## \u23ea Rollback\n\nRolling **{app}** back to last stable version...",
            app_name=app)

    if repo_url or ("deploy" in msg and ("http" in msg or "github" in msg)):
        app = _extract_app(msg) or _app_from_url(repo_url)
        return {
            "intent": "deploy_with_repo",
            "summary": f"Deploying from {repo_url}",
            "response": (
                f"## \U0001f680 Deployment Starting\n\n"
                f"Got it! I'll deploy from:\n`{repo_url}`\n\n"
                "**Running:**\n"
                "1. \U0001f4e5 Clone repository\n"
                "2. \u2705 Validate Dockerfile\n"
                "3. \U0001f40b Build Docker image\n"
                "4. \u2601\ufe0f Push to Artifact Registry\n"
                "5. \U0001f680 Deploy to Cloud Run\n\nStarting now..."
            ),
            "app_name": app,
            "repo_url": repo_url,
            "version": _extract_version(msg),
            "needs_input": False,
            "missing_fields": [],
        }

    if "deploy" in msg or "release" in msg or "ship" in msg:
        app = _extract_app(msg)
        return {
            "intent": "deploy_request",
            "summary": "Deploy requested — need GitHub repo",
            "response": (
                f"## \U0001f680 Let's Deploy Your App!\n\n"
                f"I can deploy **{app or 'your application'}** to Google Cloud Run.\n\n"
                "To get started, I need:\n\n"
                "1. \U0001f517 **GitHub repository URL** — e.g. `https://github.com/you/myapp`\n"
                "2. \U0001f433 A **Dockerfile** must exist in the repo root\n\n"
                "Please share the GitHub repo URL and I'll handle the rest!"
            ),
            "app_name": app,
            "repo_url": None,
            "version": None,
            "needs_input": True,
            "missing_fields": ["repo_url"],
        }

    if any(w in msg for w in ["log", "logs", "error", "show me", "what happened"]):
        return _resp("logs", "Fetching logs", "## \U0001f4cb Logs\n\nFetching recent log entries and scanning for errors...")

    if any(w in msg for w in ["incident", "alert", "outage", "down", "degraded", "active"]):
        return _resp("incident", "Checking incidents", "## \U0001f6a8 Incident Scan\n\nChecking all services for active incidents...")

    if any(w in msg for w in ["fix", "repair", "remediate", "auto"]):
        return _resp("fix", "Auto-remediation", "## \U0001f527 Auto-Fix\n\nAnalyzing issues and generating remediation plan...")

    if any(w in msg for w in ["status", "health", "how is", "metrics", "uptime", "overview"]):
        return _resp("status", "System health check", "## \U0001f4ca System Status\n\nFetching real-time health metrics...")

    return {
        "intent": "general",
        "summary": "General inquiry",
        "response": (
            "## \U0001f916 AI DevOps Copilot\n\n"
            "I'm your DevOps assistant. Here's what I can do:\n\n"
            "- \U0001f680 **Deploy** — `deploy https://github.com/you/myapp`\n"
            "- \u23ea **Rollback** — `rollback payment-service`\n"
            "- \U0001f50d **RCA** — `why did the last deploy fail?`\n"
            "- \U0001f6a8 **Incidents** — `any active alerts?`\n"
            "- \U0001f527 **Auto-fix** — `fix the payment service`\n"
            "- \U0001f4ca **Health** — `system health check`\n\n"
            "What would you like to do?"
        ),
        "app_name": None,
        "repo_url": None,
        "version": None,
        "needs_input": False,
        "missing_fields": [],
    }


def _resp(intent: str, summary: str, response: str, app_name=None) -> Dict:
    return {
        "intent": intent, "summary": summary, "response": response,
        "app_name": app_name, "repo_url": None, "version": None,
        "needs_input": False, "missing_fields": [],
    }


def _extract_github_url(text: str) -> Optional[str]:
    import re
    m = re.search(r'https?://github\.com/[^\s"\'<>]+', text)
    return m.group(0).rstrip("/.,)") if m else None


def _extract_app(msg: str) -> Optional[str]:
    import re
    known = ["payment-service", "auth-service", "api-gateway", "frontend", "backend", "myapp"]
    for app in known:
        if app in msg:
            return app
    # Try word after deploy/rollback/fix keyword
    m = re.search(r'\b(?:deploy|rollback|fix|restart)\s+([\w-]+)', msg)
    return m.group(1) if m else None


def _app_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    return url.rstrip("/").split("/")[-1].replace(".git", "")


def _extract_version(msg: str) -> Optional[str]:
    import re
    m = re.search(r'v?\d+\.\d+(\.\d+)?', msg)
    return m.group(0) if m else "latest"
