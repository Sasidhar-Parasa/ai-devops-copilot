"""
Deployments Router — Real + simulated deployments
"""
import json
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from models.schemas import DeployRequest, RollbackRequest
from services.database import get_deployments

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/deploy")
async def deploy(request: DeployRequest):
    """Trigger a real deployment pipeline."""
    try:
        from services.deploy_service import full_deploy_pipeline
        result = await full_deploy_pipeline(
            repo_url=request.config.get("repo_url", ""),
            app_name=request.app_name,
            version=request.version,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deploy/simulate")
async def deploy_simulate(request: DeployRequest):
    """Trigger a simulated deployment (no GCP required)."""
    try:
        from agents.deployment_agent import DeploymentAgent
        agent = DeploymentAgent()
        result = await agent.run(request.app_name, request.version)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rollback")
async def rollback(request: RollbackRequest):
    """Rollback an application to its previous stable version."""
    try:
        from agents.deployment_agent import DeploymentAgent
        agent = DeploymentAgent()
        result = await agent.rollback(request.app_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/deployments")
async def list_deployments(limit: int = Query(20, ge=1, le=100)):
    """List recent deployments with pipeline stages."""
    try:
        deps = get_deployments(limit=limit)
        for d in deps:
            if isinstance(d.get("stages"), str):
                try:
                    d["stages"] = json.loads(d["stages"])
                except Exception:
                    d["stages"] = []
        return {"deployments": deps, "total": len(deps)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cloud-run/services")
async def list_cloud_run_services():
    """List real Cloud Run services from GCP."""
    try:
        from services.gcp_monitor import list_cloud_run_services as _list
        services = _list()
        return {"services": services, "total": len(services), "source": "gcp"}
    except Exception as e:
        return {"services": [], "total": 0, "error": str(e)}
