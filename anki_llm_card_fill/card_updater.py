from __future__ import annotations

from typing import TYPE_CHECKING

from aqt import mw
from aqt.utils import showInfo, tooltip

from .llm import LLMClient
from .utils import construct_prompt, parse_field_mappings, parse_llm_response

if TYPE_CHECKING:
    from anki.cards import Card


def update_card_fields(card: Card | None = None) -> None:
    """Update the current card's fields using LLM."""
    card = card or mw.reviewer.card
    if card is None:
        showInfo("Can't determine card to update")
        return

    # Get configuration
    config = mw.addonManager.getConfig(__name__)
    if not config:
        showInfo("Configuration not found")
        return

    # Get LLM client configuration
    client_name = config.get("client", "OpenAI")
    model_name = config.get("model", "")
    api_key = config.get("api_key", "")
    temperature = config.get("temperature", 0.5)
    max_length = config.get("max_length", 1000)

    # Get template configuration
    global_prompt = config.get("global_prompt", "")
    field_mappings_text = config.get("field_mappings", "")

    if not global_prompt or not field_mappings_text:
        showInfo("Please configure the prompt template and field mappings in the settings")
        return

    # Parse field mappings
    field_mappings = parse_field_mappings(field_mappings_text)
    if not field_mappings:
        showInfo("No valid field mappings found")
        return

    note = card.note()

    # Construct prompt
    prompt = construct_prompt(global_prompt, field_mappings, note)

    # Initialize LLM client
    try:
        client_cls = LLMClient.get_client(client_name)
        client = client_cls(model=model_name, temperature=temperature, max_length=max_length, api_key=api_key)
    except Exception as e:
        showInfo(f"Error initializing LLM client: {e}")
        return

    # Call LLM
    try:
        tooltip("Generating content with LLM...")
        response = client(prompt)
        tooltip("Processing LLM response...")
    except Exception as e:
        showInfo(f"Error calling LLM: {e}")
        return

    # Parse response
    field_updates = parse_llm_response(response)
    if "error" in field_updates:
        showInfo(f"Error: {field_updates['error']}")
        return

    # Update fields
    for field_name, content in field_updates.items():
        if field_name in note:
            note[field_name] = content

    # Save changes
    note.flush()
    tooltip("Card fields updated successfully!")

    # Reload the card and ensure focus
    mw.reviewer._redraw_current_card()  # noqa: SLF001
