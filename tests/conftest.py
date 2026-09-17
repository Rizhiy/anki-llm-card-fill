# pyright: reportMissingImports=false

"""Run real Qt controls offscreen without registering Anki's add-on menu."""

import copy
import os
import sys
from types import ModuleType, SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.modules["anki_llm_card_fill.main"] = ModuleType("anki_llm_card_fill.main")

from aqt.qt import QApplication  # noqa: E402

from anki_llm_card_fill import config, config_manager, migrations  # noqa: E402


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def addon(monkeypatch, app):
    assert app is not None
    data = {
        "schema_version": 10,
        "client": "OpenAI",
        "api_keys": {},
        "models": {"OpenAI": "gpt-4.1"},
        "model_parameters": {},
        "max_prompt_tokens": 500,
        "shortcut": "Ctrl+A",
        "note_prompts": {},
        "requests_per_minute": {"OpenAI": 500},
        "tokens_per_minute": {"OpenAI": 30000},
    }

    def write_config(_name, value):
        data.clear()
        data.update(copy.deepcopy(value))

    manager = SimpleNamespace(getConfig=lambda _name: copy.deepcopy(data), writeConfig=write_config)
    mw = SimpleNamespace(addonManager=manager, col=None)
    for module in (config, config_manager, migrations):
        monkeypatch.setattr(module, "mw", mw)
    monkeypatch.setattr(config, "showInfo", lambda _message: None)
    monkeypatch.setattr(config_manager.ConfigManager, "_instance", None)
    return data
