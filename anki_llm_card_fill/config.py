from aqt import mw
from aqt.qt import QComboBox, QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout
from aqt.utils import showInfo
from PyQt6.QtCore import Qt

from .llm import LLMClient


class ConfigDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Configure LLM Client")
        self._layout = QVBoxLayout()

        # Client selection
        self._client_label = QLabel("Select Client:")
        self._layout.addWidget(self._client_label)

        self._client_selector = QComboBox()
        self._client_selector.addItems(LLMClient.get_available_clients())
        self._layout.addWidget(self._client_selector)

        # Model selection
        self._model_label = QLabel("Select Model:")
        self._layout.addWidget(self._model_label)

        self._model_selector = QComboBox()
        self._layout.addWidget(self._model_selector)

        # API Key input
        self._api_key_label = QLabel("Enter your API key:")
        self._layout.addWidget(self._api_key_label)

        self._api_key_input = QLineEdit()
        self._layout.addWidget(self._api_key_input)

        # Load existing config
        self._load_existing_config()

        # Link to get API key
        self._api_key_link = QLabel('<a href="https://platform.openai.com/api-keys">Get your OpenAI API key</a>')
        self._api_key_link.setOpenExternalLinks(True)
        self._api_key_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self._api_key_link)
        self._client_selector.currentIndexChanged.connect(self._update_model_list)

        # Save button
        self._save_button = QPushButton("Save")
        self._save_button.clicked.connect(self._save_config)
        self._layout.addWidget(self._save_button)

        self.setLayout(self._layout)
        self._update_model_list()  # Initialize model list

    @staticmethod
    def _shorten_key(key: str) -> str:
        return f"{key[:3]}...{key[-3:]}"

    def _load_existing_config(self):
        config = mw.addonManager.getConfig(__name__)
        if config:
            client_name = config.get("client", "OpenAI")
            model_name = config.get("model", "")
            api_key = config.get("api_key", "")

            self._client_selector.setCurrentText(client_name)
            self._model_selector.setCurrentText(model_name)

            if api_key:
                self._api_key_input.setText(self._shorten_key(api_key))

    def _update_model_list(self):
        client_name = self._client_selector.currentText()
        client_cls = LLMClient.get_client(client_name)
        models = client_cls.get_available_models()
        api_key_link = client_cls.get_api_key_link()

        self._api_key_link.setText(f'<a href="{api_key_link}">Get your {client_name} API key</a>')

        self._model_selector.clear()
        self._model_selector.addItems(models)

        config = mw.addonManager.getConfig(__name__)
        if config:
            self._model_selector.setCurrentText(config.get("model", ""))

    def _save_config(self):
        client_name = self._client_selector.currentText()
        model_name = self._model_selector.currentText()
        api_key = self._api_key_input.text()

        if config := mw.addonManager.getConfig(__name__):
            current_key = config.get("api_key", "")
            if self._shorten_key(api_key) == self._shorten_key(current_key):
                api_key = current_key

        config = {"client": client_name, "model": model_name, "api_key": api_key}
        mw.addonManager.writeConfig(__name__, config)
        showInfo("Configuration saved!")
        self.close()


def open_config_dialog():
    dialog = ConfigDialog()
    dialog.exec()
