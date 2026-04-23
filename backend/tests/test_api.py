"""
Backend test suite — runs in CI pipeline.
Tests critical paths: health, chat, deploy, logs endpoints.
"""
import json
import sys
import os

# Add backend root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


# ── Health & Ping ─────────────────────────────────────────────────────────────

def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "AI DevOps Copilot"
    assert data["status"] == "operational"
    assert "agents" in data


def test_ping():
    resp = client.get("/api/ping")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "llm" in data


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "overall" in data
    assert "services" in data
    assert isinstance(data["services"], list)


# ── Logs ──────────────────────────────────────────────────────────────────────

def test_get_logs():
    resp = client.get("/api/logs?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert "logs" in data
    assert "total" in data
    assert isinstance(data["logs"], list)


def test_get_logs_with_level_filter():
    resp = client.get("/api/logs?level=ERROR&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    for log in data["logs"]:
        assert log["level"] == "ERROR"


# ── Deployments ───────────────────────────────────────────────────────────────

def test_list_deployments():
    resp = client.get("/api/deployments")
    assert resp.status_code == 200
    data = resp.json()
    assert "deployments" in data
    assert "total" in data


def test_simulate_deployment():
    resp = client.post("/api/deploy/simulate", json={
        "app_name": "test-app",
        "version": "v1.0.0",
        "environment": "production"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "stages" in data
    assert data["app_name"] == "test-app"


def test_rollback():
    resp = client.post("/api/rollback", json={
        "app_name": "test-app",
        "reason": "CI test rollback"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data


# ── Incidents ─────────────────────────────────────────────────────────────────

def test_list_incidents():
    resp = client.get("/api/incidents")
    assert resp.status_code == 200
    data = resp.json()
    assert "incidents" in data
    assert "total" in data


# ── Chat (rule-based, no LLM key needed in CI) ────────────────────────────────

def test_chat_deploy_intent():
    resp = client.post("/api/chat", json={
        "message": "deploy myapp",
        "session_id": "ci-test-001",
        "history": []
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "response" in data
    assert "intent" in data
    assert "agents_used" in data
    assert len(data["agents_used"]) >= 1
    assert "deploy" in data["intent"]


def test_chat_status_intent():
    resp = client.post("/api/chat", json={
        "message": "system health check",
        "session_id": "ci-test-002",
        "history": []
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] in ("status", "general")


def test_chat_rollback_intent():
    resp = client.post("/api/chat", json={
        "message": "rollback payment-service",
        "session_id": "ci-test-003",
        "history": []
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "rollback" in data["intent"]


def test_chat_empty_message():
    resp = client.post("/api/chat", json={
        "message": "",
        "session_id": "ci-test-004"
    })
    assert resp.status_code == 400


def test_chat_rca_intent():
    resp = client.post("/api/chat", json={
        "message": "why did the deployment fail?",
        "session_id": "ci-test-005",
        "history": []
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "root_cause" in data["intent"]


def test_session_endpoint():
    resp = client.get("/api/session/ci-test-001")
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert "has_pending_deploy" in data


# ── Schema validation ─────────────────────────────────────────────────────────

def test_chat_response_schema():
    resp = client.post("/api/chat", json={
        "message": "show me recent logs",
        "session_id": "ci-schema-test"
    })
    assert resp.status_code == 200
    data = resp.json()
    required_fields = ["response", "intent", "agents_used", "session_id", "timestamp"]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"

    for agent_step in data["agents_used"]:
        assert "agent" in agent_step
        assert "action" in agent_step
        assert "result" in agent_step
        assert "duration_ms" in agent_step
        assert "status" in agent_step
