from aqt import QKeySequence, mw
from aqt.qt import QAction, QMenu
from aqt.utils import qconnect

from .card_updater import update_card_fields
from .config import open_config_dialog

submenu = QMenu("LLM Card Fill", mw)

# Config
config_action = QAction("Configure LLM Card Fill", mw)
qconnect(config_action.triggered, open_config_dialog)
submenu.addAction(config_action)

# Action + Shortcut
shortcut = "Ctrl+A"  # Default shortcut
if config := mw.addonManager.getConfig(__name__):
    shortcut = config.get("shortcut") or shortcut
update_action = QAction("Update Card with LLM", mw)
update_action.setShortcut(QKeySequence(shortcut))
qconnect(update_action.triggered, update_card_fields)
submenu.addAction(update_action)

mw.form.menubar.insertMenu(mw.form.menuHelp.menuAction(), submenu)
