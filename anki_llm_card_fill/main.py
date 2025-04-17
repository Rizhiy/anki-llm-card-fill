from aqt import QKeySequence, gui_hooks, mw
from aqt.qt import QAction, QMenu, qconnect

from .card_updater import update_editor_note, update_reviewer_card
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
