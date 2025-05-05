"""Configuration management for the Anki LLM Card Fill addon."""

import copy
import logging
from collections import UserDict
from typing import Any

from aqt import mw

from .migrations import CURRENT_SCHEMA_VERSION, DEFAULT_NOTE_TYPE, MIGRATIONS

logger = logging.getLogger(__name__)


class ConfigManager(UserDict):
    """Manages configuration for the Anki LLM Card Fill addon."""

    def __init__(self):
        super().__init__()
        self._backup_config = None
        self.load_config()

    def load_config(self) -> dict[str, Any]:
        """Load configuration from Anki's addon manager.

        :return: The current configuration dictionary
        """
        config = mw.addonManager.getConfig(__name__) or {}

        self._backup_config = copy.deepcopy(config)
        self.data = copy.deepcopy(config)  # UserDict stores data in self.data

        self._migrate_config()

        return self.data

    def save_config(self) -> None:
        """Save the current configuration to Anki's addon manager."""
        if self.data:
            self.data["schema_version"] = CURRENT_SCHEMA_VERSION
            mw.addonManager.writeConfig(__name__, self.data)

    def _detect_schema_version(self) -> int:
        """Detect the schema version of the current configuration.

        :return: The detected schema version
        :raises ValueError: If the version cannot be determined
        """
        if "schema_version" in self.data:
            return self.data["schema_version"]

        if "api_key" in self.data or "model" in self.data:
            return 0
        if "api_keys" in self.data and "models" in self.data:
            if "max_prompt_tokens" in self.data:
                return 2
            return 1

        raise ValueError("Unknown config version")

    def _migrate_config(self) -> None:
        """Migrate configuration to the current schema version.

        :raises ValueError: If no configuration is found
        """
        if not self.data:
            raise ValueError("No configuration found")

        schema_version = self._detect_schema_version()

        if schema_version == CURRENT_SCHEMA_VERSION:
            if "schema_version" not in self.data:
                self.data["schema_version"] = schema_version
            return

        logger.info(f"Migrating configuration from version {schema_version} to {CURRENT_SCHEMA_VERSION}")

        while schema_version < CURRENT_SCHEMA_VERSION:
            migration_func = MIGRATIONS[schema_version]
            logger.info(f"Applying migration from v{schema_version} to v{schema_version + 1}")
            self.data = migration_func(self.data)
            logger.info(f"Successfully migrated from v{schema_version} to v{schema_version + 1}")

            schema_version += 1

    def get_api_key_for_client(self, client_name: str) -> str:
        """Get the API key for a specific client.

        :param client_name: The name of the client to get the API key for
        :return: The API key string or empty string if not found
        """
        return self["api_keys"].get(client_name, "")

    def get_model_for_client(self, client_name: str) -> str:
        """Get the model for a specific client.

        :param client_name: The name of the client to get the model for
        :return: The model name for the client or empty string if not found
        """
        return self["models"].get(client_name, "")

    def validate_settings(self, note_type: str) -> None:
        """Validate that required settings have been configured for a specific note type.

        :param note_type: The note type to validate settings for
        :raises ValueError: If required settings are missing
        """
        client = self["client"]
        if not self.get_model_for_client(client):
            raise ValueError("Model not selected")

        if not self.get_api_key_for_client(client):
            raise ValueError("API key not configured")

        if not self.get_note_type_config(note_type):
            raise ValueError("Note type prompt not configured")

        if not self.get_field_mappings_for_note_type(note_type):
            raise ValueError("Note type field mappings not configured")

    def get_note_type_config(self, note_type: str) -> dict[str, Any]:
        """Get the prompt configuration for a specific note type, with fallback to default.

        :param note_type: The name of the note type
        :return: A dictionary containing prompt and field_mappings
        """
        return self["note_prompts"].get(note_type, self["note_prompts"][DEFAULT_NOTE_TYPE])

    def get_prompt_for_note_type(self, note_type: str) -> str:
        """Get the prompt template for a specific note type.

        :param note_type: The name of the note type
        :return: The prompt template string
        """
        return self.get_note_type_config(note_type)["prompt"]

    def get_field_mappings_for_note_type(self, note_type: str) -> dict[str, str]:
        """Get the field mappings for a specific note type.

        :param note_type: The name of the note type
        :return: Dictionary mapping prompt variables to note fields
        """
        return self.get_note_type_config(note_type)["field_mappings"]


config_manager = ConfigManager()

__all__ = ["config_manager", "ConfigManager"]
