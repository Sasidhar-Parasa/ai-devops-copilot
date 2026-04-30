"""
Real Deployment Service — works both locally AND on Cloud Run.

Auth strategy:
- Local:      uses gcloud ADC (Application Default Credentials)
- Cloud Run:  uses the attached Service Account (automatic, no key needed)
             The Cloud Run SA must have: roles/cloudbuild.builds.editor,
             roles/run.admin, roles/artifactregistry.writer
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


# ── Auth detection ─────────────────────────────────────────────────────────────

def _is_running_on_cloud_run() -> bool:
    """Detect if we're inside a Cloud Run container."""
    return (
        os.getenv("K_SERVICE") is not None          # Cloud Run sets K_SERVICE
        or os.getenv("GOOGLE_CLOUD_PROJECT") is not None
        or os.path.exists("/var/run/secrets/kubernetes.io")
    )


def check_gcp_config() -> Tuple[bool, str]:
    """
    Validate GCP is usable.
    On Cloud Run: SA auth is automatic — just verify PROJECT_ID is set.
    Locally:      verify gcloud ADC is configured.
    """
    if not GCP_PROJECT_ID:
        return False, (
            "**GCP_PROJECT_ID** is not set.\n\n"
            "Add it to your environment:\n"
            "```\n"
            "GCP_PROJECT_ID=your-project-id\n"
            "```\n"
            "Then redeploy the backend service."
        )

    if _is_running_on_cloud_run():
        # On Cloud Run, credentials come from the attached SA automatically.
        # Just verify gcloud is present (it's not in the default Python image).
        if not gcloud_available():
            return False, (
                "**gcloud CLI not found** in the Cloud Run container.\n\n"
                "The backend Dockerfile must install the Google Cloud SDK.\n"
                "See the updated Dockerfile below."
            )
        # Verify the SA can reach GCP by listing the project
        rc, out = _run(["gcloud", "projects", "describe", GCP_PROJECT_ID,
                        "--format=value(projectId)", "--quiet"])
        if rc != 0:
            return False, (
                f"Could not access GCP project `{GCP_PROJECT_ID}`.\n\n"
                "Ensure the Cloud Run service account has these roles:\n"
                "- `roles/cloudbuild.builds.editor`\n"
                "- `roles/run.admin`\n"
                "- `roles/artifactregistry.writer`\n"
                "- `roles/iam.serviceAccountUser`\n\n"
                f"Error: {out[:400]}"
            )
        logger.info("GCP auth OK via Cloud Run service account (project=%s)", GCP_PROJECT_ID)
        return True, ""

    else:
        # Local: check ADC
        rc, out = _run(["gcloud", "auth", "list",
                        "--filter=status:ACTIVE", "--format=value(account)"])
        if rc != 0 or not out.strip():
            return False, (
                "No active GCP credentials found locally.\n\n"
                "Run:\n"
                "```bash\n"
                "gcloud auth application-default login\n"
                "```"
            )
        logger.info("GCP auth OK via ADC: %s", out.strip())
        return True, ""


def gcloud_available() -> bool:
    rc, _ = _run(["gcloud", "version"])
    return rc == 0


# ── Validation ─────────────────────────────────────────────────────────────────

class ValidationResult:
    def __init__(self):
        self.valid    = True
        self.errors:  List[str] = []
        self.warnings: List[str] = []
        self.checks:  List[str] = []

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
            "Add a `Dockerfile` to your project. Quick Python example:\n"
            "```dockerfile\n"
            "FROM python:3.11-slim\n"
            "WORKDIR /app\n"
            "COPY requirements.txt .\n"
            "RUN pip install -r requirements.txt\n"
            "COPY . .\n"
            'CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]\n'
            "```"
        )
    else:
        result.ok("✅ Dockerfile found")

    entry_points = ["main.py", "app.py", "server.py", "index.js", "server.js"]
    found_entry  = [e for e in entry_points if (repo_path / e).exists()]
    if found_entry:
        result.ok(f"✅ Entry point: `{found_entry[0]}`")

    for dep in ["requirements.txt", "package.json", "pyproject.toml", "go.mod"]:
        if (repo_path / dep).exists():
            result.ok(f"✅ `{dep}` found")
            break

    return result


# ── Pipeline ───────────────────────────────────────────────────────────────────

async def full_deploy_pipeline(
    repo_url: str,
    app_name: str,
    version: str = "latest",
) -> Dict[str, Any]:
    pipeline_id  = f"dep-{uuid.uuid4().hex[:8]}"
    stages: List[Dict] = []
    start        = datetime.utcnow()
    service_name = _safe_service_name(app_name)
    image_uri    = f"{AR_HOST}/{GCP_PROJECT_ID}/{AR_REPO}/{service_name}:{version}"

    def add_stage(name: str, status: str, logs: str, dur: float):
        stages.append({
            "name": name, "status": status,
            "logs": logs, "duration_seconds": round(dur),
            "timestamp": datetime.utcnow().isoformat(),
        })

    def fail(stage: str, error: str, dur: float = 0) -> Dict:
        add_stage(stage, "failed", error, dur)
        _save(pipeline_id, app_name, version, "failed", stages, repo_url, error)
        return {
            "pipeline_id": pipeline_id, "app_name": app_name,
            "version": version, "repo_url": repo_url,
            "status": "failed", "stages": stages,
            "error": error, "service_url": None,
            "created_at": start.isoformat(),
        }

    # Pre-flight
    gcp_ok, gcp_err = check_gcp_config()
    if not gcp_ok:
        return fail("Pre-flight", gcp_err)

    if not gcloud_available():
        return fail("Pre-flight", "gcloud CLI not found. The backend container must install it.")

    # Stage 1: Clone
    t0 = asyncio.get_event_loop().time()
    repo_path, clone_log = await _clone(repo_url, service_name)
    dur = asyncio.get_event_loop().time() - t0
    if not repo_path:
        return fail("Clone", clone_log, dur)
    add_stage("Clone", "success", clone_log, dur)

    # Stage 2: Validate
    t1 = asyncio.get_event_loop().time()
    validation = validate_repo(repo_path)
    dur = asyncio.get_event_loop().time() - t1
    val_log = "\n".join(validation.checks + validation.warnings + validation.errors)
    if not validation.valid:
        shutil.rmtree(repo_path, ignore_errors=True)
        return fail("Validate", val_log, dur)
    add_stage("Validate", "success", val_log, dur)

    # Stage 3: Cloud Build
    t2 = asyncio.get_event_loop().time()
    build_ok, build_log = await _cloud_build(repo_path, image_uri)
    dur = asyncio.get_event_loop().time() - t2
    shutil.rmtree(repo_path, ignore_errors=True)
    if not build_ok:
        return fail("Build", build_log, dur)
    add_stage("Build", "success", build_log[-2000:], dur)

    # Stage 4: Cloud Run deploy
    t3 = asyncio.get_event_loop().time()
    deploy_ok, service_url, deploy_log = await _cloud_run_deploy(image_uri, service_name)
    dur = asyncio.get_event_loop().time() - t3
    if not deploy_ok:
        return fail("Deploy", deploy_log, dur)
    add_stage("Deploy", "success", deploy_log, dur)

    total = round((datetime.utcnow() - start).total_seconds())
    result = {
        "pipeline_id": pipeline_id, "app_name": app_name,
        "version": version, "repo_url": repo_url,
        "status": "success", "stages": stages, "error": None,
        "image_uri": image_uri, "service_url": service_url,
        "created_at": start.isoformat(), "total_duration_seconds": total,
    }
    _save(pipeline_id, app_name, version, "success", stages, repo_url, None, service_url)
    return result


# ── Stage helpers ──────────────────────────────────────────────────────────────

async def _clone(repo_url: str, name: str) -> Tuple[Optional[Path], str]:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    dest = WORKSPACE_DIR / f"{name}-{uuid.uuid4().hex[:6]}"
    if dest.exists():
        shutil.rmtree(dest)

    rc, output = await _run_async(
        ["git", "clone", "--depth", "1", repo_url, str(dest)],
        timeout=120,
    )
    if rc != 0:
        logger.error("Clone failed: %s", output[:500])
        return None, (
            f"Failed to clone `{repo_url}`\n\n"
            f"```\n{output[:800]}\n```\n\n"
            "Make sure the repo is public and the URL is correct."
        )
    return dest, f"✅ Cloned `{repo_url}`"


async def _cloud_build(repo_path: Path, image_uri: str) -> Tuple[bool, str]:
    logger.info("Cloud Build → %s", image_uri)
    rc, output = await _run_async(
        ["gcloud", "builds", "submit", "--tag", image_uri,
         "--timeout", "600", "--quiet", "."],
        cwd=repo_path,
        timeout=660,
    )
    if rc != 0:
        logger.error("Cloud Build failed: %s", output[-500:])
        return False, (
            "Cloud Build failed.\n\n"
            f"```\n{output[-2000:]}\n```"
        )
    return True, output


async def _cloud_run_deploy(image_uri: str, service_name: str) -> Tuple[bool, str, str]:
    logger.info("Deploying to Cloud Run: %s", service_name)
    rc, output = await _run_async(
        [
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
        ],
        timeout=300,
    )
    if rc != 0:
        logger.error("Cloud Run deploy failed: %s", output[-500:])
        return False, "", f"Cloud Run deployment failed.\n\n```\n{output[-2000:]}\n```"

    rc2, url = await _run_async([
        "gcloud", "run", "services", "describe", service_name,
        "--region", GCP_REGION, "--format=value(status.url)",
    ])
    return True, url.strip(), output


# ── Subprocess utils ───────────────────────────────────────────────────────────

def _run(cmd: List[str], cwd: Optional[Path] = None) -> Tuple[int, str]:
    try:
        r = subprocess.run(cmd, cwd=str(cwd) if cwd else None,
                           capture_output=True, text=True, timeout=30)
        return r.returncode, r.stdout + r.stderr
    except Exception as exc:  # noqa: BLE001
        return 1, str(exc)


async def _run_async(cmd: List[str], cwd: Optional[Path] = None,
                     timeout: int = 300) -> Tuple[int, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(cwd) if cwd else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode, stdout.decode() + stderr.decode()
    except asyncio.TimeoutError:
        return 1, f"Timed out after {timeout}s: {' '.join(cmd)}"
    except FileNotFoundError:
        return 1, f"Command not found: {cmd[0]}"
    except Exception as exc:  # noqa: BLE001
        return 1, str(exc)


# ── DB helper ──────────────────────────────────────────────────────────────────

def _save(dep_id: str, app_name: str, version: str, status: str,
          stages: list, repo_url: str, error: Optional[str],
          service_url: Optional[str] = None):
    try:
        from services.database import save_deployment
        save_deployment({
            "id": dep_id, "app_name": app_name, "version": version,
            "environment": "production", "status": status,
            "stages": json.dumps(stages),
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
            "triggered_by": "ai-copilot",
            "error_message": error,
            "service_url": service_url or "",
            "repo_url": repo_url or "",
        })
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not save deployment: %s", exc)


def _safe_service_name(name: str) -> str:
    name = re.sub(r"[^a-z0-9-]", "-", name.lower())
    return re.sub(r"-+", "-", name).strip("-")[:49] or "app"