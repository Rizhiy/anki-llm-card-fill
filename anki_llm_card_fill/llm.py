from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aqt.qt import QImage

logger = logging.getLogger(__name__)

# Path to model settings directory
MODEL_SETTINGS_DIR = Path(__file__).parent / "model_settings"


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
    def __call__(self, prompt: str, images: list[QImage] | None = None) -> str:
        """Generate a completion for the given prompt and optional images.

        :param prompt: Text prompt to send to the LLM
        :param images: Optional list of QImage objects to include in the prompt
        :return: Generated text response from the LLM
        """

    @classmethod
    @abstractmethod
    def get_available_models(cls) -> list[dict[str, str | bool]]:
        """Return a list of available models for this provider.

        :return: List of model dictionaries with keys:
            - name: The model name
            - vision: Boolean indicating if the model supports image input
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
        """Get a set of all registered LLM client names.

        :return: Set of client display names
        """
        return set(LLMClient._registry.keys())

    @staticmethod
    def get_client(name: str) -> type[LLMClient]:
        """Get a client class by its display name.

        :param name: Display name of the client
        :return: Client class
        """
        return LLMClient._registry[name]

    def _encode_qimage(self, image: QImage) -> str:
        """Encode a QImage as base64.

        :param image: QImage object
        :return: Base64-encoded image data
        """
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        image.save(str(temp_path), "JPEG")
        encoded = base64.b64encode(temp_path.read_bytes()).decode("utf-8")
        temp_path.unlink()

        return encoded


class OpenAIClient(LLMClient):
    """Client for OpenAI's API."""

    # Settings file path
    _SETTINGS_FILE = MODEL_SETTINGS_DIR / "openai.json"

    @classmethod
    def get_display_name(cls) -> str:
        """Return the display name for this client.

        :return: Display name
        """
        return "OpenAI"

    def __init__(self, model: str, temperature: float, max_length: int, api_key: str | None = None):
        super().__init__(model, temperature, max_length, api_key)

    @classmethod
    def _get_api_key_from_env(cls) -> str:
        """Get OpenAI API key from environment variable.

        :return: API key or empty string if not found
        """
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            logger.warning("OpenAI API key not found in environment variable OPENAI_API_KEY")
        return api_key

    @classmethod
    def get_available_models(cls) -> list[dict[str, str | bool]]:
        """Return a list of available OpenAI models.

        :return: List of model dictionaries with name and image support info
                 Format: [{"name": "model_name", "vision": bool}, ...]
        """
        if cls._models_cache:
            return cls._models_cache

        with open(cls._SETTINGS_FILE) as f:
            models = json.load(f)["models"]

        cls._models_cache = models
        return models

    def __call__(self, prompt: str, images: list[QImage] | None = None) -> str:
        """Call the OpenAI API with the prompt and optional images.

        :param prompt: Text prompt to send to the LLM
        :param images: Optional list of QImage objects to include in the prompt
        :return: Generated text response from the LLM
        """
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}

        api_url = "https://api.openai.com/v1/chat/completions"

        messages = [{"role": "user", "content": prompt}]
        if images:
            image_contents = []
            for image in images:
                image_data = self._encode_qimage(image)
                image_contents.append(
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
                )

            messages.append({"role": "user", "content": image_contents})

        data = json.dumps(
            {
                "model": self.model,
                "messages": messages,
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
        """Return the link to obtain the OpenAI API key.

        :return: URL to get API key
        """
        return "https://platform.openai.com/api-keys"


class AnthropicClient(LLMClient):
    """Client for the Anthropic API."""

    # Settings file path
    _SETTINGS_FILE = MODEL_SETTINGS_DIR / "anthropic.json"

    @classmethod
    def get_display_name(cls) -> str:
        """Return the display name for this client.

        :return: Display name
        """
        return "Anthropic"

    def __init__(self, model: str, temperature: float, max_length: int, api_key: str | None = None):
        super().__init__(model, temperature, max_length, api_key)
        self._api_url = "https://api.anthropic.com/v1/messages"

    @classmethod
    def _get_api_key_from_env(cls) -> str:
        """Get Anthropic API key from environment variable.

        :return: API key or empty string if not found
        """
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            logger.warning("Anthropic API key not found in environment variable ANTHROPIC_API_KEY")
        return api_key

    @classmethod
    def get_available_models(cls) -> list[dict[str, str | bool]]:
        """Return a list of available Claude models.

        :return: List of model dictionaries with name and image support info
                 Format: [{"name": "model_name", "vision": bool}, ...]
        """
        if cls._models_cache:
            return cls._models_cache

        with open(cls._SETTINGS_FILE) as f:
            models = json.load(f)["models"]

        cls._models_cache = models
        return models

    def __call__(self, prompt: str, images: list[QImage] | None = None) -> str:
        """Call the Anthropic API with prompt and optional images.

        :param prompt: Text prompt to send to the LLM
        :param images: Optional list of QImage objects to include in the prompt
        :return: Generated text response from the LLM
        """
        headers = {"Content-Type": "application/json", "x-api-key": self.api_key, "anthropic-version": "2023-06-01"}

        content = [{"type": "text", "text": prompt}]

        if images:
            for image in images:
                image_data = self._encode_qimage(image)
                content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_data,
                        },
                    },
                )

        data = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": content}],
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
        """Return the link to obtain the Anthropic API key.

        :return: URL to get API key
        """
        return "https://console.anthropic.com/settings/keys"
