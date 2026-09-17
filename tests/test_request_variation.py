# pyright: reportMissingImports=false

import json
from io import BytesIO

import pytest
from aqt.qt import QImage

from anki_llm_card_fill.llm import AnthropicClient, OpenAIClient, OpenRouterClient


@pytest.mark.parametrize(
    ("client_cls", "model"),
    [
        (OpenAIClient, "gpt-5.6"),
        (OpenAIClient, "gpt-5.5-pro"),
        (AnthropicClient, "claude-sonnet-4-6"),
        (OpenRouterClient, "openai/gpt-5.6"),
    ],
)
@pytest.mark.parametrize("with_image", [False, True])
def test_each_request_gets_a_compact_variation(monkeypatch, client_cls, model, with_image):
    codes = iter([123456, 654321])
    monkeypatch.setattr("anki_llm_card_fill.llm.secrets.randbelow", lambda _limit: next(codes))
    if client_cls is OpenRouterClient:
        monkeypatch.setattr(client_cls, "_models_cache", [{"name": model, "vision": True}])
    client = client_cls(model, api_key="test")
    monkeypatch.setattr(client, "_encode_qimage", lambda _image: "encoded-image")
    estimated_prompts = []
    monkeypatch.setattr(client, "_apply_rate_limits", lambda prompt, _images: estimated_prompts.append(prompt))
    requests = []
    response = {
        "choices": [{"message": {"content": "answer"}, "finish_reason": "stop"}],
        "content": [{"type": "thinking", "thinking": "hidden"}, {"type": "text", "text": "answer"}],
        "stop_reason": "end_turn",
        "status": "completed",
        "output": [{"type": "message", "content": [{"type": "output_text", "text": "answer"}]}],
    }

    def urlopen(request):
        requests.append(json.loads(request.data))
        return BytesIO(json.dumps(response).encode())

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    prompt = "Write an example sentence."
    for _ in range(2):
        assert client(prompt, images=[QImage()] if with_image else None) == "answer"

    for payload, code, estimated in zip(requests, [123456, 654321], estimated_prompts):
        message = payload.get("messages", payload.get("input"))[0]
        content = message["content"]
        text = content if isinstance(content, str) else content[0]["text"]
        assert text == f"{prompt}\n\nUse variation {code}; omit this code."
        assert estimated == text
        if with_image:
            assert "encoded-image" in json.dumps(payload)
    assert requests[0] != requests[1]
