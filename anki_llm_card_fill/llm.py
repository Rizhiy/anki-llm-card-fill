from __future__ import annotations

import base64
import json
import logging
import os
import secrets
import tempfile
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, Any

from .rate_limiter import RateLimiter

if TYPE_CHECKING:
    from aqt.qt import QImage

logger = logging.getLogger(__name__)

# Path to model settings directory
MODEL_SETTINGS_DIR = Path(__file__).parent / "model_settings"


class LLMClient(ABC):
    """Base class for LLM clients."""

    _registry = {}
    _models_cache: list[dict[str, Any]] | None = None
    _request_limiter: RateLimiter
    _token_limiter: RateLimiter

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        client_name = cls.get_display_name()
        if client_name in cls._registry:
            raise ValueError(f"Duplicate display name: {client_name}")
        cls._registry[client_name] = cls

        # Initialize class-level rate limiters with defaults
        cls._request_limiter = RateLimiter(limit=10)
        cls._token_limiter = RateLimiter(limit=1000)

    def __init__(
        self,
        model: str,
        temperature: float = 0.7,
        max_length: int = 4096,
        api_key: str | None = None,
        requests_per_minute: int = 60,
        tokens_per_minute: int = 60000,
        reasoning_effort: str | None = None,
        thinking_budget: int = 0,
    ):
        self.api_key = api_key or self._get_api_key_from_env()
        if not self.api_key:
            msg = f"""\
            {self.get_display_name()} API key is required.
            Please set it in the configuration or appropriate environment variable."""
            raise ValueError(dedent(msg))
        self.model = model
        self.temperature = temperature
        self.max_length = max_length
        self.reasoning_effort = reasoning_effort
        self.thinking_budget = thinking_budget

        # Update class-level rate limiters with current settings
        self._request_limiter.update_limit(requests_per_minute)
        self._token_limiter.update_limit(tokens_per_minute)

    @classmethod
    @abstractmethod
    def get_display_name(cls) -> str:
        """Return the display name for the client."""

    def _estimate_tokens(self, prompt: str, images: list[QImage] | None = None) -> int:
        """Estimate token count for the request.

        :param prompt: Text prompt
        :param images: Optional images
        :return: Estimated token count
        """
        # Simple estimation: ~4 characters per token for text
        token_count = len(prompt) // 4

        # Add tokens for images (rough estimate)
        if images:
            token_count += len(images) * 1024

        return max(1, token_count)

    @staticmethod
    def _randomize_prompt(prompt: str) -> str:
        # ponytail: a nonce encourages variety, not uniqueness; add history if deduplication is needed.
        # Six decimal digits take only two tokens in common tokenizers; keep the prefix cacheable.
        return f"{prompt}\n\nUse variation {secrets.randbelow(1000000):06d}; omit this code."

    def _apply_rate_limits(self, prompt: str, images: list[QImage] | None = None) -> None:
        """Apply rate limits before making API call.

        :param prompt: Text prompt
        :param images: Optional images
        """
        self._request_limiter.acquire()
        self._token_limiter.acquire(self._estimate_tokens(prompt, images))

    @abstractmethod
    def __call__(self, prompt: str, images: list[QImage] | None = None) -> str:
        """Generate a completion for the given prompt and optional images.

        :param prompt: Text prompt to send to the LLM
        :param images: Optional list of QImage objects to include in the prompt
        :return: Generated text response from the LLM
        """

    @classmethod
    @abstractmethod
    def get_available_models(cls) -> list[dict[str, Any]]:
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

    @classmethod
    def get_model_info(cls, model: str) -> dict:
        models = cls.get_available_models()
        exact = next((item for item in models if item["name"] == model), None)
        if exact is not None:
            return exact
        # Dated snapshots inherit the capabilities of their exact model family.
        return next(
            (
                item
                for item in sorted(models, key=lambda item: len(item["name"]), reverse=True)
                if model.startswith(item["name"] + "-") and model[len(item["name"]) + 1 :][:4].isdigit()
            ),
            {},
        )

    @classmethod
    def default_parameters(cls, model: str) -> dict:
        info = cls.get_model_info(model)
        return {
            "temperature": 0.7,
            "max_length": 4096 if info.get("reasoning_efforts") or info.get("thinking") else 250,
            "reasoning_effort": info.get("default_effort"),
            "thinking_budget": 0,
        }

    @classmethod
    def parameter_specs(cls, model: str, values: dict) -> dict:
        """One capability source for UI visibility, ranges and request validation."""
        info = cls.get_model_info(model)
        specs: dict[str, Any] = {"max_length": {"min": 1, "max": info.get("max_output_tokens", 4096)}}
        effort = values.get("reasoning_effort") or info.get("default_effort")
        budget = (
            values.get("thinking_budget", 0)
            if (info.get("thinking") == "enabled" or info.get("supports_thinking_budget"))
            else 0
        )
        temperature = info.get("temperature", True)
        if (
            temperature
            and (temperature != "none" or effort == "none")
            and not (budget or (info.get("thinking") == "adaptive" and effort not in (None, "off", "none")))
        ):
            specs["temperature"] = {"min": 0.0, "max": info.get("temperature_max", 1.0)}
        if info.get("reasoning_efforts") and (not budget or cls.get_display_name() == "Anthropic"):
            specs["reasoning_effort"] = {"choices": info["reasoning_efforts"]}
        if info.get("thinking") == "enabled" or info.get("supports_thinking_budget"):
            specs["thinking_budget"] = {"min": 0, "max": info.get("max_output_tokens", 4096) - 1}
        return specs

    def _request_parameters(self) -> dict:
        info = self.get_model_info(self.model)
        values = {
            "temperature": self.temperature,
            "max_length": self.max_length,
            "reasoning_effort": self.reasoning_effort or info.get("default_effort"),
            "thinking_budget": self.thinking_budget,
        }
        specs = self.parameter_specs(self.model, values)
        for name, spec in specs.items():
            value = values[name]
            if "choices" in spec:
                if value not in spec["choices"]:
                    raise ValueError(f"Unsupported {name} for {self.model}: {value}")
            elif not isinstance(value, (int, float)) or not spec["min"] <= value <= spec["max"]:
                raise ValueError(f"{name} must be between {spec['min']} and {spec['max']}")
        budget = self.thinking_budget if "thinking_budget" in specs else 0
        if budget and (budget < 1024 or budget >= self.max_length):
            raise ValueError("Thinking budget must be at least 1024 and less than Max Response Length.")
        params: dict[str, Any] = {"max_tokens": self.max_length}
        if "temperature" in specs:
            params["temperature"] = self.temperature
        effort = values["reasoning_effort"] if "reasoning_effort" in specs else None
        provider = self.get_display_name()
        if provider == "OpenAI":
            if info.get("reasoning_efforts") or info.get("responses_api"):
                params["max_completion_tokens"] = params.pop("max_tokens")
            if effort:
                params["reasoning_effort"] = effort
        elif provider == "Anthropic":
            if budget:
                params["thinking"] = {"type": "enabled", "budget_tokens": budget}
            elif info.get("thinking") == "adaptive":
                params["thinking"] = {"type": "disabled" if effort == "off" else "adaptive"}
            if effort == "off" and self.model.startswith("claude-opus-5"):
                params["output_config"] = {"effort": "high"}
            elif effort and effort != "off":
                params["output_config"] = {"effort": effort}
        elif provider == "OpenRouter":
            if budget:
                params["reasoning"] = {"max_tokens": budget, "exclude": True}
            elif effort:
                params["reasoning"] = {"effort": effort, "exclude": True}
        return params

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

    def __init__(
        self,
        model: str,
        temperature: float = 0.7,
        max_length: int = 4096,
        api_key: str | None = None,
        requests_per_minute: int = 60,
        tokens_per_minute: int = 60000,
        reasoning_effort: str | None = None,
        thinking_budget: int = 0,
    ):
        super().__init__(
            model,
            temperature,
            max_length,
            api_key,
            requests_per_minute,
            tokens_per_minute,
            reasoning_effort,
            thinking_budget,
        )

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
    def get_available_models(cls) -> list[dict[str, Any]]:
        """Return a list of available OpenAI models.

        :return: List of model dictionaries with name and image support info
                 Format: [{"name": "model_name", "vision": bool}, ...]
        """
        if cls._models_cache:
            return cls._models_cache

        try:
            with open(cls._SETTINGS_FILE) as f:
                models = json.load(f)["models"]
        except (OSError, ValueError, KeyError) as e:
            raise ValueError(f"Could not load model settings from {cls._SETTINGS_FILE}: {e}") from e

        cls._models_cache = models
        return models

    def __call__(self, prompt: str, images: list[QImage] | None = None) -> str:
        """Call the OpenAI API with the prompt and optional images.

        :param prompt: Text prompt to send to the LLM
        :param images: Optional list of QImage objects to include in the prompt
        :return: Generated text response from the LLM
        """
        prompt = self._randomize_prompt(prompt)
        self._apply_rate_limits(prompt, images)

        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}

        api_url = "https://api.openai.com/v1/chat/completions"

        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        if images:
            image_contents = []
            for image in images:
                image_data = self._encode_qimage(image)
                image_contents.append(
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
                )

            messages.append({"role": "user", "content": image_contents})

        params = self._request_parameters()
        responses_api = self.get_model_info(self.model).get("responses_api", False)
        if responses_api:
            api_url = "https://api.openai.com/v1/responses"
            content = [{"type": "input_text", "text": prompt}]
            for message in messages[1:]:
                content.extend(
                    {"type": "input_image", "image_url": item["image_url"]["url"]} for item in message["content"]
                )
            params["max_output_tokens"] = params.pop("max_completion_tokens")
            if "reasoning_effort" in params:
                params["reasoning"] = {"effort": params.pop("reasoning_effort")}
            payload = {"model": self.model, "input": [{"role": "user", "content": content}], **params}
        else:
            payload = {"model": self.model, "messages": messages, **params}
        data = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(api_url, data=data, headers=headers)  # noqa: S310

        # Let exceptions propagate to the caller
        with urllib.request.urlopen(request) as response:  # noqa: S310
            try:
                result = json.loads(response.read().decode())
            except ValueError as e:
                raise ValueError("Provider returned invalid JSON.") from e
            if responses_api:
                text = "".join(
                    block["text"]
                    for item in result.get("output", [])
                    if item["type"] == "message"
                    for block in item["content"]
                    if block["type"] == "output_text"
                ).strip()
                if result.get("status") != "completed" or not text:
                    raise ValueError("Incomplete response. Increase Max Response Length or lower thinking effort.")
                return text
            choice = result["choices"][0]
            text = choice["message"].get("content")
            if not text or choice.get("finish_reason") == "length":
                raise ValueError("Incomplete response. Increase Max Response Length or lower thinking effort/budget.")
            return text.strip()

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

    def __init__(
        self,
        model: str,
        temperature: float = 0.7,
        max_length: int = 4096,
        api_key: str | None = None,
        requests_per_minute: int = 60,
        tokens_per_minute: int = 60000,
        reasoning_effort: str | None = None,
        thinking_budget: int = 0,
    ):
        super().__init__(
            model,
            temperature,
            max_length,
            api_key,
            requests_per_minute,
            tokens_per_minute,
            reasoning_effort,
            thinking_budget,
        )
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
    def get_available_models(cls) -> list[dict[str, Any]]:
        """Return a list of available Claude models.

        :return: List of model dictionaries with name and image support info
                 Format: [{"name": "model_name", "vision": bool}, ...]
        """
        if cls._models_cache:
            return cls._models_cache

        try:
            with open(cls._SETTINGS_FILE) as f:
                models = json.load(f)["models"]
        except (OSError, ValueError, KeyError) as e:
            raise ValueError(f"Could not load model settings from {cls._SETTINGS_FILE}: {e}") from e

        cls._models_cache = models
        return models

    def __call__(self, prompt: str, images: list[QImage] | None = None) -> str:
        """Call the Anthropic API with prompt and optional images.

        :param prompt: Text prompt to send to the LLM
        :param images: Optional list of QImage objects to include in the prompt
        :return: Generated text response from the LLM
        """
        prompt = self._randomize_prompt(prompt)
        self._apply_rate_limits(prompt, images)

        headers = {"Content-Type": "application/json", "x-api-key": self.api_key, "anthropic-version": "2023-06-01"}

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]

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
                **self._request_parameters(),
            },
        ).encode("utf-8")

        request = urllib.request.Request(self._api_url, data=data, headers=headers)  # noqa: S310

        # Let exceptions propagate to the caller
        with urllib.request.urlopen(request) as response:  # noqa: S310
            try:
                result = json.loads(response.read().decode())
            except ValueError as e:
                raise ValueError("Provider returned invalid JSON.") from e
            text = "".join(block["text"] for block in result["content"] if block["type"] == "text").strip()
            if not text or result.get("stop_reason") == "max_tokens":
                raise ValueError("Incomplete response. Increase Max Response Length or lower thinking effort/budget.")
            return text

    @classmethod
    def get_api_key_link(cls) -> str:
        """Return the link to obtain the Anthropic API key.

        :return: URL to get API key
        """
        return "https://console.anthropic.com/settings/keys"


class OpenRouterClient(LLMClient):
    """Client for OpenRouter's API."""

    @classmethod
    def get_display_name(cls) -> str:
        """Return the display name for this client.

        :return: Display name
        """
        return "OpenRouter"

    def __init__(
        self,
        model: str,
        temperature: float = 0.7,
        max_length: int = 4096,
        api_key: str | None = None,
        requests_per_minute: int = 60,
        tokens_per_minute: int = 60000,
        reasoning_effort: str | None = None,
        thinking_budget: int = 0,
    ):
        super().__init__(
            model,
            temperature,
            max_length,
            api_key,
            requests_per_minute,
            tokens_per_minute,
            reasoning_effort,
            thinking_budget,
        )
        self._api_url = "https://openrouter.ai/api/v1/chat/completions"

    @classmethod
    def _get_api_key_from_env(cls) -> str:
        """Get OpenRouter API key from environment variable.

        :return: API key or empty string if not found
        """
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            logger.warning("OpenRouter API key not found in environment variable OPENROUTER_API_KEY")
        return api_key

    @classmethod
    def get_available_models(cls) -> list[dict[str, Any]]:
        """Return a list of available OpenRouter models.

        :return: List of model dictionaries with name and image support info
                 Format: [{"name": "model_name", "vision": bool}, ...]
        """
        if cls._models_cache:
            return cls._models_cache

        try:
            headers = {
                "HTTP-Referer": "https://github.com/rizhiy/anki-llm-card-fill",
                "X-Title": "Anki LLM Card Fill",
            }
            request = urllib.request.Request("https://openrouter.ai/api/v1/models", headers=headers)  # noqa: S310

            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                data = json.loads(response.read().decode())

            models = []
            for model in data["data"]:
                # Check if model supports image input
                vision = False
                if "architecture" in model and "input_modalities" in model["architecture"]:
                    vision = "image" in model["architecture"]["input_modalities"]

                supported = model.get("supported_parameters", [])
                reasoning = model.get("reasoning") or {}
                # Keep provider-specific sampling restrictions as well as gateway metadata.
                provider, _, name = model["id"].partition("/")
                client_cls = {"openai": OpenAIClient, "anthropic": AnthropicClient}.get(provider)
                native = client_cls.get_model_info(name) if client_cls else {}
                info = {
                    "name": model["id"],
                    "vision": vision,
                    "temperature": native.get("temperature", True) if "temperature" in supported else False,
                    "temperature_max": 2.0,
                    "max_output_tokens": (model.get("top_provider") or {}).get("max_completion_tokens")
                    or model.get("context_length")
                    or 4096,
                }
                if native.get("thinking"):
                    info["thinking"] = "adaptive"
                if "reasoning" in supported or "reasoning.effort" in supported:
                    if "supported_efforts" in reasoning:
                        efforts = reasoning["supported_efforts"]
                        if efforts is None:
                            efforts = ["none", "minimal", "low", "medium", "high", "xhigh", "max"]
                    elif not reasoning:
                        # Older gateway responses advertise only supported_parameters.
                        efforts = [
                            "none" if value == "off" else value
                            for value in native.get(
                                "reasoning_efforts",
                                ["none", "minimal", "low", "medium", "high", "xhigh", "max"],
                            )
                        ]
                    else:
                        efforts = []
                    if reasoning.get("mandatory"):
                        efforts = [value for value in efforts if value != "none"]
                    if efforts:
                        info["reasoning_efforts"] = efforts
                        default = reasoning.get("default_effort") or native.get("default_effort", "medium")
                        default = "none" if default == "off" else default
                        info["default_effort"] = default if default in efforts else efforts[0]
                    info["supports_thinking_budget"] = reasoning.get("supports_max_tokens", False)
                models.append(info)

            # Sort models alphabetically by name for easier navigation
            models.sort(key=lambda x: x["name"])
            cls._models_cache = models
            return models

        except Exception as e:
            logger.warning(f"Failed to fetch OpenRouter models: {e}")
            # Return empty list if API call fails
            return []

    def __call__(self, prompt: str, images: list[QImage] | None = None) -> str:
        """Call the OpenRouter API with the prompt and optional images.

        :param prompt: Text prompt to send to the LLM
        :param images: Optional list of QImage objects to include in the prompt
        :return: Generated text response from the LLM
        """
        prompt = self._randomize_prompt(prompt)
        self._apply_rate_limits(prompt, images)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/rizhiy/anki-llm-card-fill",
            "X-Title": "Anki LLM Card Fill",
        }

        if images:
            # For vision-enabled models, use content array format
            content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
            for image in images:
                image_data = self._encode_qimage(image)
                content.append(
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
                )
            messages = [{"role": "user", "content": content}]
        else:
            # For text-only requests, use simple string content
            messages = [{"role": "user", "content": prompt}]

        data = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                **self._request_parameters(),
            },
        ).encode("utf-8")

        request = urllib.request.Request(self._api_url, data=data, headers=headers)  # noqa: S310

        # Let exceptions propagate to the caller
        with urllib.request.urlopen(request) as response:  # noqa: S310
            try:
                result = json.loads(response.read().decode())
            except ValueError as e:
                raise ValueError("Provider returned invalid JSON.") from e
            choice = result["choices"][0]
            text = choice["message"].get("content")
            if not text or choice.get("finish_reason") == "length":
                raise ValueError("Incomplete response. Increase Max Response Length or lower thinking effort/budget.")
            return text.strip()

    @classmethod
    def get_api_key_link(cls) -> str:
        """Return the link to obtain the OpenRouter API key.

        :return: URL to get API key
        """
        return "https://openrouter.ai/keys"
