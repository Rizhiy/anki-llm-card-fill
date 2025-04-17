from __future__ import annotations

import concurrent.futures
import logging
from typing import TYPE_CHECKING

from aqt import mw
from aqt.qt import QApplication, QMessageBox, QProgressDialog, Qt
from aqt.utils import showInfo, tooltip

from .llm import LLMClient
from .utils import construct_prompt, parse_field_mappings, parse_llm_response

if TYPE_CHECKING:
    from anki.notes import Note
    from aqt.browser.browser import Browser
    from aqt.editor import Editor

logger = logging.getLogger()


def update_note_fields(note: Note) -> bool:
    """Update a note's fields using LLM. This is the core implementation used by other functions.

    Returns True if update was successful, False otherwise.
    """
    # Get configuration
    config = mw.addonManager.getConfig(__name__)
    if not config:
        logger.error("Configuration not found")
        return False

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
        logger.error("Prompt template or field mappings not configured")
        return False

    # Parse field mappings
    field_mappings = parse_field_mappings(field_mappings_text)
    if not field_mappings:
        logger.error("No valid field mappings found")
        return False

    # Construct prompt
    prompt = construct_prompt(global_prompt, field_mappings, dict(note.items()))

    # Initialize LLM client
    try:
        client_cls = LLMClient.get_client(client_name)
        client = client_cls(model=model_name, temperature=temperature, max_length=max_length, api_key=api_key)
    except Exception:
        logger.exception(f"Error initializing LLM client for note {note.id}")
        return False

    # Call LLM
    try:
        response = client(prompt)
    except Exception:
        logger.exception(f"Error calling LLM for note {note.id}")
        return False

    # Parse response
    field_updates = parse_llm_response(response)
    if "error" in field_updates:
        logger.error(f"Error parsing response for note {note.id}: {field_updates['error']}")
        return False

    # Update fields
    for field_name, content in field_updates.items():
        if field_name in note:
            note[field_name] = content

    # Save changes
    note.flush()
    return True


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


def update_browser_notes(browser: Browser) -> None:
    """Update all selected notes in the browser."""
    selected_nids = browser.selectedNotes()
    if not selected_nids:
        showInfo("No notes selected.")
        return

    notes = [mw.col.get_note(nid) for nid in selected_nids]

    # Ask for confirmation if many notes selected
    if len(notes) > 5:
        confirm = QMessageBox.question(
            browser,
            "Confirm Bulk Update",
            f"Do you want to update {len(notes)} notes with LLM content? This may take a while and use API credits.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

    # Process the notes in parallel
    tooltip(f"Processing {len(notes)} notes with LLM...")
    process_notes_in_parallel(notes)

    # Refresh the browser view
    browser.model.reset()


def process_notes_in_parallel(notes: list[Note]) -> None:
    """Process multiple notes in parallel using ThreadPoolExecutor with progress dialog."""
    if not notes:
        return

    total_notes = len(notes)
    completed = 0
    success_count = 0

    # Create progress dialog
    progress = QProgressDialog("Processing notes with LLM...", "Cancel", 0, total_notes, mw)
    progress.setWindowTitle("LLM Card Fill")
    progress.setWindowModality(Qt.WindowModality.ApplicationModal)
    progress.setMinimumDuration(0)  # Show immediately
    progress.setValue(0)

    # Use ThreadPoolExecutor to process notes in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Submit all tasks and collect futures
        futures = []
        for note in notes:
            if progress.wasCanceled():
                break
            futures.append(executor.submit(update_note_fields, note))

        remaining_futures = list(futures)

        # Process futures until all are done or canceled
        while remaining_futures and not progress.wasCanceled():
            # Wait for the next future to complete
            for future in concurrent.futures.as_completed(remaining_futures):
                remaining_futures.remove(future)

                completed += 1

                # Check if the future completed successfully
                if not future.exception():
                    success_count += 1
                else:
                    # Log the exception
                    logger.error("Error processing note", exc_info=future.exception())

                # Update progress bar
                progress.setValue(completed)
                progress.setLabelText(f"Processing notes with LLM... ({completed}/{total_notes})")

                # Check for cancellation after each future completes
                if progress.wasCanceled():
                    break

                # Allow UI to process events
                QApplication.processEvents()

    # Finish progress dialog
    progress.setValue(total_notes)

    # Show final completion message
    if progress.wasCanceled():
        tooltip(f"Operation canceled. Processed {completed} of {total_notes} notes.")
    elif success_count == total_notes:
        tooltip(f"Successfully updated all {total_notes} notes!")
    else:
        tooltip(f"Updated {success_count} of {total_notes} notes. Check logs for errors.")
