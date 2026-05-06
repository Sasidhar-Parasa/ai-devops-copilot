"""
Real Deployment Service
Auth: Cloud Run SA (automatic) or local ADC.
Fixes: gcloud config dir via env var, better pre-flight checks.
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


def _is_cloud_run() -> bool:
    """True when running inside a Cloud Run container."""
    return bool(os.getenv("K_SERVICE") or os.getenv("GOOGLE_CLOUD_PROJECT"))


def _gcloud_env() -> dict:
    """
    Environment for gcloud subprocess calls.
    Sets CLOUDSDK_CONFIG to a guaranteed-writable directory.
    This fixes the 'Permission denied creating log dir' error.
    """
    env = os.environ.copy()
    # Use /tmp for gcloud config — always writable, even for non-root users
    gcloud_cfg = "/tmp/gcloud-config"
    os.makedirs(f"{gcloud_cfg}/logs", exist_ok=True)
    env["CLOUDSDK_CONFIG"] = gcloud_cfg
    env["HOME"] = "/tmp"
    # Disable gcloud update checks and analytics (faster + no config writes)
    env["CLOUDSDK_CORE_DISABLE_USAGE_REPORTING"] = "true"
    env["CLOUDSDK_COMPONENT_MANAGER_DISABLE_UPDATE_CHECK"] = "true"
    return env


def gcloud_available() -> bool:
    rc, _ = _run(["gcloud", "version"])
    return rc == 0


def check_gcp_config() -> Tuple[bool, str]:
    if not GCP_PROJECT_ID:
        return False, (
            "**GCP_PROJECT_ID** is not set.\n\n"
            "Add it to your Cloud Run service environment variables:\n"
            "```\nGCP_PROJECT_ID=your-project-id\n```"
        )

    if not gcloud_available():
        return False, (
            "**gcloud CLI not found** in the container.\n\n"
            "The backend Dockerfile must install `google-cloud-cli`.\n"
            "Redeploy the backend after updating the Dockerfile."
        )

    if _is_cloud_run():
        # On Cloud Run — use service account metadata server, no ADC needed
        # Verify access by describing the project
        rc, out = _run(
            ["gcloud", "projects", "describe", GCP_PROJECT_ID,
             "--format=value(projectId)", "--quiet"],
        )
        if rc != 0:
            # Parse out just the real error, strip the log dir warning
            clean_err = "\n".join(
                line for line in out.splitlines()
                if "log file" not in line.lower()
                and "CLOUDSDK_CONFIG" not in line
                and line.strip()
            )
            return False, (
                f"Could not access GCP project `{GCP_PROJECT_ID}`.\n\n"
                "Ensure the Cloud Run service account has these roles:\n"
                "- `roles/cloudbuild.builds.editor`\n"
                "- `roles/run.admin`\n"
                "- `roles/artifactregistry.writer`\n"
                "- `roles/iam.serviceAccountUser`\n"
                "- `roles/storage.admin`\n\n"
                f"Run: `bash grant_cloudrun_roles.sh`\n\n"
                f"Raw error:\n```\n{clean_err[:600]}\n```"
            )
        logger.info("✅ GCP auth OK via Cloud Run SA (project=%s)", GCP_PROJECT_ID)
        return True, ""
    else:
        # Local — check ADC
        rc, out = _run(
            ["gcloud", "auth", "list",
             "--filter=status:ACTIVE", "--format=value(account)"],
        )
        if rc != 0 or not out.strip():
            return False, (
                "No active GCP credentials found locally.\n\n"
                "```bash\ngcloud auth application-default login\n```"
            )
        logger.info("✅ GCP auth OK via ADC: %s", out.strip())
        return True, ""


# ── Validation ─────────────────────────────────────────────────────────────────

class ValidationResult:
    def __init__(self):
        self.valid    = True
        self.errors:   List[str] = []
        self.warnings: List[str] = []
        self.checks:   List[str] = []

    def fail(self, msg: str):
        self.valid = False
        self.errors.append(msg)

    def warn(self, msg: str):
        self.warnings.append(msg)

    def ok(self, msg: str):
        self.checks.append(msg)


def validate_repo(repo_path: Path) -> ValidationResult:
    result = ValidationResult()
    if not (repo_path / "Dockerfile").exists():
        result.fail(
            "**Dockerfile not found** in repository root.\n\n"
            "Add a `Dockerfile`. Python example:\n"
            "```dockerfile\n"
            "FROM python:3.11-slim\n"
            "WORKDIR /app\n"
            "COPY requirements.txt .\n"
            "RUN pip install -r requirements.txt\n"
            "COPY . .\n"
            'CMD ["python", "app.py"]\n'
            "```"
        )
    else:
        result.ok("✅ Dockerfile found")

    for ep in ["main.py", "app.py", "server.py", "index.js", "server.js"]:
        if (repo_path / ep).exists():
            result.ok(f"✅ Entry point: `{ep}`")
            break

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
    pid          = f"dep-{uuid.uuid4().hex[:8]}"
    stages: List[Dict] = []
    start        = datetime.utcnow()
    svc_name     = _safe_service_name(app_name)
    image_uri    = f"{AR_HOST}/{GCP_PROJECT_ID}/{AR_REPO}/{svc_name}:{version}"

    def stage(name: str, status: str, logs: str, dur: float):
        stages.append({"name": name, "status": status,
                        "logs": logs, "duration_seconds": round(dur),
                        "timestamp": datetime.utcnow().isoformat()})

    def fail(name: str, err: str, dur: float = 0) -> Dict:
        stage(name, "failed", err, dur)
        _save_dep(pid, app_name, version, "failed", stages, repo_url, err)
        return {"pipeline_id": pid, "app_name": app_name, "version": version,
                "repo_url": repo_url, "status": "failed", "stages": stages,
                "error": err, "service_url": None, "created_at": start.isoformat()}

    # Pre-flight
    ok, err = check_gcp_config()
    if not ok:
        return fail("Pre-flight", err)

    # Clone
    t = asyncio.get_event_loop().time()
    repo_path, log = await _clone(repo_url, svc_name)
    dur = asyncio.get_event_loop().time() - t
    if not repo_path:
        return fail("Clone", log, dur)
    stage("Clone", "success", log, dur)

    # Validate
    t = asyncio.get_event_loop().time()
    v = validate_repo(repo_path)
    dur = asyncio.get_event_loop().time() - t
    vlog = "\n".join(v.checks + v.warnings + v.errors)
    if not v.valid:
        shutil.rmtree(repo_path, ignore_errors=True)
        return fail("Validate", vlog, dur)
    stage("Validate", "success", vlog, dur)

    # Build
    t = asyncio.get_event_loop().time()
    ok, blog = await _cloud_build(repo_path, image_uri)
    dur = asyncio.get_event_loop().time() - t
    shutil.rmtree(repo_path, ignore_errors=True)
    if not ok:
        return fail("Build", blog, dur)
    stage("Build", "success", blog[-2000:], dur)

    # Deploy
    t = asyncio.get_event_loop().time()
    ok, svc_url, dlog = await _cloud_run_deploy(image_uri, svc_name)
    dur = asyncio.get_event_loop().time() - t
    if not ok:
        return fail("Deploy", dlog, dur)
    stage("Deploy", "success", dlog, dur)

    total = round((datetime.utcnow() - start).total_seconds())
    result = {"pipeline_id": pid, "app_name": app_name, "version": version,
              "repo_url": repo_url, "status": "success", "stages": stages,
              "error": None, "image_uri": image_uri, "service_url": svc_url,
              "created_at": start.isoformat(), "total_duration_seconds": total}
    _save_dep(pid, app_name, version, "success", stages, repo_url, None, svc_url)
    return result


# ── Stage implementations ──────────────────────────────────────────────────────

async def _clone(repo_url: str, name: str) -> Tuple[Optional[Path], str]:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    dest = WORKSPACE_DIR / f"{name}-{uuid.uuid4().hex[:6]}"
    if dest.exists():
        shutil.rmtree(dest)
    rc, out = await _async(["git", "clone", "--depth", "1", repo_url, str(dest)], timeout=120)
    if rc != 0:
        logger.error("Clone failed: %s", out[:500])
        return None, (
            f"Failed to clone `{repo_url}`\n```\n{out[:800]}\n```\n"
            "Make sure the repo is public and the URL is correct."
        )
    return dest, f"✅ Cloned `{repo_url}`"


async def _cloud_build(repo_path: Path, image_uri: str) -> Tuple[bool, str]:
    logger.info("Cloud Build → %s", image_uri)
    rc, out = await _async(
        ["gcloud", "builds", "submit", "--tag", image_uri,
         "--timeout", "600", "--quiet", "."],
        cwd=repo_path, timeout=660,
    )
    if rc != 0:
        logger.error("Build failed: %s", out[-500:])
        return False, f"Cloud Build failed.\n```\n{out[-2000:]}\n```"
    return True, out


async def _cloud_run_deploy(image_uri: str, svc: str) -> Tuple[bool, str, str]:
    logger.info("Deploying to Cloud Run: %s", svc)
    rc, out = await _async([
        "gcloud", "run", "deploy", svc,
        "--image", image_uri,
        "--platform", "managed",
        "--region", GCP_REGION,
        "--allow-unauthenticated",
        "--memory", "512Mi", "--cpu", "1",
        "--min-instances", "0", "--max-instances", "5",
        "--port", "8080", "--quiet",
    ], timeout=300)
    if rc != 0:
        logger.error("Deploy failed: %s", out[-500:])
        return False, "", f"Cloud Run deploy failed.\n```\n{out[-2000:]}\n```"
    rc2, url = await _async([
        "gcloud", "run", "services", "describe", svc,
        "--region", GCP_REGION, "--format=value(status.url)",
    ])
    return True, url.strip(), out


# ── Subprocess helpers ──────────────────────────────────────────────────────────

def _run(cmd: List[str], cwd: Optional[Path] = None) -> Tuple[int, str]:
    try:
        r = subprocess.run(
            cmd, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=30,
            env=_gcloud_env(),
        )
        return r.returncode, r.stdout + r.stderr
    except Exception as exc:  # noqa: BLE001
        return 1, str(exc)


async def _async(cmd: List[str], cwd: Optional[Path] = None,
                 timeout: int = 300) -> Tuple[int, str]:
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


# ── DB + utils ─────────────────────────────────────────────────────────────────

def _save_dep(pid: str, app: str, ver: str, status: str, stages: list,
              repo_url: str, err: Optional[str], url: Optional[str] = None):
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


def _safe_service_name(name: str) -> str:
    name = re.sub(r"[^a-z0-9-]", "-", name.lower())
    return re.sub(r"-+", "-", name).strip("-")[:49] or "app"