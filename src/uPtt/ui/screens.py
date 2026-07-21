"""Re-export shim: screens.py 已依畫面拆分為多個模組（_render / login_window /
scan_setup / dialogs / main_window）。保留本檔案是為了讓既有的
`from uPtt.ui.screens import ...` 呼叫端（app.py、測試檔）不需修改即可繼續運作。
新程式碼請直接從對應的子模組 import。"""

from uPtt.ui._render import ASSETS_DIR, render_svg, render_themed_icon
from uPtt.ui.login_window import LoginWindow
from uPtt.ui.scan_setup import ScanSetupScreen
from uPtt.ui.dialogs import MessageSearchDialog, SettingsDialog, _format_contact_time
from uPtt.ui.main_window import MainWindow

__all__ = [
    "ASSETS_DIR",
    "render_svg",
    "render_themed_icon",
    "LoginWindow",
    "ScanSetupScreen",
    "MessageSearchDialog",
    "SettingsDialog",
    "MainWindow",
    "_format_contact_time",
]
