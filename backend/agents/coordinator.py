"""
Coordinator Agent — routes LLM intent to sub-agents.
deploy_with_repo returns repo_url in data so frontend can open SSE stream.
"""
import logging
import time
from typing import Any, Dict, List

from models.schemas import AgentStep, AgentType, ChatRequest, ChatResponse, Intent
from services.llm_service import call_llm, extract_github_url
from services.session_manager import (
    clear_deploy_context,
    get_pending_deploy,
    get_session,
    set_pending_deploy,
)
from agents.deployment_agent import DeploymentAgent
from agents.monitoring_agent import MonitoringAgent
from agents.incident_agent import IncidentAgent
from agents.root_cause_agent import RootCauseAgent
from agents.fix_agent import FixAgent

logger = logging.getLogger(__name__)


INTENT_MAP = {
    "deploy_request":   Intent.DEPLOY,
    "deploy_with_repo": Intent.DEPLOY,
    "rollback":         Intent.ROLLBACK,
    "status":           Intent.STATUS,
    "logs":             Intent.LOGS,
    "incident":         Intent.INCIDENT,
    "root_cause":       Intent.ROOT_CAUSE,
    "fix":              Intent.FIX,
    "general":          Intent.GENERAL,
}


class CoordinatorAgent:
    def __init__(self):
        self.sim_agent  = DeploymentAgent()
        self.monitoring = MonitoringAgent()
        self.incident   = IncidentAgent()
        self.root_cause = RootCauseAgent()
        self.fix_agent  = FixAgent()

    async def process(self, request: ChatRequest) -> ChatResponse:
        steps: List[AgentStep] = []
        data:  Dict[str, Any]  = {}
        session_id = request.session_id or "default"
        get_session(session_id)

        history = [{"role": m.role, "content": m.content}
                   for m in (request.history or [])]

        # If user is responding to pending deploy with a URL
        pending     = get_pending_deploy(session_id)
        repo_in_msg = extract_github_url(request.message)
        if pending and repo_in_msg:
            request = ChatRequest(
                message=f"Deploy from {repo_in_msg} (app: {pending.get('app_name', 'app')})",
                session_id=session_id,
                history=request.history,
            )
            history.append({"role": "user", "content": request.message})

        # LLM call
        t0 = time.monotonic()
        ai = await call_llm(request.message, history)
        intent_str = ai.get("intent", "general")
        intent     = INTENT_MAP.get(intent_str, Intent.GENERAL)

        steps.append(AgentStep(
            agent=AgentType.COORDINATOR,
            action="Intent classification",
            result=f"`{intent_str}` — {ai.get('summary', '')}",
            duration_ms=int((time.monotonic() - t0) * 1000),
            status="success",
        ))

        app_name = ai.get("app_name") or "app"
        repo_url = ai.get("repo_url")
        version  = ai.get("version") or "latest"

        try:
            if intent_str == "deploy_request" or (intent == Intent.DEPLOY and not repo_url):
                set_pending_deploy(session_id, app_name, version)
                steps.append(AgentStep(
                    agent=AgentType.DEPLOYMENT,
                    action="Waiting for repository URL",
                    result=f"Stored pending deploy for `{app_name}`",
                    duration_ms=0, status="warning",
                ))
                data["waiting_for"] = "repo_url"
                data["app_name"]    = app_name

            elif intent_str == "deploy_with_repo" or (intent == Intent.DEPLOY and repo_url):
                clear_deploy_context(session_id)
                # Tell the frontend to start the SSE stream
                # The actual pipeline runs via /api/deploy/stream
                data["deployment"] = {
                    "repo_url":  repo_url,
                    "app_name":  app_name,
                    "version":   version,
                    "status":    "streaming",  # frontend will open SSE
                }
                steps.append(AgentStep(
                    agent=AgentType.DEPLOYMENT,
                    action=f"Starting deployment pipeline for `{app_name}`",
                    result=f"SSE stream ready for `{repo_url}`",
                    duration_ms=0, status="success",
                ))

                # Update AI response to be more conversational
                # We can't analyze without cloning, so give a helpful message
                ai["response"] = (
                    f"## 🚀 Deploying `{app_name}`\n\n"
                    f"Starting deployment pipeline for:\n"
                    f"`{repo_url}`\n\n"
                    "**Pipeline:**\n"
                    "1. 🔍 Pre-flight checks\n"
                    "2. 📥 Clone repository\n"
                    "3. 🧠 Analyze (Docker Compose / Dockerfile / framework)\n"
                    "4. 🐳 Build & push image\n"
                    "5. ☁️ Deploy to Cloud Run\n"
                    "6. ✅ Health check\n\n"
                    "*Watch the live deployment log below ↓*"
                )

            elif intent == Intent.ROLLBACK:
                t1 = time.monotonic()
                rb = await self.sim_agent.rollback(app_name)
                steps.append(AgentStep(
                    agent=AgentType.DEPLOYMENT,
                    action=f"Rollback `{app_name}`",
                    result=f"Rolled back to `{rb.get('version', 'previous')}`",
                    duration_ms=int((time.monotonic() - t1) * 1000),
                    status="success",
                ))
                data["rollback"] = rb

            elif intent in (Intent.LOGS, Intent.STATUS):
                t1 = time.monotonic()
                try:
                    from services.gcp_monitor import get_real_monitoring_data
                    mon = await get_real_monitoring_data()
                except Exception:  # noqa: BLE001
                    mon = await self.monitoring.run()
                steps.append(AgentStep(
                    agent=AgentType.MONITORING,
                    action="Fetch logs & metrics",
                    result=f"{mon['log_count']} entries · {mon['error_rate']:.1f}% errors",
                    duration_ms=int((time.monotonic() - t1) * 1000),
                    status="warning" if mon["error_rate"] > 5 else "success",
                ))
                data["monitoring"] = mon

            elif intent == Intent.INCIDENT:
                t1 = time.monotonic()
                inc = await self.incident.run()
                steps.append(AgentStep(
                    agent=AgentType.INCIDENT,
                    action="Scan incidents",
                    result=f"{inc['open_count']} open · {inc['critical_count']} critical",
                    duration_ms=int((time.monotonic() - t1) * 1000),
                    status="error" if inc["critical_count"] > 0 else "warning",
                ))
                data["incidents"] = inc

            elif intent == Intent.ROOT_CAUSE:
                t1 = time.monotonic()
                try:
                    from services.gcp_monitor import get_real_monitoring_data
                    mon = await get_real_monitoring_data()
                except Exception:  # noqa: BLE001
                    mon = await self.monitoring.run()
                rca = await self.root_cause.run(mon)
                steps.append(AgentStep(
                    agent=AgentType.ROOT_CAUSE,
                    action="Root cause analysis",
                    result=rca.get("root_cause", "Complete"),
                    duration_ms=int((time.monotonic() - t1) * 1000),
                    status="success",
                ))
                data["rca"] = rca

            elif intent == Intent.FIX:
                t1 = time.monotonic()
                inc = await self.incident.run()
                fix = await self.fix_agent.run(inc)
                steps.append(AgentStep(
                    agent=AgentType.FIX,
                    action="Apply remediation",
                    result=fix.get("fix_applied", "Applied"),
                    duration_ms=int((time.monotonic() - t1) * 1000),
                    status="success",
                ))
                data["fix"] = fix

            else:
                t1 = time.monotonic()
                try:
                    from services.gcp_monitor import get_real_system_health
                    health = await get_real_system_health()
                except Exception:  # noqa: BLE001
                    health = await self.monitoring.get_system_health()
                steps.append(AgentStep(
                    agent=AgentType.MONITORING,
                    action="System health snapshot",
                    result=f"Overall: **{health['overall']}**",
                    duration_ms=int((time.monotonic() - t1) * 1000),
                    status="success",
                ))
                data["health"] = health

        except Exception as exc:  # noqa: BLE001
            logger.exception("Agent error: %s", exc)
            steps.append(AgentStep(
                agent=AgentType.COORDINATOR,
                action="Error recovery",
                result=str(exc),
                duration_ms=0,
                status="error",
            ))

        return ChatResponse(
            response=ai.get("response", ""),
            intent=intent,
            agents_used=steps,
            data=data if data else None,
            session_id=session_id,
        )

