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

    def test_get_available_model(self, client_cls):
        models = client_cls.get_available_models()
        assert isinstance(models, list)
        assert all(isinstance(name, str) for name in models)

    def test_call(self, client_cls):
        if client_cls == AnthropicClient:
            model = "claude-3-haiku-20240307"
        elif client_cls == OpenAIClient:
            model = "gpt-4o"
        else:
            raise ValueError(f"Unsupported client: {client_cls}")

        client = client_cls(model=model, temperature=0.5, max_length=16)
        assert isinstance(client("Hello"), str)
