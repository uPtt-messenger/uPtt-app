# 新對話 modal（⌘N，artboard 23）。取代側欄 inline 輸入的體驗:
# 專屬 modal + 即時「格式」查驗（PTT ID 規則,純本地、不打 PTT）。
# 真正的「該 ID 是否存在」沿用既有流程:送出 → add_or_select_contact →
# query worker 查 → 不存在則 session_archived 標記。此處只擋明顯無效輸入。
#
# 所有顏色一律讀 theme.active()，不在此檔硬寫 hex。
import logging
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton,
)

from uPtt.ui import theme
from uPtt.ui.theme import FONT_STACK

logger = logging.getLogger("uPtt.ui.new_chat_modal")

# PTT 帳號格式:字母開頭,其後字母/數字,總長 2–12。純格式檢查,不代表帳號存在。
_PTT_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]{1,11}$")


def is_valid_ptt_id(text: str) -> bool:
    return bool(_PTT_ID_RE.match((text or "").strip()))


def _restyle_container(w):
    t = theme.active()
    w.setStyleSheet(
        f"#new-chat-modal {{ background: {t['surface']}; border: 1px solid "
        f"{t['border_strong']}; border-radius: 12px; }}"
    )


def _restyle_title(w):
    t = theme.active()
    w.setStyleSheet(
        f"color: {t['text']}; font-size: 14px; font-weight: 600; "
        f"background: transparent; font-family: {FONT_STACK};"
    )


def _restyle_input(w):
    t = theme.active()
    w.setStyleSheet(
        f"background: {t['bg']}; color: {t['text']}; border: 1px solid "
        f"{t['border']}; border-radius: 8px; padding: 9px 12px; "
        f"font-family: {FONT_STACK}; font-size: 14px;"
    )


def _restyle_status(w):
    t = theme.active()
    # 中性提示用 muted;錯誤態由 set_status 另設 accent/紅（此處僅底色）。
    w.setStyleSheet(
        f"color: {t['text_muted']}; font-size: 11px; background: transparent; "
        f"font-family: {FONT_STACK};"
    )


class NewChatModal(QWidget):
    """新對話 modal。輸入有效 PTT ID 後 emit chat_requested(id);由 MainWindow
    接去 add_or_select_contact。Esc 關閉。"""

    chat_requested = Signal(str)

    def __init__(self, account_id: str, parent=None):
        super().__init__(parent)
        self.account_id = account_id or ""
        self.setObjectName("new-chat-modal")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setWindowModality(Qt.ApplicationModal)
        self.setFixedWidth(420)

        self._build_ui()
        theme.register_restyle(self, _restyle_container)
        self._revalidate()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)

        self.title = QLabel("新對話")
        theme.register_restyle(self.title, _restyle_title)
        root.addWidget(self.title)

        self.input = QLineEdit()
        self.input.setPlaceholderText("輸入 PTT 帳號")
        self.input.setMaxLength(12)
        self.input.textChanged.connect(self._revalidate)
        self.input.returnPressed.connect(self._submit)
        theme.register_restyle(self.input, _restyle_input)
        root.addWidget(self.input)

        self.status = QLabel("")
        theme.register_restyle(self.status, _restyle_status)
        root.addWidget(self.status)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.start_btn = QPushButton("開始對話  ↵")
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self._submit)
        theme.register_restyle(self.start_btn, self._restyle_button)
        btn_row.addWidget(self.start_btn)
        root.addLayout(btn_row)

    def _restyle_button(self, w):
        t = theme.active()
        enabled = w.isEnabled()
        bg = t["accent"] if enabled else t["surface_2"]
        fg = t["bg"] if enabled else t["text_faint"]
        w.setStyleSheet(
            f"QPushButton {{ background: {bg}; color: {fg}; border: none; "
            f"border-radius: 8px; padding: 8px 16px; font-weight: 600; "
            f"font-family: {FONT_STACK}; }}"
        )

    # ---- 驗證（純邏輯,便於測試）----
    def validate(self, text: str):
        """回傳 (can_submit: bool, status_msg: str)。"""
        t = (text or "").strip()
        if not t:
            return False, ""
        if self.account_id and t.lower() == self.account_id.lower():
            return False, "不能與自己開始對話"
        if not is_valid_ptt_id(t):
            return False, "帳號格式不符（字母開頭,2–12 位字母或數字）"
        return True, "按 ↵ 開始對話"

    def _revalidate(self):
        ok, msg = self.validate(self.input.text())
        self.start_btn.setEnabled(ok)
        self._restyle_button(self.start_btn)  # 依 enabled 態即時換色
        self.status.setText(msg)

    def _submit(self):
        ok, _ = self.validate(self.input.text())
        if not ok:
            return
        self.chat_requested.emit(self.input.text().strip())
        self.close()

    # ---- 開窗 / 鍵盤 ----
    def open_centered(self):
        self.input.clear()
        self._revalidate()
        parent = self.parentWidget()
        if parent is not None:
            pg = parent.frameGeometry()
            self.adjustSize()
            x = pg.center().x() - self.width() // 2
            y = pg.top() + max(90, pg.height() // 5)
            self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)
