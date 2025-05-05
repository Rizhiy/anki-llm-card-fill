from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aqt import mw
from aqt.qt import QApplication, QMessageBox, QObject, QProgressDialog, QRunnable, Qt, QThreadPool, pyqtSignal
from aqt.utils import showInfo, tooltip

from .config_manager import config_manager
from .llm import LLMClient
from .utils import construct_prompt, parse_llm_response

if TYPE_CHECKING:
    from anki.notes import Note
    from aqt.browser.browser import Browser
    from aqt.editor import Editor

logger = logging.getLogger()


class NoteProcessSignals(QObject):
    """Signals for note processing."""

    error = pyqtSignal(Exception)  # Error if any
    completed = pyqtSignal(bool)  # Success status


def estimate_token_count(text: str) -> int:
    """Estimate the number of tokens in a text.

    This is a rough approximation. A typical rule of thumb is that one token
    is about 4 characters or 0.75 words for English text.

    :param text: The text to estimate token count for
    :return: Estimated number of tokens
    """
    # Simple approximation - 4 characters per token on average
    return len(text) // 4


class NoteUpdateWorker(QRunnable):
    """Worker for updating a note with LLM content."""

    def __init__(self, note: Note, signals: NoteProcessSignals | None = None):
        super().__init__()
        self.note = note
        self.signals = signals or NoteProcessSignals()

    def log_and_emit(self, msg: str) -> None:
        """Log an error message and emit error signals.

        :param msg: The error message
        """
        logger.error(msg)
        self.signals.error.emit(ValueError(msg))
        self.signals.completed.emit(False)

    def run(self):
        """Perform the full note update process."""
        try:
            # Validate configuration
            try:
                config_manager.validate_settings()
            except ValueError as e:
                self.log_and_emit(str(e))
                return

            # Get LLM client configuration
            client_name = config_manager["client"]
            model_name = config_manager.get_model_for_client(client_name)
            api_key = config_manager.get_api_key_for_client(client_name)
            temperature = config_manager["temperature"]
            max_length = config_manager["max_length"]
            max_prompt_tokens = config_manager["max_prompt_tokens"]

            # Get template configuration
            global_prompt = config_manager.get("global_prompt", "")
            field_mappings = config_manager.get("field_mappings", {})

            # Check if field mappings exist
            if not field_mappings:
                self.log_and_emit("No valid field mappings found")
                return

            # Construct prompt
            prompt = construct_prompt(global_prompt, field_mappings, dict(self.note.items()))

            # Check prompt length
            estimated_tokens = estimate_token_count(prompt)
            if estimated_tokens > max_prompt_tokens:
                self.log_and_emit(
                    f"Prompt exceeds maximum token limit. Estimated tokens: {estimated_tokens}, "
                    f"Max: {max_prompt_tokens}",
                )
                return

            # Initialize LLM client
            client_cls = LLMClient.get_client(client_name)
            client = client_cls(model=model_name, temperature=temperature, max_length=max_length, api_key=api_key)

            # Call LLM
            response = client(prompt)

            # Parse response
            field_updates = parse_llm_response(response)
            if "error" in field_updates:
                self.log_and_emit(f"Error parsing response for note {self.note.id}: {field_updates['error']}")
                return

            # Update fields
            for field_name, content in field_updates.items():
                if field_name in self.note:
                    self.note[field_name] = content

            # Save changes
            self.note.flush()

            # Signal success
            self.signals.completed.emit(True)

        except Exception as e:
            logger.exception(f"Error updating note {self.note.id}")
            self.signals.error.emit(e)
            self.signals.completed.emit(False)


def update_note_fields(note: Note) -> bool:
    """Update a note's fields using LLM in a background thread.

    This function blocks until the update is complete but keeps the UI responsive.
    Returns True if update was successful, False otherwise.
    """
    success = False
    completed = False

    # Create a signals object for this single note
    signals = NoteProcessSignals()

    # Connect signals
    def on_completed(result):
        nonlocal success, completed
        success = result
        completed = True

    def on_error(error):
        showInfo(f"Failed to update note: {error}")

    signals.completed.connect(on_completed)
    signals.error.connect(on_error)

    # Create and start the worker directly
    worker = NoteUpdateWorker(note, signals)

    # Start with the global thread pool
    tooltip("Calling LLM...")
    QThreadPool.globalInstance().start(worker)

    # Process events while waiting for completion
    while not completed:
        QApplication.processEvents()

    # Return the result
    if success:
        tooltip("Card fields updated successfully!")

    return success


def update_reviewer_card() -> None:
    """Update the current card being reviewed."""
    card = mw.reviewer.card
    if not card:
        showInfo("No card is being reviewed.")
        return

    note = card.note()
    if update_note_fields(note):
        # Redraw the current card
        mw.reviewer._redraw_current_card()  # noqa: SLF001


def update_editor_note(editor: Editor) -> None:
    """Update the note currently open in the editor."""
    note = editor.note
    if not note:
        showInfo("No note is currently being edited.")
        return

    if update_note_fields(note):
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

    # Process multiple notes in parallel
    tooltip(f"Processing {len(notes)} notes with LLM...")
    process_notes_in_parallel(notes)

    # Refresh the browser view
    browser.model.reset()


def process_notes_in_parallel(notes: list[Note]) -> None:
    """Process multiple notes using QThreadPool with progress dialog."""
    if not notes:
        return

    total_notes = len(notes)
    completed = 0
    error_msgs = set()
    success_count = 0
    canceled = False

    # Create progress dialog
    progress = QProgressDialog("Processing notes with LLM...", "Cancel", 0, total_notes, mw)
    progress.setWindowTitle("LLM Card Fill")
    progress.setWindowModality(Qt.WindowModality.ApplicationModal)
    progress.setMinimumDuration(0)  # Show immediately
    progress.setValue(0)

    # Create signal handler
    signals = NoteProcessSignals()

    # Connect signals
    def on_note_completed(success):
        nonlocal completed, success_count
        if canceled:
            return

        completed += 1
        if success:
            success_count += 1

        progress.setValue(completed)
        progress.setLabelText(f"Processing notes with LLM... ({completed}/{total_notes})")

        # If all notes are processed, show final message
        if completed >= total_notes:
            if success_count == total_notes:
                tooltip(f"Successfully updated all {total_notes} notes!")
            else:
                tooltip(f"Updated {success_count} of {total_notes} notes. Check logs for errors.")
            progress.close()

    def on_note_error(error):
        nonlocal error_msgs
        msg = str(error)
        if msg in error_msgs:
            return
        error_msgs.add(msg)
        showInfo(f"Got an error when processing note: {msg}")

    signals.completed.connect(on_note_completed)
    signals.error.connect(on_note_error)

    # Handle cancellation
    def on_canceled():
        nonlocal canceled
        canceled = True
        tooltip(f"Operation canceled. Processed {completed} of {total_notes} notes.")

    progress.canceled.connect(on_canceled)

    # Submit tasks to thread pool
    pool = QThreadPool.globalInstance()
    for note in notes:
        if canceled:
            break
        worker = NoteUpdateWorker(note, signals)
        pool.start(worker)

    # Create a local event loop
    while completed < total_notes and not canceled:
        QApplication.processEvents()
        if progress.wasCanceled() and not canceled:
            on_canceled()
