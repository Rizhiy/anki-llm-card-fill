"""Configuration schema migrations for Anki LLM Card Fill addon."""

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

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


# List of all migrations in order
# Migration at index i converts from version i to version i+1
MIGRATIONS: list[MigrationFunction] = [
    v1,
    v2,
    v3,
    # Add new migrations here as they are created
]

# Current schema version - should match the latest migration's target
CURRENT_SCHEMA_VERSION = 3
