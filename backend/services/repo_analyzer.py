"""
Intelligent repository analyzer.
Detects: docker-compose, Dockerfile, framework type, entry points.
Returns a structured DeploymentPlan the pipeline uses directly.
"""
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ServiceSpec:
    name: str
    port: int = 8080
    build_context: Optional[str] = None
    dockerfile: Optional[str] = None
    image: Optional[str] = None
    env_vars: Dict[str, str] = field(default_factory=dict)


@dataclass
class DeploymentPlan:
    strategy: str                          # "compose" | "dockerfile" | "autodetect"
    services: List[ServiceSpec] = field(default_factory=list)
    framework: Optional[str] = None       # "fastapi" | "flask" | "nodejs" | "react" | …
    primary_port: int = 8080
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    summary: str = ""

    @property
    def valid(self) -> bool:
        return len(self.errors) == 0


def analyze_repo(repo_path: Path) -> DeploymentPlan:
    """
    Inspect the cloned repo and return a DeploymentPlan.
    Priority: docker-compose → Dockerfile → framework auto-detect.
    """
    compose_file = _find_compose(repo_path)
    if compose_file:
        return _plan_from_compose(repo_path, compose_file)

    dockerfile = repo_path / "Dockerfile"
    if dockerfile.exists():
        return _plan_from_dockerfile(repo_path, dockerfile)

    return _plan_from_framework(repo_path)


# ── Docker Compose ─────────────────────────────────────────────────────────────

def _find_compose(path: Path) -> Optional[Path]:
    for name in ["docker-compose.yml", "docker-compose.yaml",
                 "compose.yml", "compose.yaml"]:
        f = path / name
        if f.exists():
            return f
    return None


def _plan_from_compose(repo_path: Path, compose_file: Path) -> DeploymentPlan:
    try:
        import yaml  # PyYAML is already a transitive dep
    except ImportError:
        return DeploymentPlan(
            strategy="compose",
            errors=["PyYAML not installed — cannot parse docker-compose.yml"],
        )

    try:
        with open(compose_file) as f:
            compose = yaml.safe_load(f) or {}
    except Exception as exc:
        return DeploymentPlan(
            strategy="compose",
            errors=[f"Cannot parse {compose_file.name}: {exc}"],
        )

    raw_services = compose.get("services", {})
    if not raw_services:
        return DeploymentPlan(
            strategy="compose",
            errors=[f"{compose_file.name} defines no services."],
        )

    services: List[ServiceSpec] = []
    warnings: List[str] = []
    primary_port = 8080

    for svc_name, svc_conf in raw_services.items():
        svc_conf = svc_conf or {}
        spec = ServiceSpec(name=svc_name)

        # Port
        ports = svc_conf.get("ports", [])
        for p in ports:
            container_port = _parse_port(str(p))
            if container_port:
                spec.port = container_port
                primary_port = container_port
                break

        # Build context
        build = svc_conf.get("build")
        if isinstance(build, str):
            spec.build_context = build
            df = repo_path / build / "Dockerfile"
            if df.exists():
                spec.dockerfile = str(df)
            else:
                warnings.append(
                    f"Service `{svc_name}`: build context `{build}` "
                    f"has no Dockerfile."
                )
        elif isinstance(build, dict):
            ctx = build.get("context", ".")
            spec.build_context = ctx
            spec.dockerfile = build.get("dockerfile")

        # Pre-built image
        if svc_conf.get("image") and not build:
            spec.image = svc_conf["image"]

        # Environment
        env = svc_conf.get("environment", {})
        if isinstance(env, list):
            for item in env:
                if "=" in item:
                    k, v = item.split("=", 1)
                    spec.env_vars[k] = v
        elif isinstance(env, dict):
            spec.env_vars = {k: str(v) for k, v in env.items()}

        services.append(spec)

    # Pick the best service to deploy (web/backend/app/api > others)
    priority = ["web", "backend", "app", "api", "frontend", "server"]
    services.sort(key=lambda s: next(
        (i for i, p in enumerate(priority) if p in s.name.lower()), 99
    ))

    svc_names = [s.name for s in services]
    summary = (
        f"Found `{compose_file.name}` with {len(services)} service(s): "
        f"{', '.join(f'`{n}`' for n in svc_names)}."
    )

    return DeploymentPlan(
        strategy="compose",
        services=services,
        primary_port=primary_port,
        warnings=warnings,
        summary=summary,
    )


def _parse_port(port_str: str) -> Optional[int]:
    # "8080:80" → 80 (container port), "3000" → 3000
    try:
        parts = str(port_str).split(":")
        return int(parts[-1])
    except (ValueError, IndexError):
        return None


# ── Single Dockerfile ──────────────────────────────────────────────────────────

def _plan_from_dockerfile(repo_path: Path, dockerfile: Path) -> DeploymentPlan:
    port = _parse_dockerfile_port(dockerfile)
    framework = _detect_framework(repo_path)
    spec = ServiceSpec(
        name="app",
        port=port or 8080,
        build_context=".",
        dockerfile=str(dockerfile),
    )
    return DeploymentPlan(
        strategy="dockerfile",
        services=[spec],
        framework=framework,
        primary_port=port or 8080,
        summary="Found Dockerfile" + (f" ({framework})" if framework else "") + ".",
    )


def _parse_dockerfile_port(dockerfile: Path) -> Optional[int]:
    try:
        for line in dockerfile.read_text().splitlines():
            m = re.match(r"^\s*EXPOSE\s+(\d+)", line, re.IGNORECASE)
            if m:
                return int(m.group(1))
    except Exception:
        pass
    return None


# ── Framework auto-detect ──────────────────────────────────────────────────────

def _plan_from_framework(repo_path: Path) -> DeploymentPlan:
    framework = _detect_framework(repo_path)
    warnings: List[str] = []
    errors: List[str] = []

    if not framework:
        errors.append(
            "No `Dockerfile`, `docker-compose.yml`, or recognizable framework found.\n\n"
            "To deploy, add one of:\n"
            "- A `Dockerfile` in the repo root\n"
            "- A `docker-compose.yml` with at least one service\n"
            "- A `requirements.txt` + `main.py` (Python/FastAPI)\n"
            "- A `package.json` + `index.js` (Node.js)"
        )
        return DeploymentPlan(
            strategy="autodetect",
            errors=errors,
            summary="Cannot deploy — no deployment configuration found.",
        )

    # Generate a Dockerfile for known frameworks
    port, generated_df = _generate_dockerfile(repo_path, framework)
    if generated_df:
        df_path = repo_path / "Dockerfile"
        df_path.write_text(generated_df)
        warnings.append(
            f"No Dockerfile found — auto-generated one for **{framework}**."
        )
    else:
        errors.append(
            f"Detected **{framework}** but could not generate a Dockerfile automatically.\n"
            "Please add a `Dockerfile` to your repository."
        )
        return DeploymentPlan(strategy="autodetect", errors=errors)

    spec = ServiceSpec(name="app", port=port, build_context=".", dockerfile="Dockerfile")
    return DeploymentPlan(
        strategy="autodetect",
        services=[spec],
        framework=framework,
        primary_port=port,
        warnings=warnings,
        summary=f"Auto-detected **{framework}** — generated Dockerfile.",
    )


def _detect_framework(repo_path: Path) -> Optional[str]:
    files = {f.name.lower() for f in repo_path.iterdir() if f.is_file()}

    if "requirements.txt" in files or "pyproject.toml" in files:
        reqs = (repo_path / "requirements.txt").read_text().lower() \
            if (repo_path / "requirements.txt").exists() else ""
        if "fastapi" in reqs:
            return "fastapi"
        if "flask" in reqs:
            return "flask"
        if "django" in reqs:
            return "django"
        return "python"

    if "package.json" in files:
        pkg = (repo_path / "package.json").read_text().lower()
        if "next" in pkg:
            return "nextjs"
        if "react" in pkg:
            return "react"
        if "vue" in pkg:
            return "vue"
        if "express" in pkg:
            return "express"
        return "nodejs"

    if "go.mod" in files:
        return "go"
    if "pom.xml" in files:
        return "java-maven"
    if "gemfile" in files:
        return "ruby"
    if "procfile" in files:
        return "heroku"

    return None


def _generate_dockerfile(repo_path: Path, framework: str) -> tuple:
    templates = {
        "fastapi": (8080,
            "FROM python:3.11-slim\nWORKDIR /app\n"
            "COPY requirements.txt .\nRUN pip install -r requirements.txt\n"
            "COPY . .\nEXPOSE 8080\n"
            'CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]\n'),
        "flask": (8080,
            "FROM python:3.11-slim\nWORKDIR /app\n"
            "COPY requirements.txt .\nRUN pip install -r requirements.txt\n"
            "COPY . .\nEXPOSE 8080\n"
            'ENV PORT=8080\nCMD ["python", "app.py"]\n'),
        "python": (8080,
            "FROM python:3.11-slim\nWORKDIR /app\n"
            "COPY . .\nRUN pip install -r requirements.txt 2>/dev/null || true\n"
            "EXPOSE 8080\nCMD [\"python\", \"main.py\"]\n"),
        "nodejs": (8080,
            "FROM node:20-slim\nWORKDIR /app\n"
            "COPY package*.json .\nRUN npm ci --omit=dev\n"
            "COPY . .\nEXPOSE 8080\n"
            'ENV PORT=8080\nCMD ["node", "index.js"]\n'),
        "express": (8080,
            "FROM node:20-slim\nWORKDIR /app\n"
            "COPY package*.json .\nRUN npm ci --omit=dev\n"
            "COPY . .\nEXPOSE 8080\n"
            'ENV PORT=8080\nCMD ["node", "index.js"]\n'),
    }
    return templates.get(framework, (None, None))

