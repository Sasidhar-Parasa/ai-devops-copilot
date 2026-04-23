"""
Deployment Agent – Simulates CI/CD pipeline execution
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from services.database import save_deployment, get_deployments

logger = logging.getLogger(__name__)

# Realistic pipeline log templates
BUILD_LOGS = [
    "📦 Fetching dependencies from registry...",
    "🔍 Running static analysis (pylint, mypy)...",
    "✅ Linting passed — 0 errors, 2 warnings",
    "🐳 Building Docker image: {app}:{version}",
    "   Step 1/8: FROM python:3.11-slim",
    "   Step 4/8: COPY requirements.txt .",
    "   Step 5/8: RUN pip install --no-cache-dir -r requirements.txt",
    "   Step 8/8: CMD [\"uvicorn\", \"main:app\"]",
    "✅ Image built: {app}:{version} (287MB)",
    "🔐 Pushing to Artifact Registry: gcr.io/project/{app}:{version}",
    "✅ Image pushed successfully",
]

TEST_LOGS = [
    "🧪 Running test suite...",
    "   pytest tests/ -v --cov=src --cov-report=xml",
    "   tests/test_api.py::test_health_check PASSED",
    "   tests/test_api.py::test_deploy_endpoint PASSED",
    "   tests/test_auth.py::test_jwt_validation PASSED",
    "   tests/test_service.py::test_checkout_flow {test_result}",
    "   tests/test_service.py::test_payment_processing PASSED",
    "📊 Coverage: 87.3% | Threshold: 80%",
    "{test_summary}",
]

DEPLOY_LOGS = [
    "🌐 Connecting to GKE cluster: production-cluster",
    "📋 Applying Kubernetes manifests...",
    "   deployment.apps/{app} configured",
    "   service/{app} unchanged",
    "   hpa/{app} configured",
    "🔄 Rolling update: 0/3 pods updated",
    "🔄 Rolling update: 1/3 pods updated",
    "🔄 Rolling update: 2/3 pods updated",
    "🔄 Rolling update: 3/3 pods updated",
    "✅ Deployment complete — {app}:{version} is live",
    "🏥 Health checks passing (3/3 replicas ready)",
]

ROLLBACK_LOGS = [
    "⏪ Initiating rollback sequence...",
    "   Fetching deployment history for {app}",
    "   Last stable version: {prev_version}",
    "   Pulling image: gcr.io/project/{app}:{prev_version}",
    "🔄 Rolling back: 3/3 pods",
    "✅ Rollback complete — {app}:{prev_version} is live",
    "🏥 Health checks passing after rollback",
]


class DeploymentAgent:
    async def run(self, app_name: str, version: str = "latest") -> Dict[str, Any]:
        dep_id = f"dep-{uuid.uuid4().hex[:8]}"

        # Determine if this deployment will fail (30% chance for realism)
        import random
        will_fail = random.random() < 0.3
        fail_at_test = will_fail

        stages = []

        # ── Stage 1: Build ─────────────────────────────────────────────
        await asyncio.sleep(0.3)  # Simulate build time
        build_logs = [
            l.format(app=app_name, version=version) for l in BUILD_LOGS
        ]
        stages.append({
            "name": "Build",
            "status": "success",
            "duration_seconds": 47,
            "logs": build_logs,
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        })

        # ── Stage 2: Test ──────────────────────────────────────────────
        await asyncio.sleep(0.3)
        if fail_at_test:
            test_logs = [
                l.format(
                    test_result="FAILED",
                    test_summary="❌ 1 test failed | 246/247 passed",
                )
                for l in TEST_LOGS
            ]
            test_logs.append("💥 FAIL: assert response.status_code == 200, got 500")
            stages.append({
                "name": "Test",
                "status": "failed",
                "duration_seconds": 89,
                "logs": test_logs,
                "started_at": datetime.utcnow().isoformat(),
                "completed_at": datetime.utcnow().isoformat(),
            })
            stages.append({
                "name": "Deploy",
                "status": "pending",
                "duration_seconds": None,
                "logs": [],
                "started_at": None,
                "completed_at": None,
            })
            final_status = "failed"
            error_msg = f"Integration test failed: TestCheckoutFlow assertion error"
        else:
            test_logs = [
                l.format(
                    test_result="PASSED",
                    test_summary="✅ All 247 tests passed",
                )
                for l in TEST_LOGS
            ]
            stages.append({
                "name": "Test",
                "status": "success",
                "duration_seconds": 123,
                "logs": test_logs,
                "started_at": datetime.utcnow().isoformat(),
                "completed_at": datetime.utcnow().isoformat(),
            })

            # ── Stage 3: Deploy ────────────────────────────────────────
            await asyncio.sleep(0.3)
            deploy_logs = [
                l.format(app=app_name, version=version) for l in DEPLOY_LOGS
            ]
            stages.append({
                "name": "Deploy",
                "status": "success",
                "duration_seconds": 34,
                "logs": deploy_logs,
                "started_at": datetime.utcnow().isoformat(),
                "completed_at": datetime.utcnow().isoformat(),
            })
            final_status = "success"
            error_msg = None

        # Persist to DB
        dep = {
            "id": dep_id,
            "app_name": app_name,
            "version": version,
            "environment": "production",
            "status": final_status,
            "stages": json.dumps(stages),
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
            "triggered_by": "ai-copilot",
            "error_message": error_msg,
        }
        save_deployment(dep)

        return {
            "id": dep_id,
            "app_name": app_name,
            "version": version,
            "status": final_status,
            "stages": stages,
            "error_message": error_msg,
        }

    async def rollback(self, app_name: str) -> Dict[str, Any]:
        # Find previous successful deployment
        history = get_deployments()
        prev_version = "v2.3.8"
        for dep in history:
            if dep["app_name"] == app_name and dep["status"] == "success":
                prev_version = dep["version"]
                break

        dep_id = f"dep-{uuid.uuid4().hex[:8]}"
        rollback_logs = [
            l.format(app=app_name, prev_version=prev_version)
            for l in ROLLBACK_LOGS
        ]

        stages = [
            {
                "name": "Rollback",
                "status": "success",
                "duration_seconds": 28,
                "logs": rollback_logs,
                "started_at": datetime.utcnow().isoformat(),
                "completed_at": datetime.utcnow().isoformat(),
            }
        ]

        dep = {
            "id": dep_id,
            "app_name": app_name,
            "version": prev_version,
            "environment": "production",
            "status": "rolled_back",
            "stages": json.dumps(stages),
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
            "triggered_by": "ai-copilot-rollback",
            "error_message": None,
        }
        save_deployment(dep)

        return {
            "id": dep_id,
            "app_name": app_name,
            "version": prev_version,
            "status": "rolled_back",
            "stages": stages,
        }
