import socket
import threading
from collections import defaultdict
from typing import Any

from aqt import mw
from aqt.qt import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QObject,
    QPlainTextEdit,
    QPushButton,
    QRunnable,
    QSpinBox,
    Qt,
    QTabWidget,
    QThreadPool,
    QTimer,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)
from aqt.utils import showInfo

from .config_manager import ConfigManager
from .llm import LLMClient
from .utils import construct_prompt


class ConfigDialog(QDialog):
    # Class-level lock to prevent multiple model update operations
    _model_update_lock = threading.Lock()

    def __init__(self):
        super().__init__()
        self._config_manager = ConfigManager()
        self.setWindowTitle("Configure LLM Card Fill")

        # Create main layout
        self._layout = QVBoxLayout()

        # Set a larger window size and make it resizable
        self.setMinimumWidth(800)  # Wider for two-column layout
        self.setMinimumHeight(700)
        self.setSizeGripEnabled(True)  # Make the window resizable

        # Create tab widget
        self._tab_widget = QTabWidget()
        self._layout.addWidget(self._tab_widget)

        # Setup tabs
        self._setup_general_tab()
        self._setup_model_parameters_tab()
        self._setup_templates_tab()

        # Warning message for unsaved config changes (initially hidden)
        self._config_warning_label = QLabel("⚠️ Configuration needs to saved to take effect on generation!")
        self._config_warning_label.setWordWrap(True)
        self._config_warning_label.setStyleSheet(
            "color: #856404; background-color: #fff3cd; "
            "border: 1px solid #ffeaa7; padding: 8px; "
            "border-radius: 4px; font-weight: bold;",
        )
        self._layout.addWidget(self._config_warning_label)

        # Save and Debug buttons in a horizontal layout
        button_layout = QHBoxLayout()

        # Add spacer to center the buttons
        button_layout.addStretch(1)

        # Save button
        self._save_button = QPushButton("Save")
        self._save_button.clicked.connect(self._save_config)
        self._save_button.setMinimumWidth(100)
        button_layout.addWidget(self._save_button)

        # Debug button
        self._debug_button = QPushButton("Open Debug Dialog")
        self._debug_button.clicked.connect(self._open_debug_dialog)
        self._debug_button.setMinimumWidth(150)
        button_layout.addWidget(self._debug_button)

        # Add spacer to center the buttons
        button_layout.addStretch(1)

        self._layout.addLayout(button_layout)

        self.setLayout(self._layout)

        # Update model list first, then load config to preserve selected model
        self._load_existing_config()

    def _setup_general_tab(self):
        # General settings tab
        self._general_tab = QWidget()
        self._general_layout = QFormLayout(self._general_tab)

        # Client selection
        self._client_label = QLabel("Select Client:")
        self._client_selector = QComboBox()
        self._client_selector.addItems(LLMClient.get_available_clients())
        self._client_selector.currentIndexChanged.connect(self._on_client_changed)
        self._general_layout.addRow(self._client_label, self._client_selector)
        self._models = []

        # Model selection with vision support indicator
        self._model_label = QLabel("Select Model:")

        # Create a container for model selector and vision indicator
        model_container = QWidget()
        model_layout = QHBoxLayout(model_container)
        model_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins for tighter layout

        # Add model selector to the container
        self._model_selector = QComboBox()
        self._model_selector.currentIndexChanged.connect(self._on_model_changed)
        model_layout.addWidget(self._model_selector)

        # Add vision support indicator to the container
        self._vision_support_label = QLabel("")
        self._vision_support_label.setStyleSheet("font-weight: bold; margin-left: 10px;")
        model_layout.addWidget(self._vision_support_label)

        # Add the container to the form layout
        self._general_layout.addRow(self._model_label, model_container)

        # Add note about vision mode support
        vision_note = QLabel(
            "<i>Note: Vision capability (image input) is currently only supported in the "
            "card creation dialog, not for updating existing cards.</i>",
        )
        vision_note.setWordWrap(True)
        vision_note.setStyleSheet(
            "color: #555555; font-size: 11px; background-color: #f8f8f8; padding: 5px; border-radius: 3px;",
        )
        self._general_layout.addRow(vision_note)

        # API Key input
        self._api_key_label = QLabel("Enter your API key:")
        self._api_key_input = QLineEdit()
        # Connect API key changes to update model list
        self._api_key_input.textChanged.connect(self._on_api_key_changed)
        self._general_layout.addRow(self._api_key_label, self._api_key_input)

        # Link to get API key
        self._api_key_link = QLabel("")
        self._api_key_link.setOpenExternalLinks(True)
        self._api_key_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._general_layout.addRow(self._api_key_link)

        # OpenRouter warning (initially hidden)
        self._openrouter_warning = QLabel(
            "<b>⚠️ Advanced Client Warning:</b> OpenRouter provides access to many models, "
            "but some models like reasoning-only models (e.g., gpt-5, gemini-2.5-pro) "
            "may not work with this addon due to API compatibility differences.",
        )
        self._openrouter_warning.setWordWrap(True)
        self._openrouter_warning.setStyleSheet(
            "color: #d97700; font-size: 11px; background-color: #fff3cd; "
            "padding: 8px; border: 1px solid #ffc107; border-radius: 4px; margin: 5px 0;",
        )
        self._openrouter_warning.setVisible(False)  # Initially hidden
        self._general_layout.addRow(self._openrouter_warning)

        # Rate limiting settings
        self._requests_per_minute_label = QLabel("Requests per minute:")
        self._requests_per_minute_label.setToolTip(
            "Maximum number of API requests allowed per minute for the selected client",
        )
        self._requests_per_minute_input = QSpinBox()
        self._requests_per_minute_input.setRange(1, 1000)
        self._requests_per_minute_input.setValue(60)
        self._general_layout.addRow(
            self._requests_per_minute_label,
            self._requests_per_minute_input,
        )

        self._tokens_per_minute_label = QLabel("Tokens per minute:")
        self._tokens_per_minute_label.setToolTip(
            "Maximum number of tokens (approximate) allowed per minute for the selected client",
        )
        self._tokens_per_minute_input = QSpinBox()
        self._tokens_per_minute_input.setRange(1000, 1_000_000)
        self._tokens_per_minute_input.setValue(60_000)
        self._general_layout.addRow(
            self._tokens_per_minute_label,
            self._tokens_per_minute_input,
        )

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
        self._max_length_label = QLabel("Max Response Length (tokens):")
        self._max_length_input = QSpinBox()
        self._max_length_input.setRange(1, 4096)
        self._params_layout.addRow(self._max_length_label, self._max_length_input)

        # Add max prompt tokens setting
        self._max_prompt_tokens_label = QLabel("Max Prompt Length (tokens):")
        self._max_prompt_tokens_label.setToolTip(
            "Limit the maximum length of prompts to avoid excessive token usage",
        )
        self._max_prompt_tokens_input = QSpinBox()
        self._max_prompt_tokens_input.setRange(1, 4096)
        self._params_layout.addRow(
            self._max_prompt_tokens_label,
            self._max_prompt_tokens_input,
        )

        self._tab_widget.addTab(self._params_tab, "Request Parameters")

    def _setup_templates_tab(self):
        """Setup templates tab with a two-column layout supporting note types."""
        # Templates tab
        self._templates_tab = QWidget()
        main_layout = QHBoxLayout(self._templates_tab)

        # Left column - Instructions, Card Type Selector, Global Prompt, Preview
        left_column = QVBoxLayout()

        # Instructions for using templates
        self._template_instructions = QLabel(
            "You can reference card fields in the prompt with <code>{FieldName}</code> syntax. "
            "In the Fields to Update section, specify which fields should be completed by the AI "
            "and provide descriptions of what each field should contain.",
        )
        self._template_instructions.setWordWrap(True)
        left_column.addWidget(self._template_instructions)

        # Add HTML to Markdown conversion note
        self._html_md_note = QLabel(
            "<b>Note:</b> Basic HTML tags in card fields are automatically converted to Markdown "
            "format when inserted into prompts. Stuff like bold, italic, lists, etc. "
            "You can use preview below to see the converted markdown, by selecting a card.",
        )
        self._html_md_note.setWordWrap(True)
        self._html_md_note.setStyleSheet(
            "color: #555555; font-size: 11px; background-color: #f8f8f8; padding: 5px; border-radius: 3px;",
        )
        left_column.addWidget(self._html_md_note)

        # Add card type selector
        note_type_layout = QHBoxLayout()

        self._note_type_label = QLabel("Note type")
        self._note_type_label.setStyleSheet("font-weight: bold;")
        note_type_layout.addWidget(self._note_type_label)

        self._note_type_selector = QComboBox()
        self._note_type_selector.currentIndexChanged.connect(self._on_note_type_changed)
        note_type_layout.addWidget(self._note_type_selector, 1)

        # Add button to add new card type
        self._add_note_type_button = QPushButton("+")
        self._add_note_type_button.setToolTip("Add new note type")
        self._add_note_type_button.clicked.connect(self._add_new_note_type)
        self._add_note_type_button.setMaximumWidth(30)
        self._add_note_type_button.setStyleSheet("padding: 2px;")
        note_type_layout.addWidget(self._add_note_type_button)

        # Add button to remove current card type
        self._remove_note_type_button = QPushButton("️❌")
        self._remove_note_type_button.setToolTip("Remove selected note type")
        self._remove_note_type_button.clicked.connect(self._remove_current_note_type)
        self._remove_note_type_button.setMaximumWidth(30)
        self._remove_note_type_button.setStyleSheet("padding: 2px;")
        note_type_layout.addWidget(self._remove_note_type_button)

        left_column.addLayout(note_type_layout)

        # Global prompt section
        self._global_prompt_label = QLabel("Global Prompt Template")
        self._global_prompt_label.setStyleSheet("font-weight: bold;")
        left_column.addWidget(self._global_prompt_label)

        self._global_prompt_input = QPlainTextEdit()
        self._global_prompt_input.setPlaceholderText(
            "Enter your prompt template here. Use {field_name} to reference card fields.\n\n"
            "Example: Given a card with front content '{Front}', generate content for these fields:",
        )
        left_column.addWidget(self._global_prompt_input)

        # Preview section with controls for card selection
        preview_header = QWidget()
        preview_layout = QHBoxLayout(preview_header)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        self._preview_label = QLabel("Prompt Preview")
        self._preview_label.setStyleSheet("font-weight: bold;")
        preview_layout.addWidget(self._preview_label, 1)

        # Add select card button
        self._select_card_button = QPushButton("Select Card for Preview")
        self._select_card_button.clicked.connect(self._select_card_for_preview)
        self._selected_note = None
        preview_layout.addWidget(self._select_card_button)

        # Add clear selection button
        self._clear_card_button = QPushButton("Use Placeholders")
        self._clear_card_button.clicked.connect(self._clear_preview_card)
        self._clear_card_button.setEnabled(False)  # Initially disabled
        preview_layout.addWidget(self._clear_card_button)

        left_column.addWidget(preview_header)

        # Add card info label
        self._card_info_label = QLabel("Using placeholder values for preview")
        self._card_info_label.setStyleSheet("font-style: italic;")
        left_column.addWidget(self._card_info_label)

        # Add token count display
        self._token_count_label = QLabel("")
        self._token_count_label.setStyleSheet("font-weight: bold;")
        left_column.addWidget(self._token_count_label)

        self._preview_output = QPlainTextEdit()
        self._preview_output.setReadOnly(True)
        self._preview_output.setPlainText("")
        left_column.addWidget(self._preview_output)

        # Right column - Field mappings
        right_column = QVBoxLayout()

        # Add label for field mappings
        self._field_mappings_label = QLabel("Fields to Update")
        self._field_mappings_label.setStyleSheet("font-weight: bold;")
        right_column.addWidget(self._field_mappings_label)

        # Create container for field mappings
        field_mappings_widget = QWidget()
        self._field_mappings_layout = QVBoxLayout(field_mappings_widget)
        self._field_mappings_layout.setContentsMargins(0, 0, 0, 0)
        self._field_mappings_layout.setSpacing(8)  # Spacing between rows

        # Add widget to the right column
        right_column.addWidget(field_mappings_widget, 1)

        # Add button for adding new field mappings at the bottom of the column
        self._add_mapping_button = QPushButton("Add Field")
        self._add_mapping_button.clicked.connect(self._create_field_mapping_row)
        right_column.addWidget(self._add_mapping_button)

        # Add columns to main layout
        main_layout.addLayout(left_column, 3)  # 60% width
        main_layout.addLayout(right_column, 2)  # 40% width

        # Connect signals to update preview
        self._global_prompt_input.textChanged.connect(self._update_prompt_preview)
        self._max_prompt_tokens_input.valueChanged.connect(self._update_prompt_preview)

        self._tab_widget.addTab(self._templates_tab, "Templates")

        # Initialize field tracking list
        self._field_mapping_widgets = []
        self._template_initialised = False

    def _open_debug_dialog(self):
        """Open the debug dialog with the current preview text."""
        # Pass this instance as parent and the preview text as initial_prompt
        dialog = DebugDialog(self, initial_prompt=self._preview_output.toPlainText())
        dialog.exec()

    @staticmethod
    def _shorten_key(key: str) -> str:
        return f"{key[:3]}...{key[-3:]}"

    def _load_existing_config(self):
        # Use self._config_manager directly as a dictionary
        if not self._config_manager:
            return

        # Set client and model
        client_name = self._config_manager["client"]
        # Set model parameters
        temperature = self._config_manager["temperature"]
        max_length = self._config_manager["max_length"]
        max_prompt_tokens = self._config_manager["max_prompt_tokens"]

        self._client_selector.setCurrentText(client_name)
        self._temperature_input.setValue(temperature)
        self._max_length_input.setValue(max_length)
        self._max_prompt_tokens_input.setValue(max_prompt_tokens)

        # Set rate limiting parameters for current client
        requests_per_minute = self._config_manager.get_requests_per_minute_for_client(client_name)
        tokens_per_minute = self._config_manager.get_tokens_per_minute_for_client(client_name)
        self._requests_per_minute_input.setValue(requests_per_minute)
        self._tokens_per_minute_input.setValue(tokens_per_minute)

        # Get API key for the current client
        api_key = self._config_manager.get_api_key_for_client(client_name)
        if api_key:
            self._api_key_input.setText(self._shorten_key(api_key))

        # Get model for current client
        client_model = self._config_manager.get_model_for_client(client_name)
        self._model_selector.setCurrentText(client_model)

        self._load_available_note_types()

        # Load shortcut
        self._shortcut_input.setText(self._config_manager["shortcut"])

        # Update the prompt preview
        self._update_prompt_preview()

    def _update_model_list(self):
        """Update the model list for the current client."""

        try:
            client_name = self._client_selector.currentText()
            client_cls = LLMClient.get_client(client_name)

            # Get API key, handling shortened display format
            api_key = self._api_key_input.text()

            # Check if the key is already in shortened format or empty
            if not api_key or api_key == self._shorten_key(api_key):
                # Key is already shortened or empty, get the full key from config
                api_key = self._config_manager.get_api_key_for_client(client_name)

            # Show loading state
            self._model_selector.clear()

            if not api_key:
                # No API key provided - show a message
                self._model_selector.addItem(
                    f"Enter {client_name} API key to see models",
                )
                self._model_selector.setEnabled(False)
                # Clear vision support label
                self._vision_support_label.setText("N/A")
                self._vision_support_label.setStyleSheet("color: gray; font-weight: bold;")
                return

            # API key provided - try to fetch models
            self._model_selector.addItem("Loading models...")
            self._model_selector.setEnabled(False)
            # Clear vision support label
            self._vision_support_label.setText("Loading...")
            self._vision_support_label.setStyleSheet("color: gray; font-weight: bold;")

            # Check if we're already updating models
            if not ConfigDialog._model_update_lock.acquire(blocking=False):
                # Another thread is already updating models, so we'll just return
                return

            # Create and start worker
            worker = ModelFetchWorker(client_name, client_cls, api_key)
            worker.signals.result.connect(self._on_models_loaded)
            worker.signals.error.connect(self._on_models_error)
            worker.signals.finished.connect(
                lambda: ConfigDialog._model_update_lock.release(),
            )

            # Start the worker
            QThreadPool.globalInstance().start(worker)
        except Exception:
            # Ensure the lock is released even if there's an error
            ConfigDialog._model_update_lock.release()
            raise

    def _on_models_loaded(self, models):
        """Handle successfully loaded models."""
        self._model_selector.clear()
        self._model_selector.setEnabled(True)
        self._models = models  # Store models for later reference

        if not models:
            self._model_selector.addItem("No models available")
            # Update vision support indicator
            self._vision_support_label.setText("N/A")
            self._vision_support_label.setStyleSheet("color: gray; font-weight: bold;")
            return

        # Add each model to the dropdown
        for model in models:
            # Each model is now a dict with 'name' and 'vision' keys
            self._model_selector.addItem(model["name"])

        # Restore previous selection if possible
        client_name = self._client_selector.currentText()
        previous_model = self._config_manager.get_model_for_client(client_name)

        if previous_model:
            index = self._model_selector.findText(previous_model)
            if index >= 0:
                self._model_selector.setCurrentIndex(index)

    def _on_models_error(self, error_msg):
        """Handle errors during model loading."""
        self._model_selector.clear()
        self._model_selector.addItem("Error loading models")
        self._model_selector.setEnabled(False)  # Disable the model selector

        # Update vision support indicator
        self._vision_support_label.setText("N/A")
        self._vision_support_label.setStyleSheet("color: gray; font-weight: bold;")

        # Also show an info popup with more details
        client_name = self._client_selector.currentText()
        error_message = (
            f"Could not get model list for {client_name}:\n\n"
            f"{error_msg}\n\n"
            "Please check:\n"
            "- Your API key is correct\n"
            "- Your internet connection is working\n"
            "- The API service is available"
        )
        showInfo(error_message)

    def _on_model_changed(self, _=None):
        """Handle when the model selection changes."""
        # Update vision support indicator
        model_name = self._model_selector.currentText()

        for model in self._models:
            if model["name"] == model_name:
                if model["vision"]:
                    self._vision_support_label.setText("Vision ✓")
                    self._vision_support_label.setStyleSheet("color: green; font-weight: bold;")
                else:
                    self._vision_support_label.setText("Vision ✗")
                    self._vision_support_label.setStyleSheet("color: red; font-weight: bold;")
                return

        self._vision_support_label.setText("N/A")
        self._vision_support_label.setStyleSheet("color: gray;")

    def _on_client_changed(self, _):
        """Handle client selection changes."""
        # Get the newly selected client
        client_name = self._client_selector.currentText()
        client_cls = LLMClient.get_client(client_name)

        # Update API key link
        api_key_link = client_cls.get_api_key_link()
        self._api_key_link.setText(
            f'<a href="{api_key_link}">Get your {client_name} API key</a>',
        )

        # Show/hide OpenRouter warning
        if client_name == "OpenRouter":
            self._openrouter_warning.setVisible(True)
        else:
            self._openrouter_warning.setVisible(False)

        # Get API key for the new client
        api_key = self._config_manager.get_api_key_for_client(client_name)

        # Update the API key field if we have a key for this client
        if api_key:
            self._api_key_input.setText(self._shorten_key(api_key))
        else:
            self._api_key_input.setText("")

        # Update rate limits for the new client
        requests_per_minute = self._config_manager.get_requests_per_minute_for_client(client_name)
        tokens_per_minute = self._config_manager.get_tokens_per_minute_for_client(client_name)
        self._requests_per_minute_input.setValue(requests_per_minute)
        self._tokens_per_minute_input.setValue(tokens_per_minute)

        # Update the model list for the new client
        self._update_model_list()

    def _on_api_key_changed(self, _):
        """Handle API key changes."""
        self._update_model_list()

    def _save_config(self):
        """Save the configuration."""
        client_name = self._client_selector.currentText()

        # Update the current note type config and get the full note_prompts dictionary
        self._update_current_note_type_config()

        config = {
            "client": client_name,
            "temperature": self._temperature_input.value(),
            "max_length": self._max_length_input.value(),
            "max_prompt_tokens": self._max_prompt_tokens_input.value(),
            "shortcut": self._shortcut_input.text(),
        }

        api_keys = self._config_manager.get("api_keys", {})
        models = self._config_manager.get("models", {})
        requests_per_minute = self._config_manager.get("requests_per_minute", {})
        tokens_per_minute = self._config_manager.get("tokens_per_minute", {})

        # If current key input is the shortened version, get the actual key
        api_key = self._api_key_input.text()
        if api_key and "..." in api_key:
            # Use self._config_manager's method to get the full key
            api_key = self._config_manager.get_api_key_for_client(client_name)
        # Update the API key for the current client
        api_keys[client_name] = api_key

        if model_name := self._model_selector.currentText():
            models[client_name] = model_name

        # Update rate limits for the current client
        requests_per_minute[client_name] = self._requests_per_minute_input.value()
        tokens_per_minute[client_name] = self._tokens_per_minute_input.value()

        # Update the config with all values
        self._config_manager.update(config)

        # Save the updated configuration using the config manager
        self._config_manager.save_config()
        showInfo("Configuration saved!")

    def _update_prompt_preview(self):
        """Update the prompt preview based on current template and field mappings."""
        global_prompt = self._global_prompt_input.toPlainText()

        # Get field mappings using our helper method
        field_mappings = self._get_field_mappings_from_widgets()

        if not global_prompt and not field_mappings:
            self._preview_output.setPlainText("")
            self._token_count_label.setText("")
            return

        # Get card fields - either from selected card or use placeholders
        if self._selected_note:
            # Use actual card data
            card_fields = dict(self._selected_note.items())
        else:
            # Create a defaultdict that returns the key as its own placeholder
            class FieldPlaceholder(defaultdict):
                def __missing__(self, key):
                    return f"{key}"

            card_fields = FieldPlaceholder(str)

        # Use the construct_prompt function
        preview = construct_prompt(global_prompt, field_mappings, card_fields)

        # Estimate token count
        from .card_updater import estimate_token_count

        estimated_tokens = estimate_token_count(preview)
        max_tokens = self._max_prompt_tokens_input.value()

        # Update token count display
        token_info = f"Approximate token count: {estimated_tokens} "
        if estimated_tokens > max_tokens:
            token_info += f"(EXCEEDS LIMIT OF {max_tokens})"
            self._token_count_label.setStyleSheet("color: red; font-weight: bold;")
        else:
            token_info += f"(limit: {max_tokens})"
            self._token_count_label.setStyleSheet("color: green; font-weight: bold;")

        self._token_count_label.setText(token_info)
        self._preview_output.setPlainText(preview)

    def _select_card_for_preview(self):
        """Open a dialog to select a card for the preview."""
        # Create and show the selection dialog
        dialog = CardSelectDialog(self, self._current_note_type)

        if dialog.exec():
            # User selected a card and hit OK
            note_id = dialog.get_selected_note_id()
            if note_id:
                self._selected_note = mw.col.get_note(note_id)

                # Update the UI
                note_type = self._selected_note.note_type()["name"]
                first_field_content = self._selected_note.fields[0]

                # Truncate content if too long
                if len(first_field_content) > 30:
                    first_field_content = first_field_content[:27] + "..."

                self._card_info_label.setText(
                    f"Using selected card: {note_type} - {first_field_content}",
                )
                self._clear_card_button.setEnabled(True)

                # Update the preview with the selected card's data
                self._update_prompt_preview()

    def _clear_preview_card(self):
        """Clear the selected card and use placeholders instead."""
        self._selected_note = None
        self._card_info_label.setText("Using placeholder values for preview")
        self._clear_card_button.setEnabled(False)
        self._update_prompt_preview()

    def _create_field_mapping_row(self, *, prompt_var="", note_field=""):
        """Create a row for field mapping with delete button."""
        row_widget = QWidget()

        def get_valid_field_names() -> list[str]:
            note_type_fields = mw.col.models.by_name(self._current_note_type)["flds"]
            existing_mappings = {mapping["prompt_var_input"].currentText() for mapping in self._field_mapping_widgets}
            return [field["name"] for field in note_type_fields if field["name"] not in existing_mappings]

        row_layout = QVBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(2)  # Very minimal spacing

        # Top row with field name and delete button
        field_row = QWidget()
        field_layout = QHBoxLayout(field_row)
        field_layout.setContentsMargins(0, 0, 0, 0)

        # Create prompt variable input with consistent styling
        prompt_var_input = QComboBox()
        prompt_var_input.addItems(get_valid_field_names())

        prev_selection = None

        def select_field_name(_):
            nonlocal prev_selection
            selected_item = prompt_var_input.currentText()
            if selected_item == prev_selection:
                return
            for mapping in self._field_mapping_widgets:
                combo_box = mapping["prompt_var_input"]
                if combo_box == prompt_var_input:
                    continue
                combo_box.removeItem(combo_box.findText(selected_item))
                if prev_selection:
                    combo_box.addItem(prev_selection)
            prev_selection = selected_item

        prompt_var_input.currentIndexChanged.connect(select_field_name)
        prompt_var_input.setCurrentText(prompt_var)
        prompt_var_input.currentIndexChanged.connect(
            lambda: self._update_prompt_preview(),
        )

        # Create delete button with consistent styling
        delete_button = QPushButton("️❌")
        delete_button.setToolTip("Remove this field mapping")
        delete_button.setMinimumWidth(30)
        delete_button.setMaximumWidth(30)
        delete_button.setStyleSheet("padding: 2px;")

        # Add field name and delete button to top row
        field_layout.addWidget(prompt_var_input, 1)
        field_layout.addWidget(delete_button)

        # Add top row to main layout
        row_layout.addWidget(field_row)

        # Create description input with compact styling
        note_field_input = QPlainTextEdit()
        note_field_input.setPlaceholderText(
            "Description of what this field should contain",
        )
        note_field_input.setPlainText(note_field)
        # Connect text changed to update height
        note_field_input.textChanged.connect(self._update_prompt_preview)

        # Add description to main layout
        row_layout.addWidget(note_field_input)

        self._field_mappings_layout.addWidget(row_widget)

        mapping = {
            "widget": row_widget,
            "prompt_var_input": prompt_var_input,
            "note_field_input": note_field_input,
        }
        delete_button.clicked.connect(lambda: self._remove_specific_mapping(mapping))
        # Add to our tracking list
        self._field_mapping_widgets.append(mapping)

    def _remove_specific_mapping(self, mapping: dict[str, QWidget]) -> None:
        """Remove a specific field mapping row."""
        # Remove the widget from layout and delete it
        self._field_mappings_layout.removeWidget(mapping["widget"])
        # Add field name to all other field inputs
        for other in self._field_mapping_widgets:
            other["prompt_var_input"].addItem(mapping["prompt_var_input"].currentText())

        # Remove from our tracking list
        for idx, other in enumerate(self._field_mapping_widgets):
            if other == mapping:
                self._field_mapping_widgets.pop(idx)
                break

        mapping["widget"].setParent(None)
        mapping["widget"].deleteLater()
        self._update_prompt_preview()

    def _get_field_mappings_from_widgets(self) -> dict[str, str]:
        """Extract field mappings dictionary from widget list"""
        field_mappings = {}
        for mapping in self._field_mapping_widgets:
            prompt_var = mapping["prompt_var_input"].currentText().strip()
            note_field = mapping["note_field_input"].toPlainText().strip()
            if prompt_var and note_field:
                field_mappings[prompt_var] = note_field
        return field_mappings

    def _load_field_mappings(self, note_prompts: dict[str, Any]):
        """Load field mappings from a dictionary.

        Args:
            field_mappings: Dictionary mapping field names to descriptions
        """
        field_mappings = note_prompts.get("field_mappings", {})
        create_only_fields = note_prompts.get("create_only_fields", [])

        for mapping in list(self._field_mapping_widgets):
            self._remove_specific_mapping(mapping)

        # Add each mapping from the dictionary, skipping create-only fields
        for prompt_var, note_field in field_mappings.items():
            # Skip create-only fields in the template tab
            if prompt_var in create_only_fields:
                continue

            self._create_field_mapping_row(prompt_var=prompt_var, note_field=note_field)

        # Update the preview
        self._update_prompt_preview()

    def _update_current_note_type_config(self) -> None:
        """Update the configuration for the current note type"""
        if not self._template_initialised:
            return
        field_mappings = self._get_field_mappings_from_widgets()
        global_prompt = self._global_prompt_input.toPlainText()
        note_prompts = self._config_manager["note_prompts"]

        # Get existing config or create a new one
        note_type_config = note_prompts.get(self._current_note_type, {})

        # Preserve create-only fields by adding them back to field_mappings
        existing_field_mappings = note_type_config.get("field_mappings", {})
        create_only_fields = note_type_config.get("create_only_fields", [])

        # Add create-only fields back to the new field mappings
        for field in create_only_fields:
            if field in existing_field_mappings:
                field_mappings[field] = existing_field_mappings[field]

        # Update with new values
        note_type_config.update(
            {
                "update_prompt": global_prompt,
                "field_mappings": field_mappings,
            },
        )

        note_prompts[self._current_note_type] = note_type_config
        self._config_manager["note_prompts"] = note_prompts

    def _on_note_type_changed(self, _):
        """Handle when the note type selection changes."""
        # Save the current note type's configuration
        self._update_current_note_type_config()
        self._current_note_type = self._note_type_selector.currentData()
        if not self._current_note_type:
            return

        # Load the appropriate prompt and field mappings for this note type
        note_prompts = self._config_manager["note_prompts"].get(
            self._current_note_type,
            {},
        )

        self._global_prompt_input.setPlainText(note_prompts.get("update_prompt", ""))
        self._load_field_mappings(note_prompts)

        self._clear_preview_card()
        self._update_prompt_preview()
        self._template_initialised = True

    def _load_available_note_types(self):
        """Load available note types from Anki collection and add to selector."""
        # Clear existing card types except default
        self._note_type_selector.clear()

        # Get card types from config
        note_prompts = self._config_manager["note_prompts"]

        for note_type in list(note_prompts):
            self._note_type_selector.addItem(note_type, note_type)

        self._on_note_type_changed(0)

    def _add_new_note_type(self):
        """Add a new note type configuration by selecting an existing Anki note type."""
        # Only proceed if we have access to the Anki collection
        if not mw or not mw.col:
            showInfo("Cannot access Anki collection")
            return

        # Get all available note types from the collection
        all_note_types = mw.col.models.all_names()

        # Get current note types from config
        note_prompts = self._config_manager["note_prompts"]
        existing_types = set(note_prompts.keys())

        # Filter out already configured note types
        available_types = [nt for nt in all_note_types if nt not in existing_types]

        if not available_types:
            showInfo("All note types are already configured")
            return

        # Create a selection dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Note Type")
        layout = QVBoxLayout()

        # Create a combobox for note type selection
        combo_box = QComboBox()
        for note_type in available_types:
            combo_box.addItem(note_type, note_type)  # Store note type as user data
        layout.addWidget(combo_box)

        # Add OK/Cancel buttons
        button_box = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")

        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)

        button_box.addWidget(ok_button)
        button_box.addWidget(cancel_button)
        layout.addLayout(button_box)

        dialog.setLayout(layout)

        # Execute the dialog
        if dialog.exec():
            # Get the selected note type
            selected_note_type = combo_box.currentData()

            # Add the new note type to the selector
            self._note_type_selector.addItem(selected_note_type, selected_note_type)

            # Select the newly added note type
            new_index = self._note_type_selector.findData(selected_note_type)
            if new_index >= 0:
                self._note_type_selector.setCurrentIndex(new_index)

    def _remove_current_note_type(self):
        """Remove the currently selected note type."""
        current_note_type = self._current_note_type

        # Get note prompts
        note_prompts = self._config_manager["note_prompts"]

        # Remove the current note type from the config
        if current_note_type in note_prompts:
            del note_prompts[current_note_type]
            self._config_manager["note_prompts"] = note_prompts
        self._template_initialised = False

        # Remove from the selector
        current_index = self._note_type_selector.currentIndex()
        self._note_type_selector.removeItem(current_index)


class DebugDialog(QDialog):
    """Dialog for testing API calls."""

    def __init__(self, parent=None, initial_prompt=None):
        super().__init__(parent)
        self._config_manager = ConfigManager()
        self.setWindowTitle("LLM API Debug")
        self._layout = QVBoxLayout()

        # Set size
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        self._prompt_label = QLabel("Enter prompt:")
        self._layout.addWidget(self._prompt_label)

        self._prompt_input = QPlainTextEdit()
        self._prompt_input.setPlaceholderText(
            "Enter your prompt here (supports multiple lines)",
        )
        self._prompt_input.setMinimumHeight(150)  # Make it reasonably tall

        # Set the initial prompt if provided
        if initial_prompt:
            self._prompt_input.setPlainText(initial_prompt)

        self._layout.addWidget(self._prompt_input)

        self._output_label = QLabel("API Response:")
        self._layout.addWidget(self._output_label)

        self._output_display = QPlainTextEdit()
        self._output_display.setReadOnly(True)
        self._layout.addWidget(self._output_display)

        self._query_button = QPushButton("Query API")
        self._query_button.clicked.connect(self._query_api)
        self._layout.addWidget(self._query_button)

        # Add status label
        self._status_label = QLabel("")
        self._layout.addWidget(self._status_label)

        self.setLayout(self._layout)

        # Create thread pool for worker
        self._thread_pool = QThreadPool()

    def _query_api(self):
        # Get the prompt from the QTextEdit
        prompt = self._prompt_input.toPlainText()
        if not prompt.strip():
            self._output_display.setPlainText("Please enter a prompt.")
            return

        if not self._config_manager:
            self._output_display.setPlainText("No configuration found.")
            return

        client_name = self._config_manager["client"]

        # Get the API key and model using self._config_manager methods
        api_key = self._config_manager.get_api_key_for_client(client_name)
        model_name = self._config_manager.get_model_for_client(client_name)
        requests_per_minute = self._config_manager.get_requests_per_minute_for_client(client_name)
        tokens_per_minute = self._config_manager.get_tokens_per_minute_for_client(client_name)

        temperature = self._config_manager["temperature"]
        max_length = self._config_manager["max_length"]

        # Disable the query button and update status
        self._query_button.setEnabled(False)
        self._status_label.setText("Querying API...")

        # Create worker
        worker = DebugLLMWorker(
            client_name,
            api_key,
            model_name,
            temperature,
            max_length,
            prompt,
            requests_per_minute,
            tokens_per_minute,
        )

        # Connect signals
        worker.signals.result.connect(self._handle_response)
        worker.signals.error.connect(self._handle_error)
        worker.signals.finished.connect(lambda: self._query_button.setEnabled(True))

        # Start the worker
        self._thread_pool.start(worker)

    def _handle_response(self, response):
        """Handle the API response."""
        self._output_display.setPlainText(response)
        self._status_label.setText("Response received.")

    def _handle_error(self, error_msg):
        """Handle API errors."""
        self._output_display.setPlainText(f"Error querying API: {error_msg}")
        self._status_label.setText("Error occurred.")


class DebugWorkerSignals(QObject):
    """Signals for the debug worker."""

    result = pyqtSignal(str)
    error = pyqtSignal(str)
    finished = pyqtSignal()


class DebugLLMWorker(QRunnable):
    """Worker for making LLM API calls in the debug dialog."""

    def __init__(
        self,
        client_name,
        api_key,
        model_name,
        temperature,
        max_length,
        prompt,
        requests_per_minute,
        tokens_per_minute,
    ):
        super().__init__()
        self.client_name = client_name
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.max_length = max_length
        self.prompt = prompt
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self.signals = DebugWorkerSignals()

    def run(self):
        try:
            client_cls = LLMClient.get_client(self.client_name)
            client = client_cls(
                api_key=self.api_key,
                model=self.model_name,
                temperature=self.temperature,
                max_length=self.max_length,
                requests_per_minute=self.requests_per_minute,
                tokens_per_minute=self.tokens_per_minute,
            )

            response = client(self.prompt)
            self.signals.result.emit(response)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


class CardSelectDialog(QDialog):
    """Dialog for selecting a card for prompt preview."""

    def __init__(self, parent, note_type: str):
        super().__init__(parent)
        self._note_type = note_type
        self.setWindowTitle("Select Card for Preview")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)

        # Add deck selector
        deck_layout = QHBoxLayout()
        deck_layout.addWidget(QLabel("Deck:"))
        self.deck_selector = QComboBox()
        self.deck_selector.setMinimumWidth(300)
        self.populate_deck_selector()
        self.deck_selector.currentIndexChanged.connect(self.on_deck_changed)
        deck_layout.addWidget(self.deck_selector)
        layout.addLayout(deck_layout)

        # Search box
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Start typing to search...")
        search_layout.addWidget(self.search_input)

        # Create a timer for debouncing search input
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300)  # 300ms debounce time
        self.search_timer.timeout.connect(self.perform_search)

        # Connect text changes to start the timer
        self.search_input.textChanged.connect(self.on_search_text_changed)

        layout.addLayout(search_layout)

        # Results list
        self.results_list = QListWidget()
        self.results_list.setAlternatingRowColors(True)
        # Enable double-click to select
        self.results_list.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self.results_list)

        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # Buttons
        button_layout = QHBoxLayout()
        select_button = QPushButton("Select")
        select_button.clicked.connect(self.accept)
        button_layout.addWidget(select_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

        # Initialize with cards from the selected deck
        self.perform_search()

    def on_search_text_changed(self):
        """Handle search text changes with debouncing."""
        # Reset the timer each time the text changes
        self.search_timer.stop()
        self.search_timer.start()

    def populate_deck_selector(self):
        """Populate the deck selector with all available decks."""
        self.deck_selector.clear()

        # Add "All Decks" option
        self.deck_selector.addItem("All Decks", "")

        # Get all decks
        decks = mw.col.decks.all_names_and_ids()
        decks.sort(key=lambda x: x.name)

        # Add each deck to the selector
        for deck in decks:
            self.deck_selector.addItem(deck.name, deck.id)

    def on_deck_changed(self):
        """Update the search when the deck selection changes."""
        self.perform_search()

    def perform_search(self):
        """Search for cards based on the query and selected deck."""
        # Get the base query from the search input
        base_query = self.search_input.text().strip()

        base_query = f'"note:{self._note_type}" {base_query}'

        # Get the selected deck ID and name
        deck_id = self.deck_selector.currentData()
        deck_name = self.deck_selector.currentText()

        # Build the query
        if deck_id and deck_name != "All Decks":
            # Use deck:DeckName format without quotes (which can cause issues)
            query = f'"deck:{deck_name}"'
            if base_query:
                query += f" {base_query}"
        else:
            # Use the base query for all decks
            query = base_query or "added:30"  # Default to recent cards if no query

        try:
            self.status_label.setText(f"Searching with query: {query}")
            card_ids = mw.col.find_cards(query)
            self.results_list.clear()

            if not card_ids:
                self.status_label.setText(
                    f"No cards found matching your criteria. Query: {query}",
                )
                return

            # Limit to 100 cards for performance
            displayed_cards = card_ids[:100]
            if len(card_ids) > 100:
                self.status_label.setText(
                    f"Found {len(card_ids)} cards (showing first 100)",
                )
            else:
                self.status_label.setText(f"Found {len(card_ids)} cards")

            # Add cards to the list
            for card_id in displayed_cards:
                card = mw.col.get_card(card_id)
                note = card.note()
                note_type = note.note_type()["name"]
                deck_name = mw.col.decks.name(card.did)

                # Get the first field content
                first_field = note.fields[0]
                if len(first_field) > 60:
                    first_field = first_field[:57] + "..."

                # Include deck name in the display if "All Decks" is selected
                if not deck_id:
                    display_text = f"{deck_name} - {note_type}: {first_field}"
                else:
                    display_text = f"{note_type}: {first_field}"

                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, note.id)
                self.results_list.addItem(item)

        except Exception as e:
            self.status_label.setText(f"Error searching: {str(e)}")

    def get_selected_note_id(self):
        """Return the ID of the selected note."""
        current_item = self.results_list.currentItem()
        if current_item:
            return current_item.data(Qt.ItemDataRole.UserRole)
        return None


def open_config_dialog():
    dialog = ConfigDialog()
    dialog.exec()


class ModelFetchWorkerSignals(QObject):
    """Signals for the model fetching worker."""

    result = pyqtSignal(list)
    error = pyqtSignal(str)
    finished = pyqtSignal()


class ModelFetchWorker(QRunnable):
    """Worker for fetching model list from API."""

    def __init__(self, client_name, client_cls, api_key):
        super().__init__()
        self.client_name = client_name
        self.client_cls = client_cls
        self.api_key = api_key
        self.signals = ModelFetchWorkerSignals()

    def run(self):
        # Set up a timeout for network operations
        original_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(5.0)  # 5 second timeout

        try:
            # Get models (returns a list of dicts with name and vision keys)
            models = self.client_cls.get_available_models()
            self.signals.result.emit(models)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            # Restore original timeout
            socket.setdefaulttimeout(original_timeout)
            self.signals.finished.emit()
