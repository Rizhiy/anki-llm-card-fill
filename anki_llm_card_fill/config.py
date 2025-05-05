import socket
import threading
from collections import defaultdict

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
    QPushButton,
    QRunnable,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QThreadPool,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)
from aqt.utils import showInfo
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence

from .config_manager import config_manager
from .llm import LLMClient
from .utils import construct_prompt, parse_field_mappings


class ConfigDialog(QDialog):
    # Class-level lock to prevent multiple model update operations
    _model_update_lock = threading.Lock()

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

        # Model selection
        self._model_label = QLabel("Select Model:")
        self._model_selector = QComboBox()
        self._general_layout.addRow(self._model_label, self._model_selector)

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
        self._max_prompt_tokens_label.setToolTip("Limit the maximum length of prompts to avoid excessive token usage")
        self._max_prompt_tokens_input = QSpinBox()
        self._max_prompt_tokens_input.setRange(1, 4096)
        self._params_layout.addRow(self._max_prompt_tokens_label, self._max_prompt_tokens_input)

        self._tab_widget.addTab(self._params_tab, "Request Parameters")

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

        # Add HTML to Markdown conversion note
        self._html_md_note = QLabel(
            "<b>Note:</b> Basic HTML tags in card fields are automatically converted to Markdown "
            "format when inserted into prompts. Stuff like bold, italic, lists, etc. "
            "You can use preview below to see the converted markdown, by selecting a card.",
        )
        self._html_md_note.setWordWrap(True)
        self._html_md_note.setStyleSheet(
            "color: #555; font-size: 11px; background-color: #f8f8f8; padding: 5px; border-radius: 3px;",
        )
        self._templates_layout.addWidget(self._html_md_note)

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
        self._field_description_note = QLabel(
            "<b>Field Descriptions Format:</b><br>"
            "Specify fields using the format:<br>"
            "<code>&lt;field name&gt;: &lt;description for the field&gt;</code>, one per line.<br>"
            "Example:<br>"
            "<code>Definition: A definition of the concept</code><br>"
            "<code>Mnemonic: A memory aid for remembering this concept</code>",
        )
        self._field_description_note.setWordWrap(True)
        self._templates_layout.addWidget(self._field_description_note)
        self._templates_layout.addWidget(self._field_mappings_label)

        self._field_mappings_input = QTextEdit()
        self._field_mappings_input.setPlaceholderText(
            "Example: A practical example of the concept\nMnemonic: A memory aid for remembering this concept",
        )
        self._field_mappings_input.setFixedHeight(80)
        self._templates_layout.addWidget(self._field_mappings_input)

        # Preview section with controls for card selection
        preview_header = QWidget()
        preview_layout = QHBoxLayout(preview_header)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        self._preview_label = QLabel("Prompt Preview:")
        preview_layout.addWidget(self._preview_label, 1)

        # Add select card button
        self._select_card_button = QPushButton("Select Card for Preview")
        self._select_card_button.clicked.connect(self._select_card_for_preview)
        preview_layout.addWidget(self._select_card_button)

        # Add clear selection button
        self._clear_card_button = QPushButton("Use Placeholders")
        self._clear_card_button.clicked.connect(self._clear_preview_card)
        self._clear_card_button.setEnabled(False)  # Initially disabled
        preview_layout.addWidget(self._clear_card_button)

        self._templates_layout.addWidget(preview_header)

        # Add card info label
        self._card_info_label = QLabel("Using placeholder values for preview")
        self._card_info_label.setStyleSheet("font-style: italic;")
        self._templates_layout.addWidget(self._card_info_label)

        # Add token count display
        self._token_count_label = QLabel("")
        self._token_count_label.setStyleSheet("font-weight: bold;")
        self._templates_layout.addWidget(self._token_count_label)

        self._preview_output = QTextEdit()
        self._preview_output.setReadOnly(True)
        self._preview_output.setText("")
        self._templates_layout.addWidget(self._preview_output)

        # Connect signals to update preview
        self._global_prompt_input.textChanged.connect(self._update_prompt_preview)
        self._field_mappings_input.textChanged.connect(self._update_prompt_preview)
        self._max_prompt_tokens_input.valueChanged.connect(self._update_prompt_preview)

        self._tab_widget.addTab(self._templates_tab, "Templates")

        # Initialize selected card variable
        self._selected_note = None

    def _open_debug_dialog(self):
        """Open the debug dialog with the current preview text."""
        # Pass this instance as parent and the preview text as initial_prompt
        dialog = DebugDialog(self, initial_prompt=self._preview_output.toPlainText())
        dialog.exec()

    @staticmethod
    def _shorten_key(key: str) -> str:
        return f"{key[:3]}...{key[-3:]}"

    def _load_existing_config(self):
        # Use config_manager directly as a dictionary
        if not config_manager:
            return

        # Set client and model
        client_name = config_manager["client"]

        # Set model parameters
        temperature = config_manager["temperature"]
        max_length = config_manager["max_length"]
        max_prompt_tokens = config_manager["max_prompt_tokens"]

        self._client_selector.setCurrentText(client_name)
        self._temperature_input.setValue(temperature)
        self._max_length_input.setValue(max_length)
        self._max_prompt_tokens_input.setValue(max_prompt_tokens)

        # Get API key for the current client
        api_key = config_manager.get_api_key_for_client(client_name)
        if api_key:
            self._api_key_input.setText(self._shorten_key(api_key))

        # Get model for current client
        client_model = config_manager.get_model_for_client(client_name)

        # Set model after API key is loaded
        self._model_selector.setCurrentText(client_model)

        # Load template data
        global_prompt = config_manager.get("global_prompt", "")
        field_mappings = config_manager.get("field_mappings", "")

        self._global_prompt_input.setText(global_prompt)
        self._field_mappings_input.setText(field_mappings)

        # Update the prompt preview
        self._update_prompt_preview()

        # Load shortcut
        shortcut = config_manager["shortcut"]
        self._shortcut_input.setText(shortcut)

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
                api_key = config_manager.get_api_key_for_client(client_name)

            # Show loading state
            self._model_selector.clear()

            if not api_key:
                # No API key provided - show a message
                self._model_selector.addItem(f"Enter {client_name} API key to see models")
                self._model_selector.setEnabled(False)
                return

            # API key provided - try to fetch models
            self._model_selector.addItem("Loading models...")
            self._model_selector.setEnabled(False)
            # Check if we're already updating models
            if not ConfigDialog._model_update_lock.acquire(blocking=False):
                # Another thread is already updating models, so we'll just return
                return

            # Create and start worker
            worker = ModelFetchWorker(client_name, client_cls, api_key)
            worker.signals.result.connect(self._on_models_loaded)
            worker.signals.error.connect(self._on_models_error)
            worker.signals.finished.connect(lambda: ConfigDialog._model_update_lock.release())

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

        if not models:
            self._model_selector.addItem("No models available")
            return

        self._model_selector.addItems(models)

        # Restore previous selection if possible
        client_name = self._client_selector.currentText()
        previous_model = config_manager.get_model_for_client(client_name)

        if previous_model:
            index = self._model_selector.findText(previous_model)
            if index >= 0:
                self._model_selector.setCurrentIndex(index)

    def _on_models_error(self, error_msg):
        """Handle errors during model loading."""
        self._model_selector.clear()
        self._model_selector.addItem("Error loading models")
        self._model_selector.setEnabled(False)  # Disable the model selector

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

    def _on_client_changed(self, _):
        """Handle client selection changes."""
        # Get the newly selected client
        client_name = self._client_selector.currentText()
        client_cls = LLMClient.get_client(client_name)

        # Update API key link
        api_key_link = client_cls.get_api_key_link()
        self._api_key_link.setText(f'<a href="{api_key_link}">Get your {client_name} API key</a>')

        # Get API key for the new client
        api_key = config_manager.get_api_key_for_client(client_name)

        # Update the API key field if we have a key for this client
        if api_key:
            self._api_key_input.setText(self._shorten_key(api_key))

        # Update the model list for the new client
        self._update_model_list()

    def _on_api_key_changed(self, _):
        """Handle API key changes."""
        self._update_model_list()

    def _save_config(self):
        client_name = self._client_selector.currentText()
        model_name = self._model_selector.currentText()
        api_key = self._api_key_input.text()
        temperature = self._temperature_input.value()
        max_length = self._max_length_input.value()
        max_prompt_tokens = self._max_prompt_tokens_input.value()

        # Keep using .get() for user collections
        api_keys = config_manager.get("api_keys", {})
        models = config_manager.get("models", {})

        # If current key input is the shortened version, get the actual key
        if api_key and "..." in api_key:
            # Use config_manager's method to get the full key
            api_key = config_manager.get_api_key_for_client(client_name)

        # Update the API key for the current client
        api_keys[client_name] = api_key

        # Save the current model for this client
        if model_name:
            models[client_name] = model_name

        global_prompt = self._global_prompt_input.toPlainText()
        field_mappings = self._field_mappings_input.toPlainText()
        shortcut = self._shortcut_input.text()

        # Check for shortcut conflicts
        if QKeySequence(shortcut).isEmpty():
            showInfo("Invalid shortcut. Please enter a valid shortcut.")
            return

        # Update the config with all values
        config_manager.update(
            {
                "client": client_name,
                "api_keys": api_keys,  # Store keys per client
                "models": models,  # Store models per client
                "temperature": temperature,
                "max_length": max_length,
                "max_prompt_tokens": max_prompt_tokens,
                "global_prompt": global_prompt,
                "field_mappings": field_mappings,
                "shortcut": shortcut,
            },
        )

        # Save the updated configuration using the config manager
        config_manager.save_config()
        showInfo("Configuration saved!")

    def _update_prompt_preview(self):
        """Update the prompt preview based on current template and field mappings."""
        global_prompt = self._global_prompt_input.toPlainText()
        field_mappings_text = self._field_mappings_input.toPlainText()

        if not global_prompt and not field_mappings_text:
            self._preview_output.setText("")
            self._token_count_label.setText("")
            return

        # Parse field mappings
        field_mappings = parse_field_mappings(field_mappings_text)

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

        # Use the same construct_prompt function that's used for actual LLM calls
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
        self._preview_output.setText(preview)

    def _select_card_for_preview(self):
        """Open a dialog to select a card for the preview."""
        # Create and show the selection dialog
        dialog = CardSelectDialog(self)

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

                self._card_info_label.setText(f"Using selected card: {note_type} - {first_field_content}")
                self._clear_card_button.setEnabled(True)

                # Update the preview with the selected card's data
                self._update_prompt_preview()

    def _clear_preview_card(self):
        """Clear the selected card and use placeholders instead."""
        self._selected_note = None
        self._card_info_label.setText("Using placeholder values for preview")
        self._clear_card_button.setEnabled(False)
        self._update_prompt_preview()


class DebugDialog(QDialog):
    """Dialog for testing API calls."""

    def __init__(self, parent=None, initial_prompt=None):
        super().__init__(parent)
        self.setWindowTitle("LLM API Debug")
        self._layout = QVBoxLayout()

        # Set size
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        self._prompt_label = QLabel("Enter prompt:")
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
            self._output_display.setText("Please enter a prompt.")
            return

        if not config_manager:
            self._output_display.setText("No configuration found.")
            return

        client_name = config_manager["client"]

        # Get the API key and model using config_manager methods
        api_key = config_manager.get_api_key_for_client(client_name)
        model_name = config_manager.get_model_for_client(client_name)

        temperature = config_manager["temperature"]
        max_length = config_manager["max_length"]

        # Disable the query button and update status
        self._query_button.setEnabled(False)
        self._status_label.setText("Querying API...")
        self._output_display.setText("Waiting for response...")

        # Create worker
        worker = DebugLLMWorker(client_name, api_key, model_name, temperature, max_length, prompt)

        # Connect signals
        worker.signals.result.connect(self._handle_response)
        worker.signals.error.connect(self._handle_error)
        worker.signals.finished.connect(lambda: self._query_button.setEnabled(True))

        # Start the worker
        self._thread_pool.start(worker)

    def _handle_response(self, response):
        """Handle the API response."""
        self._output_display.setText(response)
        self._status_label.setText("Response received.")

    def _handle_error(self, error_msg):
        """Handle API errors."""
        self._output_display.setText(f"Error querying API: {error_msg}")
        self._status_label.setText("Error occurred.")


class DebugWorkerSignals(QObject):
    """Signals for the debug worker."""

    result = pyqtSignal(str)
    error = pyqtSignal(str)
    finished = pyqtSignal()


class DebugLLMWorker(QRunnable):
    """Worker for making LLM API calls in the debug dialog."""

    def __init__(self, client_name, api_key, model_name, temperature, max_length, prompt):
        super().__init__()
        self.client_name = client_name
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.max_length = max_length
        self.prompt = prompt
        self.signals = DebugWorkerSignals()

    def run(self):
        try:
            client_cls = LLMClient.get_client(self.client_name)
            client = client_cls(
                api_key=self.api_key,
                model=self.model_name,
                temperature=self.temperature,
                max_length=self.max_length,
            )

            response = client(self.prompt)
            self.signals.result.emit(response)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


class CardSelectDialog(QDialog):
    """Dialog for selecting a card for prompt preview."""

    def __init__(self, parent=None):
        super().__init__(parent)
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
                self.status_label.setText(f"No cards found matching your criteria. Query: {query}")
                return

            # Limit to 100 cards for performance
            displayed_cards = card_ids[:100]
            if len(card_ids) > 100:
                self.status_label.setText(f"Found {len(card_ids)} cards (showing first 100)")
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
            models = self.client_cls.get_available_models(self.api_key)
            self.signals.result.emit(models)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            # Restore original timeout
            socket.setdefaulttimeout(original_timeout)
            self.signals.finished.emit()
