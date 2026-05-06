"""
AI DevOps Copilot — FastAPI entry point.
dotenv is loaded FIRST so all os.getenv() calls in imported modules
see the values from backend/.env. The # noqa: E402 comments tell ruff
that the imports below load_dotenv() are intentionally placed here.
"""
from dotenv import load_dotenv
load_dotenv()  # must be before any other local import

import logging  # noqa: E402
import os  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from routers import chat, deployments, logs, health  # noqa: E402
from services.database import init_db  # noqa: E402
from utils.logger import setup_logger  # noqa: E402

setup_logger()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 AI DevOps Copilot starting...")
    groq_key   = os.getenv("GROQ_API_KEY", "")
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    gcp_proj   = os.getenv("GCP_PROJECT_ID", "")

    if groq_key:
        logger.info("✅ Groq API key loaded (%s...)", groq_key[:8])
    elif gemini_key:
        logger.info("✅ Gemini API key loaded (%s...)", gemini_key[:8])
    else:
        logger.warning("⚠️  No LLM API key — add GROQ_API_KEY to backend/.env")

    if gcp_proj:
        logger.info("✅ GCP project: %s", gcp_proj)
    else:
        logger.warning("⚠️  GCP_PROJECT_ID not set — deployments will fail")

    init_db()
    logger.info("✅ Database ready")
    yield
    logger.info("👋 Shutting down")


app = FastAPI(
    title="AI DevOps Copilot",
    description="Multi-Agent Deployment & Incident Management System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600,
)

app.include_router(chat.router,        prefix="/api", tags=["Chat"])
app.include_router(deployments.router, prefix="/api", tags=["Deployments"])
app.include_router(logs.router,        prefix="/api", tags=["Logs"])
app.include_router(health.router,      prefix="/api", tags=["Health"])


@app.get("/")
async def root():
    return {
        "service": "AI DevOps Copilot",
        "version": "1.0.0",
        "status":  "operational",
        "llm": (
            "groq"   if os.getenv("GROQ_API_KEY")   else
            "gemini" if os.getenv("GEMINI_API_KEY")  else
            "not-configured"
        ),
        "agents": ["coordinator", "deployment", "monitoring",
                   "incident", "root_cause", "fix"],
    }