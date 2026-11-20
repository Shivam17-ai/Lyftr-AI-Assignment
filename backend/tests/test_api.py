import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import litellm
from litellm import AuthenticationError, InternalServerError, RateLimitError

from app.config import settings
from app.db import _get_session_messages_sync


def make_mock_response(content="Hello there!", model="groq/llama-3.3-70b-versatile", prompt_tokens=25, completion_tokens=10):
    usage = SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens
    )
    choice = SimpleNamespace(
        message=SimpleNamespace(content=content)
    )
    return SimpleNamespace(
        choices=[choice],
        usage=usage,
        model=model
    )


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["keys_configured"] == 2
    assert data["cache_enabled"] is True


def test_post_chat_success(client):
    mock_resp = make_mock_response("Paris is the capital of France.")
    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acomplete:
        mock_acomplete.return_value = mock_resp
        payload = {
            "session_id": "test-sess-1",
            "message": "What is the capital of France?"
        }
        res = client.post("/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["session_id"] == "test-sess-1"
        assert data["reply"] == "Paris is the capital of France."
        meta = data["metadata"]
        assert meta["resolution_source"] == "LIVE_INFERENCE"
        assert meta["model"] == "groq/llama-3.3-70b-versatile"
        assert isinstance(meta["latency_ms"], int)
        assert meta["latency_ms"] >= 0
        assert meta["input_tokens"] == 25
        assert meta["output_tokens"] == 10
        assert meta["key_id"] == "key_1"
        assert meta["fallback_attempts"] == 0


def test_validation_errors(client):
    # 1. Missing message
    res = client.post("/chat", json={"session_id": "s1"})
    assert res.status_code == 422
    assert "detail" in res.json()

    # 2. Empty string message
    res = client.post("/chat", json={"session_id": "s1", "message": ""})
    assert res.status_code == 422
    assert "detail" in res.json()

    # 3. Whitespace-only message
    res = client.post("/chat", json={"session_id": "s1", "message": "    "})
    assert res.status_code == 422
    assert "detail" in res.json()

    # 4. Message > 4000 characters
    res = client.post("/chat", json={"session_id": "s1", "message": "a" * 4001})
    assert res.status_code == 422
    assert "detail" in res.json()

    # 5. Missing session_id
    res = client.post("/chat", json={"message": "hello"})
    assert res.status_code == 422
    assert "detail" in res.json()

    # 6. session_id > 128 characters
    res = client.post("/chat", json={"session_id": "s" * 129, "message": "hello"})
    assert res.status_code == 422
    assert "detail" in res.json()

    # 7. Malformed JSON
    res = client.post(
        "/chat",
        content="not valid json",
        headers={"Content-Type": "application/json"}
    )
    assert res.status_code == 422
    assert "detail" in res.json()


def test_multi_turn_history_and_isolation(client):
    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acomplete:
        # Turn 1 in Session A
        mock_acomplete.return_value = make_mock_response("Nice to meet you Alice.")
        res1 = client.post("/chat", json={"session_id": "sess-a", "message": "My name is Alice."})
        assert res1.status_code == 200

        # Turn 2 in Session A
        mock_acomplete.return_value = make_mock_response("Your name is Alice.")
        res2 = client.post("/chat", json={"session_id": "sess-a", "message": "What is my name?"})
        assert res2.status_code == 200

        # Check call arguments of Turn 2: should include system prompt, turn 1 user, turn 1 assistant, turn 2 user
        called_messages = mock_acomplete.call_args.kwargs["messages"]
        assert len(called_messages) == 4
        assert called_messages[0]["role"] == "system"
        assert called_messages[1] == {"role": "user", "content": "My name is Alice."}
        assert called_messages[2] == {"role": "assistant", "content": "Nice to meet you Alice."}
        assert called_messages[3] == {"role": "user", "content": "What is my name?"}

        # Turn 1 in Session B: isolated from Session A
        mock_acomplete.return_value = make_mock_response("I do not know your name.")
        res3 = client.post("/chat", json={"session_id": "sess-b", "message": "What is my name?"})
        assert res3.status_code == 200

        called_messages_b = mock_acomplete.call_args.kwargs["messages"]
        assert len(called_messages_b) == 2
        assert called_messages_b[0]["role"] == "system"
        assert called_messages_b[1] == {"role": "user", "content": "What is my name?"}


def test_history_endpoint(client):
    # Unknown session -> 404
    res_404 = client.get("/sessions/unknown-id/messages")
    assert res_404.status_code == 404
    assert res_404.json() == {"detail": "session not found"}

    # Complete a turn in a new session
    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acomplete:
        mock_acomplete.return_value = make_mock_response("Reply text")
        client.post("/chat", json={"session_id": "sess-hist", "message": "Hello"})

    res_hist = client.get("/sessions/sess-hist/messages")
    assert res_hist.status_code == 200
    data = res_hist.json()
    assert data["session_id"] == "sess-hist"
    messages = data["messages"]
    assert len(messages) == 2
    # Oldest first: user first, assistant second
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"
    assert messages[0].get("metadata") is None

    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "Reply text"
    assert messages[1]["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert messages[1]["metadata"]["input_tokens"] == 25
    assert messages[1]["metadata"]["output_tokens"] == 10


def test_caching(client):
    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acomplete:
        # Simulate delay in live inference
        async def delayed_acompletion(*args, **kwargs):
            await asyncio.sleep(0.05)
            return make_mock_response("Cached answer")

        mock_acomplete.side_effect = delayed_acompletion

        # First request in session 1 -> LIVE_INFERENCE
        res1 = client.post("/chat", json={"session_id": "sess-c1", "message": "Explain quantum computing"})
        assert res1.status_code == 200
        d1 = res1.json()
        assert d1["metadata"]["resolution_source"] == "LIVE_INFERENCE"
        assert d1["metadata"]["key_id"] == "key_1"
        assert d1["metadata"]["fallback_attempts"] == 0
        live_latency = d1["metadata"]["latency_ms"]

        # Exact same first message in a NEW session 2 -> LLM_CACHE
        res2 = client.post("/chat", json={"session_id": "sess-c2", "message": "Explain quantum computing"})
        assert res2.status_code == 200
        d2 = res2.json()
        assert d2["metadata"]["resolution_source"] == "LLM_CACHE"
        assert d2["reply"] == d1["reply"]
        assert d2["metadata"]["key_id"] is None
        assert d2["metadata"]["fallback_attempts"] == 0
        assert d2["metadata"]["input_tokens"] == d1["metadata"]["input_tokens"]
        assert d2["metadata"]["output_tokens"] == d1["metadata"]["output_tokens"]
        assert d2["metadata"]["model"] == d1["metadata"]["model"]
        assert d2["metadata"]["latency_ms"] < live_latency

        # Different message in session 3 -> LIVE_INFERENCE
        mock_acomplete.side_effect = None
        mock_acomplete.return_value = make_mock_response("Different answer")
        res3 = client.post("/chat", json={"session_id": "sess-c3", "message": "Different query"})
        assert res3.status_code == 200
        d3 = res3.json()
        assert d3["metadata"]["resolution_source"] == "LIVE_INFERENCE"


def test_failover_simulation_headers(client):
    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acomplete:
        mock_acomplete.return_value = make_mock_response("Key 2 succeeded", model="cerebras/llama3.1-8b")

        # 1. key_1=429 -> fails over to key_2
        res1 = client.post(
            "/chat",
            json={"session_id": "sess-fail-1", "message": "test failover 429"},
            headers={"X-Simulate-Failure": "key_1=429"}
        )
        assert res1.status_code == 200
        d1 = res1.json()
        assert d1["metadata"]["key_id"] == "key_2"
        assert d1["metadata"]["fallback_attempts"] == 1
        assert d1["metadata"]["model"] == "cerebras/llama3.1-8b"

        # 2. key_1=500 -> fails over to key_2
        res2 = client.post(
            "/chat",
            json={"session_id": "sess-fail-2", "message": "test failover 500"},
            headers={"X-Simulate-Failure": "key_1=500"}
        )
        assert res2.status_code == 200
        d2 = res2.json()
        assert d2["metadata"]["key_id"] == "key_2"
        assert d2["metadata"]["fallback_attempts"] == 1

        # 3. key_1=429,key_2=500 -> 503
        res3 = client.post(
            "/chat",
            json={"session_id": "sess-fail-3", "message": "both fail"},
            headers={"X-Simulate-Failure": "key_1=429,key_2=500"}
        )
        assert res3.status_code == 503
        assert res3.json() == {"detail": "all providers unavailable"}
        # Verify nothing saved to history
        hist3 = _get_session_messages_sync("sess-fail-3", settings.sqlite_db_path)
        assert len(hist3) == 0

        # 4. *=429 -> 503
        res4 = client.post(
            "/chat",
            json={"session_id": "sess-fail-4", "message": "all fail wildcard"},
            headers={"X-Simulate-Failure": "*=429"}
        )
        assert res4.status_code == 503
        assert res4.json() == {"detail": "all providers unavailable"}
        hist4 = _get_session_messages_sync("sess-fail-4", settings.sqlite_db_path)
        assert len(hist4) == 0


def test_failover_header_ignored_when_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_FAILURE_SIMULATION", "false")
    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acomplete:
        mock_acomplete.return_value = make_mock_response("Success on key 1")
        res = client.post(
            "/chat",
            json={"session_id": "sess-sim-off", "message": "hello"},
            headers={"X-Simulate-Failure": "key_1=429"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["metadata"]["key_id"] == "key_1"
        assert data["metadata"]["fallback_attempts"] == 0


def test_real_provider_errors_failover(client):
    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acomplete:
        # First call raises RateLimitError, second call succeeds
        mock_acomplete.side_effect = [
            RateLimitError("Rate limit reached", llm_provider="groq", model="groq/llama-3.3-70b-versatile"),
            make_mock_response("Key 2 response", model="cerebras/llama3.1-8b")
        ]
        res = client.post("/chat", json={"session_id": "sess-real-fail", "message": "test"})
        assert res.status_code == 200
        data = res.json()
        assert data["metadata"]["key_id"] == "key_2"
        assert data["metadata"]["fallback_attempts"] == 1


def test_tokens_are_per_request(client):
    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acomplete:
        mock_acomplete.return_value = make_mock_response("Hi", prompt_tokens=20, completion_tokens=5)
        res1 = client.post("/chat", json={"session_id": "sess-tok-1", "message": "Hello"})
        d1 = res1.json()

        mock_acomplete.return_value = make_mock_response("Hi", prompt_tokens=20, completion_tokens=5)
        res2 = client.post("/chat", json={"session_id": "sess-tok-2", "message": "World"})
        d2 = res2.json()

        # Input tokens must not accumulate across requests
        assert d1["metadata"]["input_tokens"] == 20
        assert d2["metadata"]["input_tokens"] == 20


def test_unhandled_exception_returns_clean_500():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        with patch("app.main.execute_chat", side_effect=RuntimeError("Secret database connection string leaked!")):
            res = c.post("/chat", json={"session_id": "sess-err", "message": "crash"})
            assert res.status_code == 500
            assert res.json() == {"detail": "internal server error"}
            assert "Secret" not in res.text
            assert "Traceback" not in res.text


def test_live_smoke_optional():
    """Optional live smoke test; skipped unless explicitly requested via RUN_LIVE_TESTS=true."""
    if os.getenv("RUN_LIVE_TESTS", "").lower() != "true":
        pytest.skip("Live smoke test skipped. Set RUN_LIVE_TESTS=true with real keys to run.")

    real_key = os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEYS")
    if not real_key or "your_" in real_key or "mock_" in real_key:
        pytest.skip("No real API key configured in environment for live smoke test.")

    import litellm
    from app.config import settings
    response = litellm.completion(
        model=settings.primary_model,
        messages=[{"role": "user", "content": "ping"}],
        api_key=real_key.split(",")[0].strip(),
        max_tokens=5
    )
    assert response.choices[0].message.content is not None
