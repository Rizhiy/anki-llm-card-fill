"""Configuration management for the Anki LLM Card Fill addon."""

import copy
import logging
from collections import UserDict
from typing import Any, Literal

from aqt import mw

from .migrations import CURRENT_SCHEMA_VERSION, MIGRATIONS

logger = logging.getLogger(__name__)


class ConfigManager(UserDict):
    """Manages configuration for the Anki LLM Card Fill addon."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

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
        if not self.data:
            return 0

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
        """Migrate configuration to the current schema version."""
        schema_version = self._detect_schema_version()

        if schema_version == CURRENT_SCHEMA_VERSION:
            if "schema_version" not in self.data:
                self.data["schema_version"] = schema_version
            return

        logger.info(f"Migrating configuration from version {schema_version} to {CURRENT_SCHEMA_VERSION}")

        while schema_version < CURRENT_SCHEMA_VERSION:
            migration_func = MIGRATIONS[schema_version]
            logger.info(f"Applying migration from v{schema_version} to v{schema_version + 1}")
            try:
                self.data = migration_func(self.data)
                logger.info(f"Successfully migrated from v{schema_version} to v{schema_version + 1}")
            except Exception:
                logger.exception(f"Error migrating from v{schema_version} to v{schema_version + 1}")
                raise

            schema_version += 1
        self.save_config()

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

    def get_requests_per_minute_for_client(self, client_name: str) -> int:
        """Get the requests per minute limit for a specific client.

        :param client_name: The name of the client to get the limit for
        :return: The requests per minute limit or default value if not found
        """
        return self["requests_per_minute"].get(client_name, 0)

    def get_tokens_per_minute_for_client(self, client_name: str) -> int:
        """Get the tokens per minute limit for a specific client.

        :param client_name: The name of the client to get the limit for
        :return: The tokens per minute limit or default value if not found
        """
        return self["tokens_per_minute"].get(client_name, 0)

    def validate_settings(self, note_type: str, *, prompt_type: Literal["update", "create"] = "update") -> None:
        """Validate that required settings have been configured for a specific note type.

        :param note_type: The note type to validate settings for
        :param prompt_type: Type of prompt to validate ('update' or 'create')
        :raises ValueError: If required settings are missing
        """
        client = self["client"]
        if not self.get_model_for_client(client):
            raise ValueError("Model not selected")

        if not self.get_api_key_for_client(client):
            raise ValueError("API key not configured")

        if not self.get_requests_per_minute_for_client(client):
            raise ValueError("Request per minute not configured")

        if not self.get_tokens_per_minute_for_client(client):
            raise ValueError("Tokens per minute not configured")

        if not self.get_note_type_config(note_type):
            raise ValueError("Note type config not configured")

        if not self.get_field_mappings_for_note_type(note_type):
            raise ValueError("Note type field mappings not configured")

        if prompt_type == "update" and not self.get_prompt_for_update(note_type):
            raise ValueError("Note type update prompt not configured")

        if prompt_type == "create" and not self.get_prompt_for_create(note_type):
            raise ValueError("Note type create prompt not configured")

    def get_note_type_config(self, note_type: str) -> dict[str, Any]:
        """Get the prompt configuration for a specific note type, with fallback to default.

        :param note_type: The name of the note type
        :return: A dictionary containing prompt and field_mappings
        """
        return self["note_prompts"].get(note_type, {})

    def set_note_type_config(self, note_type: str, config: dict[str, Any]) -> None:
        """Set the prompt configuration for a specific note type.

        :param note_type: The name of the note type
        :param config: The configuration to set
        """
        self["note_prompts"][note_type] = config

    def update_note_type_config(self, note_type: str, key: str, value: Any) -> None:
        """Update a specific key in the note type config.

        :param note_type: The name of the note type
        :param key: The key to update
        :param value: The value to set
        """
        note_type_config = self.get_note_type_config(note_type)
        note_type_config[key] = value
        self.set_note_type_config(note_type, note_type_config)

    def get_prompt_for_update(self, note_type: str) -> str:
        """Get the update prompt template for a specific note type.

        :param note_type: The name of the note type
        :return: The update prompt template string
        """
        return self.get_note_type_config(note_type).get("update_prompt", "")

    def set_prompt_for_update(self, note_type: str, prompt: str) -> None:
        """Set the update prompt template for a specific note type.

        :param note_type: The name of the note type
        :param prompt: The update prompt template string
        """
        self.update_note_type_config(note_type, "update_prompt", prompt)

    def get_prompt_for_create(self, note_type: str) -> str:
        """Get the creation prompt template for a specific note type.

        :param note_type: The name of the note type
        :return: The creation prompt template string
        """
        return self.get_note_type_config(note_type).get("create_prompt", "")

    def set_prompt_for_create(self, note_type: str, prompt: str) -> None:
        """Set the creation prompt template for a specific note type.

        :param note_type: The name of the note type
        :param prompt: The creation prompt template string
        """
        self.update_note_type_config(note_type, "create_prompt", prompt)

    def get_field_mappings_for_note_type(self, note_type: str) -> dict[str, str]:
        """Get the field mappings for a specific note type.

        :param note_type: The name of the note type
        :return: Dictionary mapping prompt variables to note fields
        """
        return self.get_note_type_config(note_type)["field_mappings"]

    def set_field_mappings_for_note_type(self, note_type: str, field_mappings: dict[str, str]) -> None:
        """Set the field mappings for a specific note type.

        :param note_type: The name of the note type
        :param field_mappings: The field mappings to set
        """
        self.update_note_type_config(note_type, "field_mappings", field_mappings)

    def get_create_only_fields(self, note_type: str) -> list[str]:
        """Get the list of fields that should only be editable during card creation.

        :param note_type: The name of the note type
        :return: List of field names that are only editable during card creation
        """
        return self.get_note_type_config(note_type)["create_only_fields"]

    def add_create_only_field(self, note_type: str, field_name: str) -> None:
        """Add a field to the create-only fields list for a note type.

        :param note_type: The name of the note type
        :param field_name: The field name to add to create-only fields
        """
        note_type_config = self.get_note_type_config(note_type)

        create_only_fields = note_type_config.get("create_only_fields", [])
        if field_name not in create_only_fields:
            create_only_fields.append(field_name)
            self.update_note_type_config(note_type, "create_only_fields", create_only_fields)

    def remove_create_only_field(self, note_type: str, field_name: str) -> None:
        """Remove a field from the create-only fields list for a note type.

        :param note_type: The name of the note type
        :param field_name: The field name to remove from create-only fields
        """
        note_type_config = self.get_note_type_config(note_type)

        create_only_fields = note_type_config.get("create_only_fields", [])
        if field_name in create_only_fields:
            create_only_fields.remove(field_name)
            self.update_note_type_config(note_type, "create_only_fields", create_only_fields)

    def get_preferred_deck_name(self, note_type: str) -> str:
        """Get the preferred deck name for a specific note type.

        :param note_type: The name of the note type
        :return: The deck name or None if not set
        """
        return self.get_note_type_config(note_type).get("preferred_deck_name")

    def set_preferred_deck_name(self, note_type: str, deck_name: str) -> None:
        """Set the preferred deck name for a specific note type.

        :param note_type: The name of the note type
        :param deck_name: The deck name to save
        """
        self.update_note_type_config(note_type, "preferred_deck_name", deck_name)


__all__ = ["ConfigManager"]
