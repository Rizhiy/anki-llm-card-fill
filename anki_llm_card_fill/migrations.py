"""Configuration schema migrations for Anki LLM Card Fill addon."""

import logging
from typing import Any, Callable

from aqt import mw
from aqt.qt import QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

logger = logging.getLogger(__name__)

# Constants
DEFAULT_NOTE_TYPE = "__default__"

# Type definition for migration functions
MigrationFunction = Callable[[dict[str, Any]], dict[str, Any]]


def v1(config: dict[str, Any]) -> dict[str, Any]:
    """Move API key and model to client-specific dictionaries.

    - Move api_key to api_keys[client]
    - Move model to models[client]
    - Add schema_version
    """
    # Initialize new structures if they don't exist
    if "api_keys" not in config:
        config["api_keys"] = {}

    if "models" not in config:
        config["models"] = {}

    # Get the client name
    client_name = config.get("client", "OpenAI")

    # Migrate API key
    if api_key := config.get("api_key"):
        config["api_keys"][client_name] = api_key
        del config["api_key"]

    # Migrate model
    if model := config.get("model"):
        config["models"][client_name] = model
        del config["model"]

    # Set schema version
    config["schema_version"] = 1
    return config


def v2(config: dict[str, Any]) -> dict[str, Any]:
    """Add max_prompt_tokens setting."""
    # Add max_prompt_tokens if it doesn't exist
    if "max_prompt_tokens" not in config:
        config["max_prompt_tokens"] = 500

    # Set schema version
    config["schema_version"] = 2
    return config


def v3(config: dict[str, Any]) -> dict[str, Any]:
    """Formalize schema versioning."""
    # Set schema version
    config["schema_version"] = 3
    return config


def v4(config: dict[str, Any]) -> dict[str, Any]:
    """Convert field_mappings from string to dictionary format."""

    # Get the existing field_mappings string
    field_mappings_str = config.get("field_mappings", "")

    # Convert to dictionary
    field_mappings_dict = {}
    if isinstance(field_mappings_str, str) and field_mappings_str:
        # Split by lines and parse each line
        for line in field_mappings_str.strip().split("\n"):
            if ":" in line:
                prompt_var, note_field = [x.strip() for x in line.split(":", 1)]
                field_mappings_dict[prompt_var] = note_field

    # Update the config with the new dictionary
    config["field_mappings"] = field_mappings_dict

    # Update schema version
    config["schema_version"] = 4
    return config


def v5(config: dict[str, Any]) -> dict[str, Any]:
    """Migrate to note type-specific prompts and field mappings.

    Convert the global prompt and field_mappings to a structure where
    different note types can have their own prompts and field mappings.
    """
    # Create the new note_prompts dictionary if it doesn't exist
    config["note_prompts"] = {}

    # Move existing global prompt and field mappings to default entry
    global_prompt = config.get("global_prompt", "")
    field_mappings = config.get("field_mappings", {})
    config["note_prompts"][DEFAULT_NOTE_TYPE] = {
        "prompt": global_prompt,
        "field_mappings": field_mappings,
    }
    if config.get("global_prompt"):
        del config["global_prompt"]
    if config.get("field_mappings"):
        del config["field_mappings"]

    config["schema_version"] = 5
    return config


def v6(config: dict[str, Any]) -> dict[str, Any]:
    """Migrate default note type to user-selected note type.

    This migration will present a dialog asking the user to select a note type,
    and migrate the default configuration to that note type.
    """
    # If no default prompt exists yet, nothing to do
    note_prompts = config["note_prompts"]
    default_config = note_prompts.get(DEFAULT_NOTE_TYPE, {})

    try:
        note_types = mw.col.models.all_names()
    except Exception as e:
        raise ValueError(f"Error accessing note types: {e}") from None

    if not note_types:
        raise ValueError("No note types found in Anki collection")

    # Create a dialog to ask the user which note type to use
    class NoteTypeSelectDialog(QDialog):
        def __init__(self):
            super().__init__(mw)
            self.setWindowTitle("LLM Card Fill - Select Note Type")
            self.layout = QVBoxLayout()

            # Add explanation with add-on name
            explanation = QLabel(
                "<b>LLM Card Fill Add-on Configuration</b><br><br>"
                "We need to migrate your existing configuration to a specific note type. "
                "Please select the note type you want to use with LLM Card Fill:",
            )
            explanation.setWordWrap(True)
            self.layout.addWidget(explanation)

            # Add note type selector
            self.selector = QComboBox()
            for note_type in note_types:
                self.selector.addItem(note_type)
            self.layout.addWidget(self.selector)

            # Add explanation of what's happening
            migration_info = QLabel(
                "This migration is required because the code has been updated to support "
                "note type-specific configuration. Your existing default configuration will "
                "be migrated to the selected note type.",
            )
            migration_info.setWordWrap(True)
            self.layout.addWidget(migration_info)

            # Add buttons
            button_layout = QHBoxLayout()
            self.ok_button = QPushButton("OK")
            self.ok_button.clicked.connect(self.accept)
            self.cancel_button = QPushButton("Cancel")
            self.cancel_button.clicked.connect(self.reject)

            button_layout.addWidget(self.ok_button)
            button_layout.addWidget(self.cancel_button)
            self.layout.addLayout(button_layout)

            self.setLayout(self.layout)

    dialog = NoteTypeSelectDialog()
    result = dialog.exec()

    # Only proceed with migration if user confirmed their selection
    if result:
        selected_note_type = dialog.selector.currentText()

        # Copy default config to selected note type
        note_prompts[selected_note_type] = {
            "prompt": default_config.get("prompt", ""),
            "field_mappings": default_config.get("field_mappings", {}),
        }
        del note_prompts[DEFAULT_NOTE_TYPE]

        # Update schema version only after successful migration
        config["schema_version"] = 6
    else:
        raise ValueError("Migration canceled")

    return config


def v7(config: dict[str, Any]) -> dict[str, Any]:
    """Rename 'prompt' to 'update_prompt' and add 'create_prompt' in note_prompts.

    This migration updates the structure to support separate prompts for:
    - Updating existing cards (update_prompt)
    - Creating new cards (create_prompt)
    """
    note_prompts = config["note_prompts"]

    for note_config in note_prompts.values():
        note_config["update_prompt"] = note_config["prompt"]
        del note_config["prompt"]

    config["note_prompts"] = note_prompts

    config["schema_version"] = 7
    return config


def v8(config: dict[str, Any]) -> dict[str, Any]:
    """Add 'create_only_fields' to each note type configuration.

    This allows some fields to be editable only during card creation,
    but not when updating existing cards.
    """
    note_prompts = config["note_prompts"]

    for note_config in note_prompts.values():
        note_config["create_only_fields"] = []

    config["note_prompts"] = note_prompts
    config["schema_version"] = 8
    return config


# Mapping of version numbers to migration functions
MIGRATIONS = [
    v1,
    v2,
    v3,
    v4,
    v5,
    v6,
    v7,
    v8,
]

# Current schema version
CURRENT_SCHEMA_VERSION = 8
