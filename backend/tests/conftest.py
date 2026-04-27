"""
pytest conftest — sets TEST_DB_PATH env var before any app module is imported.
This makes database.py use a temp file instead of ./data/copilot.db.
"""
import os
import sys
import tempfile
import pytest

# ── Must happen BEFORE any app import ─────────────────────────────────────────
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["TEST_DB_PATH"] = _tmp.name

# Ensure backend root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Now safe to import app modules
import services.database as _db  # noqa: E402
_db.DB_PATH = _db.DB_PATH.__class__(_tmp.name)  # re-apply after module load
_db.init_db()


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from main import app
    with TestClient(app) as c:
        yield c