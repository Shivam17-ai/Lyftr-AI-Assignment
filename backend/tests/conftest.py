import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import _init_db_sync
from app.llm import cache_manager, _key_cooldowns
from app.main import app


@pytest.fixture(autouse=True)
def configure_test_environment(monkeypatch, tmp_path):
    # Set up temporary SQLite database
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{db_file}")

    # Set default test keys and models
    monkeypatch.setattr(settings, "LLM_API_KEYS", "mock_key_1,mock_key_2")
    monkeypatch.setattr(
        settings,
        "LLM_MODELS",
        "groq/llama-3.3-70b-versatile,cerebras/llama3.1-8b"
    )
    monkeypatch.setattr(settings, "ENABLE_FAILURE_SIMULATION", "true")

    # Clear caches and cooldowns
    cache_manager._local_store.clear()
    _key_cooldowns.clear()

    # Initialize SQLite database schema
    _init_db_sync(str(db_file))

    yield

    # Clean up
    cache_manager._local_store.clear()
    _key_cooldowns.clear()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
