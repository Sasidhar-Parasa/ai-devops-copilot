"""
Real Deployment Service
Pipeline: git clone → validate → gcloud builds submit → gcloud run deploy
No simulation — every step is real or returns an honest error.
"""
import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

WORKSPACE_DIR  = Path(os.getenv("WORKSPACE_DIR", "/tmp/copilot-workspace"))
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "").strip()
GCP_REGION     = os.getenv("GCP_REGION", "us-central1").strip()
AR_HOST        = f"{GCP_REGION}-docker.pkg.dev"
AR_REPO        = "copilot"


# ── Pre-flight checks ──────────────────────────────────────────────────────────

def check_gcp_config() -> Tuple[bool, str]:
    """Returns (ok, error_message)."""
    if not GCP_PROJECT_ID:
        return False, (
            "GCP_PROJECT_ID is not set. Add it to your `.env` file.\n"
            "Example: `GCP_PROJECT_ID=my-project-123`"
        )
    rc, out = _run(["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"])
    if rc != 0 or not out.strip():
        return False, (
            "No active GCP credentials found.\n"
            "Run: `gcloud auth application-default login`\n"
            "Or configure a service account key."
        )
    return True, ""


def gcloud_available() -> bool:
    rc, _ = _run(["gcloud", "version"])
    return rc == 0


# ── Validation ─────────────────────────────────────────────────────────────────

class ValidationResult:
    def __init__(self):
        self.valid = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.checks: List[str] = []

    def fail(self, msg: str):
        self.valid = False
        self.errors.append(msg)

    def warn(self, msg: str):
        self.warnings.append(msg)

    def ok(self, msg: str):
        self.checks.append(msg)


def validate_repo(repo_path: Path) -> ValidationResult:
    result = ValidationResult()

    dockerfile = repo_path / "Dockerfile"
    if not dockerfile.exists():
        result.fail(
            "**Dockerfile not found** in the repository root.\n\n"
            "Add a `Dockerfile` to your project. Quick example for Python:\n"
            "```dockerfile\n"
            "FROM python:3.11-slim\n"
            "WORKDIR /app\n"
            "COPY requirements.txt .\n"
            "RUN pip install -r requirements.txt\n"
            "COPY . .\n"
            "CMD [\"uvicorn\", \"main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8080\"]\n"
            "```"
        )
    else:
        result.ok("✅ Dockerfile found")

    # Check for common app entry points
    entry_points = ["main.py", "app.py", "server.py", "index.js", "server.js", "manage.py"]
    found = [e for e in entry_points if (repo_path / e).exists()]
    if found:
        result.ok(f"✅ Entry point found: `{found[0]}`")
    elif not (repo_path / "Dockerfile").exists():
        result.warn("No common entry point found — ensure your Dockerfile CMD is correct")

    # Check for dependency files
    for dep_file in ["requirements.txt", "package.json", "pyproject.toml", "go.mod", "Gemfile"]:
        if (repo_path / dep_file).exists():
            result.ok(f"✅ `{dep_file}` found")
            break

    return result


# ── Core pipeline ──────────────────────────────────────────────────────────────

async def full_deploy_pipeline(
    repo_url: str,
    app_name: str,
    version: str = "latest",
) -> Dict[str, Any]:
    """
    Real deployment pipeline. Returns detailed result dict.
    Never simulates — every failure returns the real error.
    """
    pipeline_id = f"dep-{uuid.uuid4().hex[:8]}"
    stages: List[Dict] = []
    start = datetime.utcnow()
    service_name = _safe_service_name(app_name)
    image_uri = f"{AR_HOST}/{GCP_PROJECT_ID}/{AR_REPO}/{service_name}:{version}"

    def add_stage(name: str, status: str, logs: str, dur: float):
        stages.append({
            "name": name,
            "status": status,
            "logs": logs,
            "duration_seconds": round(dur),
            "timestamp": datetime.utcnow().isoformat(),
        })

    def fail(stage: str, error: str, dur: float) -> Dict:
        add_stage(stage, "failed", error, dur)
        _save_deployment(pipeline_id, app_name, version, "failed", stages, repo_url, error)
        return {
            "pipeline_id": pipeline_id, "app_name": app_name,
            "version": version, "repo_url": repo_url,
            "status": "failed", "stages": stages,
            "error": error, "service_url": None,
            "created_at": start.isoformat(),
        }

    # ── Pre-flight ─────────────────────────────────────────────────────────────
    gcp_ok, gcp_err = check_gcp_config()
    if not gcp_ok:
        return fail("Pre-flight", gcp_err, 0)

    if not gcloud_available():
        return fail("Pre-flight", "gcloud CLI not found. Install the Google Cloud SDK.", 0)

    # ── Stage 1: Clone ─────────────────────────────────────────────────────────
    t0 = asyncio.get_event_loop().time()
    repo_path, clone_log = await _clone(repo_url, service_name)
    dur = asyncio.get_event_loop().time() - t0

    if not repo_path:
        return fail("Clone", clone_log, dur)
    add_stage("Clone", "success", clone_log, dur)

    # ── Stage 2: Validate ──────────────────────────────────────────────────────
    t1 = asyncio.get_event_loop().time()
    validation = validate_repo(repo_path)
    dur = asyncio.get_event_loop().time() - t1
    val_log = "\n".join(validation.checks + validation.warnings + validation.errors)

    if not validation.valid:
        shutil.rmtree(repo_path, ignore_errors=True)
        return fail("Validate", val_log, dur)
    add_stage("Validate", "success", val_log, dur)

    # ── Stage 3: Build & Push via Cloud Build ──────────────────────────────────
    t2 = asyncio.get_event_loop().time()
    build_ok, build_log = await _cloud_build(repo_path, image_uri)
    dur = asyncio.get_event_loop().time() - t2
    shutil.rmtree(repo_path, ignore_errors=True)

    if not build_ok:
        return fail("Build", build_log, dur)
    add_stage("Build", "success", f"Image: `{image_uri}`\n\n{build_log[-2000:]}", dur)

    # ── Stage 4: Deploy to Cloud Run ───────────────────────────────────────────
    t3 = asyncio.get_event_loop().time()
    deploy_ok, service_url, deploy_log = await _cloud_run_deploy(image_uri, service_name)
    dur = asyncio.get_event_loop().time() - t3

    if not deploy_ok:
        return fail("Deploy", deploy_log, dur)
    add_stage("Deploy", "success", deploy_log, dur)

    total = round((datetime.utcnow() - start).total_seconds())
    result = {
        "pipeline_id": pipeline_id,
        "app_name":    app_name,
        "version":     version,
        "repo_url":    repo_url,
        "status":      "success",
        "stages":      stages,
        "error":       None,
        "image_uri":   image_uri,
        "service_url": service_url,
        "created_at":  start.isoformat(),
        "total_duration_seconds": total,
    }
    _save_deployment(pipeline_id, app_name, version, "success", stages, repo_url, None, service_url)
    return result


# ── Stage implementations ──────────────────────────────────────────────────────

async def _clone(repo_url: str, name: str) -> Tuple[Optional[Path], str]:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    dest = WORKSPACE_DIR / f"{name}-{uuid.uuid4().hex[:6]}"
    if dest.exists():
        shutil.rmtree(dest)

    cmd = ["git", "clone", "--depth", "1", repo_url, str(dest)]
    logger.info("Cloning: %s", repo_url)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        output = stderr.decode()

        if proc.returncode != 0:
            logger.error("Clone failed:\n%s", output)
            return None, (
                f"Failed to clone `{repo_url}`.\n\n"
                f"**Error:**\n```\n{output[:1000]}\n```\n\n"
                "Check that the repository URL is correct and publicly accessible."
            )

        logger.info("Clone OK → %s", dest)
        return dest, f"✅ Cloned `{repo_url}` successfully."

    except asyncio.TimeoutError:
        return None, f"Clone timed out after 120s for `{repo_url}`."
    except FileNotFoundError:
        return None, "git not found. Install git: `sudo apt install git`"
    except Exception as exc:  # noqa: BLE001
        return None, f"Clone error: {exc}"


async def _cloud_build(repo_path: Path, image_uri: str) -> Tuple[bool, str]:
    logger.info("Starting Cloud Build → %s", image_uri)
    cmd = [
        "gcloud", "builds", "submit",
        "--tag", image_uri,
        "--timeout", "600",
        "--quiet",
        ".",
    ]
    rc, output = await _run_async(cmd, cwd=repo_path, timeout=660)
    if rc != 0:
        logger.error("Cloud Build failed:\n%s", output[-1000:])
        return False, (
            "Cloud Build failed.\n\n"
            f"**Error output:**\n```\n{output[-2000:]}\n```\n\n"
            "Common causes:\n"
            "- Dockerfile has a syntax error\n"
            "- A dependency failed to install\n"
            "- Artifact Registry permissions missing"
        )
    return True, output


async def _cloud_run_deploy(image_uri: str, service_name: str) -> Tuple[bool, str, str]:
    logger.info("Deploying to Cloud Run: %s", service_name)
    cmd = [
        "gcloud", "run", "deploy", service_name,
        "--image", image_uri,
        "--platform", "managed",
        "--region", GCP_REGION,
        "--allow-unauthenticated",
        "--memory", "512Mi",
        "--cpu", "1",
        "--min-instances", "0",
        "--max-instances", "5",
        "--port", "8080",
        "--quiet",
    ]
    rc, output = await _run_async(cmd, timeout=300)
    if rc != 0:
        logger.error("Cloud Run deploy failed:\n%s", output[-1000:])
        return False, "", (
            "Cloud Run deployment failed.\n\n"
            f"**Error:**\n```\n{output[-2000:]}\n```"
        )

    # Extract URL
    rc2, url_out = await _run_async([
        "gcloud", "run", "services", "describe", service_name,
        "--region", GCP_REGION,
        "--format=value(status.url)",
    ])
    url = url_out.strip() if rc2 == 0 else ""
    return True, url, output


# ── Subprocess helpers ──────────────────────────────────────────────────────────

def _run(cmd: List[str], cwd: Optional[Path] = None) -> Tuple[int, str]:
    try:
        r = subprocess.run(cmd, cwd=str(cwd) if cwd else None,
                           capture_output=True, text=True, timeout=30)
        return r.returncode, r.stdout + r.stderr
    except Exception as exc:  # noqa: BLE001
        return 1, str(exc)


async def _run_async(cmd: List[str], cwd: Optional[Path] = None, timeout: int = 300) -> Tuple[int, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd) if cwd else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode, stdout.decode() + stderr.decode()
    except asyncio.TimeoutError:
        return 1, f"Command timed out after {timeout}s: {' '.join(cmd)}"
    except FileNotFoundError:
        return 1, f"Command not found: {cmd[0]}"
    except Exception as exc:  # noqa: BLE001
        return 1, str(exc)


# ── DB save ────────────────────────────────────────────────────────────────────

def _save_deployment(
    dep_id: str,
    app_name: str,
    version: str,
    status: str,
    stages: List[Dict],
    repo_url: str,
    error_msg: Optional[str],
    service_url: Optional[str] = None,
):
    try:
        from services.database import save_deployment
        save_deployment({
            "id":            dep_id,
            "app_name":      app_name,
            "version":       version,
            "environment":   "production",
            "status":        status,
            "stages":        json.dumps(stages),
            "created_at":    datetime.utcnow().isoformat(),
            "completed_at":  datetime.utcnow().isoformat(),
            "triggered_by":  "ai-copilot",
            "error_message": error_msg,
            "service_url":   service_url or "",
        })
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not save deployment to DB: %s", exc)


def _safe_service_name(name: str) -> str:
    """Cloud Run service names: lowercase, alphanumeric + hyphens, max 49 chars."""
    name = re.sub(r"[^a-z0-9-]", "-", name.lower())
    name = re.sub(r"-+", "-", name).strip("-")
    return name[:49] or "app"
