import logging

from aqt import mw
from aqt.qt import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from aqt.utils import showInfo, tooltip

from .card_updater import estimate_token_count
from .config import DebugDialog
from .config_manager import ConfigManager
from .llm import LLMClient
from .utils import construct_prompt, parse_llm_response

logger = logging.getLogger()


class CardCreationDialog(QDialog):
    """Dialog for creating new cards using LLM."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config_manager = ConfigManager()
        self.setWindowTitle("Create New Card with LLM")

        self.setMinimumWidth(800)
        self.setMinimumHeight(700)
        self.setSizeGripEnabled(True)

        self._layout = QVBoxLayout()

        self._setup_selection_area()
        self._setup_content_area()
        self._setup_actions_area()

        self.setLayout(self._layout)

        self._deck_loaded = False

        self._load_available_note_types()
        self._load_available_decks()
        self._on_note_type_changed(0)

    def _setup_selection_area(self):
        """Setup area for selecting note type and deck."""
        selection_widget = QWidget()
        selection_layout = QHBoxLayout(selection_widget)

        note_type_layout = QFormLayout()
        self._note_type_label = QLabel("Note Type:")
        self._note_type_selector = QComboBox()
        self._note_type_selector.currentIndexChanged.connect(self._on_note_type_changed)
        note_type_layout.addRow(self._note_type_label, self._note_type_selector)
        selection_layout.addLayout(note_type_layout)

        deck_layout = QFormLayout()
        self._deck_label = QLabel("Deck:")
        self._deck_selector = QComboBox()
        self._deck_selector.currentIndexChanged.connect(self._on_deck_changed)
        deck_layout.addRow(self._deck_label, self._deck_selector)
        selection_layout.addLayout(deck_layout)

        self._layout.addWidget(selection_widget)

    def _setup_content_area(self):
        """Setup two-column layout for input/template and field mappings."""
        content_widget = QWidget()
        main_layout = QHBoxLayout(content_widget)

        left_column = QVBoxLayout()
        self._setup_user_input_area(left_column)

        self._global_prompt_label = QLabel("Prompt Template")
        self._global_prompt_label.setStyleSheet("font-weight: bold;")
        left_column.addWidget(self._global_prompt_label)

        self._prompt_input = QPlainTextEdit()
        self._prompt_input.setPlaceholderText(
            "Enter your prompt template here. Use {__input__} to reference user input.\n\n"
            "Example: Generate content based on this input: '{__input__}'",
        )
        self._prompt_input.textChanged.connect(self._update_token_count)
        left_column.addWidget(self._prompt_input)

        self._token_count_label = QLabel("")
        self._token_count_label.setStyleSheet("font-weight: bold;")
        left_column.addWidget(self._token_count_label)

        input_info = QLabel(
            "<b>Note:</b> Your input text is automatically available in the prompt using the special "
            "<code>{__input__}</code> placeholder.",
        )
        input_info.setWordWrap(True)
        input_info.setStyleSheet(
            "color: #555555; font-size: 11px; background-color: #f8f8f8; padding: 5px; border-radius: 3px;",
        )
        left_column.addWidget(input_info)

        right_column = QVBoxLayout()

        self._field_mappings_label = QLabel("Fields to Generate")
        self._field_mappings_label.setStyleSheet("font-weight: bold;")
        right_column.addWidget(self._field_mappings_label)

        # Add create-only fields explanation
        create_only_info = QLabel(
            "Fields added here will only be available during card creation, and won't appear "
            "in the template editor. Use this for fields that should only be set when initially "
            "creating cards.",
        )
        create_only_info.setWordWrap(True)
        create_only_info.setStyleSheet(
            "color: #555555; font-size: 11px; background-color: #f8f8f8; padding: 5px; border-radius: 3px;",
        )
        right_column.addWidget(create_only_info)

        field_mappings_widget = QWidget()
        self._field_mappings_layout = QVBoxLayout(field_mappings_widget)
        self._field_mappings_layout.setContentsMargins(0, 0, 0, 0)
        self._field_mappings_layout.setSpacing(8)
        right_column.addWidget(field_mappings_widget, 1)

        self._add_mapping_button = QPushButton("Add Field")
        self._add_mapping_button.clicked.connect(self._add_new_create_only_field)
        right_column.addWidget(self._add_mapping_button)

        main_layout.addLayout(left_column, 3)
        main_layout.addLayout(right_column, 2)

        self._layout.addWidget(content_widget)

        self._field_mapping_widgets = []

    def _setup_user_input_area(self, parent_layout):
        """Setup area for user input."""
        self._input_label = QLabel("Enter your input:")
        self._input_label.setStyleSheet("font-weight: bold;")
        parent_layout.addWidget(self._input_label)

        self._user_input = QPlainTextEdit()
        self._user_input.setPlaceholderText(
            "Enter text that will be used to generate the card...",
        )
        self._user_input.setMinimumHeight(100)
        self._user_input.textChanged.connect(self._update_token_count)
        parent_layout.addWidget(self._user_input)

    def _setup_actions_area(self):
        """Setup buttons for actions."""
        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)

        self._debug_button = QPushButton("Debug")
        self._debug_button.setToolTip("Test the prompt with the LLM")
        self._debug_button.clicked.connect(self._open_debug_dialog)
        actions_layout.addWidget(self._debug_button)

        # Add Save Config button
        self._save_config_button = QPushButton("Save Config")
        self._save_config_button.setToolTip(
            "Save the current prompt and fields without creating a card",
        )
        self._save_config_button.clicked.connect(self._save_config)
        actions_layout.addWidget(self._save_config_button)

        actions_layout.addStretch(1)

        self._preview_button = QPushButton("Preview")
        self._preview_button.clicked.connect(self._preview_prompt)
        actions_layout.addWidget(self._preview_button)

        self._create_button = QPushButton("Create Card")
        self._create_button.clicked.connect(self._create_card)
        actions_layout.addWidget(self._create_button)

        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.clicked.connect(self.reject)
        actions_layout.addWidget(self._cancel_button)

        self._layout.addWidget(actions_widget)

    def _open_debug_dialog(self):
        """Open the debug dialog with the current preview text."""
        user_input = self._user_input.toPlainText()
        if not user_input:
            showInfo("Please enter some input text first.")
            return

        global_prompt = self._prompt_input.toPlainText()
        field_mappings = self._get_field_mappings_from_widgets()
        card_fields = {"__input__": user_input}

        preview = construct_prompt(global_prompt, field_mappings, card_fields)

        dialog = DebugDialog(self, initial_prompt=preview)
        dialog.exec()

    def _load_available_note_types(self):
        """Load available note types from Anki collection."""
        self._note_type_selector.clear()

        note_prompts = self._config_manager["note_prompts"]

        for note_type in note_prompts:
            self._note_type_selector.addItem(note_type, note_type)

        if self._note_type_selector.count() > 0:
            self._note_type_selector.setCurrentIndex(0)

    def _load_available_decks(self):
        """Load available decks from Anki collection."""
        self._deck_selector.clear()

        decks = mw.col.decks.all_names_and_ids()
        decks.sort(key=lambda x: x.name)

        for deck in decks:
            self._deck_selector.addItem(deck.name, deck.id)

    def _on_deck_changed(self, _):
        """Save preferred deck when deck selection changes."""
        if not self._deck_loaded:
            return

        note_type = self._note_type_selector.currentText()
        deck_name = self._deck_selector.currentText()

        if note_type and deck_name:
            self._config_manager.set_preferred_deck_name(note_type, deck_name)

    def _on_note_type_changed(self, _):
        """Handle when the note type selection changes."""
        self._current_note_type = self._note_type_selector.currentData()
        if not self._current_note_type:
            return

        note_prompts = self._config_manager["note_prompts"]
        note_type_config = note_prompts.get(self._current_note_type, {})

        self._prompt_input.setPlainText(
            note_type_config.get("create_prompt", ""),
        )
        self._load_all_field_mappings(note_type_config)
        self._update_add_field_button_state()
        self._update_token_count()

        self._deck_loaded = False
        if preferred_deck_name := self._config_manager.get_preferred_deck_name(
            self._current_note_type,
        ):
            for i in range(self._deck_selector.count()):
                if self._deck_selector.itemText(i) == preferred_deck_name:
                    self._deck_selector.setCurrentIndex(i)
                    self._deck_loaded = True
                    break

    def _load_all_field_mappings(self, _):
        """Load both regular and create-only field mappings."""
        # Clear existing mappings
        for mapping in list(self._field_mapping_widgets):
            self._remove_specific_mapping(mapping)

        # Get field mappings and create-only fields
        field_mappings = self._config_manager.get_field_mappings_for_note_type(
            self._current_note_type,
        )
        create_only_fields = self._config_manager.get_create_only_fields(
            self._current_note_type,
        )

        # Load regular field mappings
        for prompt_var, note_field in field_mappings.items():
            # Skip if this is a create-only field (it will be added below)
            if prompt_var not in create_only_fields:
                self._create_field_mapping_row(
                    prompt_var=prompt_var,
                    note_field=note_field,
                )

        # Also load create-only field mappings if they exist
        for field_name in create_only_fields:
            if field_name in field_mappings:
                self._create_field_mapping_row(
                    prompt_var=field_name,
                    note_field=field_mappings[field_name],
                    is_create_only=True,
                )

    def _create_field_mapping_row(
        self,
        *,
        prompt_var="",
        note_field="",
        is_create_only=False,
    ):
        """Create a row for field mapping with delete button."""
        row_widget = QWidget()

        def get_valid_field_names() -> list[str]:
            # Get all field names from note type
            note_type_fields = mw.col.models.by_name(self._current_note_type)["flds"]
            all_fields = [field["name"] for field in note_type_fields]
            existing_mappings = {mapping["prompt_var_input"].currentText() for mapping in self._field_mapping_widgets}
            return [field for field in all_fields if field not in existing_mappings]

        row_layout = QVBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(2)

        field_row = QWidget()
        field_layout = QHBoxLayout(field_row)
        field_layout.setContentsMargins(0, 0, 0, 0)

        prompt_var_input = QComboBox()
        valid_fields = get_valid_field_names()
        prompt_var_input.addItems(valid_fields)

        # If we have a specific field to select and it's in the list, select it
        if prompt_var and prompt_var in valid_fields:
            prompt_var_input.setCurrentText(prompt_var)
        # Otherwise select first item if available
        elif valid_fields:
            prompt_var_input.setCurrentIndex(0)

        field_layout.addWidget(prompt_var_input, 1)

        # Add a label to indicate status
        if is_create_only:
            create_only_label = QLabel("Create Only")
            create_only_label.setStyleSheet("color: #808080; font-style: italic;")
            field_layout.addWidget(create_only_label)
        else:
            # For non-create-only fields, add a label indicating they're from template
            template_label = QLabel("From Template")
            template_label.setStyleSheet("color: #808080; font-style: italic;")
            field_layout.addWidget(template_label)

        delete_button = QPushButton("️❌")
        delete_button.setToolTip("Remove this field mapping")
        delete_button.setMinimumWidth(30)
        delete_button.setMaximumWidth(30)
        delete_button.setStyleSheet("padding: 2px;")
        field_layout.addWidget(delete_button)

        row_layout.addWidget(field_row)

        note_field_input = QPlainTextEdit()
        note_field_input.setPlaceholderText(
            "Description of what this field should contain",
        )
        note_field_input.setPlainText(note_field)
        row_layout.addWidget(note_field_input)

        # Make non-create-only fields non-editable
        if not is_create_only:
            # Disable field name selection
            prompt_var_input.setEnabled(False)
            # Disable delete button
            delete_button.setEnabled(False)
            # Make text field read-only
            note_field_input.setReadOnly(True)
            # Change background to indicate read-only state
            note_field_input.setStyleSheet("background-color: #f5f5f5;")
        else:
            # For create-only fields, connect to token count update
            note_field_input.textChanged.connect(self._update_token_count)
            prompt_var_input.currentIndexChanged.connect(
                lambda: self._update_token_count(),
            )

        self._field_mappings_layout.addWidget(row_widget)

        mapping = {
            "widget": row_widget,
            "prompt_var_input": prompt_var_input,
            "note_field_input": note_field_input,
            "is_create_only": is_create_only,
            "delete_button": delete_button,
        }

        delete_button.clicked.connect(lambda: self._remove_specific_mapping(mapping))
        self._field_mapping_widgets.append(mapping)

    def _remove_specific_mapping(self, mapping: dict[str, QWidget]) -> None:
        """Remove a specific field mapping row."""
        self._field_mappings_layout.removeWidget(mapping["widget"])

        for idx, other in enumerate(self._field_mapping_widgets):
            if other == mapping:
                self._field_mapping_widgets.pop(idx)
                break

        mapping["widget"].setParent(None)
        mapping["widget"].deleteLater()

        # Update Add Field button state after removing a field
        self._update_add_field_button_state()

        # Update token count since field mappings have changed
        self._update_token_count()

    def _get_field_mappings_from_widgets(self) -> dict[str, str]:
        """Extract field mappings dictionary from widget list."""
        field_mappings = {}
        for mapping in self._field_mapping_widgets:
            prompt_var = mapping["prompt_var_input"].currentText().strip()
            note_field = mapping["note_field_input"].toPlainText().strip()
            if prompt_var and note_field:
                field_mappings[prompt_var] = note_field

        return field_mappings

    def _get_create_only_mappings_from_widgets(self) -> dict[str, str]:
        """Extract only the create-only field mappings that user can edit."""
        field_mappings = {}
        for mapping in self._field_mapping_widgets:
            if mapping["is_create_only"]:
                prompt_var = mapping["prompt_var_input"].currentText().strip()
                note_field = mapping["note_field_input"].toPlainText().strip()
                if prompt_var and note_field:
                    field_mappings[prompt_var] = note_field

        return field_mappings

    def _preview_prompt(self):
        """Preview the prompt that will be sent to the LLM."""
        global_prompt = self._prompt_input.toPlainText()
        field_mappings = self._get_field_mappings_from_widgets()
        user_input = self._user_input.toPlainText()

        if not global_prompt or not user_input:
            showInfo("Please enter both a prompt template and input text.")
            return

        # Update token count (this will calculate the prompt)
        self._update_token_count()

        # Get the constructed prompt
        card_fields = {"__input__": user_input}
        preview = construct_prompt(global_prompt, field_mappings, card_fields)

        # Show preview in a dialog
        preview_dialog = QDialog(self)
        preview_dialog.setWindowTitle("Prompt Preview")
        preview_layout = QVBoxLayout(preview_dialog)

        # Get token count from the existing label
        token_info = QLabel(self._token_count_label.text())
        preview_layout.addWidget(token_info)

        # Preview text
        preview_text = QPlainTextEdit()
        preview_text.setPlainText(preview)
        preview_text.setReadOnly(True)
        preview_layout.addWidget(preview_text)

        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(preview_dialog.accept)
        preview_layout.addWidget(close_button)

        preview_dialog.setMinimumWidth(600)
        preview_dialog.setMinimumHeight(400)
        preview_dialog.exec()

    def _create_card(self):
        """Create a new card using the LLM."""
        note_type_name = self._note_type_selector.currentText()
        deck_id = self._deck_selector.currentData()

        user_input = self._user_input.toPlainText()
        if not user_input.strip():
            showInfo("Please enter input text.")
            return

        global_prompt = self._prompt_input.toPlainText()
        field_mappings = self._get_field_mappings_from_widgets()

        if not global_prompt or not field_mappings:
            showInfo("Please set up prompt template and field mappings.")
            return

        card_fields = {"__input__": user_input}

        prompt = construct_prompt(global_prompt, field_mappings, card_fields)

        estimated_tokens = estimate_token_count(prompt)
        max_tokens = self._config_manager["max_prompt_tokens"]

        if estimated_tokens > max_tokens:
            showInfo(
                f"Prompt exceeds maximum token limit. Estimated tokens: {estimated_tokens}, Max: {max_tokens}",
            )
            return

        client_name = self._config_manager["client"]
        model_name = self._config_manager.get_model_for_client(client_name)
        api_key = self._config_manager.get_api_key_for_client(client_name)
        temperature = self._config_manager["temperature"]
        max_length = self._config_manager["max_length"]

        client_cls = LLMClient.get_client(client_name)

        try:
            client = client_cls(
                model=model_name,
                temperature=temperature,
                max_length=max_length,
                api_key=api_key,
            )

            tooltip("Calling LLM...")

            response = client(prompt)

            field_updates = parse_llm_response(response)

            if "error" in field_updates:
                showInfo(f"Error parsing response: {field_updates['error']}")
                return

            note = mw.col.new_note(mw.col.models.by_name(note_type_name))

            for field_name, content in field_updates.items():
                if field_name in note:
                    note[field_name] = content

            # Ensure first field has content if it's empty
            first_field = note.keys()[0] if note.keys() else None
            if first_field and not note[first_field]:
                note[first_field] = user_input

            mw.col.add_note(note, deck_id)
            mw.col.save()

            # Use tooltip instead of showInfo and keep dialog open
            tooltip("Card created successfully!", period=3000)  # Show for 3 seconds

            # Clear the input field for the next card
            self._user_input.clear()
            self._user_input.setFocus()

            # Clear token count label since input is cleared
            self._token_count_label.setText("")

        except Exception as e:
            logger.exception("Error creating card")
            showInfo(f"Error creating card: {str(e)}")

    def _save_config(self):
        """Save the creation configuration to the config."""
        # Get the note type config
        note_type_name = self._note_type_selector.currentText()
        create_prompt = self._prompt_input.toPlainText()
        note_config = self._config_manager.get_note_type_config(note_type_name)

        note_config["create_prompt"] = create_prompt
        note_config["preferred_deck_name"] = self._deck_selector.currentText()

        # Get currently displayed create-only fields (both existing and new)
        current_create_only_fields = []
        for mapping in self._field_mapping_widgets:
            if mapping["is_create_only"]:
                field_name = mapping["prompt_var_input"].currentText().strip()
                if field_name:
                    current_create_only_fields.append(field_name)

        note_config["create_only_fields"] = current_create_only_fields
        existing_mappings = note_config.get("field_mappings", {}).copy()

        for mapping in self._field_mapping_widgets:
            if mapping["is_create_only"]:
                field_name = mapping["prompt_var_input"].currentText().strip()
                field_desc = mapping["note_field_input"].toPlainText().strip()
                if field_name and field_desc:
                    existing_mappings[field_name] = field_desc

        note_config["field_mappings"] = existing_mappings

        self._config_manager.set_note_type_config(note_type_name, note_config)
        self._config_manager.save_config()

    def _add_new_create_only_field(self):
        """Add a new create-only field to the mapping."""
        # Check if there are any fields available to add
        note_type_fields = mw.col.models.by_name(self._current_note_type)["flds"]
        all_fields = {field["name"] for field in note_type_fields}

        # Get fields already in use (both template and create-only)
        field_mappings = self._config_manager.get_field_mappings_for_note_type(
            self._current_note_type,
        )

        available_fields = [field for field in all_fields if field not in field_mappings]

        if not available_fields:
            # No more fields available
            showInfo("All available fields have been used. You cannot add more fields.")
            return

        self._create_field_mapping_row(is_create_only=True)

        # Check if there are any more fields available and update button state
        self._update_add_field_button_state()

    def _update_add_field_button_state(self):
        """Enable or disable the Add Field button based on available fields."""
        # Get all field names from note type
        note_type_fields = mw.col.models.by_name(self._current_note_type)["flds"]
        all_fields = {field["name"] for field in note_type_fields}

        # Get fields already in use
        field_mappings = self._config_manager.get_field_mappings_for_note_type(
            self._current_note_type,
        )
        used_fields = set(field_mappings.keys())

        # Add fields currently in the UI
        for mapping in self._field_mapping_widgets:
            field_name = mapping["prompt_var_input"].currentText()
            if field_name:
                used_fields.add(field_name)

        # Enable button only if there are unused fields
        has_available_fields = len(used_fields) < len(all_fields)
        self._add_mapping_button.setEnabled(has_available_fields)

        if not has_available_fields:
            self._add_mapping_button.setToolTip("All available fields have been used")
        else:
            self._add_mapping_button.setToolTip("Add a new field to generate")

    def _update_token_count(self):
        """Update the token count based on the current input and prompt."""
        user_input = self._user_input.toPlainText()
        global_prompt = self._prompt_input.toPlainText()

        if not global_prompt or not user_input:
            self._token_count_label.setText("")
            return

        field_mappings = self._get_field_mappings_from_widgets()
        card_fields = {"__input__": user_input}

        # Use the construct_prompt function
        preview = construct_prompt(global_prompt, field_mappings, card_fields)

        # Estimate token count
        estimated_tokens = estimate_token_count(preview)
        max_tokens = self._config_manager["max_prompt_tokens"]

        # Update token count display
        token_info = f"Approximate token count: {estimated_tokens} "
        if estimated_tokens > max_tokens:
            token_info += f"(EXCEEDS LIMIT OF {max_tokens})"
            self._token_count_label.setStyleSheet("color: red; font-weight: bold;")
        else:
            token_info += f"(limit: {max_tokens})"
            self._token_count_label.setStyleSheet("color: green; font-weight: bold;")

        self._token_count_label.setText(token_info)


def open_card_creation_dialog():
    """Open the card creation dialog."""
    dialog = CardCreationDialog()
    dialog.exec()
