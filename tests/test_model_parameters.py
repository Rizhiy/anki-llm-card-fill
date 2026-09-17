# pyright: reportMissingImports=false
# ruff: noqa: SLF001

import json

import pytest

from anki_llm_card_fill.config import ConfigDialog
from anki_llm_card_fill.config_manager import ConfigManager
from anki_llm_card_fill.llm import AnthropicClient, OpenAIClient, OpenRouterClient
from anki_llm_card_fill.migrations import v10


def test_v10_preserves_legacy_parameters_for_every_configured_model():
    config = {
        "models": {"OpenAI": "gpt-4.1", "Anthropic": "claude-sonnet-4-20250514"},
        "temperature": 0.25,
        "max_length": 321,
    }

    migrated = v10(config)

    assert migrated["schema_version"] == 10
    assert "temperature" not in migrated
    assert "max_length" not in migrated
    with pytest.raises(KeyError):
        migrated["temperature"]
    assert migrated["model_parameters"] == {
        "OpenAI": {"gpt-4.1": {"temperature": 0.25, "max_length": 321}},
        "Anthropic": {"claude-sonnet-4-20250514": {"temperature": 0.25, "max_length": 321}},
    }


def test_new_openai_and_anthropic_payload_parameters():
    openai = OpenAIClient("gpt-5.5", api_key="key", reasoning_effort="xhigh", max_length=8000)
    assert openai._request_parameters() == {"max_completion_tokens": 8000, "reasoning_effort": "xhigh"}

    gpt_5_6 = OpenAIClient("gpt-5.6-terra", api_key="key", reasoning_effort="max", max_length=8000)
    assert gpt_5_6._request_parameters() == {"max_completion_tokens": 8000, "reasoning_effort": "max"}
    assert "temperature" not in gpt_5_6._request_parameters()

    openai_sampling = OpenAIClient("gpt-5.1", api_key="key", reasoning_effort="none", temperature=0.2)
    assert openai_sampling._request_parameters()["temperature"] == 0.2

    anthropic = AnthropicClient(
        "claude-sonnet-4-6",
        api_key="key",
        reasoning_effort="medium",
        max_length=8000,
    )
    assert anthropic._request_parameters() == {
        "max_tokens": 8000,
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": "medium"},
    }

    legacy_thinking = AnthropicClient(
        "claude-sonnet-4-20250514",
        api_key="key",
        thinking_budget=2000,
        max_length=8000,
    )
    assert legacy_thinking._request_parameters()["thinking"] == {
        "type": "enabled",
        "budget_tokens": 2000,
    }
    assert "temperature" not in legacy_thinking._request_parameters()


def test_gpt_5_5_pro_uses_responses_api(monkeypatch):
    request_data = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def read(self):
            return json.dumps(
                {
                    "status": "completed",
                    "output": [{"type": "message", "content": [{"type": "output_text", "text": "answer"}]}],
                },
            ).encode()

    def urlopen(request):
        request_data.update(url=request.full_url, payload=json.loads(request.data))
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    client = OpenAIClient("gpt-5.5-pro", api_key="key", reasoning_effort="high", max_length=8000)

    assert client("question") == "answer"
    assert request_data["url"].endswith("/v1/responses")
    assert request_data["payload"]["reasoning"] == {"effort": "high"}
    assert request_data["payload"]["max_output_tokens"] == 8000


def test_openrouter_uses_discovered_capabilities(monkeypatch):
    model = {
        "id": "openai/gpt-5.5",
        "architecture": {"input_modalities": ["text", "image"]},
        "supported_parameters": ["reasoning", "temperature"],
        "reasoning": {
            "supported_efforts": ["low", "medium", "high", "xhigh"],
            "default_effort": "medium",
            "mandatory": True,
        },
        "top_provider": {"max_completion_tokens": 128000},
    }

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def read(self):
            return json.dumps({"data": [model]}).encode()

    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: Response())
    OpenRouterClient._models_cache = None
    [info] = OpenRouterClient.get_available_models()

    assert info["vision"] is True
    assert info["temperature"] is False  # native GPT-5.5 restriction wins
    assert info["reasoning_efforts"] == ["low", "medium", "high", "xhigh"]
    client = OpenRouterClient("openai/gpt-5.5", api_key="key", reasoning_effort="high", max_length=8000)
    assert client._request_parameters() == {
        "max_tokens": 8000,
        "reasoning": {"effort": "high", "exclude": True},
    }
    OpenRouterClient._models_cache = None


def test_config_remembers_each_models_parameters(addon):
    assert addon["client"] == "OpenAI"
    dialog = ConfigDialog()
    dialog._model_selector.setCurrentText("gpt-5.5")
    assert dialog._temperature_input.isHidden()
    dialog._reasoning_effort_input.setCurrentText("high")
    dialog._max_length_input.setValue(9000)

    dialog._model_selector.setCurrentText("gpt-4.1")
    assert not dialog._temperature_input.isHidden()
    dialog._temperature_input.setValue(0.23)
    dialog._max_length_input.setValue(777)

    dialog._model_selector.setCurrentText("gpt-5.5")
    assert dialog._reasoning_effort_input.currentText() == "high"
    assert dialog._max_length_input.value() == 9000
    dialog._model_selector.setCurrentText("gpt-4.1")
    assert dialog._temperature_input.value() == pytest.approx(0.23)
    assert dialog._max_length_input.value() == 777
    dialog.close()


def test_config_manager_merges_defaults_without_mutating_saved_values(addon):
    addon["models"] = {"OpenAI": "gpt-5.5"}
    addon["model_parameters"] = {"OpenAI": {"gpt-4.1": {"temperature": 0.1, "max_length": 222}}}
    ConfigManager._instance = None
    manager = ConfigManager()

    assert manager.get_model_parameters("OpenAI")["reasoning_effort"] == "medium"
    assert manager["model_parameters"] == addon["model_parameters"]
