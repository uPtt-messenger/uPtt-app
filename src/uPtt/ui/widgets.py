import os
import logging
from datetime import datetime
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QSizePolicy, QStyle, QListWidgetItem, QListWidget, QAbstractItemView,
    QPushButton, QDialog, QTextEdit, QMenu, QApplication
)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QAction, QDrag, QColor, QPainter, QPixmap
from uPtt.ui.styles import get_bubble_style, get_waterball_bubble_style
from uPtt.ui import theme
from uPtt.ui.theme import FONT_STACK, ASSETS_DIR, render_svg
from uPtt.utils import resolve_display_name


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

class ChatBubble(QWidget):
    """
    自訂對話氣泡元件 (極致緊湊與貼合版)。
    """
    reply_requested = Signal(str, bool)  # (message_text, is_me)
    delete_requested = Signal(int)  # message_id
    retry_requested = Signal(int)  # message_id（重新傳送發送失敗的自訊息）

    def __init__(self, text: str, time_str: str, is_me: bool = False,
                 reply_info: Optional[dict] = None, send_status: Optional[str] = None,
                 message_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.is_me = is_me
        self._text = text
        self._reply_info = reply_info
        self._send_status = send_status
        self.message_id = message_id

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 1, 0, 1)
        self.main_layout.setSpacing(4)

        self.bubble_container = QFrame()
        self.bubble_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        self.content_layout = QVBoxLayout(self.bubble_container)
        self.content_layout.setContentsMargins(10, 6, 10, 6)
        self.content_layout.setSpacing(4)

        # 若有回覆引用資訊，在訊息上方加一個引用區塊
        # 本人氣泡底色現為實心 accent 綠（見 get_bubble_style），引用區塊要跟著換成
        # 深色系，否則綠字疊綠底會看不清楚；對方氣泡維持原本的綠色點綴風格。
        self.quote_frame = None
        self.quote_sender_label = None
        self.quote_preview_label = None
        if reply_info:
            self.quote_frame = QFrame()
            quote_layout = QVBoxLayout(self.quote_frame)
            quote_layout.setContentsMargins(6, 3, 6, 3)
            quote_layout.setSpacing(1)

            self.quote_sender_label = QLabel(f"@{reply_info['sender']}")
            self.quote_preview_label = QLabel(reply_info['preview'])
            self.quote_preview_label.setWordWrap(True)

            quote_layout.addWidget(self.quote_sender_label)
            quote_layout.addWidget(self.quote_preview_label)
            self.content_layout.addWidget(self.quote_frame)

        self.message_label = QLabel(text)
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # 移除硬編碼寬度，改由 resizeEvent 動態控制
        self.message_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.content_layout.addWidget(self.message_label)

        self.time_label = QLabel(time_str)
        self.time_label.setAlignment(Qt.AlignBottom)

        # 送出狀態指示標籤（僅自己的訊息）
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignBottom)
        if is_me and send_status:
            if send_status == 'sent':
                self.status_label.setText("✓")
            elif send_status == 'failed':
                self.status_label.setText("✗")
            elif send_status == 'pending':
                self.status_label.setText("⏳")

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

        theme.register_restyle(self, lambda w: w._apply_theme())

    def _apply_theme(self):
        t = theme.active()
        self.bubble_container.setStyleSheet(get_bubble_style(self.is_me))

        if self.quote_frame is not None:
            if self.is_me:
                self.quote_frame.setStyleSheet(f"""
                    QFrame {{
                        background-color: rgba(14, 17, 20, 0.14);
                        border-left: 2px solid {t['bg']};
                        border-radius: 2px;
                    }}
                """)
                quote_sender_color = t['bg']
                quote_preview_color = "rgba(14, 17, 20, 0.65)"
            else:
                self.quote_frame.setStyleSheet(f"""
                    QFrame {{
                        background-color: rgba(143, 191, 160, 0.08);
                        border-left: 2px solid {t['accent']};
                        border-radius: 2px;
                    }}
                """)
                quote_sender_color = t['accent']
                quote_preview_color = t['text_muted']
            self.quote_sender_label.setStyleSheet(
                f"color: {quote_sender_color}; font-size: 11px; font-weight: bold; background: transparent;"
            )
            self.quote_preview_label.setStyleSheet(
                f"color: {quote_preview_color}; font-size: 11px; background: transparent;"
            )

        self.time_label.setStyleSheet(f"color: {t['text_muted']}; font-size: 10px;")

        if self.is_me and self._send_status:
            if self._send_status == 'sent':
                self.status_label.setStyleSheet(f"color: {t['status_online']}; font-size: 10px;")
            elif self._send_status == 'failed':
                self.status_label.setStyleSheet(f"color: {t['danger']}; font-size: 10px;")
            elif self._send_status == 'pending':
                self.status_label.setStyleSheet(f"color: {t['msg_pending']}; font-size: 10px;")

    def _show_context_menu_from_child(self, pos):
        # 將子元件座標轉換為全域座標後顯示選單
        self._show_context_menu(self.sender().mapToGlobal(pos))

    def _build_context_menu(self) -> QMenu:
        menu = QMenu(self)

        copy_action = QAction("複製文字\t⌘C", self)
        copy_action.triggered.connect(lambda: QApplication.clipboard().setText(self._text))
        menu.addAction(copy_action)

        reply_action = QAction("引用回覆\t⇧⌘R", self)
        reply_action.triggered.connect(lambda: self.reply_requested.emit(self._text, self.is_me))
        menu.addAction(reply_action)

        if self.message_id is not None:
            menu.addSeparator()
            # 自訊息且發送失敗 → 提供「重新傳送」
            if self.is_me and self._send_status == 'failed':
                retry_action = QAction("重新傳送", self)
                retry_action.triggered.connect(lambda: self.retry_requested.emit(self.message_id))
                menu.addAction(retry_action)
            delete_action = QAction("刪除（僅本機）", self)
            delete_action.triggered.connect(lambda: self.delete_requested.emit(self.message_id))
            menu.addAction(delete_action)

        # ponytail: 設計稿另有「轉寄給…」「釘選訊息」，轉寄需要新聯絡人選擇 UI、
        # 釘選需要 message 級新欄位 + 釘選面板，兩者都延後至下一輪 Phase 3。
        return menu

    def _show_context_menu(self, global_pos):
        self._build_context_menu().exec(global_pos)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        _apply_bubble_resize(self.message_label, self.bubble_container, self, event.size())

class WaterballBubble(QWidget):
    """
    水球訊息：置中的低調細 pill（非左右對話氣泡），內容依序為
    💧 標記 / 訊息內容 / 時間，兩側以 stretch 置中，對齊設計稿。
    水球是即時提示訊息而非一般對話，故不分本人/對方分靠左靠右。
    """
    def __init__(self, text: str, time_str: str, is_me: bool = False, parent=None):
        super().__init__(parent)
        self.is_me = is_me

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 4, 0, 4)
        self.main_layout.setSpacing(0)
        self.main_layout.addStretch(1)

        self.bubble_container = QFrame()
        self.bubble_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        content_layout = QHBoxLayout(self.bubble_container)
        content_layout.setContentsMargins(10, 4, 10, 4)
        content_layout.setSpacing(6)

        # 水球標記
        self.tag_label = QLabel("💧 水球")
        content_layout.addWidget(self.tag_label)

        # 訊息內容
        self.message_label = QLabel(text)
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.message_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        content_layout.addWidget(self.message_label)

        # 時間（含分隔點，行內顯示於 pill 尾端）
        self.time_label = QLabel(f"·  {time_str}")
        content_layout.addWidget(self.time_label)

        self.main_layout.addWidget(self.bubble_container)
        self.main_layout.addStretch(1)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        theme.register_restyle(self, lambda w: w._apply_theme())

    def _apply_theme(self):
        t = theme.active()
        self.bubble_container.setStyleSheet(get_waterball_bubble_style(self.is_me))
        self.tag_label.setStyleSheet(
            f"color: {t['accent']}; font-size: 10px; font-weight: bold; background: transparent; border: none;"
        )
        self.message_label.setStyleSheet(
            f"color: {t['text_muted']}; font-size: 12px; background: transparent; border: none;"
        )
        self.time_label.setStyleSheet(
            f"color: {t['text_faint']}; font-size: 10px; background: transparent; border: none;"
        )

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

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 2, 0, 2)
        main_layout.setSpacing(0)

        self.card = QFrame()
        self.card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(12, 8, 12, 8)
        card_layout.setSpacing(6)

        # 標題列：✉️ 圖示 + 主旨 + 時間
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)

        icon_label = QLabel("✉️")
        icon_label.setStyleSheet("font-size: 14px; border: none;")
        icon_label.setFixedWidth(20)

        self.subject_label = QLabel(subject if subject else "(無主旨)")
        self.subject_label.setWordWrap(False)

        self.time_label = QLabel(time_str)
        self.time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        header_layout.addWidget(icon_label)
        header_layout.addWidget(self.subject_label, 1)
        header_layout.addWidget(self.time_label)

        # 分隔線
        self.divider = QFrame()
        self.divider.setFrameShape(QFrame.HLine)

        # 內文預覽 (最多 MAX_LINES 行)
        lines = text.splitlines()
        preview_text = "\n".join(lines[:self.MAX_LINES])
        self.content_label = QLabel(preview_text if preview_text else " ")
        self.content_label.setWordWrap(True)
        self.content_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        card_layout.addLayout(header_layout)
        card_layout.addWidget(self.divider)
        card_layout.addWidget(self.content_label)

        # 若超過 MAX_LINES 行，顯示「展開全文」按鈕
        self.expand_btn = None
        if len(lines) > self.MAX_LINES:
            self.expand_btn = QPushButton("展開全文 ▾")
            self.expand_btn.setCursor(Qt.PointingHandCursor)
            self.expand_btn.clicked.connect(self._show_full_content)
            card_layout.addWidget(self.expand_btn)

        main_layout.addWidget(self.card)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        theme.register_restyle(self, lambda w: w._apply_theme())

    def _apply_theme(self):
        t = theme.active()
        self.card.setStyleSheet(f"""
            QFrame {{
                background-color: {t['surface']};
                border: 1px solid {t['border']};
                border-radius: 8px;
            }}
        """)
        self.subject_label.setStyleSheet(f"""
            font-weight: bold;
            font-size: 13px;
            color: {t['accent']};
            border: none;
        """)
        self.time_label.setStyleSheet(f"color: {t['text_muted']}; font-size: 10px; border: none;")
        self.divider.setStyleSheet(f"background-color: {t['border']}; border: none; max-height: 1px;")
        self.content_label.setStyleSheet(f"color: {t['text']}; font-size: 13px; border: none;")
        if self.expand_btn is not None:
            self.expand_btn.setStyleSheet(f"""
                QPushButton {{
                    color: {t['accent']};
                    background: transparent;
                    border: none;
                    font-size: 12px;
                    text-align: left;
                    padding: 0;
                }}
                QPushButton:hover {{
                    color: {t['accent_tint_hover']};
                    text-decoration: underline;
                }}
            """)

    def _show_full_content(self):
        t = theme.active()
        dialog = QDialog(self)
        dialog.setWindowTitle(f"✉️  {self.subject if self.subject else '信件內容'}")
        dialog.setMinimumSize(520, 420)
        dialog.setStyleSheet(f"background-color: {t['bg']}; color: {t['text']};")

        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(self.full_text)
        text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {t['surface_2']};
                color: {t['text']};
                border: 1px solid {t['border']};
                border-radius: 4px;
                font-size: 13px;
                font-family: {FONT_STACK};
                padding: 8px;
            }}
        """)

        close_btn = QPushButton("關閉")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['surface_2']};
                color: {t['text']};
                border: 1px solid {t['border_strong']};
                border-radius: 4px;
                padding: 6px 20px;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: {t['accent_bg']}; }}
        """)
        close_btn.clicked.connect(dialog.accept)

        layout.addWidget(text_edit)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)
        dialog.exec()


class ContactItem(QWidget):
    """
    自訂會話清單項目。
    """
    def __init__(self, ptt_id: str, nickname: str = "", unread_count: int = 0, is_pinned: bool = False,
                 last_msg_time: str = "", custom_name: str = "", parent=None):
        super().__init__(parent)
        self.ptt_id_display = ptt_id
        self.ptt_id = ptt_id.lower()
        self.is_pinned = is_pinned
        self.unread_count = unread_count
        self._is_online = False
        self._online_state = 'offline'  # 'online' | 'offline' | 'unknown'
        self._is_archived = False
        self._nickname = nickname
        self._custom_name = custom_name
        self._is_muted = False

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        # 主佈局：左右排列
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 0, 10, 0)
        main_layout.setSpacing(0)

        # 0. 釘選指示條 (左側細條)
        self.pin_bar = QFrame()
        self.pin_bar.setFixedWidth(3)
        self.pin_bar.setFixedHeight(32)
        main_layout.addWidget(self.pin_bar, alignment=Qt.AlignVCenter)
        main_layout.addSpacing(8)

        # 1. 頭像圓圈 (含在線狀態指示點)
        avatar_container = QWidget()
        avatar_container.setFixedSize(40, 40)
        avatar_container.setStyleSheet("background: transparent;")

        self.avatar_label = QLabel(ptt_id[0].upper() if ptt_id else "?", avatar_container)
        self.avatar_label.setFixedSize(36, 36)
        self.avatar_label.move(0, 2)
        self.avatar_label.setAlignment(Qt.AlignCenter)

        # 在線狀態指示點 (右下角)
        self.online_dot = QLabel(avatar_container)
        self.online_dot.setFixedSize(10, 10)
        self.online_dot.move(27, 28)

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
        self.id_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.nickname_label = QLabel()
        self.nickname_label.setFixedHeight(14)
        self.nickname_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.nickname_label.setWordWrap(False)

        text_layout.addWidget(self.id_label)
        text_layout.addWidget(self.nickname_label)

        main_layout.addWidget(text_container, 1, Qt.AlignVCenter)
        main_layout.addSpacing(4)

        # 3.5 靜音圖示（僅靜音時顯示，位於文字區與時間欄之間，trailing 端）
        self.mute_icon_label = QLabel()
        self.mute_icon_label.setFixedSize(14, 14)
        self.mute_icon_label.setVisible(False)
        main_layout.addWidget(self.mute_icon_label, alignment=Qt.AlignVCenter)
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

        self.unread_label = QLabel()
        self.unread_label.setFixedSize(22, 22)
        self.unread_label.setAlignment(Qt.AlignCenter)

        right_vbox.addWidget(self.time_label)
        right_vbox.addWidget(self.unread_label, alignment=Qt.AlignHCenter)

        main_layout.addWidget(right_container, alignment=Qt.AlignVCenter)

        # 設定固定高度
        self.setFixedHeight(62)

        self._refresh_secondary_label()

        theme.register_restyle(self, lambda w: w._apply_theme())

    def _refresh_secondary_label(self):
        """依 custom_name > nickname > display_id 優先序，重繪二級標籤（括號名）。"""
        resolved = resolve_display_name(self.ptt_id_display, self._nickname, self._custom_name)
        self.nickname_label.setText(f"({resolved})" if resolved != self.ptt_id_display else "")

    def _apply_theme(self):
        t = theme.active()
        self.avatar_label.setStyleSheet(f"""
            background-color: {t['accent_bg']};
            color: {t['accent']};
            border-radius: 18px;
            font-weight: bold;
            font-size: 14px;
        """)
        self._update_online_dot_style()
        self._update_pin_style()
        self._update_text_colors()
        self.time_label.setStyleSheet(f"font-size: 10px; color: {t['text_faint']}; background: transparent;")
        self.update_unread_style(self.unread_count)
        self._update_mute_icon()

    def update_info(self, ptt_id_display: str, nickname: str):
        """
        更新聯絡人資訊，包含正確大小寫的 ID 與暱稱。
        """
        if ptt_id_display:
            self.ptt_id_display = ptt_id_display
            self.id_label.setText(ptt_id_display)
            self.avatar_label.setText(ptt_id_display[0].upper())

        self._nickname = nickname
        self._refresh_secondary_label()

        logger.debug(f"UI 已更新資訊: {self.ptt_id} -> ID={ptt_id_display}, Nick={nickname}")

    def set_nickname(self, nickname: str):
        self._nickname = nickname
        self._refresh_secondary_label()

    def set_custom_name(self, custom_name: str):
        """設定本機自訂顯示名稱（空字串 = 清除，還原為讀 PTT 暱稱）。"""
        self._custom_name = custom_name
        self._refresh_secondary_label()

    def _tinted_icon_pixmap(self, path: str, size: int, color: str) -> QPixmap:
        """把單色 SVG 依主題色重上色：先用 render_svg 取得形狀 alpha 遮罩，
        再用 SourceIn 合成模式把遮罩填成目標顏色，讓同一份 SVG 資產能套三主題。"""
        dpr = self.devicePixelRatioF()
        base = render_svg(path, size, size, dpr)
        if base.isNull():
            return base
        tinted = QPixmap(base.size())
        tinted.setDevicePixelRatio(dpr)
        tinted.fill(Qt.transparent)
        painter = QPainter(tinted)
        painter.drawPixmap(0, 0, base)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), QColor(color))
        painter.end()
        return tinted

    def _update_mute_icon(self):
        if not self._is_muted:
            self.mute_icon_label.setVisible(False)
            return
        t = theme.active()
        path = os.path.join(ASSETS_DIR, "icon_mute.svg")
        pixmap = self._tinted_icon_pixmap(path, 14, t['text_muted'])
        self.mute_icon_label.setPixmap(pixmap)
        self.mute_icon_label.setVisible(True)
        self.mute_icon_label.setToolTip("已靜音通知")

    def set_muted(self, muted: bool):
        """設定並即時反映聯絡人的靜音通知狀態（icon 隨三主題上色）。"""
        self._is_muted = muted
        self._update_mute_icon()

    def _update_online_dot_style(self):
        t = theme.active()
        color = {
            'online': t['status_online'],
            'offline': t['text_faint'],
            'unknown': t['status_unknown'],
        }[self._online_state]
        self.online_dot.setStyleSheet(
            f"background-color: {color}; border-radius: 5px; border: 2px solid {t['surface']};"
        )

    def set_online(self, is_online: bool):
        """更新在線狀態指示點。"""
        self._is_online = is_online
        self._online_state = 'online' if is_online else 'offline'
        self._update_online_dot_style()

    def set_online_unknown(self):
        """副 session 降級時,把在線狀態點改為「未知」淺灰色。"""
        self._online_state = 'unknown'
        self._update_online_dot_style()
        self.online_dot.setToolTip("使用者狀態暫時無法更新")

    def _update_pin_style(self):
        if self.is_pinned:
            self.pin_bar.setStyleSheet(f"background-color: {theme.active()['accent']}; border-radius: 1px;")
        else:
            self.pin_bar.setStyleSheet("background: transparent;")

    def set_pinned(self, is_pinned: bool):
        self.is_pinned = is_pinned
        self._update_pin_style()

    def get_data(self) -> dict:
        """返回此項目的完整資料，供重建時使用。"""
        return {
            'ptt_id': self.ptt_id,
            'ptt_id_display': self.ptt_id_display,
            'nickname': self._nickname,
            'custom_name': self._custom_name,
            'unread_count': self.unread_count,
            'is_pinned': self.is_pinned,
            'is_online': self._is_online,
            'is_archived': self._is_archived,
            'is_muted': self._is_muted,
            'last_msg_time': self.time_label.text(),
        }

    def _update_text_colors(self):
        """依目前的封存狀態重上 id_label / nickname_label 顏色。"""
        t = theme.active()
        if self._is_archived:
            self.id_label.setStyleSheet(f"""
                font-weight: bold;
                font-size: 14px;
                color: {t['text_faint']};
                background: transparent;
            """)
            self.nickname_label.setStyleSheet(f"""
                font-size: 11px;
                color: {t['archived_text']};
                background: transparent;
            """)
        else:
            self.id_label.setStyleSheet(f"""
                font-weight: bold;
                font-size: 14px;
                color: {t['text']};
                background: transparent;
            """)
            self.nickname_label.setStyleSheet(f"""
                font-size: 11px;
                color: {t['text_muted']};
                background: transparent;
            """)

    def set_archived(self, archived: bool):
        """標記此聯絡人為封存狀態（使用者已不存在）。"""
        self._is_archived = archived
        if archived:
            self._is_online = False
            self._online_state = 'offline'
            self._update_online_dot_style()
            self.nickname_label.setText("(已不存在)")
        self._update_text_colors()

    def set_last_msg_time(self, time_str: str):
        self.time_label.setText(time_str)

    def update_unread_style(self, count: int):
        self.unread_count = count
        if count > 0:
            t = theme.active()
            self.unread_label.setText(f"{count}")
            # 色值取樣自設計稿 14_main_graphite.png 的未讀徽章「3」「1」：實色底為
            # active()['accent']，文字為 active()['bg']。
            self.unread_label.setStyleSheet(f"""
                background-color: {t['accent']};
                color: {t['bg']};
                border-radius: 11px;
                font-size: 9px;
                font-weight: bold;
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

        # 清除並重建清單
        while self.count() > 0:
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
