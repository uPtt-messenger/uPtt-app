# 個人資料面板（artboard 31）。顯示登入者本人的 get_user 資訊。
# 資料來源:QueryWorker.refresh_self_info → user_info_result（不落 DB session）。
#
# 所有顏色一律讀 theme.active()，不在此檔硬寫 hex。
import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel,
)

from uPtt.ui import theme
from uPtt.ui.theme import FONT_STACK

logger = logging.getLogger("uPtt.ui.profile_panel")


def profile_rows(info: dict) -> list:
    """把 user_info dict 整理成 [(label, value), ...]。ID/暱稱/在線 一定顯示；
    其餘欄位有值才列。純函式,便於測試。"""
    info = info or {}
    rows = [
        ("ID", info.get("ptt_id", "") or "—"),
        ("暱稱", info.get("nickname", "") or "—"),
        ("狀態", "在線" if info.get("is_online") else "離線"),
    ]
    optional = [
        ("動態", info.get("activity", "")),
        ("登入次數", info.get("login_count", "")),
        ("最後登入", info.get("last_login_date", "")),
        ("文章數", info.get("legal_post", "")),
        ("違規數", info.get("illegal_post", "")),
        ("P 幣", info.get("money", "")),
    ]
    rows.extend((label, str(val)) for label, val in optional if val not in ("", None))
    return rows


def _restyle_container(w):
    t = theme.active()
    w.setStyleSheet(
        f"#profile-panel {{ background: {t['surface']}; border: 1px solid "
        f"{t['border_strong']}; border-radius: 12px; }}"
    )


def _restyle_title(w):
    t = theme.active()
    w.setStyleSheet(
        f"color: {t['text']}; font-size: 15px; font-weight: 700; "
        f"background: transparent; font-family: {FONT_STACK};"
    )


def _restyle_key(w):
    t = theme.active()
    w.setStyleSheet(
        f"color: {t['text_muted']}; font-size: 12px; background: transparent; "
        f"font-family: {FONT_STACK};"
    )


def _restyle_val(w):
    t = theme.active()
    w.setStyleSheet(
        f"color: {t['text']}; font-size: 12px; background: transparent; "
        f"font-family: {FONT_STACK};"
    )


class ProfilePanel(QWidget):
    """本人個人資料浮層。open_centered() 顯示;set_info(dict) 填資料;
    set_loading() 顯示查詢中。Esc 關閉。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("profile-panel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setWindowModality(Qt.ApplicationModal)
        self.setFixedWidth(360)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        self.title = QLabel("個人資料")
        theme.register_restyle(self.title, _restyle_title)
        root.addWidget(self.title)

        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(16)
        self._grid.setVerticalSpacing(8)
        self._grid.setColumnStretch(1, 1)
        root.addLayout(self._grid)

        theme.register_restyle(self, _restyle_container)
        self.set_loading()

    def _clear_grid(self):
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def set_loading(self):
        self._clear_grid()
        hint = QLabel("查詢中…")
        theme.register_restyle(hint, _restyle_key)
        self._grid.addWidget(hint, 0, 0, 1, 2)

    def set_info(self, info: dict):
        self._clear_grid()
        for r, (label, value) in enumerate(profile_rows(info)):
            key = QLabel(label)
            theme.register_restyle(key, _restyle_key)
            val = QLabel(value)
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            theme.register_restyle(val, _restyle_val)
            self._grid.addWidget(key, r, 0, Qt.AlignRight | Qt.AlignTop)
            self._grid.addWidget(val, r, 1)

    def open_centered(self):
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

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)
