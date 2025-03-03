from collections import defaultdict

from aqt import mw
from aqt.qt import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
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
from PyQt6.QtGui import QKeySequence

from .llm import LLMClient
from .utils import construct_prompt, parse_field_mappings


class ConfigDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Configure LLM Card Fill")
        self._layout = QVBoxLayout()

        # Set a larger window size
        self.setMinimumWidth(600)
        self.setMinimumHeight(700)

        # Tab widget
        self._tab_widget = QTabWidget()
        self._layout.addWidget(self._tab_widget)

        # Setup tabs
        self._setup_general_tab()
        self._setup_model_parameters_tab()
        self._setup_templates_tab()

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
        self._general_layout = QFormLayout(self._general_tab)

        # Client selection
        self._client_label = QLabel("Select Client:")
        self._client_selector = QComboBox()
        self._client_selector.addItems(LLMClient.get_available_clients())
        self._client_selector.currentIndexChanged.connect(self._update_model_list)
        self._general_layout.addRow(self._client_label, self._client_selector)

        # Model selection
        self._model_label = QLabel("Select Model:")
        self._model_selector = QComboBox()
        self._general_layout.addRow(self._model_label, self._model_selector)

        # API Key input
        self._api_key_label = QLabel("Enter your API key:")
        self._api_key_input = QLineEdit()
        self._general_layout.addRow(self._api_key_label, self._api_key_input)

        # Link to get API key
        self._api_key_link = QLabel("")
        self._api_key_link.setOpenExternalLinks(True)
        self._api_key_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._general_layout.addRow(self._api_key_link)

        # Add shortcut configuration
        self._shortcut_label = QLabel("Keyboard shortcut for updating cards:")
        self._shortcut_input = QLineEdit()
        self._general_layout.addRow(self._shortcut_label, self._shortcut_input)

        # Add note about shortcut conflicts
        self._shortcut_note = QLabel(
            "<i>Note: If the shortcut doesn't work, it might be conflicting with another shortcut. "
            "Please try a different one.</i>",
        )
        self._shortcut_note.setWordWrap(True)
        self._general_layout.addRow(self._shortcut_note)

        self._tab_widget.addTab(self._general_tab, "General")

    def _setup_model_parameters_tab(self):
        # Model parameters tab
        self._params_tab = QWidget()
        self._params_layout = QFormLayout(self._params_tab)

        # Temperature setting
        self._temperature_label = QLabel("Temperature:")
        self._temperature_input = QDoubleSpinBox()
        self._temperature_input.setRange(0.0, 1.0)
        self._temperature_input.setSingleStep(0.01)
        self._params_layout.addRow(self._temperature_label, self._temperature_input)

        # Max length setting
        self._max_length_label = QLabel("Max Length:")
        self._max_length_input = QSpinBox()
        self._max_length_input.setRange(1, 2048)
        self._params_layout.addRow(self._max_length_label, self._max_length_input)

        self._tab_widget.addTab(self._params_tab, "Model Parameters")

    def _setup_templates_tab(self):
        # Templates tab
        self._templates_tab = QWidget()
        self._templates_layout = QVBoxLayout(self._templates_tab)

        # Instructions for using templates
        self._template_instructions = QLabel(
            "You can use existing fields in the prompt using <code>{field_name}</code> syntax.",
        )
        self._template_instructions.setWordWrap(True)
        self._templates_layout.addWidget(self._template_instructions)

        # Global prompt section
        self._global_prompt_label = QLabel("Global Prompt Template:")
        self._templates_layout.addWidget(self._global_prompt_label)

        self._global_prompt_input = QTextEdit()
        self._global_prompt_input.setPlaceholderText(
            "Enter your prompt template here. Use {field_name} to reference card fields.\n\n"
            "Example: Given a card with front content '{Front}', generate content for these fields:",
        )
        self._templates_layout.addWidget(self._global_prompt_input)

        # Field mappings section
        self._field_mappings_label = QLabel("Field Descriptions:")
        self._templates_layout.addWidget(self._field_mappings_label)

        self._field_mappings_input = QTextEdit()
        self._field_mappings_input.setPlaceholderText(
            "Define each field and what content should be generated for it.\n\n"
            "Example:\n"
            "Back: A detailed explanation of the concept\n"
            "Example: A practical example of the concept\n"
            "Mnemonic: A memory aid for remembering this concept",
        )
        self._templates_layout.addWidget(self._field_mappings_input)

        # Preview section
        self._preview_label = QLabel("Prompt Preview:")
        self._templates_layout.addWidget(self._preview_label)

        self._preview_output = QTextEdit()
        self._preview_output.setReadOnly(True)
        self._preview_output.setText("")
        self._templates_layout.addWidget(self._preview_output)

        # Connect signals to update preview
        self._global_prompt_input.textChanged.connect(self._update_prompt_preview)
        self._field_mappings_input.textChanged.connect(self._update_prompt_preview)

        self._tab_widget.addTab(self._templates_tab, "Templates")

    def _open_debug_dialog(self):
        dialog = DebugDialog(self, initial_prompt=self._preview_output.toPlainText())
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

            # Load template data
            global_prompt = config.get("global_prompt", "")
            field_mappings = config.get("field_mappings", "")

            self._global_prompt_input.setText(global_prompt)
            self._field_mappings_input.setText(field_mappings)

            # Update the prompt preview
            self._update_prompt_preview()

            # Load shortcut
            shortcut = config.get("shortcut", "Ctrl+A")
            self._shortcut_input.setText(shortcut)

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

        global_prompt = self._global_prompt_input.toPlainText()
        field_mappings = self._field_mappings_input.toPlainText()
        shortcut = self._shortcut_input.text()

        # Check for shortcut conflicts
        if QKeySequence(shortcut).isEmpty():
            showInfo("Invalid shortcut. Please enter a valid shortcut.")
            return

        config = {
            "client": client_name,
            "model": model_name,
            "api_key": api_key,
            "temperature": temperature,
            "max_length": max_length,
            "global_prompt": global_prompt,
            "field_mappings": field_mappings,
            "shortcut": shortcut,
        }
        mw.addonManager.writeConfig(__name__, config)
        showInfo("Configuration saved!")

    def _update_prompt_preview(self):
        """Update the prompt preview based on current template and field mappings."""
        global_prompt = self._global_prompt_input.toPlainText()
        field_mappings_text = self._field_mappings_input.toPlainText()

        if not global_prompt and not field_mappings_text:
            self._preview_output.setText("")
            return

        # Parse field mappings
        field_mappings = parse_field_mappings(field_mappings_text)

        # Create a defaultdict that returns the key as its own placeholder
        # This simulates having access to all possible fields
        class FieldPlaceholder(defaultdict):
            def __missing__(self, key):
                return f"{key}"

        card_fields = FieldPlaceholder(str)

        # Use the same construct_prompt function that's used for actual LLM calls
        preview = construct_prompt(global_prompt, field_mappings, card_fields)

        self._preview_output.setText(preview)


class DebugDialog(QDialog):
    def __init__(self, parent=None, initial_prompt=""):
        super().__init__(parent)
        self.setWindowTitle("Debug API Query")
        self._layout = QVBoxLayout()

        # Set a reasonable size for the debug dialog
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        # Use QTextEdit instead of QLineEdit for multi-line prompt input
        self._prompt_label = QLabel("Enter your prompt:")
        self._layout.addWidget(self._prompt_label)

        self._prompt_input = QTextEdit()
        self._prompt_input.setPlaceholderText("Enter your prompt here (supports multiple lines)")
        self._prompt_input.setMinimumHeight(150)  # Make it reasonably tall

        # Set the initial prompt if provided
        if initial_prompt:
            self._prompt_input.setText(initial_prompt)

        self._layout.addWidget(self._prompt_input)

        self._output_label = QLabel("API Response:")
        self._layout.addWidget(self._output_label)

        self._output_display = QTextEdit()
        self._output_display.setReadOnly(True)
        self._layout.addWidget(self._output_display)

        self._query_button = QPushButton("Query API")
        self._query_button.clicked.connect(self._query_api)
        self._layout.addWidget(self._query_button)

        self.setLayout(self._layout)

    def _query_api(self):
        # Get the prompt from the QTextEdit instead of QLineEdit
        prompt = self._prompt_input.toPlainText()

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
        except Exception as e:
            self._output_display.setText(f"Error querying API: {e}")


def open_config_dialog():
    dialog = ConfigDialog()
    dialog.exec()
