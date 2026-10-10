"""Each test run gets its own database and recap folder, and never needs the real
OpenAI key: the deterministic tests replace the Realtime API with a fake
(test_chat.py). The live smoke test (live_smoke.py) is a separate script."""

import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="compass-tests-")
os.environ["DB_PATH"] = str(Path(_tmp) / "test.db")
os.environ["RECAPS_DIR"] = str(Path(_tmp) / "recaps")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-not-used")
os.environ["DEMO_ACCESS_CODE"] = "compass"
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

import server


@pytest.fixture
def client():
    """A browser: its own cookie jar, a visitor session after /api/me."""
    with TestClient(server.app) as c:
        assert c.get("/api/me").json() == {"kind": "visitor"}
        yield c
