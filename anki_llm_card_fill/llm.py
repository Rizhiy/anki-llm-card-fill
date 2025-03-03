from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from textwrap import dedent

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """Base class for LLM clients."""

    _registry = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        client_name = cls.get_display_name()
        if client_name in cls._registry:
            raise ValueError(f"Duplicate display name: {client_name}")
        cls._registry[client_name] = cls

    def __init__(self, model: str, temperature: float, max_length: int, api_key: str | None = None):
        self.api_key = api_key or self._get_api_key_from_env()
        if not self.api_key:
            msg = f"""\
            {self.get_display_name()} API key is required.
            Please set it in the configuration or appropriate environment variable."""
            raise ValueError(dedent(msg))
        self.model = model
        self.temperature = temperature
        self.max_length = max_length

    @classmethod
    @abstractmethod
    def get_display_name(cls) -> str:
        """Return the display name for the client."""

    @abstractmethod
    def __call__(self, prompt: str) -> str:
        """Generate a completion for the given prompt."""

    @classmethod
    @abstractmethod
    def get_available_models(cls) -> list[str]:
        """Return a list of available models for this provider."""

    @classmethod
    @abstractmethod
    def get_api_key_link(cls) -> str:
        """Return the link to obtain the API key for the client."""

    @classmethod
    @abstractmethod
    def _get_api_key_from_env(cls) -> str:
        """Get API key from environment variables."""

    @staticmethod
    def get_available_clients() -> set[str]:
        return set(LLMClient._registry.keys())

    @staticmethod
    def get_client(name: str) -> type[LLMClient]:
        return LLMClient._registry[name]


class OpenAIClient(LLMClient):
    """Client for OpenAI's API."""

    @classmethod
    def get_display_name(cls) -> str:
        return "OpenAI"

    def __init__(self, model: str, temperature: float, max_length: int, api_key: str | None = None):
        super().__init__(model, temperature, max_length, api_key)
        self._api_url = "https://api.openai.com/v1/chat/completions"

    @classmethod
    def get_available_models(cls) -> list[str]:
        """Return a list of available OpenAI models."""
        return [
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k",
            "gpt-4",
            "gpt-4-turbo",
            "gpt-4o",
        ]

    @classmethod
    def _get_api_key_from_env(cls) -> str:
        """Get OpenAI API key from environment variable."""
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            logger.warning("OpenAI API key not found in environment variable OPENAI_API_KEY")
        return api_key

    def __call__(self, prompt: str) -> str:
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}

        data = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": self.max_length,
                "temperature": self.temperature,
            },
        ).encode("utf-8")

        request = urllib.request.Request(self._api_url, data=data, headers=headers)  # noqa: S310

        # Let exceptions propagate to the caller
        with urllib.request.urlopen(request) as response:  # noqa: S310
            result = json.loads(response.read().decode())
            return result["choices"][0]["message"]["content"].strip()

    @classmethod
    def get_api_key_link(cls) -> str:
        return "https://platform.openai.com/api-keys"


class AnthropicClient(LLMClient):
    """Client for Anthropic's API."""

    @classmethod
    def get_display_name(cls) -> str:
        return "Anthropic"

    def __init__(self, model: str, temperature: float, max_length: int, api_key: str | None = None):
        super().__init__(model, temperature, max_length, api_key)
        self._api_url = "https://api.anthropic.com/v1/messages"

    @classmethod
    def get_available_models(cls) -> list[str]:
        """Return a list of available Anthropic models."""
        return [
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            "claude-2.1",
            "claude-2.0",
        ]

    @classmethod
    def _get_api_key_from_env(cls) -> str:
        """Get Anthropic API key from environment variable."""
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            logger.warning("Anthropic API key not found in environment variable ANTHROPIC_API_KEY")
        return api_key

    def __call__(self, prompt: str) -> str:
        headers = {"Content-Type": "application/json", "x-api-key": self.api_key, "anthropic-version": "2023-06-01"}

        data = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": self.max_length,
                "temperature": self.temperature,
            },
        ).encode("utf-8")

        request = urllib.request.Request(self._api_url, data=data, headers=headers)  # noqa: S310

        # Let exceptions propagate to the caller
        with urllib.request.urlopen(request) as response:  # noqa: S310
            result = json.loads(response.read().decode())
            return result["content"][0]["text"].strip()

    @classmethod
    def get_api_key_link(cls) -> str:
        return "https://console.anthropic.com/settings/keys"
