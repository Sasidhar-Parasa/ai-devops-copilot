"""
Coordinator Agent — Upgraded with real deployment + conversational flow
Handles GitHub repo → validate → build → deploy pipeline
"""
import logging
import time
from typing import Any, Dict, List

from models.schemas import AgentStep, AgentType, ChatRequest, ChatResponse, Intent
from services.llm_service import call_llm, _extract_github_url
from services.session_manager import (
    get_session, update_session, clear_deploy_context,
    get_pending_deploy, set_pending_deploy,
)
from agents.monitoring_agent import MonitoringAgent
from agents.incident_agent import IncidentAgent
from agents.root_cause_agent import RootCauseAgent
from agents.fix_agent import FixAgent

logger = logging.getLogger(__name__)

# Import real deployment service
try:
    from services.deploy_service import full_deploy_pipeline
    REAL_DEPLOY_AVAILABLE = True
except ImportError:
    REAL_DEPLOY_AVAILABLE = False
    logger.warning("deploy_service not available")

# Import real deployment agent for rollback/simulation
from agents.deployment_agent import DeploymentAgent


class CoordinatorAgent:
    def __init__(self):
        self.sim_deployment_agent = DeploymentAgent()
        self.monitoring_agent = MonitoringAgent()
        self.incident_agent = IncidentAgent()
        self.root_cause_agent = RootCauseAgent()
        self.fix_agent = FixAgent()

    async def process(self, request: ChatRequest) -> ChatResponse:
        steps: List[AgentStep] = []
        all_data: Dict[str, Any] = {}
        session_id = request.session_id or "default"
        session = get_session(session_id)

        # ── Step 1: Understand intent via LLM ────────────────────────────────
        t0 = time.monotonic()
        history = [{"role": m.role, "content": m.content} for m in (request.history or [])]

        # Check if user is responding to a pending deploy (providing repo URL)
        pending = get_pending_deploy(session_id)
        repo_url_in_message = _extract_github_url(request.message)

        # If we were waiting for a repo URL and user provided one
        if pending and repo_url_in_message:
            ai_result = {
                "intent": "deploy_with_repo",
                "summary": f"Deploying {pending['app_name']} from {repo_url_in_message}",
                "response": f"## \U0001f680 Deployment Starting\n\nPerfect! Deploying **{pending['app_name']}** from:\n`{repo_url_in_message}`\n\nRunning pipeline now...",
                "app_name": pending["app_name"],
                "repo_url": repo_url_in_message,
                "version": pending.get("version", "latest"),
                "needs_input": False,
                "missing_fields": [],
            }
        else:
            ai_result = await call_llm(request.message, history)

        intent_str = ai_result.get("intent", "general")

        # Map new intents to existing Intent enum
        intent_map = {
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
        intent = intent_map.get(intent_str, Intent.GENERAL)

        steps.append(AgentStep(
            agent=AgentType.COORDINATOR,
            action="Intent detection & routing",
            result=f"Intent: `{intent_str}` — {ai_result.get('summary', '')}",
            duration_ms=int((time.monotonic() - t0) * 1000),
            status="success",
        ))

        app_name = ai_result.get("app_name") or "myapp"
        repo_url = ai_result.get("repo_url")
        version  = ai_result.get("version") or "latest"
        needs_input = ai_result.get("needs_input", False)

        # ── Step 2: Route to sub-agents ───────────────────────────────────────
        try:
            # ── DEPLOY REQUEST (needs repo URL) ───────────────────────────────
            if intent_str == "deploy_request" or (intent == Intent.DEPLOY and needs_input):
                set_pending_deploy(session_id, app_name, version)
                steps.append(AgentStep(
                    agent=AgentType.DEPLOYMENT,
                    action="Awaiting repository URL",
                    result=f"Stored pending deploy for `{app_name}` — waiting for GitHub URL",
                    duration_ms=0,
                    status="warning",
                ))
                all_data["waiting_for"] = "repo_url"

            # ── DEPLOY WITH REPO (real pipeline) ──────────────────────────────
            elif intent_str == "deploy_with_repo" or (intent == Intent.DEPLOY and repo_url):
                clear_deploy_context(session_id)
                t1 = time.monotonic()

                steps.append(AgentStep(
                    agent=AgentType.DEPLOYMENT,
                    action=f"Starting real deployment pipeline for `{app_name}`",
                    result=f"Cloning `{repo_url}` → Validate → Build → Deploy",
                    duration_ms=0,
                    status="success",
                ))

                if REAL_DEPLOY_AVAILABLE:
                    dep_data = await full_deploy_pipeline(repo_url, app_name, version)
                else:
                    dep_data = await self.sim_deployment_agent.run(app_name, version)

                pipeline_status = dep_data.get("status", "unknown")
                svc_url = dep_data.get("service_url", "")
                stages = dep_data.get("stages", [])
                val_errors = dep_data.get("validation_errors", [])

                # Build human-readable response
                if pipeline_status == "success":
                    response_text = (
                        f"## \u2705 Deployment Successful!\n\n"
                        f"**App:** `{app_name}`\n"
                        f"**Version:** `{version}`\n"
                        f"**Pipeline:** {len(stages)} stages completed\n\n"
                        f"### \U0001f310 Live URL\n"
                        f"[{svc_url}]({svc_url})\n\n"
                        f"**Stages completed:**\n"
                        + "\n".join(f"- ✅ {s['name']} ({s.get('duration_seconds', 0)}s)" for s in stages)
                    )
                elif pipeline_status == "validation_failed":
                    response_text = (
                        f"## \u274c Deployment Blocked — Validation Failed\n\n"
                        f"I checked **{repo_url}** but found issues:\n\n"
                        + "\n\n".join(val_errors) +
                        "\n\n**Fix the above issues and try again.**"
                    )
                elif pipeline_status == "simulated":
                    response_text = (
                        f"## \U0001f9ea Deployment Simulated\n\n"
                        f"Ran full validation on **{repo_url}** ✅\n\n"
                        f"**Note:** `gcloud` CLI not found — deployment was simulated.\n"
                        f"Configure GCP credentials to deploy for real.\n\n"
                        f"Simulated URL: `{svc_url}`"
                    )
                else:
                    err = dep_data.get("error", "Unknown error")
                    failed_stage = next((s["name"] for s in stages if s["status"] == "failed"), "Unknown")
                    response_text = (
                        f"## \u274c Deployment Failed — {failed_stage} Stage\n\n"
                        f"**Error:** {err}\n\n"
                        f"**Stages:**\n"
                        + "\n".join(
                            f"- {'✅' if s['status'] == 'success' else '❌'} {s['name']}"
                            for s in stages
                        ) +
                        "\n\n**Tip:** Check the stage logs above for details."
                    )

                ai_result["response"] = response_text
                all_data["deployment"] = dep_data

                steps.append(AgentStep(
                    agent=AgentType.DEPLOYMENT,
                    action=f"Pipeline complete: `{app_name}`",
                    result=f"Status: **{pipeline_status}** | Stages: {len(stages)}",
                    duration_ms=int((time.monotonic() - t1) * 1000),
                    status="success" if pipeline_status == "success" else "error",
                ))

            # ── ROLLBACK ──────────────────────────────────────────────────────
            elif intent == Intent.ROLLBACK:
                t1 = time.monotonic()
                rb_data = await self.sim_deployment_agent.rollback(app_name)
                steps.append(AgentStep(
                    agent=AgentType.DEPLOYMENT,
                    action=f"Rollback initiated for `{app_name}`",
                    result=f"Rolled back to **{rb_data.get('version', 'previous')}**",
                    duration_ms=int((time.monotonic() - t1) * 1000),
                    status="success",
                ))
                all_data["rollback"] = rb_data

            # ── LOGS / STATUS ─────────────────────────────────────────────────
            elif intent in (Intent.LOGS, Intent.STATUS):
                t1 = time.monotonic()
                try:
                    from services.gcp_monitor import get_real_monitoring_data
                    mon_data = await get_real_monitoring_data()
                except Exception:
                    mon_data = await self.monitoring_agent.run()

                steps.append(AgentStep(
                    agent=AgentType.MONITORING,
                    action=f"Fetching logs [{mon_data.get('source', 'local')}]",
                    result=f"{mon_data['log_count']} entries | Error rate: {mon_data['error_rate']:.1f}%",
                    duration_ms=int((time.monotonic() - t1) * 1000),
                    status="warning" if mon_data["error_rate"] > 5 else "success",
                ))
                all_data["monitoring"] = mon_data

            # ── INCIDENT ──────────────────────────────────────────────────────
            elif intent == Intent.INCIDENT:
                t1 = time.monotonic()
                inc_data = await self.incident_agent.run()
                steps.append(AgentStep(
                    agent=AgentType.INCIDENT,
                    action="Scanning for active incidents",
                    result=f"{len(inc_data['incidents'])} incidents | Critical: {inc_data['critical_count']}",
                    duration_ms=int((time.monotonic() - t1) * 1000),
                    status="error" if inc_data["critical_count"] > 0 else "warning",
                ))
                all_data["incidents"] = inc_data

            # ── ROOT CAUSE ────────────────────────────────────────────────────
            elif intent == Intent.ROOT_CAUSE:
                t1 = time.monotonic()
                try:
                    from services.gcp_monitor import get_real_monitoring_data
                    mon_data = await get_real_monitoring_data()
                except Exception:
                    mon_data = await self.monitoring_agent.run()

                steps.append(AgentStep(
                    agent=AgentType.MONITORING,
                    action="Collecting signals for RCA",
                    result=f"{mon_data['log_count']} log entries, {mon_data['error_count']} errors",
                    duration_ms=int((time.monotonic() - t1) * 1000),
                    status="success",
                ))

                t2 = time.monotonic()
                rca_data = await self.root_cause_agent.run(mon_data)
                steps.append(AgentStep(
                    agent=AgentType.ROOT_CAUSE,
                    action="Running RCA engine",
                    result=f"Root cause: {rca_data.get('root_cause', 'Unknown')}",
                    duration_ms=int((time.monotonic() - t2) * 1000),
                    status="success",
                ))
                all_data["rca"] = rca_data

            # ── FIX ───────────────────────────────────────────────────────────
            elif intent == Intent.FIX:
                t1 = time.monotonic()
                inc_data = await self.incident_agent.run()
                t2 = time.monotonic()
                fix_data = await self.fix_agent.run(inc_data)
                steps.append(AgentStep(
                    agent=AgentType.FIX,
                    action="Applying remediation plan",
                    result=f"Fix: {fix_data.get('fix_applied', 'Auto-scale + Restart')}",
                    duration_ms=int((time.monotonic() - t2) * 1000),
                    status="success",
                ))
                all_data["fix"] = fix_data

            # ── GENERAL ───────────────────────────────────────────────────────
            else:
                t1 = time.monotonic()
                try:
                    from services.gcp_monitor import get_real_system_health
                    health_data = await get_real_system_health()
                except Exception:
                    health_data = await self.monitoring_agent.get_system_health()

                steps.append(AgentStep(
                    agent=AgentType.MONITORING,
                    action="System health snapshot",
                    result=f"Overall: **{health_data['overall']}** | Incidents: {health_data['active_incidents']}",
                    duration_ms=int((time.monotonic() - t1) * 1000),
                    status="success",
                ))
                all_data["health"] = health_data

        except Exception as e:
            logger.error(f"Agent error: {e}", exc_info=True)
            steps.append(AgentStep(
                agent=AgentType.COORDINATOR,
                action="Error recovery",
                result=f"Error: {str(e)}",
                duration_ms=0,
                status="error",
            ))

        return ChatResponse(
            response=ai_result.get("response", "Processing your request..."),
            intent=intent,
            agents_used=steps,
            data=all_data if all_data else None,
            session_id=session_id,
        )
