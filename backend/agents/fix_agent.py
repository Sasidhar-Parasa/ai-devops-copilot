"""
Fix Agent - Suggests and simulates automated remediation
"""
import logging
from datetime import datetime
from typing import Any, Dict

from services.database import save_incident

logger = logging.getLogger(__name__)


class FixAgent:
    async def run(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        incidents = incident_data.get("incidents", [])
        open_incidents = [i for i in incidents if i["status"] in ("open", "investigating")]

        if not open_incidents:
            return {
                "fix_applied":  "No active incidents requiring fixes",
                "actions_taken": [],
                "status":       "no_action_needed",
            }

        actions = []
        for inc in open_incidents[:2]:
            fix = self._select_fix(inc)
            actions.append(fix)
            inc["status"]      = "resolved"
            inc["fix_applied"] = fix["action"]
            inc["resolved_at"] = datetime.utcnow().isoformat()
            try:
                save_incident(inc)
            except Exception as exc:
                logger.warning("Could not update incident: %s", exc)

        return {
            "fix_applied":            actions[0]["action"] if actions else "General remediation",
            "actions_taken":          actions,
            "status":                 "remediated",
            "estimated_recovery_time": "2-5 minutes",
        }

    def _select_fix(self, incident: Dict) -> Dict[str, Any]:
        severity = incident.get("severity", "medium")
        service  = incident.get("service", "unknown")

        fixes = {
            "critical": {
                "action":    f"Emergency rollback of {service} to last stable version",
                "type":      "rollback",
                "automated": True,
                "commands":  [
                    f"kubectl rollout undo deployment/{service}",
                    f"kubectl rollout status deployment/{service}",
                ],
            },
            "high": {
                "action":    f"Auto-scale {service}: replicas 2 → 6 + circuit breaker enabled",
                "type":      "scale_out",
                "automated": True,
                "commands":  [
                    f"kubectl scale deployment/{service} --replicas=6",
                    f"kubectl annotate deployment/{service} circuit-breaker=enabled",
                ],
            },
            "medium": {
                "action":    f"Restart {service} pods + increase memory limit 512Mi → 1Gi",
                "type":      "restart_and_resize",
                "automated": True,
                "commands":  [
                    f"kubectl rollout restart deployment/{service}",
                    f"kubectl set resources deployment/{service} --limits=memory=1Gi",
                ],
            },
            "low": {
                "action":    f"Drain and reschedule {service} pods to less-loaded nodes",
                "type":      "reschedule",
                "automated": False,
                "commands":  [
                    "kubectl drain node --ignore-daemonsets",
                    f"kubectl rollout restart deployment/{service}",
                ],
            },
        }

        return fixes.get(severity, fixes["medium"])