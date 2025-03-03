# import the main window object (mw) from aqt
from aqt import mw

# import all of the Qt GUI library
from aqt.qt import QAction

# import the "show info" tool from utils.py
from aqt.utils import qconnect

# import the config module
from .config import open_config_dialog

# Add a new menu item for configuration
config_action = QAction("Configure LLM Client", mw)
qconnect(config_action.triggered, open_config_dialog)
mw.form.menuTools.addAction(config_action)
