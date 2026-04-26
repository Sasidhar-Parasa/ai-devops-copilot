"""
AI DevOps Copilot - Main FastAPI Application
"""
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import chat, deployments, logs, health
from services.database import init_db
from utils.logger import setup_logger

setup_logger()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 AI DevOps Copilot starting up...")
    init_db()
    logger.info("✅ Database initialized")
    yield
    logger.info("👋 Shutting down...")


app = FastAPI(
    title="AI DevOps Copilot",
    description="Multi-Agent Deployment & Incident Management System",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS — allow all origins for Cloud Run cross-service calls ────────────────
# In production you could restrict this to your specific frontend Cloud Run URL.
# Using wildcard here so the frontend can reach the backend regardless of URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # Allow any origin (Cloud Run URLs are unpredictable)
    allow_credentials=False,       # Must be False when allow_origins=["*"]
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
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
        "status": "operational",
        "agents": ["coordinator", "deployment", "monitoring", "incident", "root_cause", "fix"],
        "llm": "groq" if os.getenv("GROQ_API_KEY") else "rule-based",
    }