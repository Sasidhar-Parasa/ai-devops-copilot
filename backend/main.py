"""
AI DevOps Copilot - Main FastAPI Application
"""
import logging
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
    logger.info("👋 AI DevOps Copilot shutting down...")


app = FastAPI(
    title="AI DevOps Copilot",
    description="Multi-Agent Deployment & Incident Management System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(deployments.router, prefix="/api", tags=["Deployments"])
app.include_router(logs.router, prefix="/api", tags=["Logs"])
app.include_router(health.router, prefix="/api", tags=["Health"])


@app.get("/")
async def root():
    return {
        "service": "AI DevOps Copilot",
        "version": "1.0.0",
        "status": "operational",
        "agents": [
            "coordinator",
            "deployment",
            "monitoring",
            "incident",
            "root_cause",
            "fix",
        ],
    }
