# Config Schema Migration Plan

## Background
The Anki LLM Card Fill plugin currently uses a simple configuration system that needs to be updated to support schema migrations as new features are added. We need to ensure backward compatibility while allowing for future extensions.

## Implementation Plan

### 1. Create a ConfigManager Class
- Implement a class that handles loading, validating, and migrating configuration data
- Include version tracking for schema
- Provide sensible defaults for all configuration options

### 2. Update Existing Code to Use the ConfigManager
- Replace direct calls to `mw.addonManager.getConfig(__name__)` with the new manager
- Update all places that modify config to use manager methods instead

### 3. Implement Schema Migration Logic
- Add migration paths for each version upgrade
- Make each migration function handle one schema version transition
- Store the current schema version in the config file

### 4. Move Current Migration Code
- Refactor existing migration code from `ConfigDialog.get_api_key_for_client` and `ConfigDialog.get_model_for_client`
- Integrate into the ConfigManager's migration system

### 5. Add Validation
- Validate config after loading to ensure required fields exist
- Add type checking for important fields
- Provide helpful error messages when validation fails

### 6. Create Safety Mechanisms
- Implement backup of config before migrations
- Add recovery mechanism if migration fails
- Log changes made during migration

## Expected Schema Structure

```python
{
    "schema_version": 2,
    "client": "OpenAI",
    "api_keys": {
        "OpenAI": "sk-...",
        "Anthropic": "sk-ant-..."
    },
    "models": {
        "OpenAI": "gpt-4o",
        "Anthropic": "claude-3-opus-20240229"
    },
    "temperature": 0.7,
    "max_length": 300,
    "max_prompt_tokens": 1000,
    "global_prompt": "...",
    "field_mappings": "...",
    "shortcut": "Ctrl+A"
}
```

## Migration Paths

### V0 to V1
- Move `api_key` to `api_keys[client]`
- Move `model` to `models[client]`
- Add `schema_version: 1`

### V1 to V2
- Add `max_prompt_tokens` with default value
- Update `schema_version` to 2

## Future Considerations
- Support for per-model configuration
- Template versioning
- User profiles for different use cases
- Export/import of configurations

This plan will ensure smooth upgrades while maintaining compatibility with existing user configurations.
