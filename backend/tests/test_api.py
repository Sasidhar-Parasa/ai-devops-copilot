"""
Backend test suite.
Chat intent tests use flexible assertions since LLM is not available in CI.
"""

# ── Root & Health ─────────────────────────────────────────────────────────────

def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    d = r.json()
    assert d["service"] == "AI DevOps Copilot"
    assert d["status"] == "operational"


def test_ping(client):
    r = client.get("/api/ping")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    d = r.json()
    assert "overall" in d
    assert "services" in d


# ── Logs ──────────────────────────────────────────────────────────────────────

def test_get_logs(client):
    r = client.get("/api/logs?limit=5")
    assert r.status_code == 200
    d = r.json()
    assert "logs" in d
    assert isinstance(d["logs"], list)


def test_get_logs_level_filter(client):
    r = client.get("/api/logs?level=ERROR&limit=10")
    assert r.status_code == 200
    for log in r.json()["logs"]:
        assert log["level"] == "ERROR"


# ── Deployments ───────────────────────────────────────────────────────────────

def test_list_deployments(client):
    r = client.get("/api/deployments")
    assert r.status_code == 200
    d = r.json()
    assert "deployments" in d
    assert "total" in d


def test_simulate_deployment(client):
    r = client.post("/api/deploy/simulate", json={
        "app_name": "test-app",
        "version": "v1.0.0",
        "environment": "production",
    })
    assert r.status_code == 200
    d = r.json()
    assert "status" in d
    assert d["app_name"] == "test-app"


def test_rollback(client):
    r = client.post("/api/rollback", json={
        "app_name": "test-app",
        "reason": "CI test",
    })
    assert r.status_code == 200
    assert "status" in r.json()


# ── Incidents ─────────────────────────────────────────────────────────────────

def test_list_incidents(client):
    r = client.get("/api/incidents")
    assert r.status_code == 200
    d = r.json()
    assert "incidents" in d
    assert "total" in d


# ── Chat ──────────────────────────────────────────────────────────────────────
# NOTE: In CI there is no GROQ_API_KEY or GEMINI_API_KEY.
#       The LLM service returns a "not configured" response with intent=general.
#       We test the API contract (status, schema, agent trace) — not specific intents.
#       Intent-specific assertions are done locally where LLM keys are available.

def test_chat_empty_message(client):
    r = client.post("/api/chat", json={"message": "", "session_id": "ci-empty"})
    assert r.status_code == 400


def test_chat_returns_valid_response(client):
    r = client.post("/api/chat", json={"message": "hello", "session_id": "ci-hello"})
    assert r.status_code == 200
    d = r.json()
    assert "response" in d
    assert len(d["response"]) > 0
    assert "intent" in d
    assert "agents_used" in d
    assert len(d["agents_used"]) >= 1


def test_chat_response_schema(client):
    r = client.post("/api/chat", json={
        "message": "system health",
        "session_id": "ci-schema",
    })
    assert r.status_code == 200
    d = r.json()
    for field in ["response", "intent", "agents_used", "session_id", "timestamp"]:
        assert field in d, f"Missing field: {field}"
    for step in d["agents_used"]:
        for key in ["agent", "action", "result", "duration_ms", "status"]:
            assert key in step, f"Agent step missing: {key}"


def test_chat_agent_trace_present(client):
    r = client.post("/api/chat", json={
        "message": "deploy my app",
        "session_id": "ci-trace",
    })
    assert r.status_code == 200
    d = r.json()
    agents = [s["agent"] for s in d["agents_used"]]
    assert "coordinator" in agents  # coordinator always runs


def test_chat_multi_turn(client):
    """Verify conversation history is accepted without error."""
    r = client.post("/api/chat", json={
        "message": "what can you help me with?",
        "session_id": "ci-multi",
        "history": [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "Hello! How can I help?"},
        ],
    })
    assert r.status_code == 200
    assert len(r.json()["response"]) > 0


def test_session_endpoint(client):
    r = client.get("/api/session/ci-hello")
    assert r.status_code == 200
    d = r.json()
    assert "session_id" in d
    assert "has_pending_deploy" in d


def test_chat_no_llm_message_is_helpful(client):
    """When LLM is unconfigured, the error message must mention GROQ_API_KEY."""
    import os
    if os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY"):
        return  # LLM is configured — skip this test
    r = client.post("/api/chat", json={"message": "hello", "session_id": "ci-nollm"})
    assert r.status_code == 200
    response_text = r.json()["response"]
    # Must explain what's wrong, not be a silent failure
    assert any(kw in response_text for kw in ["GROQ_API_KEY", "GEMINI_API_KEY", "configured", "API key"])
