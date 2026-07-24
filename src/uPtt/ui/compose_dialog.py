# 寫站內信 compose（artboard 29）。寫「純站內信」給任意 PTT 帳號（含非 uPtt
# 用戶）:不套 uPtt 格式外殼,經 PTTWorker.enqueue_plain_mail 送出。
#
# 所有顏色一律讀 theme.active()，不在此檔硬寫 hex。
import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton, QTextEdit,
)

from uPtt.ui import theme
from uPtt.ui.theme import FONT_STACK
from uPtt.ui.new_chat_modal import is_valid_ptt_id

logger = logging.getLogger("uPtt.ui.compose_dialog")


def _restyle_container(w):
    t = theme.active()
    w.setStyleSheet(
        f"#compose-dialog {{ background: {t['surface']}; border: 1px solid "
        f"{t['border_strong']}; border-radius: 12px; }}"
    )


def _restyle_title(w):
    t = theme.active()
    w.setStyleSheet(
        f"color: {t['text']}; font-size: 14px; font-weight: 600; "
        f"background: transparent; font-family: {FONT_STACK};"
    )


def _restyle_field(w):
    t = theme.active()
    w.setStyleSheet(
        f"background: {t['bg']}; color: {t['text']}; border: 1px solid "
        f"{t['border']}; border-radius: 8px; padding: 8px 11px; "
        f"font-family: {FONT_STACK}; font-size: 13px;"
    )


def _restyle_status(w):
    t = theme.active()
    w.setStyleSheet(
        f"color: {t['text_muted']}; font-size: 11px; background: transparent; "
        f"font-family: {FONT_STACK};"
    )


class ComposeDialog(QWidget):
    """寫站內信浮層。send_requested(receiver, title, content) 於送出時發出;
    由 MainWindow 接去 worker.enqueue_plain_mail。set_result() 回報結果。"""

    send_requested = Signal(str, str, str)

    def __init__(self, account_id: str, parent=None):
        super().__init__(parent)
        self.account_id = account_id or ""
        self.setObjectName("compose-dialog")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setWindowModality(Qt.ApplicationModal)
        self.setFixedWidth(460)

        self._build_ui()
        theme.register_restyle(self, _restyle_container)
        self._revalidate()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(9)

        title = QLabel("寫站內信")
        theme.register_restyle(title, _restyle_title)
        root.addWidget(title)

        self.recipient = QLineEdit()
        self.recipient.setPlaceholderText("收件人 PTT 帳號")
        self.recipient.setMaxLength(12)
        self.recipient.textChanged.connect(self._revalidate)
        theme.register_restyle(self.recipient, _restyle_field)
        root.addWidget(self.recipient)

        self.subject = QLineEdit()
        self.subject.setPlaceholderText("標題")
        theme.register_restyle(self.subject, _restyle_field)
        root.addWidget(self.subject)

        self.body = QTextEdit()
        self.body.setPlaceholderText("內文")
        self.body.setFixedHeight(150)
        self.body.textChanged.connect(self._revalidate)
        theme.register_restyle(self.body, _restyle_field)
        root.addWidget(self.body)

        self.status = QLabel("")
        theme.register_restyle(self.status, _restyle_status)
        root.addWidget(self.status)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.send_btn = QPushButton("送出")
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.clicked.connect(self._submit)
        theme.register_restyle(self.send_btn, self._restyle_button)
        btn_row.addWidget(self.send_btn)
        root.addLayout(btn_row)

    def _restyle_button(self, w):
        t = theme.active()
        enabled = w.isEnabled()
        bg = t["accent"] if enabled else t["surface_2"]
        fg = t["bg"] if enabled else t["text_faint"]
        w.setStyleSheet(
            f"QPushButton {{ background: {bg}; color: {fg}; border: none; "
            f"border-radius: 8px; padding: 8px 18px; font-weight: 600; "
            f"font-family: {FONT_STACK}; }}"
        )

    # ---- 驗證（純邏輯,便於測試）----
    def validate(self, recipient: str, body: str):
        """回傳 (can_send: bool, status_msg: str)。"""
        r = (recipient or "").strip()
        if not r:
            return False, ""
        if self.account_id and r.lower() == self.account_id.lower():
            return False, "不能寄給自己"
        if not is_valid_ptt_id(r):
            return False, "收件人格式不符（字母開頭,2–12 位字母或數字）"
        if not (body or "").strip():
            return False, "內文不可空白"
        return True, "按「送出」寄出站內信"

    def _revalidate(self):
        ok, msg = self.validate(self.recipient.text(), self.body.toPlainText())
        self.send_btn.setEnabled(ok)
        self._restyle_button(self.send_btn)
        # 送出中/結果訊息不被驗證訊息蓋掉:只有非 busy 時才更新提示。
        if not getattr(self, "_busy", False):
            self.status.setText(msg)

    def _submit(self):
        ok, _ = self.validate(self.recipient.text(), self.body.toPlainText())
        if not ok:
            return
        self._busy = True
        self.send_btn.setEnabled(False)
        self._restyle_button(self.send_btn)
        self.status.setText("寄送中…")
        self.send_requested.emit(
            self.recipient.text().strip(), self.subject.text().strip(), self.body.toPlainText()
        )

    def set_result(self, success: bool, message: str):
        """由 MainWindow 接 worker.compose_result 後呼叫。成功則關閉。"""
        self._busy = False
        if success:
            self.close()
        else:
            self.status.setText(message or "發送失敗")
            self._revalidate_enable()

    def _revalidate_enable(self):
        ok, _ = self.validate(self.recipient.text(), self.body.toPlainText())
        self.send_btn.setEnabled(ok)
        self._restyle_button(self.send_btn)

    # ---- 開窗 / 鍵盤 ----
    def open_centered(self):
        self._busy = False
        self.recipient.clear()
        self.subject.clear()
        self.body.clear()
        self._revalidate()
        parent = self.parentWidget()
        if parent is not None:
            pg = parent.frameGeometry()
            self.adjustSize()
            x = pg.center().x() - self.width() // 2
            y = pg.top() + max(70, pg.height() // 7)
            self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self.recipient.setFocus()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)
