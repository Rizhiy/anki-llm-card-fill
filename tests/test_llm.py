import pytest

from anki_llm_card_fill.llm import LLMClient


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
        client = client_cls()
        assert isinstance(client("Hello"), str)
