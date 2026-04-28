"""
Coordinator Agent — routes LLM intent to sub-agents.
Every response goes through the real LLM. No simulated deployments.
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

try:
    from services.deploy_service import full_deploy_pipeline
    REAL_DEPLOY = True
except ImportError:
    REAL_DEPLOY = False
    logger.warning("deploy_service not available")

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
        self.sim_agent    = DeploymentAgent()
        self.monitoring   = MonitoringAgent()
        self.incident     = IncidentAgent()
        self.root_cause   = RootCauseAgent()
        self.fix_agent    = FixAgent()

    async def process(self, request: ChatRequest) -> ChatResponse:
        steps: List[AgentStep] = []
        data:  Dict[str, Any]  = {}
        session_id = request.session_id or "default"
        get_session(session_id)  # ensure session exists

        history = [{"role": m.role, "content": m.content} for m in (request.history or [])]

        # ── Check if user is completing a pending deploy (providing repo URL) ─
        pending     = get_pending_deploy(session_id)
        repo_in_msg = extract_github_url(request.message)
        if pending and repo_in_msg:
            # User replied with a GitHub URL after we asked — construct context
            request = ChatRequest(
                message=f"Deploy from {repo_in_msg} (app: {pending.get('app_name', 'myapp')})",
                session_id=session_id,
                history=request.history,
            )
            history.append({"role": "user", "content": request.message})

        # ── LLM call ──────────────────────────────────────────────────────────
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

        app_name = ai.get("app_name") or "myapp"
        repo_url = ai.get("repo_url")
        version  = ai.get("version") or "latest"

        # ── Route ─────────────────────────────────────────────────────────────
        try:
            if intent_str == "deploy_request" or (intent == Intent.DEPLOY and not repo_url):
                set_pending_deploy(session_id, app_name, version)
                steps.append(AgentStep(
                    agent=AgentType.DEPLOYMENT,
                    action="Waiting for repository URL",
                    result=f"Stored pending deploy for `{app_name}`",
                    duration_ms=0,
                    status="warning",
                ))
                data["waiting_for"] = "repo_url"

            elif intent_str == "deploy_with_repo" or (intent == Intent.DEPLOY and repo_url):
                clear_deploy_context(session_id)
                t1 = time.monotonic()

                if REAL_DEPLOY:
                    dep = await full_deploy_pipeline(repo_url, app_name, version)
                else:
                    dep = await self.sim_agent.run(app_name, version)

                status  = dep.get("status", "unknown")
                svc_url = dep.get("service_url", "")
                stages  = dep.get("stages", [])
                val_err = dep.get("validation_errors", [])

                if status == "success":
                    ai["response"] = (
                        f"## ✅ Deployment Successful!\n\n"
                        f"**{app_name}** is live:\n\n"
                        f"🌐 [{svc_url}]({svc_url})\n\n"
                        f"**Pipeline:** {len(stages)} stages — "
                        + ", ".join(f"{s['name']} ({s.get('duration_seconds',0)}s)" for s in stages)
                    )
                elif status == "validation_failed":
                    ai["response"] = (
                        f"## ❌ Deployment Blocked\n\n"
                        f"Validation failed for `{repo_url}`:\n\n"
                        + "\n\n".join(val_err or dep.get("error", ["Unknown validation error"]))
                    )
                else:
                    err = dep.get("error", "Unknown error")
                    failed = next((s["name"] for s in stages if s["status"] == "failed"), "Unknown")
                    ai["response"] = (
                        f"## ❌ Deployment Failed — {failed} stage\n\n{err}"
                    )

                data["deployment"] = dep
                steps.append(AgentStep(
                    agent=AgentType.DEPLOYMENT,
                    action=f"Pipeline for `{app_name}`",
                    result=f"Status: **{status}**" + (f" · {svc_url}" if svc_url else ""),
                    duration_ms=int((time.monotonic() - t1) * 1000),
                    status="success" if status == "success" else "error",
                ))

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
                    result=f"{mon['log_count']} entries · {mon['error_rate']:.1f}% error rate [{mon.get('source','local')}]",
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
                    result=rca.get("root_cause", "Analysis complete"),
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
                    result=fix.get("fix_applied", "Remediation applied"),
                    duration_ms=int((time.monotonic() - t1) * 1000),
                    status="success",
                ))
                data["fix"] = fix

            else:  # GENERAL
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
