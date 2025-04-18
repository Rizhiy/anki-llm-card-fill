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
    _models_cache = None

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
    def get_available_models(cls, api_key: str) -> list[str]:
        """Return a list of available models for this provider.

        Args:
            api_key: API key to use for fetching models from the API

        Returns:
            List of model names
        """

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

    @classmethod
    def _get_api_key_from_env(cls) -> str:
        """Get OpenAI API key from environment variable."""
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            logger.warning("OpenAI API key not found in environment variable OPENAI_API_KEY")
        return api_key

    @classmethod
    def get_available_models(cls, api_key: str) -> list[str]:
        """Return a list of available OpenAI models.

        Args:
            api_key: API key for fetching up-to-date models

        Returns:
            List of model names or empty list if fetch fails
        """
        # Return cached results if available
        if cls._models_cache:
            return cls._models_cache

        models = cls._fetch_models_from_api(api_key)
        # Cache the result
        cls._models_cache = models
        return models

    @classmethod
    def _fetch_models_from_api(cls, api_key: str) -> list[str]:
        """Fetch available models from the OpenAI API."""

        # Set up the request with authentication
        request = urllib.request.Request("https://api.openai.com/v1/models")
        request.add_header("Authorization", f"Bearer {api_key}")

        with urllib.request.urlopen(request) as response:  # noqa: S310
            data = json.loads(response.read().decode())

        model_list = data.get("data", [])
        models = sorted(model_list, key=lambda model: model.get("created", 0), reverse=True)
        return [m["id"] for m in models]

    def __call__(self, prompt: str) -> str:
        """Call the OpenAI API with the prompt."""
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}

        api_url = "https://api.openai.com/v1/chat/completions"

        data = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": self.max_length,
                "temperature": self.temperature,
            },
        ).encode("utf-8")

        request = urllib.request.Request(api_url, data=data, headers=headers)  # noqa: S310

        # Let exceptions propagate to the caller
        with urllib.request.urlopen(request) as response:  # noqa: S310
            result = json.loads(response.read().decode())
            return result["choices"][0]["message"]["content"].strip()

    @classmethod
    def get_api_key_link(cls) -> str:
        return "https://platform.openai.com/api-keys"


class AnthropicClient(LLMClient):
    """Client for the Anthropic API."""

    @classmethod
    def get_display_name(cls) -> str:
        return "Anthropic"

    def __init__(self, model: str, temperature: float, max_length: int, api_key: str | None = None):
        super().__init__(model, temperature, max_length, api_key)
        self._api_url = "https://api.anthropic.com/v1/messages"

    @classmethod
    def _get_api_key_from_env(cls) -> str:
        """Get Anthropic API key from environment variable."""
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            logger.warning("Anthropic API key not found in environment variable ANTHROPIC_API_KEY")
        return api_key

    @classmethod
    def get_available_models(cls, api_key: str) -> list[str]:
        """Return a list of available Claude models.

        Args:
            api_key: API key for fetching up-to-date models

        Returns:
            List of model names or empty list if fetch fails
        """
        # Return cached results if available
        if cls._models_cache:
            return cls._models_cache

        models = cls._fetch_models_from_api(api_key)
        # Cache the result
        cls._models_cache = models
        return models

    @classmethod
    def _fetch_models_from_api(cls, api_key: str) -> list[str]:
        """Fetch available models from the Anthropic API."""

        # Set up the request with authentication
        request = urllib.request.Request("https://api.anthropic.com/v1/models")
        request.add_header("x-api-key", api_key)
        request.add_header("anthropic-version", "2023-06-01")

        with urllib.request.urlopen(request) as response:  # noqa: S310
            data = json.loads(response.read().decode())

        # Extract model data from response
        model_list = data.get("data", [])

        # Sort models by creation date (newest first)
        models = sorted(model_list, key=lambda model: model.get("created_at", ""), reverse=True)

        # Return just the model IDs
        return [m["id"] for m in models]

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
