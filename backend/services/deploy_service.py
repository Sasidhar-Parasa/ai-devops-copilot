"""
Real Deployment Service with SSE streaming.
Supports: docker-compose, Dockerfile, framework auto-detect.
Streams real-time events to the frontend via async generators.
"""
import asyncio
import json
import logging
import os
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

WORKSPACE_DIR       = Path(os.getenv("WORKSPACE_DIR", "/tmp/copilot-workspace"))
GCP_PROJECT_ID      = os.getenv("GCP_PROJECT_ID", "").strip()
GCP_REGION          = os.getenv("GCP_REGION", "us-central1").strip()
AR_HOST             = f"{GCP_REGION}-docker.pkg.dev"
AR_REPO             = "copilot"
BUILD_POLL_TIMEOUT  = 600
BUILD_POLL_INTERVAL = 5


# ── Event helpers ──────────────────────────────────────────────────────────────

def _evt(stage: str, status: str, message: str,
         data: Optional[Dict] = None) -> Dict:
    return {
        "stage":     stage,
        "status":    status,   # running | success | error | info
        "message":   message,
        "timestamp": datetime.utcnow().isoformat(),
        "data":      data or {},
    }


def _sse(event: Dict) -> str:
    """Format dict as SSE data line."""
    return f"data: {json.dumps(event)}\n\n"


# ── GCP helpers ────────────────────────────────────────────────────────────────

def _is_cloud_run() -> bool:
    return bool(os.getenv("K_SERVICE") or os.getenv("GOOGLE_CLOUD_PROJECT"))


def _gcloud_env() -> dict:
    env = os.environ.copy()
    cfg = "/tmp/gcloud-cfg"
    os.makedirs(f"{cfg}/logs", exist_ok=True)
    env["CLOUDSDK_CONFIG"] = cfg
    env["HOME"] = "/tmp"
    env["CLOUDSDK_CORE_DISABLE_USAGE_REPORTING"] = "true"
    env["CLOUDSDK_COMPONENT_MANAGER_DISABLE_UPDATE_CHECK"] = "true"
    return env


def gcloud_available() -> bool:
    rc, _ = _run_sync(["gcloud", "version"])
    return rc == 0


def _clean(text: str) -> str:
    skip = ("log file", "CLOUDSDK_CONFIG", "configuration directory",
            "Permission denied", "creating a configuration")
    return "\n".join(
        ln for ln in text.splitlines()
        if not any(s.lower() in ln.lower() for s in skip) and ln.strip()
    )


def check_gcp_config() -> Tuple[bool, str]:
    if not GCP_PROJECT_ID:
        return False, (
            "**GCP_PROJECT_ID** not set.\n"
            "Add it to your Cloud Run service environment variables."
        )
    if not gcloud_available():
        return False, "**gcloud CLI not found** in the container. Rebuild the backend."

    rc, out = _run_sync(
        ["gcloud", "projects", "describe", GCP_PROJECT_ID,
         "--format=value(projectId)", "--quiet"]
    )
    if rc != 0:
        return False, (
            f"Cannot access GCP project `{GCP_PROJECT_ID}`.\n"
            "Run `grant_cloudrun_roles.sh` to fix SA permissions.\n\n"
            f"```\n{_clean(out)[:400]}\n```"
        )
    return True, ""


# ── Main streaming pipeline ────────────────────────────────────────────────────

async def stream_deploy_pipeline(
    repo_url: str,
    app_name: str,
    version: str = "latest",
) -> AsyncIterator[str]:
    """
    Async generator — yields SSE strings as deployment progresses.
    Caller does:  async for chunk in stream_deploy_pipeline(...): yield chunk
    """
    pid      = f"dep-{uuid.uuid4().hex[:8]}"
    stages:  List[Dict] = []
    start    = datetime.utcnow()
    svc_name = _safe_name(app_name)

    def completed_stage(name: str, status: str, logs: str, dur: float):
        stages.append({
            "name": name, "status": status, "logs": logs,
            "duration_seconds": round(dur),
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def emit(stage: str, status: str, msg: str, data: Dict = {}) -> str:
        return _sse(_evt(stage, status, msg, data))

    # ── Pre-flight ─────────────────────────────────────────────────────────────
    yield await emit("preflight", "running", "Checking GCP credentials…")
    ok, err = check_gcp_config()
    if not ok:
        yield await emit("preflight", "error", err)
        yield _sse({"stage": "done", "status": "failed",
                    "pipeline_id": pid, "error": err, "stages": stages,
                    "timestamp": datetime.utcnow().isoformat()})
        return
    yield await emit("preflight", "success", f"GCP project `{GCP_PROJECT_ID}` verified ✓")

    # ── Clone ──────────────────────────────────────────────────────────────────
    yield await emit("clone", "running", f"Cloning `{repo_url}`…")
    t = asyncio.get_event_loop().time()
    repo_path, clone_err = await _clone(repo_url, svc_name)
    dur = asyncio.get_event_loop().time() - t

    if not repo_path:
        yield await emit("clone", "error", clone_err)
        completed_stage("Clone", "failed", clone_err, dur)
        yield _sse({"stage": "done", "status": "failed", "pipeline_id": pid,
                    "error": clone_err, "stages": stages,
                    "timestamp": datetime.utcnow().isoformat()})
        return

    completed_stage("Clone", "success", f"Cloned `{repo_url}`", dur)
    yield await emit("clone", "success", "Repository cloned ✓")

    # ── Analyze ────────────────────────────────────────────────────────────────
    yield await emit("analyze", "running", "Analyzing repository structure…")
    from services.repo_analyzer import analyze_repo
    plan = analyze_repo(repo_path)

    if not plan.valid:
        err_msg = "\n\n".join(plan.errors)
        yield await emit("analyze", "error", err_msg)
        shutil.rmtree(repo_path, ignore_errors=True)
        completed_stage("Analyze", "failed", err_msg, 0)
        yield _sse({"stage": "done", "status": "failed", "pipeline_id": pid,
                    "error": err_msg, "stages": stages,
                    "timestamp": datetime.utcnow().isoformat()})
        return

    # Emit analysis summary
    for w in plan.warnings:
        yield await emit("analyze", "info", w)
    yield await emit("analyze", "success", plan.summary,
                     {"strategy": plan.strategy,
                      "framework": plan.framework,
                      "services": [s.name for s in plan.services]})
    completed_stage("Analyze", "success", plan.summary, 0)

    # ── Build + Push ───────────────────────────────────────────────────────────
    # Use the primary/first deployable service
    primary = _pick_primary_service(plan)
    image_uri = f"{AR_HOST}/{GCP_PROJECT_ID}/{AR_REPO}/{svc_name}:{version}"

    yield await emit("build", "running",
                     f"Submitting Cloud Build for `{svc_name}`…",
                     {"image": image_uri})

    t = asyncio.get_event_loop().time()
    ok, build_id, build_log = await _cloud_build(repo_path, image_uri, primary)
    dur = asyncio.get_event_loop().time() - t
    shutil.rmtree(repo_path, ignore_errors=True)

    if not ok:
        yield await emit("build", "error", build_log)
        completed_stage("Build", "failed", build_log, dur)
        yield _sse({"stage": "done", "status": "failed", "pipeline_id": pid,
                    "error": build_log, "stages": stages,
                    "timestamp": datetime.utcnow().isoformat()})
        return

    build_url = (
        f"https://console.cloud.google.com/cloud-build/builds"
        f"/{build_id}?project={GCP_PROJECT_ID}"
    ) if build_id else ""
    yield await emit("build", "success",
                     "Image built and pushed ✓",
                     {"image": image_uri, "build_url": build_url})
    completed_stage("Build", "success",
                     f"Image: `{image_uri}`\n[Logs]({build_url})", dur)

    # ── Deploy to Cloud Run ────────────────────────────────────────────────────
    port = primary.port if primary else plan.primary_port
    yield await emit("deploy", "running",
                     f"Deploying `{svc_name}` to Cloud Run ({GCP_REGION})…",
                     {"port": port})

    t = asyncio.get_event_loop().time()
    ok, svc_url, deploy_log = await _cloud_run_deploy(image_uri, svc_name, port)
    dur = asyncio.get_event_loop().time() - t

    if not ok:
        yield await emit("deploy", "error", deploy_log)
        completed_stage("Deploy", "failed", deploy_log, dur)
        yield _sse({"stage": "done", "status": "failed", "pipeline_id": pid,
                    "error": deploy_log, "stages": stages,
                    "timestamp": datetime.utcnow().isoformat()})
        return

    completed_stage("Deploy", "success", f"Live at {svc_url}", dur)
    yield await emit("deploy", "success",
                     "Deployed to Cloud Run ✓",
                     {"url": svc_url})

    # ── Health check ───────────────────────────────────────────────────────────
    yield await emit("health", "running", "Running health check…")
    import httpx
    healthy = False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            for _ in range(5):
                try:
                    r = await client.get(svc_url)
                    if r.status_code < 500:
                        healthy = True
                        break
                except Exception:
                    await asyncio.sleep(3)
    except Exception:
        pass

    if healthy:
        yield await emit("health", "success", "Health check passed ✓",
                         {"url": svc_url})
    else:
        yield await emit("health", "info",
                         "Service deployed but health check did not respond "
                         "(may still be starting up)",
                         {"url": svc_url})

    # ── Done ───────────────────────────────────────────────────────────────────
    total = round((datetime.utcnow() - start).total_seconds())
    _save_dep(pid, app_name, version, "success", stages, repo_url, None, svc_url)

    yield _sse({
        "stage":       "done",
        "status":      "success",
        "pipeline_id": pid,
        "service_url": svc_url,
        "image_uri":   image_uri,
        "stages":      stages,
        "total_seconds": total,
        "timestamp":   datetime.utcnow().isoformat(),
    })


# ── Non-streaming wrapper (used by chat coordinator) ──────────────────────────

async def full_deploy_pipeline(
    repo_url: str,
    app_name: str,
    version: str = "latest",
) -> Dict[str, Any]:
    """
    Collects all SSE events and returns final result dict.
    Used by the chat coordinator which doesn't need streaming.
    """
    stages: List[Dict] = []
    final: Dict[str, Any] = {}

    async for chunk in stream_deploy_pipeline(repo_url, app_name, version):
        if not chunk.startswith("data: "):
            continue
        try:
            evt = json.loads(chunk[6:])
        except json.JSONDecodeError:
            continue

        if evt.get("stage") == "done":
            final = evt
        elif evt.get("status") in ("success", "failed", "error"):
            stages.append(evt)

    status = "success" if final.get("status") == "success" else "failed"
    return {
        "pipeline_id":  final.get("pipeline_id", ""),
        "app_name":     app_name,
        "version":      version,
        "repo_url":     repo_url,
        "status":       status,
        "stages":       stages,
        "error":        final.get("error") if status == "failed" else None,
        "service_url":  final.get("service_url"),
        "image_uri":    final.get("image_uri"),
        "created_at":   datetime.utcnow().isoformat(),
        "total_duration_seconds": final.get("total_seconds", 0),
    }


# ── Stage implementations ──────────────────────────────────────────────────────

async def _clone(repo_url: str, name: str) -> Tuple[Optional[Path], str]:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    dest = WORKSPACE_DIR / f"{name}-{uuid.uuid4().hex[:6]}"
    if dest.exists():
        shutil.rmtree(dest)
    rc, out = await _run(
        ["git", "clone", "--depth", "1", repo_url, str(dest)], timeout=120
    )
    if rc != 0:
        return None, (
            f"Failed to clone `{repo_url}`\n"
            f"```\n{out[:600]}\n```\n"
            "Ensure the repo is public and the URL is correct."
        )
    return dest, f"Cloned `{repo_url}`"


def _pick_primary_service(plan):
    if not plan.services:
        return None
    priority = ["web", "backend", "app", "api", "frontend", "server"]
    for key in priority:
        for svc in plan.services:
            if key in svc.name.lower():
                return svc
    return plan.services[0]


async def _cloud_build(
    repo_path: Path,
    image_uri: str,
    primary_svc,
) -> Tuple[bool, str, str]:
    # Build the correct context (compose service may have a subdir)
    build_cwd = repo_path
    df_flag: List[str] = []

    if primary_svc and primary_svc.build_context:
        ctx = repo_path / primary_svc.build_context
        if ctx.exists():
            build_cwd = ctx
    if primary_svc and primary_svc.dockerfile:
        df_path = Path(primary_svc.dockerfile)
        if df_path.is_absolute():
            rel = df_path.relative_to(build_cwd) if df_path.is_relative_to(build_cwd) else df_path
            df_flag = ["--file", str(rel)]

    cmd = (
        ["gcloud", "builds", "submit",
         "--tag", image_uri,
         "--timeout", "600",
         "--async", "--quiet"]
        + df_flag
        + ["."]
    )

    logger.info("Cloud Build cmd: %s (cwd=%s)", cmd, build_cwd)
    rc, out = await _run(cmd, cwd=build_cwd, timeout=120)
    build_id = _extract_build_id(out)
    logger.info("Build submitted: id=%s rc=%d", build_id, rc)

    if not build_id:
        return False, "", f"Failed to submit build.\n```\n{_clean(out)[:1500]}\n```"

    ok, poll_log = await _poll_build(build_id)
    return ok, build_id, poll_log


async def _poll_build(build_id: str) -> Tuple[bool, str]:
    deadline = asyncio.get_event_loop().time() + BUILD_POLL_TIMEOUT
    last = "UNKNOWN"
    while asyncio.get_event_loop().time() < deadline:
        rc, out = await _run(
            ["gcloud", "builds", "describe", build_id,
             "--format=value(status)", "--quiet"]
        )
        if rc == 0:
            last = out.strip()
            logger.info("Build %s: %s", build_id, last)
            if last == "SUCCESS":
                return True, f"Build succeeded (id: `{build_id}`)"
            if last in ("FAILURE", "INTERNAL_ERROR", "TIMEOUT", "CANCELLED"):
                _, log_out = await _run(
                    ["gcloud", "builds", "log", build_id, "--quiet"], timeout=30
                )
                tail = log_out[-1500:] if log_out else "(no logs)"
                return False, (
                    f"Cloud Build **{last}** (id: `{build_id}`)\n\n"
                    f"```\n{tail}\n```\n\n"
                    f"[Full logs](https://console.cloud.google.com/cloud-build"
                    f"/builds/{build_id}?project={GCP_PROJECT_ID})"
                )
        await asyncio.sleep(BUILD_POLL_INTERVAL)
    return False, f"Build timed out after {BUILD_POLL_TIMEOUT}s (status: {last})"


def _extract_build_id(output: str) -> Optional[str]:
    m = re.search(
        r"builds/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}"
        r"-[0-9a-f]{4}-[0-9a-f]{12})",
        output,
    )
    return m.group(1) if m else None


async def _cloud_run_deploy(
    image_uri: str, svc: str, port: int = 8080
) -> Tuple[bool, str, str]:
    rc, out = await _run(
        ["gcloud", "run", "deploy", svc,
         "--image", image_uri,
         "--platform", "managed",
         "--region", GCP_REGION,
         "--allow-unauthenticated",
         "--memory", "512Mi", "--cpu", "1",
         "--min-instances", "0", "--max-instances", "5",
         "--port", str(port), "--quiet"],
        timeout=300,
    )
    if rc != 0:
        return False, "", f"Cloud Run deploy failed.\n```\n{_clean(out)[-1500:]}\n```"
    rc2, url = await _run(
        ["gcloud", "run", "services", "describe", svc,
         "--region", GCP_REGION, "--format=value(status.url)"]
    )
    return True, url.strip(), f"Deployed `{svc}`"


# ── Subprocess utils ────────────────────────────────────────────────────────────

def _run_sync(cmd: List[str]) -> Tuple[int, str]:
    import subprocess
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, env=_gcloud_env()
        )
        return r.returncode, r.stdout + r.stderr
    except Exception as exc:  # noqa: BLE001
        return 1, str(exc)


async def _run(
    cmd: List[str],
    cwd: Optional[Path] = None,
    timeout: int = 300,
) -> Tuple[int, str]:
    env = _gcloud_env()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd) if cwd else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode, stdout.decode() + stderr.decode()
    except asyncio.TimeoutError:
        return 1, f"Timed out after {timeout}s"
    except FileNotFoundError:
        return 1, f"Command not found: {cmd[0]}"
    except Exception as exc:  # noqa: BLE001
        return 1, str(exc)


# ── DB ──────────────────────────────────────────────────────────────────────────

def _save_dep(
    pid: str, app: str, ver: str, status: str,
    stages: list, repo_url: str,
    err: Optional[str], url: Optional[str] = None,
) -> None:
    try:
        from services.database import save_deployment
        save_deployment({
            "id": pid, "app_name": app, "version": ver,
            "environment": "production", "status": status,
            "stages": json.dumps(stages),
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
            "triggered_by": "ai-copilot",
            "error_message": err,
            "service_url": url or "",
            "repo_url": repo_url or "",
        })
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not save deployment: %s", exc)


def _safe_name(name: str) -> str:
    name = re.sub(r"[^a-z0-9-]", "-", name.lower())
    return re.sub(r"-+", "-", name).strip("-")[:49] or "app"

