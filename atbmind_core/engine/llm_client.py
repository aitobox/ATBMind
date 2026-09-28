"""
ATBMind OpenAI-Compatible LLM Client
Unified client supporting cloud commercial APIs (OpenAI, DeepSeek, Doubao) and local instances (Ollama, vLLM).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Type, Union

import httpx
from pydantic import BaseModel

from atbmind_core.config import LLMConfig, AppConfig

logger = logging.getLogger("atbmind.engine.llm_client")

class LLMClientError(Exception):
    """Base exception for LLM client operations."""
    pass

class LLMConnectionError(LLMClientError):
    """Raised when network connection or transport fails."""
    pass

class LLMResponseError(LLMClientError):
    """Raised when LLM API returns an error status code."""
    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code

class LLMJSONParseError(LLMClientError):
    """Raised when LLM response cannot be parsed as valid JSON."""
    def __init__(self, message: str, raw_content: Optional[str] = None) -> None:
        super().__init__(message)
        self.raw_content = raw_content

def clean_json_text(text: str) -> str:
    """
    Cleans Markdown code fences and extracts JSON content.

    Args:
        text: Raw text string potentially wrapped in ```json ... ```.

    Returns:
        Cleaned JSON string.
    """
    cleaned = text.strip()

    # Strip markdown code blocks
    fence_pattern = r"^```(?:json)?\s*\n?(.*?)\n?```$"
    match = re.search(fence_pattern, cleaned, re.DOTALL)
    if match:
        cleaned = match.group(1).strip()
    elif cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned[3:-3].strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

    return cleaned

class OpenAICompatClient:
    """
    Synchronous and asynchronous OpenAI-compatible protocol client.
    Handles authentication, exponential backoff retries, and structured JSON parsing.
    """

    def __init__(
        self,
        base_url: str = "https://api.openai.com/v1",
        api_key: str = "",
        model: str = "gpt-4o",
        temperature: float = 0.1,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._transport = transport

        # Determine endpoint URL
        if self.base_url.endswith("/chat/completions"):
            self.endpoint = self.base_url
        else:
            self.endpoint = f"{self.base_url}/chat/completions"

    @classmethod
    def from_config(
        cls,
        config: Union[LLMConfig, AppConfig],
        transport: Optional[httpx.BaseTransport] = None,
    ) -> OpenAICompatClient:
        """Instantiates client from LLMConfig or AppConfig."""
        if isinstance(config, AppConfig):
            llm_cfg = config.llm
        else:
            llm_cfg = config

        return cls(
            base_url=llm_cfg.base_url,
            api_key=llm_cfg.api_key,
            model=llm_cfg.model,
            temperature=llm_cfg.temperature,
            timeout_seconds=llm_cfg.timeout_seconds,
            max_retries=llm_cfg.max_retries,
            transport=transport,
        )

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _should_retry(self, status_code: Optional[int], exc: Optional[Exception]) -> bool:
        if isinstance(exc, (httpx.NetworkError, httpx.TimeoutException)):
            return True
        if status_code in (429, 500, 502, 503, 504):
            return True
        return False

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """
        Executes synchronous chat completion request with retries.

        Args:
            messages: List of message dictionaries [{"role": "user", "content": "..."}].
            temperature: Optional override for temperature.
            model: Optional override for model name.
            response_format: Optional response format (e.g. {"type": "json_object"}).

        Returns:
            str: Assistant message content.
        """
        payload: Dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            **kwargs,
        }
        if response_format:
            payload["response_format"] = response_format

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                client_kwargs: Dict[str, Any] = {"timeout": self.timeout_seconds}
                if self._transport is not None:
                    client_kwargs["transport"] = self._transport

                with httpx.Client(**client_kwargs) as client:
                    response = client.post(
                        self.endpoint,
                        headers=self._get_headers(),
                        json=payload,
                    )

                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]

                if not self._should_retry(response.status_code, None) or attempt == self.max_retries:
                    raise LLMResponseError(
                        f"LLM API request failed with status {response.status_code}: {response.text}",
                        status_code=response.status_code,
                    )

                last_error = LLMResponseError(
                    f"Retryable status {response.status_code}",
                    status_code=response.status_code,
                )
            except Exception as e:
                if isinstance(e, LLMResponseError) and not self._should_retry(e.status_code, None):
                    raise
                last_error = e
                if not self._should_retry(None, e) or attempt == self.max_retries:
                    if isinstance(e, (httpx.NetworkError, httpx.TimeoutException)):
                        raise LLMConnectionError(f"LLM network failure: {e}") from e
                    raise

            # Exponential backoff
            sleep_time = self.retry_delay * (2 ** (attempt - 1))
            logger.warning(
                "Attempt %d failed (%s). Retrying in %.2f seconds...",
                attempt,
                last_error,
                sleep_time,
            )
            time.sleep(sleep_time)

        raise LLMClientError(f"Exceeded max retries: {last_error}")

    async def achat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """
        Executes asynchronous chat completion request with retries.
        """
        payload: Dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            **kwargs,
        }
        if response_format:
            payload["response_format"] = response_format

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                client_kwargs: Dict[str, Any] = {"timeout": self.timeout_seconds}
                if self._transport is not None:
                    client_kwargs["transport"] = self._transport

                async with httpx.AsyncClient(**client_kwargs) as client:
                    response = await client.post(
                        self.endpoint,
                        headers=self._get_headers(),
                        json=payload,
                    )

                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]

                if not self._should_retry(response.status_code, None) or attempt == self.max_retries:
                    raise LLMResponseError(
                        f"LLM API request failed with status {response.status_code}: {response.text}",
                        status_code=response.status_code,
                    )

                last_error = LLMResponseError(
                    f"Retryable status {response.status_code}",
                    status_code=response.status_code,
                )
            except Exception as e:
                if isinstance(e, LLMResponseError) and not self._should_retry(e.status_code, None):
                    raise
                last_error = e
                if not self._should_retry(None, e) or attempt == self.max_retries:
                    if isinstance(e, (httpx.NetworkError, httpx.TimeoutException)):
                        raise LLMConnectionError(f"LLM network failure: {e}") from e
                    raise

            sleep_time = self.retry_delay * (2 ** (attempt - 1))
            await asyncio.sleep(sleep_time)

        raise LLMClientError(f"Exceeded max retries: {last_error}")

    def generate_structured_json(
        self,
        messages: List[Dict[str, str]],
        schema: Optional[Union[Type[BaseModel], Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Any:
        """
        Generates structured JSON, optionally validated against a Pydantic schema model.

        Args:
            messages: Prompt messages.
            schema: Optional Pydantic BaseModel class for validation.

        Returns:
            Dict or parsed Pydantic model instance.
        """
        raw_text = self.chat_completion(
            messages=messages,
            response_format={"type": "json_object"},
            **kwargs,
        )

        cleaned = clean_json_text(raw_text)
        try:
            parsed = json.loads(cleaned)
        except Exception as e:
            raise LLMJSONParseError(
                f"Failed to parse LLM response into JSON: {e}",
                raw_content=raw_text,
            ) from e

        if schema is not None and isinstance(schema, type) and issubclass(schema, BaseModel):
            return schema.model_validate(parsed)

        return parsed

    async def agenerate_structured_json(
        self,
        messages: List[Dict[str, str]],
        schema: Optional[Union[Type[BaseModel], Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Any:
        """
        Asynchronously generates structured JSON.
        """
        raw_text = await self.achat_completion(
            messages=messages,
            response_format={"type": "json_object"},
            **kwargs,
        )

        cleaned = clean_json_text(raw_text)
        try:
            parsed = json.loads(cleaned)
        except Exception as e:
            raise LLMJSONParseError(
                f"Failed to parse LLM response into JSON: {e}",
                raw_content=raw_text,
            ) from e

        if schema is not None and isinstance(schema, type) and issubclass(schema, BaseModel):
            return schema.model_validate(parsed)

        return parsed
