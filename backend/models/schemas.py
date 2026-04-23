"""
Pydantic models for AI DevOps Copilot
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ─── Enums ────────────────────────────────────────────────────────────────────

class DeploymentStatus(str, Enum):
    PENDING = "pending"
    BUILDING = "building"
    TESTING = "testing"
    DEPLOYING = "deploying"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class AgentType(str, Enum):
    COORDINATOR = "coordinator"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"
    INCIDENT = "incident"
    ROOT_CAUSE = "root_cause"
    FIX = "fix"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Intent(str, Enum):
    DEPLOY = "deploy"
    ROLLBACK = "rollback"
    STATUS = "status"
    LOGS = "logs"
    INCIDENT = "incident"
    ROOT_CAUSE = "root_cause"
    FIX = "fix"
    GENERAL = "general"


# ─── Chat Models ──────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)
    agent: Optional[AgentType] = None
    metadata: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    history: Optional[List[ChatMessage]] = []


class AgentStep(BaseModel):
    agent: AgentType
    action: str
    result: str
    duration_ms: int
    status: str  # "success" | "error" | "warning"


class ChatResponse(BaseModel):
    response: str
    intent: Intent
    agents_used: List[AgentStep]
    data: Optional[Dict[str, Any]] = None
    session_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ─── Deployment Models ────────────────────────────────────────────────────────

class DeployRequest(BaseModel):
    app_name: str
    version: str = "latest"
    environment: str = "production"
    replicas: int = 2
    config: Optional[Dict[str, Any]] = {}


class PipelineStage(BaseModel):
    name: str
    status: DeploymentStatus
    duration_seconds: Optional[int] = None
    logs: List[str] = []
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class Deployment(BaseModel):
    id: str
    app_name: str
    version: str
    environment: str
    status: DeploymentStatus
    stages: List[PipelineStage]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    triggered_by: str = "user"
    error_message: Optional[str] = None


class RollbackRequest(BaseModel):
    app_name: str
    target_version: Optional[str] = None
    reason: str = "Manual rollback"


# ─── Log Models ───────────────────────────────────────────────────────────────

class LogEntry(BaseModel):
    id: str
    timestamp: datetime
    level: str  # DEBUG | INFO | WARN | ERROR | CRITICAL
    service: str
    message: str
    metadata: Optional[Dict[str, Any]] = {}


class LogsResponse(BaseModel):
    logs: List[LogEntry]
    total: int
    has_errors: bool
    error_rate: float


# ─── Incident Models ──────────────────────────────────────────────────────────

class Incident(BaseModel):
    id: str
    title: str
    severity: Severity
    status: str  # "open" | "investigating" | "resolved"
    service: str
    description: str
    root_cause: Optional[str] = None
    fix_applied: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


# ─── Health / Metrics Models ──────────────────────────────────────────────────

class ServiceHealth(BaseModel):
    service: str
    status: str  # "healthy" | "degraded" | "down"
    uptime_pct: float
    cpu_pct: float
    memory_pct: float
    request_rate: float
    error_rate: float
    latency_p99_ms: float


class SystemHealth(BaseModel):
    overall: str
    services: List[ServiceHealth]
    active_incidents: int
    deployments_today: int
    success_rate: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
