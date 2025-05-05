"""Configuration schema migrations for Anki LLM Card Fill addon."""

import logging
from typing import Any, Callable

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
    del config["global_prompt"]
    del config["field_mappings"]

    config["schema_version"] = 5
    return config


# Mapping of version numbers to migration functions
MIGRATIONS = [
    v1,
    v2,
    v3,
    v4,
    v5,
]

# Current schema version
CURRENT_SCHEMA_VERSION = 5
