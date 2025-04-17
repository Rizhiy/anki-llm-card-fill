from aqt import QKeySequence, gui_hooks, mw
from aqt.browser import Browser
from aqt.qt import QAction, QMenu, qconnect

from .card_updater import update_browser_notes, update_editor_note, update_reviewer_card
from .config import open_config_dialog

submenu = QMenu("LLM Card Fill", mw)

# Config
config_action = QAction("Configure LLM Card Fill", mw)
qconnect(config_action.triggered, open_config_dialog)
submenu.addAction(config_action)

# Action + Shortcut for reviewer
shortcut = "Ctrl+A"  # Default shortcut
if config := mw.addonManager.getConfig(__name__):
    shortcut = config.get("shortcut") or shortcut
update_action = QAction("Update Card with LLM", mw)
update_action.setShortcut(QKeySequence(shortcut))
qconnect(update_action.triggered, update_reviewer_card)
submenu.addAction(update_action)

mw.form.menubar.insertMenu(mw.form.menuHelp.menuAction(), submenu)


# Add button to card editor
def add_button_to_card_editor(buttons, editor):
    button = editor.addButton(
        cmd="LLM Card Fill",
        label="LLM",
        func=lambda editor: update_editor_note(editor),
        icon=None,
    )
    buttons.append(button)


gui_hooks.editor_did_init_buttons.append(add_button_to_card_editor)


# Add browser context menu
def on_browser_context_menu(browser: Browser, menu: QMenu) -> None:
    """Add LLM Fill option to browser context menu."""
    selected_notes = browser.selectedNotes()
    if not selected_notes:
        return

    # Create and add the action
    action_text = f"Fill {len(selected_notes)} note(s) with LLM"
    action = menu.addAction(action_text)
    qconnect(action.triggered, lambda: update_browser_notes(browser))


# Connect to browser context menu hook
gui_hooks.browser_will_show_context_menu.append(on_browser_context_menu)


# Add menu item to browser
def on_browser_setup_menus(browser: Browser) -> None:
    """Add LLM Fill option to browser's Edit menu."""
    action = QAction("Fill Selected Notes with LLM", browser)
    qconnect(action.triggered, lambda: update_browser_notes(browser))
    browser.form.menu_Notes.addAction(action)


gui_hooks.browser_menus_did_init.append(on_browser_setup_menus)
