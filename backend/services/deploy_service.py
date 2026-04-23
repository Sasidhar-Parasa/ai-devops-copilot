"""
Real Deployment Service
Clones GitHub repos, validates structure, builds Docker images,
pushes to GCP Artifact Registry, deploys to Cloud Run.
"""
import asyncio
import logging
import os
import re
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

WORKSPACE_DIR  = Path(os.getenv("WORKSPACE_DIR", "/tmp/copilot-workspace"))
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
GCP_REGION     = os.getenv("GCP_REGION", "us-central1")
ARTIFACT_REPO  = f"{GCP_REGION}-docker.pkg.dev"


# ── Validation ────────────────────────────────────────────────────────────────

class ValidationResult:
    def __init__(self):
        self.valid = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def fail(self, msg: str):
        self.valid = False
        self.errors.append(msg)

    def warn(self, msg: str):
        self.warnings.append(msg)

    def ok(self, msg: str):
        self.info.append(msg)


def validate_repo_structure(repo_path: Path, app_name: str) -> ValidationResult:
    """Validate cloned repo has everything needed to deploy."""
    result = ValidationResult()

    # Must have Dockerfile
    dockerfile = repo_path / "Dockerfile"
    if not dockerfile.exists():
        result.fail(
            "❌ **Dockerfile not found** in repo root.\n"
            "   Please add a `Dockerfile` to deploy this application.\n\n"
            "   **Quick example for Python:**\n"
            "   ```dockerfile\n"
            "   FROM python:3.11-slim\n"
            "   WORKDIR /app\n"
            "   COPY requirements.txt .\n"
            "   RUN pip install -r requirements.txt\n"
            "   COPY . .\n"
            "   CMD [\"uvicorn\", \"main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8080\"]\n"
            "   ```"
        )
    else:
        result.ok("✅ Dockerfile found")

    # Python project checks
    if (repo_path / "requirements.txt").exists():
        result.ok("✅ requirements.txt found")
    elif (repo_path / "pyproject.toml").exists():
        result.ok("✅ pyproject.toml found")
    elif (repo_path / "setup.py").exists():
        result.ok("✅ setup.py found")

    # Node project checks
    if (repo_path / "package.json").exists():
        result.ok("✅ package.json found")

    # Warn if no app entry point guessable
    common_entries = ["main.py", "app.py", "server.py", "index.js", "server.js"]
    found_entry = any((repo_path / e).exists() for e in common_entries)
    if not found_entry and dockerfile.exists():
        result.warn("⚠️ No common entry point detected — ensure your Dockerfile CMD is set correctly")

    return result


# ── Git ───────────────────────────────────────────────────────────────────────

async def clone_repo(repo_url: str, app_name: str) -> Tuple[Optional[Path], str]:
    """Clone a GitHub repo. Returns (path, log_output)."""
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    dest = WORKSPACE_DIR / f"{app_name}-{uuid.uuid4().hex[:6]}"

    # Remove if already exists
    if dest.exists():
        shutil.rmtree(dest)

    cmd = ["git", "clone", "--depth", "1", repo_url, str(dest)]
    log_lines = [f"$ git clone --depth 1 {repo_url}"]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        output = stderr.decode()

        if proc.returncode != 0:
            log_lines.append(f"❌ Git clone failed:\n{output}")
            return None, "\n".join(log_lines)

        log_lines.append(f"✅ Cloned to {dest}")
        return dest, "\n".join(log_lines)

    except asyncio.TimeoutError:
        log_lines.append("❌ Git clone timed out (120s)")
        return None, "\n".join(log_lines)
    except FileNotFoundError:
        log_lines.append("❌ `git` not found — please install git")
        return None, "\n".join(log_lines)
    except Exception as e:
        log_lines.append(f"❌ Clone error: {e}")
        return None, "\n".join(log_lines)


# ── Docker / GCP ─────────────────────────────────────────────────────────────

def _run_cmd(cmd: List[str], cwd: Optional[Path] = None, timeout: int = 300) -> Tuple[int, str]:
    """Run a shell command synchronously, capture output."""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        return result.returncode, output
    except subprocess.TimeoutExpired:
        return 1, f"❌ Command timed out after {timeout}s: {' '.join(cmd)}"
    except FileNotFoundError as e:
        return 1, f"❌ Command not found: {e}"
    except Exception as e:
        return 1, f"❌ Error: {e}"


def _gcloud_available() -> bool:
    rc, _ = _run_cmd(["gcloud", "version"])
    return rc == 0


def _docker_available() -> bool:
    rc, _ = _run_cmd(["docker", "info"])
    return rc == 0


async def build_and_push_image(
    repo_path: Path,
    app_name: str,
    version: str = "latest",
) -> Tuple[bool, str, str]:
    """
    Build Docker image and push to GCP Artifact Registry.
    Returns (success, image_uri, logs).
    Falls back to Cloud Build if local Docker unavailable.
    """
    logs = []
    image_tag = re.sub(r"[^a-z0-9-]", "-", app_name.lower())
    image_uri = f"{ARTIFACT_REPO}/{GCP_PROJECT_ID}/copilot/{image_tag}:{version}"

    if not GCP_PROJECT_ID:
        return False, "", "❌ GCP_PROJECT_ID not set in environment"

    # Try Cloud Build (no local Docker needed)
    logs.append(f"☁️  Using Cloud Build to build image...")
    logs.append(f"📦 Image: {image_uri}")
    logs.append(f"$ gcloud builds submit --tag {image_uri}")

    rc, out = _run_cmd(
        ["gcloud", "builds", "submit",
         "--tag", image_uri,
         "--timeout", "600",
         "--quiet",
         "."],
        cwd=repo_path,
        timeout=660,
    )

    logs.append(out[-3000:] if len(out) > 3000 else out)  # last 3k chars

    if rc != 0:
        return False, image_uri, "\n".join(logs)

    logs.append(f"✅ Image built and pushed: {image_uri}")
    return True, image_uri, "\n".join(logs)


async def deploy_to_cloud_run(
    image_uri: str,
    app_name: str,
    region: str = None,
) -> Tuple[bool, str, str]:
    """
    Deploy image to Cloud Run.
    Returns (success, service_url, logs).
    """
    logs = []
    region = region or GCP_REGION
    service_name = re.sub(r"[^a-z0-9-]", "-", app_name.lower())[:50]

    logs.append(f"🚀 Deploying `{service_name}` to Cloud Run ({region})...")
    logs.append(f"$ gcloud run deploy {service_name} --image {image_uri}")

    rc, out = _run_cmd(
        [
            "gcloud", "run", "deploy", service_name,
            "--image", image_uri,
            "--platform", "managed",
            "--region", region,
            "--allow-unauthenticated",
            "--memory", "512Mi",
            "--cpu", "1",
            "--min-instances", "0",
            "--max-instances", "3",
            "--port", "8080",
            "--quiet",
        ],
        timeout=300,
    )

    logs.append(out[-2000:] if len(out) > 2000 else out)

    if rc != 0:
        return False, "", "\n".join(logs)

    # Extract URL
    rc2, url_out = _run_cmd([
        "gcloud", "run", "services", "describe", service_name,
        "--region", region,
        "--format=value(status.url)",
    ])
    service_url = url_out.strip() if rc2 == 0 else ""
    logs.append(f"✅ Service live at: {service_url}")

    return True, service_url, "\n".join(logs)


# ── High-level orchestrator ───────────────────────────────────────────────────

async def full_deploy_pipeline(
    repo_url: str,
    app_name: str,
    version: str = "latest",
) -> Dict[str, Any]:
    """
    Full pipeline: clone → validate → build → push → deploy.
    Returns structured result dict with all stage details.
    """
    pipeline_id = f"pipeline-{uuid.uuid4().hex[:8]}"
    stages = []
    start_time = datetime.utcnow()

    def stage(name: str, status: str, logs: str, duration_s: float):
        stages.append({
            "name": name,
            "status": status,
            "logs": logs,
            "duration_seconds": round(duration_s),
            "timestamp": datetime.utcnow().isoformat(),
        })

    # ── Stage 1: Clone ────────────────────────────────────────────────────────
    t0 = asyncio.get_event_loop().time()
    repo_path, clone_logs = await clone_repo(repo_url, app_name)
    clone_dur = asyncio.get_event_loop().time() - t0

    if not repo_path:
        stage("Clone", "failed", clone_logs, clone_dur)
        return _failed_result(pipeline_id, app_name, stages, "Repository clone failed")

    stage("Clone", "success", clone_logs, clone_dur)

    # ── Stage 2: Validate ─────────────────────────────────────────────────────
    t1 = asyncio.get_event_loop().time()
    validation = validate_repo_structure(repo_path, app_name)
    val_dur = asyncio.get_event_loop().time() - t1

    val_logs = "\n".join(validation.info + validation.warnings + validation.errors)

    if not validation.valid:
        stage("Validate", "failed", val_logs, val_dur)
        # Clean up
        shutil.rmtree(repo_path, ignore_errors=True)
        return {
            "pipeline_id": pipeline_id,
            "app_name": app_name,
            "repo_url": repo_url,
            "status": "validation_failed",
            "stages": stages,
            "error": "Validation failed — see logs for details",
            "validation_errors": validation.errors,
            "validation_warnings": validation.warnings,
            "service_url": None,
            "created_at": start_time.isoformat(),
        }

    stage("Validate", "success", val_logs, val_dur)

    # ── Stage 3: Build & Push ─────────────────────────────────────────────────
    if not _gcloud_available():
        # Simulate for local dev without gcloud
        stage("Build", "simulated", "⚠️ gcloud not available — simulating build step", 2)
        stage("Deploy", "simulated", "⚠️ gcloud not available — simulating deploy step", 1)
        shutil.rmtree(repo_path, ignore_errors=True)
        return {
            "pipeline_id": pipeline_id,
            "app_name": app_name,
            "repo_url": repo_url,
            "status": "simulated",
            "stages": stages,
            "error": None,
            "service_url": f"https://{app_name}-simulated.run.app",
            "created_at": start_time.isoformat(),
            "note": "gcloud CLI not found — deployment was simulated. Configure GCP to deploy for real.",
        }

    t2 = asyncio.get_event_loop().time()
    build_ok, image_uri, build_logs = await build_and_push_image(repo_path, app_name, version)
    build_dur = asyncio.get_event_loop().time() - t2

    stage("Build", "success" if build_ok else "failed", build_logs, build_dur)

    if not build_ok:
        shutil.rmtree(repo_path, ignore_errors=True)
        return _failed_result(pipeline_id, app_name, stages, "Docker build/push failed")

    # ── Stage 4: Deploy ───────────────────────────────────────────────────────
    t3 = asyncio.get_event_loop().time()
    deploy_ok, service_url, deploy_logs = await deploy_to_cloud_run(image_uri, app_name)
    deploy_dur = asyncio.get_event_loop().time() - t3

    stage("Deploy", "success" if deploy_ok else "failed", deploy_logs, deploy_dur)

    # Cleanup workspace
    shutil.rmtree(repo_path, ignore_errors=True)

    total_dur = (datetime.utcnow() - start_time).total_seconds()

    if not deploy_ok:
        return _failed_result(pipeline_id, app_name, stages, "Cloud Run deployment failed")

    return {
        "pipeline_id": pipeline_id,
        "app_name": app_name,
        "repo_url": repo_url,
        "status": "success",
        "stages": stages,
        "error": None,
        "image_uri": image_uri,
        "service_url": service_url,
        "created_at": start_time.isoformat(),
        "total_duration_seconds": round(total_dur),
    }


def _failed_result(pipeline_id: str, app_name: str, stages: list, error: str) -> Dict:
    return {
        "pipeline_id": pipeline_id,
        "app_name": app_name,
        "status": "failed",
        "stages": stages,
        "error": error,
        "service_url": None,
        "created_at": datetime.utcnow().isoformat(),
    }
