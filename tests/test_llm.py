# pyright: reportMissingImports=false

import pytest

from anki_llm_card_fill.llm import AnthropicClient, LLMClient, OpenAIClient


class TestLLMClient:
    def test_get_available_clients(self):
        assert LLMClient.get_available_clients()

    def test_get_client(self):
        client_name = next(iter(LLMClient.get_available_clients()))
        assert issubclass(LLMClient.get_client(client_name), LLMClient)


@pytest.mark.parametrize(("client_cls"), [LLMClient.get_client(name) for name in LLMClient.get_available_clients()])
class TestLLMClientImpl:
    def test_get_display_name(self, client_cls):
        assert isinstance(client_cls.get_display_name(), str)

    def test_get_api_key_link(self, client_cls):
        assert isinstance(client_cls.get_api_key_link(), str)

    def test_get_available_model(self, client_cls, monkeypatch):
        if client_cls == LLMClient.get_client("OpenRouter"):
            monkeypatch.setattr(client_cls, "_models_cache", [{"name": "openai/gpt-4o", "vision": True}])
        models = client_cls.get_available_models()
        assert isinstance(models, list)
        assert all(isinstance(model, dict) for model in models)
        assert all("name" in model and "vision" in model for model in models)
        assert all(isinstance(model["name"], str) for model in models)
        assert all(isinstance(model["vision"], bool) for model in models)

    def test_call(self, client_cls, monkeypatch):
        if client_cls == AnthropicClient:
            model = "claude-3-haiku-20240307"
        elif client_cls == OpenAIClient:
            model = "gpt-4o"
        else:
            model = "openai/gpt-4o"

        monkeypatch.setattr(client_cls, "_models_cache", [{"name": model, "vision": False}])

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                pass

            def read(self):
                if client_cls == AnthropicClient:
                    return b'{"content":[{"type":"text","text":"Hello"}],"stop_reason":"end_turn"}'
                return b'{"choices":[{"message":{"content":"Hello"},"finish_reason":"stop"}]}'

        monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: Response())
        client = client_cls(
            api_key="test",
            model=model,
            temperature=0.5,
            max_length=16,
            requests_per_minute=10,
            tokens_per_minute=1000,
        )
        assert isinstance(client("Hello"), str)
