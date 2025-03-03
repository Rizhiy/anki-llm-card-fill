from aqt import mw
from aqt.qt import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from aqt.utils import showInfo
from PyQt6.QtCore import Qt

from .llm import LLMClient


class ConfigDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Configure LLM Client")
        self._layout = QVBoxLayout()

        # Tab widget
        self._tab_widget = QTabWidget()
        self._layout.addWidget(self._tab_widget)

        # Setup tabs
        self._setup_general_tab()
        self._setup_model_parameters_tab()

        # Save button
        self._save_button = QPushButton("Save")
        self._save_button.clicked.connect(self._save_config)
        self._layout.addWidget(self._save_button)

        # Debug button
        self._debug_button = QPushButton("Open Debug Dialog")
        self._debug_button.clicked.connect(self._open_debug_dialog)
        self._layout.addWidget(self._debug_button)

        self.setLayout(self._layout)
        self._update_model_list()
        self._load_existing_config()

    def _setup_general_tab(self):
        # General settings tab
        self._general_tab = QWidget()
        self._general_layout = QVBoxLayout(self._general_tab)

        # Client selection
        self._client_label = QLabel("Select Client:")
        self._general_layout.addWidget(self._client_label)

        self._client_selector = QComboBox()
        self._client_selector.addItems(LLMClient.get_available_clients())
        self._general_layout.addWidget(self._client_selector)

        # Model selection
        self._model_label = QLabel("Select Model:")
        self._general_layout.addWidget(self._model_label)

        self._model_selector = QComboBox()
        self._general_layout.addWidget(self._model_selector)

        # API Key input
        self._api_key_label = QLabel("Enter your API key:")
        self._general_layout.addWidget(self._api_key_label)

        self._api_key_input = QLineEdit()
        self._general_layout.addWidget(self._api_key_input)

        # Link to get API key
        self._api_key_link = QLabel("")
        self._api_key_link.setOpenExternalLinks(True)
        self._api_key_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._general_layout.addWidget(self._api_key_link)
        self._client_selector.currentIndexChanged.connect(self._update_model_list)

        self._tab_widget.addTab(self._general_tab, "General")

    def _setup_model_parameters_tab(self):
        # Model parameters tab
        self._params_tab = QWidget()
        self._params_layout = QVBoxLayout(self._params_tab)

        # Temperature setting
        self._temperature_label = QLabel("Temperature:")
        self._params_layout.addWidget(self._temperature_label)

        self._temperature_input = QDoubleSpinBox()
        self._temperature_input.setRange(0.0, 1.0)
        self._temperature_input.setSingleStep(0.01)
        self._params_layout.addWidget(self._temperature_input)

        # Max length setting
        self._max_length_label = QLabel("Max Length:")
        self._params_layout.addWidget(self._max_length_label)

        self._max_length_input = QSpinBox()
        self._max_length_input.setRange(1, 2048)
        self._params_layout.addWidget(self._max_length_input)

        self._tab_widget.addTab(self._params_tab, "Model Parameters")

    def _open_debug_dialog(self):
        dialog = DebugDialog(self)
        dialog.exec()

    @staticmethod
    def _shorten_key(key: str) -> str:
        return f"{key[:3]}...{key[-3:]}"

    def _load_existing_config(self):
        config = mw.addonManager.getConfig(__name__)
        if config:
            client_name = config.get("client", "OpenAI")
            model_name = config.get("model", "")
            api_key = config.get("api_key", "")
            temperature = config.get("temperature", 0.5)
            max_length = config.get("max_length", 200)

            self._client_selector.setCurrentText(client_name)
            self._model_selector.setCurrentText(model_name)
            self._temperature_input.setValue(temperature)
            self._max_length_input.setValue(max_length)

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

    def _save_config(self):
        client_name = self._client_selector.currentText()
        model_name = self._model_selector.currentText()
        api_key = self._api_key_input.text()
        temperature = self._temperature_input.value()
        max_length = self._max_length_input.value()

        if config := mw.addonManager.getConfig(__name__):
            current_key = config.get("api_key", "")
            if self._shorten_key(api_key) == self._shorten_key(current_key):
                api_key = current_key

        config = {
            "client": client_name,
            "model": model_name,
            "api_key": api_key,
            "temperature": temperature,
            "max_length": max_length,
        }
        mw.addonManager.writeConfig(__name__, config)
        showInfo("Configuration saved!")


class DebugDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Debug API Query")
        self._layout = QVBoxLayout()

        self._prompt_input = QLineEdit()
        self._prompt_input.setPlaceholderText("Enter your prompt here")
        self._layout.addWidget(self._prompt_input)

        self._output_display = QTextEdit()
        self._output_display.setReadOnly(True)
        self._layout.addWidget(self._output_display)

        self._query_button = QPushButton("Query API")
        self._query_button.clicked.connect(self._query_api)
        self._layout.addWidget(self._query_button)

        self.setLayout(self._layout)

    def _query_api(self):
        prompt = self._prompt_input.text()
        config = mw.addonManager.getConfig(__name__)
        if not config:
            self._output_display.setText("No configuration found.")
            return

        client_name = config.get("client", "OpenAI")
        model_name = config.get("model", "")
        api_key = config.get("api_key", "")
        temperature = config.get("temperature", 0.5)
        max_length = config.get("max_length", 200)

        client_cls = LLMClient.get_client(client_name)
        client = client_cls(api_key=api_key, model=model_name, temperature=temperature, max_length=max_length)

        try:
            response = client(prompt)
            self._output_display.setText(response)
        except Exception as e:  # noqa: BLE001
            self._output_display.setText(f"Error querying API: {e}")


def open_config_dialog():
    dialog = ConfigDialog()
    dialog.exec()
