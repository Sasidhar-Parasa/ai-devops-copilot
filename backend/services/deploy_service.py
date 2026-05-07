"""
Real Deployment Service
Key fix: gcloud builds submit returns exit code 1 when it can't stream logs,
even if the build SUCCEEDS. We detect this and poll build status separately.
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

# Build timeout in seconds (Cloud Build default is 10min)
BUILD_POLL_TIMEOUT = 600
BUILD_POLL_INTERVAL = 5


def _is_cloud_run() -> bool:
    return bool(os.getenv("K_SERVICE") or os.getenv("GOOGLE_CLOUD_PROJECT"))


def _gcloud_env() -> dict:
    """Always route gcloud config to /tmp — writable in any container."""
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


def check_gcp_config() -> Tuple[bool, str]:
    if not GCP_PROJECT_ID:
        return False, (
            "**GCP_PROJECT_ID** is not set.\n\n"
            "Add it to your Cloud Run service environment variables and redeploy."
        )
    if not gcloud_available():
        return False, (
            "**gcloud CLI not found** in the container.\n\n"
            "Rebuild and redeploy the backend after updating the Dockerfile."
        )

    # Verify GCP access
    rc, out = _run_sync(
        ["gcloud", "projects", "describe", GCP_PROJECT_ID,
         "--format=value(projectId)", "--quiet"]
    )
    if rc != 0:
        clean = _clean_gcloud_output(out)
        return False, (
            f"Cannot access GCP project `{GCP_PROJECT_ID}`.\n\n"
            "Run `grant_cloudrun_roles.sh` to fix SA permissions.\n\n"
            f"```\n{clean[:400]}\n```"
        )
    logger.info("✅ GCP OK (project=%s, cloud_run=%s)", GCP_PROJECT_ID, _is_cloud_run())
    return True, ""


def _clean_gcloud_output(text: str) -> str:
    """Remove gcloud log-dir warnings — they're noise, not real errors."""
    skip = ("log file", "CLOUDSDK_CONFIG", "configuration directory",
            "Permission denied", "creating a configuration")
    lines = [l for l in text.splitlines()
             if not any(s.lower() in l.lower() for s in skip)
             and l.strip()]
    return "\n".join(lines)


# ── Validation ─────────────────────────────────────────────────────────────────

class ValidationResult:
    def __init__(self):
        self.valid    = True
        self.errors:   List[str] = []
        self.warnings: List[str] = []
        self.checks:   List[str] = []

    def fail(self, m: str):
        self.valid = False
        self.errors.append(m)

    def warn(self, m: str):
        self.warnings.append(m)

    def ok(self, m: str):
        self.checks.append(m)


def validate_repo(path: Path) -> ValidationResult:
    r = ValidationResult()
    if not (path / "Dockerfile").exists():
        r.fail(
            "**Dockerfile not found** in repo root.\n\n"
            "Quick Python example:\n"
            "```dockerfile\n"
            "FROM python:3.11-slim\n"
            "WORKDIR /app\n"
            "COPY . .\n"
            "RUN pip install flask\n"
            'CMD ["python", "app.py"]\n'
            "```"
        )
    else:
        r.ok("✅ Dockerfile found")
    for ep in ["main.py", "app.py", "server.py", "index.js"]:
        if (path / ep).exists():
            r.ok(f"✅ Entry point: `{ep}`")
            break
    for dep in ["requirements.txt", "package.json", "pyproject.toml"]:
        if (path / dep).exists():
            r.ok(f"✅ `{dep}` found")
            break
    return r


# ── Main pipeline ──────────────────────────────────────────────────────────────

async def full_deploy_pipeline(
    repo_url: str,
    app_name: str,
    version: str = "latest",
) -> Dict[str, Any]:
    pid       = f"dep-{uuid.uuid4().hex[:8]}"
    stages:  List[Dict] = []
    start     = datetime.utcnow()
    svc_name  = _safe_name(app_name)
    image_uri = f"{AR_HOST}/{GCP_PROJECT_ID}/{AR_REPO}/{svc_name}:{version}"

    def add(name: str, status: str, logs: str, dur: float):
        stages.append({"name": name, "status": status,
                        "logs": logs, "duration_seconds": round(dur),
                        "timestamp": datetime.utcnow().isoformat()})

    def fail(name: str, err: str, dur: float = 0) -> Dict:
        add(name, "failed", err, dur)
        _save(pid, app_name, version, "failed", stages, repo_url, err)
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
    add("Clone", "success", log, dur)

    # Validate
    t = asyncio.get_event_loop().time()
    v = validate_repo(repo_path)
    dur = asyncio.get_event_loop().time() - t
    vlog = "\n".join(v.checks + v.warnings + v.errors)
    if not v.valid:
        shutil.rmtree(repo_path, ignore_errors=True)
        return fail("Validate", vlog, dur)
    add("Validate", "success", vlog, dur)

    # Build
    t = asyncio.get_event_loop().time()
    ok, build_id, blog = await _cloud_build(repo_path, image_uri)
    dur = asyncio.get_event_loop().time() - t
    shutil.rmtree(repo_path, ignore_errors=True)
    if not ok:
        return fail("Build", blog, dur)
    build_log_url = (
        f"https://console.cloud.google.com/cloud-build/builds/{build_id}"
        f"?project={GCP_PROJECT_ID}"
    ) if build_id else ""
    add("Build", "success",
        f"✅ Image: `{image_uri}`\n[View build logs]({build_log_url})", dur)

    # Deploy
    t = asyncio.get_event_loop().time()
    ok, svc_url, dlog = await _cloud_run_deploy(image_uri, svc_name)
    dur = asyncio.get_event_loop().time() - t
    if not ok:
        return fail("Deploy", dlog, dur)
    add("Deploy", "success", dlog, dur)

    total = round((datetime.utcnow() - start).total_seconds())
    result = {"pipeline_id": pid, "app_name": app_name, "version": version,
              "repo_url": repo_url, "status": "success", "stages": stages,
              "error": None, "image_uri": image_uri, "service_url": svc_url,
              "created_at": start.isoformat(), "total_duration_seconds": total}
    _save(pid, app_name, version, "success", stages, repo_url, None, svc_url)
    return result


# ── Stage: Clone ───────────────────────────────────────────────────────────────

async def _clone(repo_url: str, name: str) -> Tuple[Optional[Path], str]:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    dest = WORKSPACE_DIR / f"{name}-{uuid.uuid4().hex[:6]}"
    if dest.exists():
        shutil.rmtree(dest)
    rc, out = await _run(["git", "clone", "--depth", "1", repo_url, str(dest)],
                         timeout=120)
    if rc != 0:
        return None, (
            f"Failed to clone `{repo_url}`\n```\n{out[:600]}\n```\n"
            "Ensure the repo is public and the URL is correct."
        )
    return dest, f"✅ Cloned `{repo_url}`"


# ── Stage: Build ───────────────────────────────────────────────────────────────

async def _cloud_build(repo_path: Path, image_uri: str) -> Tuple[bool, str, str]:
    """
    Submit build and poll for completion.

    WHY we don't just check the exit code of 'gcloud builds submit':
    When the Cloud Run SA lacks 'logging.viewer' role, gcloud can't stream
    build logs and exits with code 1 — even if the build SUCCEEDS.
    Solution: extract the build ID from output, then poll build status.
    """
    logger.info("Submitting Cloud Build → %s", image_uri)

    rc, out = await _run(
        ["gcloud", "builds", "submit",
         "--tag", image_uri,
         "--timeout", "600",
         "--async",          # ← don't wait for streaming — just submit
         "--quiet", "."],
        cwd=repo_path,
        timeout=120,         # just for submission, not the build itself
    )

    # Extract build ID from output regardless of rc
    build_id = _extract_build_id(out)
    logger.info("Build submitted: id=%s rc=%d", build_id, rc)

    if not build_id:
        # Submission itself failed (not a streaming issue)
        return False, "", (
            "Failed to submit build to Cloud Build.\n\n"
            f"```\n{_clean_gcloud_output(out)[:1500]}\n```"
        )

    # Poll until build finishes
    logger.info("Polling build %s ...", build_id)
    ok, poll_log = await _poll_build(build_id)
    return ok, build_id, poll_log


async def _poll_build(build_id: str) -> Tuple[bool, str]:
    """Poll Cloud Build status until SUCCESS or FAILURE."""
    deadline = asyncio.get_event_loop().time() + BUILD_POLL_TIMEOUT
    last_status = "UNKNOWN"

    while asyncio.get_event_loop().time() < deadline:
        rc, out = await _run([
            "gcloud", "builds", "describe", build_id,
            "--format=value(status)",
            "--quiet",
        ])

        if rc == 0:
            last_status = out.strip()
            logger.info("Build %s status: %s", build_id, last_status)

            if last_status == "SUCCESS":
                return True, f"✅ Cloud Build succeeded (id: `{build_id}`)"

            if last_status in ("FAILURE", "INTERNAL_ERROR", "TIMEOUT", "CANCELLED"):
                # Fetch the last few log lines for context
                _, log_out = await _run([
                    "gcloud", "builds", "log", build_id,
                    "--quiet",
                ], timeout=30)
                tail = log_out[-1500:] if log_out else "(no logs available)"
                return False, (
                    f"Cloud Build **{last_status}** (id: `{build_id}`)\n\n"
                    f"```\n{tail}\n```\n\n"
                    f"[Full logs](https://console.cloud.google.com/cloud-build/builds/"
                    f"{build_id}?project={GCP_PROJECT_ID})"
                )

        await asyncio.sleep(BUILD_POLL_INTERVAL)

    return False, (
        f"Build timed out after {BUILD_POLL_TIMEOUT}s (status: {last_status}).\n"
        f"Check: https://console.cloud.google.com/cloud-build/builds/{build_id}"
    )


def _extract_build_id(output: str) -> Optional[str]:
    """Pull build UUID from gcloud output."""
    # Pattern: 'Created [https://.../builds/UUID]'
    m = re.search(
        r"builds/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
        output,
    )
    return m.group(1) if m else None


# ── Stage: Deploy ──────────────────────────────────────────────────────────────

async def _cloud_run_deploy(image_uri: str, svc: str) -> Tuple[bool, str, str]:
    logger.info("Deploying to Cloud Run: %s", svc)
    rc, out = await _run([
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
        clean = _clean_gcloud_output(out)
        return False, "", f"Cloud Run deploy failed.\n```\n{clean[-1500:]}\n```"

    rc2, url = await _run([
        "gcloud", "run", "services", "describe", svc,
        "--region", GCP_REGION, "--format=value(status.url)",
    ])
    return True, url.strip(), f"✅ Deployed `{svc}` to Cloud Run"


# ── Subprocess helpers ──────────────────────────────────────────────────────────

def _run_sync(cmd: List[str]) -> Tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=30, env=_gcloud_env())
        return r.returncode, r.stdout + r.stderr
    except Exception as exc:  # noqa: BLE001
        return 1, str(exc)


async def _run(cmd: List[str], cwd: Optional[Path] = None,
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
        return 1, f"Timed out after {timeout}s: {' '.join(cmd)}"
    except FileNotFoundError:
        return 1, f"Command not found: {cmd[0]}"
    except Exception as exc:  # noqa: BLE001
        return 1, str(exc)


# ── DB + utils ─────────────────────────────────────────────────────────────────

def _save(pid: str, app: str, ver: str, status: str, stages: list,
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


def _safe_name(name: str) -> str:
    name = re.sub(r"[^a-z0-9-]", "-", name.lower())
    return re.sub(r"-+", "-", name).strip("-")[:49] or "app"S
