"""
Backend test suite — all tests share one session-scoped TestClient.
DB is initialized once in conftest.py before any import.
"""


# ── Root & Health ─────────────────────────────────────────────────────────────

def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["service"] == "AI DevOps Copilot"
    assert r.json()["status"] == "operational"


def test_ping(client):
    r = client.get("/api/ping")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    d = r.json()
    assert "overall" in d
    assert isinstance(d["services"], list)


# ── Logs ──────────────────────────────────────────────────────────────────────

def test_get_logs(client):
    r = client.get("/api/logs?limit=5")
    assert r.status_code == 200
    d = r.json()
    assert "logs" in d
    assert isinstance(d["logs"], list)


def test_get_logs_level_filter(client):
    r = client.get("/api/logs?level=ERROR&limit=20")
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
        "version":  "v1.0.0",
        "environment": "production",
    })
    assert r.status_code == 200
    d = r.json()
    assert "status" in d
    assert d["app_name"] == "test-app"


def test_rollback(client):
    r = client.post("/api/rollback", json={
        "app_name": "test-app",
        "reason":   "CI test",
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

def test_chat_empty_message(client):
    r = client.post("/api/chat", json={"message": "", "session_id": "ci-empty"})
    assert r.status_code == 400


def test_chat_deploy_intent(client):
    r = client.post("/api/chat", json={"message": "deploy myapp", "session_id": "ci-01"})
    assert r.status_code == 200
    d = r.json()
    assert "deploy" in d["intent"]
    assert len(d["agents_used"]) >= 1


def test_chat_status_intent(client):
    r = client.post("/api/chat", json={"message": "system health check", "session_id": "ci-02"})
    assert r.status_code == 200
    assert r.json()["intent"] in ("status", "general")


def test_chat_rollback_intent(client):
    r = client.post("/api/chat", json={"message": "rollback payment-service", "session_id": "ci-03"})
    assert r.status_code == 200
    assert "rollback" in r.json()["intent"]


def test_chat_rca_intent(client):
    r = client.post("/api/chat", json={"message": "why did the deployment fail?", "session_id": "ci-04"})
    assert r.status_code == 200
    assert "root_cause" in r.json()["intent"]


def test_chat_incident_intent(client):
    r = client.post("/api/chat", json={"message": "any active incidents?", "session_id": "ci-05"})
    assert r.status_code == 200
    assert "incident" in r.json()["intent"]


def test_chat_fix_intent(client):
    r = client.post("/api/chat", json={"message": "auto fix the payment service", "session_id": "ci-06"})
    assert r.status_code == 200
    assert "fix" in r.json()["intent"]


# ── Schema ────────────────────────────────────────────────────────────────────

def test_chat_response_schema(client):
    r = client.post("/api/chat", json={"message": "show me recent logs", "session_id": "ci-07"})
    assert r.status_code == 200
    d = r.json()
    for field in ["response", "intent", "agents_used", "session_id", "timestamp"]:
        assert field in d, f"Missing: {field}"
    for step in d["agents_used"]:
        for key in ["agent", "action", "result", "duration_ms", "status"]:
            assert key in step, f"Agent step missing: {key}"


def test_session_endpoint(client):
    r = client.get("/api/session/ci-01")
    assert r.status_code == 200
    d = r.json()
    assert "session_id" in d
    assert "has_pending_deploy" in d