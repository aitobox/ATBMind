import json
import pytest
import httpx
from pydantic import BaseModel

from atbmind_core.engine.llm_client import (
    OpenAICompatClient,
    LLMClientError,
    LLMConnectionError,
    LLMResponseError,
    LLMJSONParseError,
    clean_json_text,
)

class SampleSchema(BaseModel):
    intent: str
    confidence: float

def test_clean_json_text():
    """Verify markdown fences stripping and whitespace trimming."""
    raw1 = "```json\n{\"key\": \"val\"}\n```"
    assert clean_json_text(raw1) == '{"key": "val"}'

    raw2 = "```\n{\"key\": 123}\n```"
    assert clean_json_text(raw2) == '{"key": 123}'

    raw3 = '  {"key": true}  '
    assert clean_json_text(raw3) == '{"key": true}'

def test_sync_chat_completion():
    """Verify synchronous chat completion with mock transport."""
    def handler(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content.decode("utf-8"))
        assert data["model"] == "test-model"
        assert len(data["messages"]) == 1
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": "Hello from mock LLM!"}
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    client = OpenAICompatClient(
        base_url="https://api.example.com/v1",
        api_key="test-key",
        model="test-model",
        transport=transport,
    )

    reply = client.chat_completion([{"role": "user", "content": "Hi"}])
    assert reply == "Hello from mock LLM!"

def test_async_chat_completion():
    """Verify asynchronous chat completion."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Async Hello!"}}]},
        )

    transport = httpx.MockTransport(handler)
    client = OpenAICompatClient(
        base_url="https://api.example.com/v1",
        model="async-model",
        transport=transport,
    )

    import asyncio
    reply = asyncio.run(client.achat_completion([{"role": "user", "content": "Hi"}]))
    assert reply == "Async Hello!"


def test_generate_structured_json():
    """Verify JSON parsing and Pydantic validation."""
    def handler(request: httpx.Request) -> httpx.Response:
        content = "```json\n{\"intent\": \"slimming\", \"confidence\": 0.95}\n```"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
        )

    transport = httpx.MockTransport(handler)
    client = OpenAICompatClient(
        base_url="https://api.example.com/v1",
        model="json-model",
        transport=transport,
    )

    # 1. Plain dictionary
    res_dict = client.generate_structured_json([{"role": "user", "content": "parse"}])
    assert res_dict == {"intent": "slimming", "confidence": 0.95}

    # 2. Pydantic validation
    res_model = client.generate_structured_json(
        [{"role": "user", "content": "parse"}], schema=SampleSchema
    )
    assert isinstance(res_model, SampleSchema)
    assert res_model.intent == "slimming"
    assert res_model.confidence == 0.95

def test_retry_on_transient_failure():
    """Verify retry mechanism with exponential backoff on 503 errors."""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(503, content=b"Service Unavailable")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Success on attempt 3"}}]},
        )

    transport = httpx.MockTransport(handler)
    client = OpenAICompatClient(
        base_url="https://api.example.com/v1",
        model="retry-model",
        max_retries=3,
        retry_delay=0.01,  # fast test
        transport=transport,
    )

    res = client.chat_completion([{"role": "user", "content": "retry test"}])
    assert res == "Success on attempt 3"
    assert attempts == 3

def test_max_retries_exceeded():
    """Verify LLMResponseError raised after exceeding retries."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"Internal Server Error")

    transport = httpx.MockTransport(handler)
    client = OpenAICompatClient(
        base_url="https://api.example.com/v1",
        model="fail-model",
        max_retries=2,
        retry_delay=0.01,
        transport=transport,
    )

    with pytest.raises(LLMResponseError):
        client.chat_completion([{"role": "user", "content": "fail"}])

def test_invalid_json_handling():
    """Verify LLMJSONParseError when response is not valid JSON."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "This is definitely not JSON."}}]},
        )

    transport = httpx.MockTransport(handler)
    client = OpenAICompatClient(
        base_url="https://api.example.com/v1",
        model="bad-json-model",
        transport=transport,
    )

    with pytest.raises(LLMJSONParseError):
        client.generate_structured_json([{"role": "user", "content": "test"}])
