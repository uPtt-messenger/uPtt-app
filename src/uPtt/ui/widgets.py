import logging
from datetime import datetime
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QSizePolicy, QStyle, QListWidgetItem, QListWidget, QAbstractItemView,
    QPushButton, QDialog, QTextEdit, QPlainTextEdit, QMenu, QCheckBox
)
from PySide6.QtCore import Qt, QSize, Signal, QTimer
from PySide6.QtGui import QAction, QDrag, QPainter, QPen, QColor
from uPtt.ui import styles
from uPtt.ui.styles import get_bubble_style, get_waterball_bubble_style


def _apply_bubble_resize(message_label, bubble_container, owner_widget, new_size):
    """共用的氣泡 resizeEvent 邏輯：動態調整最大寬度 (80%)，防止提前換行。"""
    total_w = new_size.width()
    if total_w <= 0:
        return
    max_bubble_w = int(total_w * 0.8)
    message_label.setWordWrap(False)
    text_ideal_w = message_label.sizeHint().width()
    label_max_allowed_w = max_bubble_w - 25

    if text_ideal_w > label_max_allowed_w:
        message_label.setWordWrap(True)
        message_label.setFixedWidth(label_max_allowed_w)
    else:
        message_label.setWordWrap(False)
        message_label.setFixedWidth(text_ideal_w)

    h = message_label.sizeHint().height()
    message_label.setMinimumHeight(h)
    message_label.updateGeometry()
    bubble_container.updateGeometry()
    owner_widget.updateGeometry()

logger = logging.getLogger("uPtt.ui.widgets")


class MessageInput(QPlainTextEdit):
    """訊息輸入框：Enter 送出、Shift+Enter 換行；隨內容自動長高（上限約 4 行後內部捲動）。"""
    send_requested = Signal()

    _MAX_LINES = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("message-edit")
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTabChangesFocus(True)
        # 內容變動時重算高度
        self.document().documentLayout().documentSizeChanged.connect(self._adjust_height)
        self._adjust_height()

    def keyPressEvent(self, event):
        # Enter 送出；Shift+Enter 交給父類插入換行
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            self.send_requested.emit()
            return
        super().keyPressEvent(event)

    def _adjust_height(self, *_):
        fm = self.fontMetrics()
        line_h = fm.lineSpacing()
        doc = self.document()
        # QPlainTextEdit 的 documentSize().height() 以「行數」為單位
        line_count = int(doc.size().height()) or 1
        lines = max(1, min(self._MAX_LINES, line_count))
        # 上下 padding（QSS）+ document margin + 邊框
        extra = int(doc.documentMargin() * 2) + self.frameWidth() * 2 + 12
        self.setFixedHeight(line_h * lines + extra)


class ChatBubble(QWidget):
    """
    自訂對話氣泡元件 (極致緊湊與貼合版)。
    """
    reply_requested = Signal(str, bool)  # (message_text, is_me)

    def __init__(self, text: str, time_str: str, is_me: bool = False,
                 reply_info: Optional[dict] = None, send_status: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.is_me = is_me
        self._text = text

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 1, 0, 1)
        self.main_layout.setSpacing(4)

        self.bubble_container = QFrame()
        self.bubble_container.setStyleSheet(get_bubble_style(is_me))
        self.bubble_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        t = styles.theme()

        self.content_layout = QVBoxLayout(self.bubble_container)
        self.content_layout.setContentsMargins(12, 8, 12, 8)
        self.content_layout.setSpacing(4)

        # 若有回覆引用資訊，在訊息上方加一個引用區塊
        if reply_info:
            quote_frame = QFrame()
            quote_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {t['quoteBg']};
                    border-left: 2px solid {t['quoteBar']};
                    border-radius: 0px 4px 4px 0px;
                }}
            """)
            quote_layout = QVBoxLayout(quote_frame)
            quote_layout.setContentsMargins(9, 5, 9, 5)
            quote_layout.setSpacing(1)

            sender_label = QLabel(f"@{reply_info['sender']}")
            sender_label.setTextFormat(Qt.PlainText)  # 引用來源同屬不受信任內容
            sender_label.setStyleSheet(f"color: {t['accent']}; font-size: 10px; font-weight: bold; background: transparent;")

            preview_label = QLabel(reply_info['preview'])
            preview_label.setTextFormat(Qt.PlainText)  # 引用預覽同屬不受信任內容
            preview_label.setStyleSheet(f"color: {t['muted']}; font-size: 12px; background: transparent;")
            preview_label.setWordWrap(True)

            quote_layout.addWidget(sender_label)
            quote_layout.addWidget(preview_label)
            self.content_layout.addWidget(quote_frame)

        self.message_label = QLabel(text)
        # 站內信內容來自任意 PTT 使用者（信任邊界）；強制純文字算繪，
        # 避免預設 AutoText 把夾帶的 <img src=遠端>/<a> 當 rich text 執行。
        self.message_label.setTextFormat(Qt.PlainText)
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # 移除硬編碼寬度，改由 resizeEvent 動態控制
        self.message_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.message_label.setStyleSheet("font-size: 13px; font-weight: normal; background: transparent;")
        self.content_layout.addWidget(self.message_label)

        self.time_label = QLabel(time_str)
        self.time_label.setStyleSheet(f"color: {t['faint']}; font-size: 10px;")
        self.time_label.setAlignment(Qt.AlignBottom)

        # 送出狀態指示標籤（僅自己的訊息）
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignBottom)
        if is_me and send_status:
            if send_status == 'sent':
                self.status_label.setText("✓")
                self.status_label.setStyleSheet(f"color: {t['online']}; font-size: 10px;")
            elif send_status == 'failed':
                self.status_label.setText("✗")
                self.status_label.setStyleSheet(f"color: {t['danger']}; font-size: 10px;")
            elif send_status == 'pending':
                self.status_label.setText("⏳")
                self.status_label.setStyleSheet(f"color: {t['faint']}; font-size: 10px;")

        if is_me:
            self.main_layout.addStretch()
            if send_status:
                self.main_layout.addWidget(self.status_label)
            self.main_layout.addWidget(self.time_label)
            self.main_layout.addWidget(self.bubble_container)
        else:
            self.main_layout.addWidget(self.bubble_container)
            self.main_layout.addWidget(self.time_label)
            self.main_layout.addStretch()

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # 右鍵選單：需同時設定在 bubble_container 與 message_label 上，
        # 因為 TextSelectableByMouse 會攔截右鍵事件，不讓它冒泡到父元件
        for widget in (self, self.bubble_container, self.message_label):
            widget.setContextMenuPolicy(Qt.CustomContextMenu)
            widget.customContextMenuRequested.connect(self._show_context_menu_from_child)

    def _show_context_menu_from_child(self, pos):
        # 將子元件座標轉換為全域座標後顯示選單
        self._show_context_menu(self.sender().mapToGlobal(pos))

    def _show_context_menu(self, global_pos):
        menu = QMenu(self)
        reply_action = QAction("回覆", self)
        reply_action.triggered.connect(lambda: self.reply_requested.emit(self._text, self.is_me))
        menu.addAction(reply_action)
        menu.exec(global_pos)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        _apply_bubble_resize(self.message_label, self.bubble_container, self, event.size())

class WaterballBubble(QWidget):
    """
    水球訊息氣泡，帶有 💧 標記和藍色調背景。
    """
    def __init__(self, text: str, time_str: str, is_me: bool = False, parent=None):
        super().__init__(parent)
        self.is_me = is_me

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 1, 0, 1)
        self.main_layout.setSpacing(4)

        t = styles.theme()

        self.bubble_container = QFrame()
        self.bubble_container.setStyleSheet(get_waterball_bubble_style(is_me))
        self.bubble_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        content_layout = QVBoxLayout(self.bubble_container)
        content_layout.setContentsMargins(8, 4, 12, 4)
        content_layout.setSpacing(2)

        # 水球標記
        tag_label = QLabel("💧 水球")
        tag_label.setStyleSheet(f"color: {t['waterballInk']}; font-size: 10px; font-weight: bold; background: transparent; border: none;")
        content_layout.addWidget(tag_label)

        # 訊息內容
        self.message_label = QLabel(text)
        self.message_label.setTextFormat(Qt.PlainText)  # 不受信任內容，禁止 HTML 算繪
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.message_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.message_label.setStyleSheet("font-size: 12px; background: transparent;")
        content_layout.addWidget(self.message_label)

        time_label = QLabel(time_str)
        time_label.setStyleSheet(f"color: {t['faint']}; font-size: 10px;")
        time_label.setAlignment(Qt.AlignBottom)

        if is_me:
            self.main_layout.addStretch()
            self.main_layout.addWidget(time_label)
            self.main_layout.addWidget(self.bubble_container)
        else:
            self.main_layout.addWidget(self.bubble_container)
            self.main_layout.addWidget(time_label)
            self.main_layout.addStretch()

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        _apply_bubble_resize(self.message_label, self.bubble_container, self, event.size())


class MailCard(QWidget):
    """
    傳統信件卡片，用於顯示非 uPtt 的一般站內信。
    有明顯邊框、標題欄與 ✉️ 圖示；超過 5 行時顯示「展開全文」按鈕。
    """
    MAX_LINES = 5

    def __init__(self, subject: str, text: str, time_str: str, parent=None):
        super().__init__(parent)
        self.full_text = text
        self.subject = subject

        t = styles.theme()

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 2, 0, 2)
        main_layout.setSpacing(0)

        self.card = QFrame()
        self.card.setStyleSheet(f"""
            QFrame {{
                background-color: {t['mail']};
                border: 1px dashed {t['mailBorder']};
                border-radius: 6px;
            }}
        """)
        self.card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(14, 10, 14, 10)
        card_layout.setSpacing(6)

        # 標題列：✉️ 圖示 + 主旨 + 時間
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)

        icon_label = QLabel("✉️")
        icon_label.setStyleSheet("font-size: 14px; border: none;")
        icon_label.setFixedWidth(20)

        subject_label = QLabel(subject if subject else "(無主旨)")
        subject_label.setTextFormat(Qt.PlainText)  # 信件主旨為不受信任內容
        subject_label.setStyleSheet(f"""
            font-weight: bold;
            font-size: 12px;
            color: {t['accent']};
            border: none;
        """)
        subject_label.setWordWrap(False)

        time_label = QLabel(time_str)
        time_label.setStyleSheet(f"color: {t['faint']}; font-size: 10px; border: none;")
        time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        header_layout.addWidget(icon_label)
        header_layout.addWidget(subject_label, 1)
        header_layout.addWidget(time_label)

        # 分隔線
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet(f"background-color: {t['divider']}; border: none; max-height: 1px;")

        # 內文預覽 (最多 MAX_LINES 行)
        lines = text.splitlines()
        preview_text = "\n".join(lines[:self.MAX_LINES])
        content_label = QLabel(preview_text if preview_text else " ")
        content_label.setTextFormat(Qt.PlainText)  # 不受信任內容，禁止 HTML 算繪
        content_label.setWordWrap(True)
        content_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        content_label.setStyleSheet(f"color: {t['ink2']}; font-size: 12px; border: none;")

        card_layout.addLayout(header_layout)
        card_layout.addWidget(divider)
        card_layout.addWidget(content_label)

        # 若超過 MAX_LINES 行，顯示「展開全文」按鈕
        if len(lines) > self.MAX_LINES:
            expand_btn = QPushButton("展開全文 ▾")
            expand_btn.setStyleSheet(f"""
                QPushButton {{
                    color: {t['accent']};
                    background: transparent;
                    border: none;
                    font-size: 12px;
                    text-align: left;
                    padding: 0;
                }}
                QPushButton:hover {{
                    color: {t['ink']};
                    text-decoration: underline;
                }}
            """)
            expand_btn.setCursor(Qt.PointingHandCursor)
            expand_btn.clicked.connect(self._show_full_content)
            card_layout.addWidget(expand_btn)

        main_layout.addWidget(self.card)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        total_w = event.size().width()
        if total_w > 0:
            self.card.setMaximumWidth(int(total_w * 0.72))

    def _show_full_content(self):
        t = styles.theme()
        dialog = QDialog(self)
        dialog.setWindowTitle(f"✉️  {self.subject if self.subject else '信件內容'}")
        dialog.setMinimumSize(520, 420)
        dialog.setStyleSheet(f"background-color: {t['bg']}; color: {t['ink2']};")

        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(self.full_text)
        text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {t['surface']};
                color: {t['ink2']};
                border: 1px solid {t['border']};
                border-radius: 4px;
                font-size: 13px;
                font-family: "JetBrains Mono", "Cascadia Code", "SF Mono", "Menlo", "Consolas", "DejaVu Sans Mono", monospace;
                padding: 8px;
            }}
        """)

        close_btn = QPushButton("關閉")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['surface2']};
                color: {t['ink2']};
                border: 1px solid {t['border']};
                border-radius: 4px;
                padding: 6px 20px;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: {t['selection']}; }}
        """)
        close_btn.clicked.connect(dialog.accept)

        layout.addWidget(text_edit)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)
        dialog.exec()


class ContactItem(QWidget):
    """
    自訂會話清單項目。
    """
    def __init__(self, ptt_id: str, nickname: str = "", unread_count: int = 0, is_pinned: bool = False, last_msg_time: str = "", parent=None):
        super().__init__(parent)
        self.ptt_id_display = ptt_id
        self.ptt_id = ptt_id.lower()
        self.is_pinned = is_pinned
        self.unread_count = unread_count
        self._is_online = False
        self._is_archived = False

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        t = styles.theme()

        # 主佈局：左右排列
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 0, 10, 0)
        main_layout.setSpacing(0)

        # 0. 釘選指示條 (左側細條)
        self.pin_bar = QFrame()
        self.pin_bar.setFixedWidth(3)
        self.pin_bar.setFixedHeight(32)
        self._update_pin_style()
        main_layout.addWidget(self.pin_bar, alignment=Qt.AlignVCenter)
        main_layout.addSpacing(8)

        # 1. 頭像圓圈 (含在線狀態指示點)
        avatar_container = QWidget()
        avatar_container.setFixedSize(40, 40)
        avatar_container.setStyleSheet("background: transparent;")

        self.avatar_label = QLabel(ptt_id[0].upper() if ptt_id else "?", avatar_container)
        # 頭像字首取自對方 ID（不受信任內容），一併禁止 HTML 算繪
        self.avatar_label.setTextFormat(Qt.TextFormat.PlainText)
        self.avatar_label.setFixedSize(36, 36)
        self.avatar_label.move(0, 2)
        self.avatar_label.setAlignment(Qt.AlignCenter)
        self.avatar_label.setStyleSheet(f"""
            background-color: {t['accentSoft']};
            color: {t['ink']};
            border-radius: 8px;
            font-weight: bold;
            font-size: 13px;
        """)

        # 在線狀態指示點 (右下角)
        self.online_dot = QLabel(avatar_container)
        self.online_dot.setFixedSize(10, 10)
        self.online_dot.move(27, 28)
        self._update_online_dot_style()

        main_layout.addWidget(avatar_container, alignment=Qt.AlignVCenter)
        main_layout.addSpacing(8)

        # 2. 中央文字區域 (ID + 暱稱)
        text_container = QWidget()
        text_container.setStyleSheet("background: transparent;")
        text_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self.id_label = QLabel(self.ptt_id_display)
        # 對方 PTT ID/暱稱同屬不受信任內容，禁止 HTML 算繪；一次設定，setText 更新時沿用
        self.id_label.setTextFormat(Qt.TextFormat.PlainText)
        self.id_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.id_label.setStyleSheet(f"""
            font-weight: bold;
            font-size: 12px;
            color: {t['ink']};
            background: transparent;
        """)

        self.nickname_label = QLabel(f"({nickname})" if nickname else "")
        self.nickname_label.setTextFormat(Qt.TextFormat.PlainText)
        self.nickname_label.setFixedHeight(14)
        self.nickname_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.nickname_label.setWordWrap(False)
        self.nickname_label.setStyleSheet(f"""
            font-size: 11px;
            color: {t['muted']};
            background: transparent;
        """)

        text_layout.addWidget(self.id_label)
        text_layout.addWidget(self.nickname_label)

        main_layout.addWidget(text_container, 1, Qt.AlignVCenter)
        main_layout.addSpacing(4)

        # 3. 右側：時間（上）+ 未讀紅點（下）
        right_container = QWidget()
        right_container.setStyleSheet("background: transparent;")
        right_container.setFixedWidth(38)
        right_vbox = QVBoxLayout(right_container)
        right_vbox.setContentsMargins(0, 0, 0, 0)
        right_vbox.setSpacing(3)
        right_vbox.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)

        self.time_label = QLabel(last_msg_time)
        self.time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.time_label.setStyleSheet(f"font-size: 10px; color: {t['faint']}; background: transparent;")

        self.unread_label = QLabel()
        self.unread_label.setFixedHeight(16)
        self.unread_label.setMinimumWidth(16)
        self.unread_label.setAlignment(Qt.AlignCenter)

        right_vbox.addWidget(self.time_label)
        right_vbox.addWidget(self.unread_label, alignment=Qt.AlignHCenter)

        self.update_unread_style(unread_count)
        main_layout.addWidget(right_container, alignment=Qt.AlignVCenter)

        # 設定固定高度
        self.setFixedHeight(62)

    def update_info(self, ptt_id_display: str, nickname: str):
        """
        更新聯絡人資訊，包含正確大小寫的 ID 與暱稱。
        """
        if ptt_id_display:
            self.ptt_id_display = ptt_id_display
            self.id_label.setText(ptt_id_display)
            self.avatar_label.setText(ptt_id_display[0].upper())

        if nickname:
            self.nickname_label.setText(f"({nickname})")
        else:
            self.nickname_label.setText("")

        logger.debug(f"UI 已更新資訊: {self.ptt_id} -> ID={ptt_id_display}, Nick={nickname}")

    def set_nickname(self, nickname: str):
        self.update_info(self.ptt_id_display, nickname)

    def _update_online_dot_style(self):
        t = styles.theme()
        color = t['online'] if self._is_online else t['danger']
        self.online_dot.setStyleSheet(
            f"background-color: {color}; border-radius: 5px; border: 2px solid {t['panel']};"
        )

    def set_online(self, is_online: bool):
        """更新在線狀態指示點。"""
        self._is_online = is_online
        self._update_online_dot_style()

    def set_online_unknown(self):
        """副 session 降級時,把在線狀態點改為「未知」淺灰色。"""
        t = styles.theme()
        self.online_dot.setStyleSheet(
            f"background-color: {t['faint']}; border-radius: 5px; border: 2px solid {t['panel']};"
        )
        self.online_dot.setToolTip("使用者狀態暫時無法更新")

    def _update_pin_style(self):
        if self.is_pinned:
            t = styles.theme()
            self.pin_bar.setStyleSheet(f"background-color: {t['accent']}; border-radius: 1px;")
        else:
            self.pin_bar.setStyleSheet("background: transparent;")

    def set_pinned(self, is_pinned: bool):
        self.is_pinned = is_pinned
        self._update_pin_style()

    def get_data(self) -> dict:
        """返回此項目的完整資料，供重建時使用。"""
        nick_text = self.nickname_label.text()
        nickname = nick_text[1:-1] if nick_text.startswith("(") and nick_text.endswith(")") else nick_text
        return {
            'ptt_id': self.ptt_id,
            'ptt_id_display': self.ptt_id_display,
            'nickname': nickname,
            'unread_count': self.unread_count,
            'is_pinned': self.is_pinned,
            'is_online': self._is_online,
            'is_archived': self._is_archived,
            'last_msg_time': self.time_label.text(),
        }

    def set_archived(self, archived: bool):
        """標記此聯絡人為封存狀態（使用者已不存在）。"""
        self._is_archived = archived
        if archived:
            t = styles.theme()
            self._is_online = False
            self._update_online_dot_style()
            self.id_label.setStyleSheet(f"""
                font-weight: bold;
                font-size: 12px;
                color: {t['faint']};
                background: transparent;
            """)
            self.nickname_label.setText("(已不存在)")
            self.nickname_label.setStyleSheet(f"""
                font-size: 11px;
                color: {t['danger']};
                background: transparent;
            """)

    def set_last_msg_time(self, time_str: str):
        self.time_label.setText(time_str)

    def update_unread_style(self, count: int):
        self.unread_count = count
        if count > 0:
            t = styles.theme()
            self.unread_label.setText(f"{count}")
            self.unread_label.setStyleSheet(f"""
                background-color: {t['accent']};
                color: {t['accentInk']};
                border-radius: 8px;
                font-size: 10px;
                font-weight: bold;
                padding: 0 5px;
            """)
        else:
            self.unread_label.setText("")
            self.unread_label.setStyleSheet("background: transparent;")

    def set_unread(self, count: int):
        self.update_unread_style(count)


class ContactListWidget(QListWidget):
    """支援拖放排序的聯絡人清單，釘選項目限於釘選區內拖動。"""
    items_reordered = Signal(list)  # 發送完整的新 ptt_id 順序清單 (小寫)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.SingleSelection)

    def resizeEvent(self, event):
        """side-effect: 立即同步既有 itemWidget 的列內佈局。

        QAbstractItemView 對 setItemWidget() 掛上去的 widget，其幾何同步
        (updateEditorGeometries) 預設延後到下一輪事件迴圈/繪製才真正套用，
        於是會出現一個時間差：view 本身已經改變寬度，但列內的 ContactItem
        仍依照舊寬度排列子元件（未讀徽章因此沒有貼齊右緣，直到下一次重繪
        才自我修正）。resize 當下立即同步一次，消除這個時間差。
        """
        super().resizeEvent(event)
        self.updateEditorGeometries()
        for i in range(self.count()):
            w = self.itemWidget(self.item(i))
            if w and w.layout():
                w.layout().activate()

    def startDrag(self, supportedActions):
        """覆寫以防止 InternalMove 在拖放完成後自動刪除來源項目。
        dropEvent 已手動重建整個清單，不需要 Qt 再移除。"""
        drag = QDrag(self)
        indexes = self.selectedIndexes()
        if not indexes:
            return
        mime_data = self.model().mimeData(indexes)
        if mime_data:
            drag.setMimeData(mime_data)
        drag.exec(supportedActions)

    def _pinned_count(self) -> int:
        """回傳清單頂端連續釘選項目的數量。"""
        count = 0
        for i in range(self.count()):
            w = self.itemWidget(self.item(i))
            if w and w.is_pinned:
                count += 1
            else:
                break
        return count

    def dropEvent(self, event):
        source_item = self.currentItem()
        if not source_item:
            event.ignore()
            return

        source_row = self.row(source_item)
        source_widget = self.itemWidget(source_item)
        if not source_widget:
            event.ignore()
            return

        # 計算目標列
        drop_pos = event.position().toPoint()
        target_item = self.itemAt(drop_pos)
        target_row = self.row(target_item) if target_item else self.count() - 1

        # 限制拖放範圍：釘選只能在釘選區內，非釘選只能在非釘選區內
        pinned_count = self._pinned_count()
        if source_widget.is_pinned:
            target_row = max(0, min(target_row, max(0, pinned_count - 1)))
        else:
            target_row = max(pinned_count, min(target_row, self.count() - 1))

        if target_row == source_row:
            event.ignore()
            return

        # 記錄目前選取的項目 ID
        selected_ptt_id = None
        current = self.currentItem()
        if current:
            w = self.itemWidget(current)
            if w:
                selected_ptt_id = w.ptt_id

        # 擷取所有項目資料後執行移動
        items_data = []
        for i in range(self.count()):
            w = self.itemWidget(self.item(i))
            if w:
                items_data.append(w.get_data())

        moved = items_data.pop(source_row)
        items_data.insert(target_row, moved)

        # 清除並重建清單。removeItemWidget() 只解除綁定，widget 仍留在 viewport 底下
        # 存活，須額外 deleteLater() 才會真的釋放（否則每次拖曳都洩漏舊 ContactItem）。
        while self.count() > 0:
            item = self.item(0)
            old_widget = self.itemWidget(item)
            self.removeItemWidget(item)
            if old_widget:
                old_widget.deleteLater()
            self.takeItem(0)

        for data in items_data:
            new_item = QListWidgetItem()
            new_item.setSizeHint(QSize(0, 70))
            new_widget = ContactItem(
                ptt_id=data['ptt_id_display'],
                nickname=data['nickname'],
                unread_count=data['unread_count'],
                is_pinned=data['is_pinned'],
                last_msg_time=data.get('last_msg_time', ''),
            )
            new_widget.set_online(data.get('is_online', False))
            if data.get('is_archived'):
                new_widget.set_archived(True)
            self.addItem(new_item)
            self.setItemWidget(new_item, new_widget)

        # 還原選取狀態
        if selected_ptt_id:
            for i in range(self.count()):
                w = self.itemWidget(self.item(i))
                if w and w.ptt_id == selected_ptt_id:
                    self.setCurrentItem(self.item(i))
                    break

        new_order = [d['ptt_id'] for d in items_data]
        self.items_reordered.emit(new_order)
        event.accept()


class EmptyChatPlaceholder(QWidget):
    """未選任何對話時，聊天區中央顯示的置中空狀態（logo 方塊 + 標題 + 提示文字）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(16)
        layout.addStretch(1)

        self.logo_label = QLabel("[u]")
        self.logo_label.setFixedSize(72, 72)
        self.logo_label.setAlignment(Qt.AlignCenter)

        self.title_label = QLabel("選一個對話，或開始新的")
        self.title_label.setAlignment(Qt.AlignCenter)

        self.subtitle_label = QLabel("從左側點一位聯絡人，或在搜尋框輸入 PTT ID 開始聊天")
        # 提示文字為靜態文案，非 PTT 來源，但沿用全域「不受信任內容禁 HTML」慣例
        self.subtitle_label.setTextFormat(Qt.PlainText)
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        # 注意：wordWrap 的 QLabel 若用 setMaximumWidth() 限制寬度、又搭配
        # addWidget(..., alignment=Qt.AlignHCenter)，Qt 算出來的 sizeHint()
        # 不會考慮換行後的高度（仍當單行計算），導致換行後的第二行疊繪在
        # 第一行上面。改用 setFixedWidth() 給 sizeHint() 一個明確寬度即可正確
        # 換行；置中則交給下面 addWidget 的 AlignHCenter。
        self.subtitle_label.setFixedWidth(360)

        layout.addWidget(self.logo_label, alignment=Qt.AlignHCenter)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label, alignment=Qt.AlignHCenter)
        layout.addStretch(1)

        self.refresh_theme()

    def refresh_theme(self):
        t = styles.theme()
        self.logo_label.setStyleSheet(f"""
            background-color: {t['accentSoft']};
            color: {t['accent']};
            border-radius: 16px;
            font-family: {t['fontDisplay']};
            font-size: 36px;
            font-weight: bold;
        """)
        self.title_label.setStyleSheet(f"""
            font-family: {t['fontDisplay']};
            font-size: 22px;
            font-weight: 500;
            color: {t['ink']};
            background: transparent;
        """)
        self.subtitle_label.setStyleSheet(
            f"font-size: 12px; color: {t['muted']}; background: transparent; line-height: 1.7;"
        )


class EmptySidebarPlaceholder(QWidget):
    """聯絡人清單為空時，側欄顯示的置中提示（虛線圖示框 + 標題 + 提示文字）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(10)
        layout.addStretch(1)

        self.icon_label = QLabel("＋")
        self.icon_label.setFixedSize(40, 40)
        self.icon_label.setAlignment(Qt.AlignCenter)

        self.title_label = QLabel("還沒有對話")
        self.title_label.setAlignment(Qt.AlignCenter)

        self.subtitle_label = QLabel("在上方搜尋框輸入 PTT ID 新增聯絡人")
        self.subtitle_label.setTextFormat(Qt.PlainText)
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setWordWrap(True)

        layout.addWidget(self.icon_label, alignment=Qt.AlignHCenter)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)
        layout.addStretch(1)

        self.refresh_theme()

    def refresh_theme(self):
        t = styles.theme()
        self.icon_label.setStyleSheet(f"""
            border: 1px dashed {t['border']};
            border-radius: 9px;
            color: {t['faint']};
            font-size: 16px;
            background: transparent;
        """)
        self.title_label.setStyleSheet(
            f"font-size: 12px; font-weight: 500; color: {t['ink2']}; background: transparent;"
        )
        self.subtitle_label.setStyleSheet(
            f"font-size: 10px; color: {t['muted']}; background: transparent;"
        )


class SyncSpinner(QWidget):
    """初次同步進度畫面用的旋轉圓環（34x34，2px accent 弧線，缺口約 90 度，約 0.9 秒轉一圈）。

    Qt 沒有 CSS animation，這裡用 QTimer 逐格推進角度、QPainter 畫弧線來模擬旋轉。
    start()/stop() 由呼叫端在顯示/離開進度畫面時控制，避免畫面不可見時仍持續計時重繪。
    """

    _INTERVAL_MS = 60
    _STEP_DEG = 24  # 360 度 / (900ms / 60ms) ≈ 每格 24 度，約 0.9 秒轉一圈

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(34, 34)
        self.setStyleSheet("background: transparent;")
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(self._INTERVAL_MS)
        self._timer.timeout.connect(self._tick)

    def start(self):
        self._angle = 0
        self._timer.start()
        self.update()

    def stop(self):
        self._timer.stop()

    def _tick(self):
        self._angle = (self._angle + self._STEP_DEG) % 360
        self.update()

    def paintEvent(self, event):
        t = styles.theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(t['accent']))
        pen.setWidth(2)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        margin = 3
        rect = self.rect().adjusted(margin, margin, -margin, -margin)
        # QPainter 角度單位為 1/16 度、0 度在 3 點鐘方向、正值逆時針；缺口約 90 度
        # (270 度弧線)，缺口位置隨 _angle 推進，視覺上呈現旋轉效果。
        start_angle = int(self._angle * 16)
        span_angle = int(-270 * 16)
        painter.drawArc(rect, start_angle, span_angle)
        painter.end()


class ToggleSwitch(QCheckBox):
    """滑動式開關（設定頁用），取代預設 QCheckBox 外觀。
    軌道 32x18、radius 999，on=accent、off=中性灰；把手 14x14 白圓。
    繼承 QCheckBox 只為維持 isChecked()/setChecked()/toggled 等標準 API，
    好讓既有的存讀邏輯（db.get_config/set_config 讀寫 bool）不必改動；
    外觀完全由 paintEvent 自行繪製，不呼叫 super().paintEvent()。"""

    _W, _H = 32, 18
    _KNOB = 14
    _MARGIN = (_H - _KNOB) // 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self._W, self._H)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("background: transparent;")
        self.toggled.connect(lambda _checked: self.update())

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, event):
        t = styles.theme()  # 當下取色，不快取，切主題後下次重繪即生效
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)

        track_rect = self.rect()
        track_color = QColor(t['accent']) if self.isChecked() else QColor(t['faint'])
        painter.setBrush(track_color)
        painter.drawRoundedRect(track_rect, self._H / 2, self._H / 2)

        knob_x = (track_rect.width() - self._MARGIN - self._KNOB) if self.isChecked() else self._MARGIN
        # ponytail: 把手固定白圓，設計稿三主題通用（在 accent/faint 軌道上皆有對比），刻意不 token 化
        painter.setBrush(QColor(Qt.white))
        painter.drawEllipse(knob_x, self._MARGIN, self._KNOB, self._KNOB)
        painter.end()


class ThemeCard(QFrame):
    """單張主題預覽卡：name + tag + bg/surface/accent 色票，選中時套 accent 邊框。
    點擊發射 clicked(theme_id)；選中狀態由外層容器 (ThemePicker) 透過 set_selected() 控制。"""

    clicked = Signal(str)

    def __init__(self, theme_id: str, theme_dict: dict, parent=None):
        super().__init__(parent)
        self.theme_id = theme_id
        self._selected = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(116, 116)  # tag 最長兩行需要的高度（如 mono 的「純黑白‧排版至上」）

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 8)
        layout.setSpacing(6)

        swatch = QWidget()
        swatch.setFixedHeight(24)
        swatch.setStyleSheet("background: transparent;")
        swatch_layout = QHBoxLayout(swatch)
        swatch_layout.setContentsMargins(0, 0, 0, 0)
        swatch_layout.setSpacing(0)
        for i, color_key in enumerate(('bg', 'surface', 'accent')):
            chip = QFrame()
            radius_css = ""
            if i == 0:
                radius_css = "border-top-left-radius: 4px; border-bottom-left-radius: 4px;"
            elif i == 2:
                radius_css = "border-top-right-radius: 4px; border-bottom-right-radius: 4px;"
            chip.setStyleSheet(
                f"background-color: {theme_dict[color_key]}; border: none; {radius_css}"
            )
            swatch_layout.addWidget(chip, 1)
        layout.addWidget(swatch)

        self._name_label = QLabel(theme_dict['name'])
        layout.addWidget(self._name_label)

        self._tag_label = QLabel(theme_dict['tag'])
        self._tag_label.setWordWrap(True)
        layout.addWidget(self._tag_label)

        self.set_selected(False)

    def mousePressEvent(self, event):
        self.clicked.emit(self.theme_id)
        super().mousePressEvent(event)

    def set_selected(self, is_selected: bool):
        """套用選中/未選中外觀。卡片外框與文字一律用「目前作用中 UI 主題」
        （非卡片代表的主題）的 token 當下取色，確保在任何主題下都清晰可讀；
        只有色票 swatch 才顯示該卡代表的主題本身的顏色。"""
        self._selected = is_selected
        t = styles.theme()
        border_color = t['accent'] if is_selected else t['border']
        border_width = 2 if is_selected else 1
        self.setStyleSheet(
            f"QFrame {{ background-color: {t['surface']}; "
            f"border: {border_width}px solid {border_color}; border-radius: 8px; }}"
        )
        self._name_label.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {t['ink']}; background: transparent;"
        )
        self._tag_label.setStyleSheet(
            f"font-size: 10px; color: {t['muted']}; background: transparent;"
        )
