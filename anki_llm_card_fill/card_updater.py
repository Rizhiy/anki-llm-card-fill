from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aqt import mw
from aqt.utils import showInfo, tooltip

from .llm import LLMClient
from .utils import construct_prompt, parse_field_mappings, parse_llm_response

if TYPE_CHECKING:
    from anki.notes import Note
    from aqt.editor import Editor

logger = logging.getLogger()


def update_note_fields(note: Note) -> None:
    """Update a note's fields using LLM. This is the core implementation used by other functions."""
    # Get configuration
    config = mw.addonManager.getConfig(__name__)
    if not config:
        showInfo("Configuration not found")
        return

    # Get LLM client configuration
    client_name = config["client"]
    model_name = config["model"]
    api_key = config["api_key"]
    temperature = config["temperature"]
    max_length = config["max_length"]

    # Get template configuration
    global_prompt = config.get("global_prompt", "")
    field_mappings_text = config.get("field_mappings", "")

    if not (global_prompt and field_mappings_text):
        showInfo("Please configure the prompt template and field mappings in the settings")
        return

    # Parse field mappings
    field_mappings = parse_field_mappings(field_mappings_text)
    if not field_mappings:
        showInfo("No valid field mappings found")
        return

    # Construct prompt
    prompt = construct_prompt(global_prompt, field_mappings, dict(note.items()))

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


def update_reviewer_card() -> None:
    """Update the current card being reviewed."""
    card = mw.reviewer.card
    if not card:
        showInfo("No card is being reviewed.")
        return

    note = card.note()
    update_note_fields(note)

    # Redraw the current card
    mw.reviewer._redraw_current_card()  # noqa: SLF001


def update_editor_note(editor: Editor) -> None:
    """Update the note currently open in the editor."""
    note = editor.note
    if not note:
        showInfo("No note is currently being edited.")
        return

    update_note_fields(note)

    # Refresh the editor view
    editor.loadNoteKeepingFocus()
    # If reviewer is also open, reload that as well
    if mw.reviewer.card:
        mw.reviewer._redraw_current_card()  # noqa: SLF001
