import logging
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QSizePolicy, QStyle, QListWidgetItem, QListWidget, QAbstractItemView,
    QPushButton, QDialog, QTextEdit, QMenu
)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QAction, QDrag
from uPtt.ui.styles import get_bubble_style, get_waterball_bubble_style

logger = logging.getLogger("uPtt.ui.widgets")

class ChatBubble(QWidget):
    """
    自訂對話氣泡元件 (極致緊湊與貼合版)。
    """
    reply_requested = Signal(str, bool)  # (message_text, is_me)

    def __init__(self, text: str, time_str: str, is_me: bool = False,
                 reply_info: dict = None, send_status: str = None, parent=None):
        super().__init__(parent)
        self.is_me = is_me
        self._text = text

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 1, 0, 1)
        self.main_layout.setSpacing(4)

        self.bubble_container = QFrame()
        self.bubble_container.setStyleSheet(get_bubble_style(is_me))
        self.bubble_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        self.content_layout = QVBoxLayout(self.bubble_container)
        self.content_layout.setContentsMargins(10, 6, 10, 6)
        self.content_layout.setSpacing(4)

        # 若有回覆引用資訊，在訊息上方加一個引用區塊
        if reply_info:
            quote_frame = QFrame()
            quote_frame.setStyleSheet("""
                QFrame {
                    background-color: rgba(160, 196, 180, 0.08);
                    border-left: 2px solid #A0C4B4;
                    border-radius: 2px;
                }
            """)
            quote_layout = QVBoxLayout(quote_frame)
            quote_layout.setContentsMargins(6, 3, 6, 3)
            quote_layout.setSpacing(1)

            sender_label = QLabel(f"@{reply_info['sender']}")
            sender_label.setStyleSheet("color: #A0C4B4; font-size: 11px; font-weight: bold; background: transparent;")

            preview_label = QLabel(reply_info['preview'])
            preview_label.setStyleSheet("color: #8B949E; font-size: 11px; background: transparent;")
            preview_label.setWordWrap(True)

            quote_layout.addWidget(sender_label)
            quote_layout.addWidget(preview_label)
            self.content_layout.addWidget(quote_frame)

        self.message_label = QLabel(text)
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # 移除硬編碼寬度，改由 resizeEvent 動態控制
        self.message_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.content_layout.addWidget(self.message_label)

        self.time_label = QLabel(time_str)
        self.time_label.setStyleSheet("color: #5C6773; font-size: 10px;")
        self.time_label.setAlignment(Qt.AlignBottom)

        # 送出狀態指示標籤（僅自己的��息）
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignBottom)
        if is_me and send_status:
            if send_status == 'sent':
                self.status_label.setText("✓")
                self.status_label.setStyleSheet("color: #56D364; font-size: 10px;")
            elif send_status == 'failed':
                self.status_label.setText("✗")
                self.status_label.setStyleSheet("color: #C27474; font-size: 10px;")
            elif send_status == 'pending':
                self.status_label.setText("⏳")
                self.status_label.setStyleSheet("color: #5C6773; font-size: 10px;")

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
        """
        根據容器寬度動態調整氣泡最大寬度 (80%)，並防止提前換行。
        """
        super().resizeEvent(event)
        total_w = event.size().width()
        if total_w <= 0:
            return
            
        # 1. 計算氣泡容器的最大可用寬度 (視窗寬度的 80%)
        max_bubble_w = int(total_w * 0.8)
        
        # 2. 暫時關閉換行，計算文字在「理想狀態」下所需的寬度
        # 這能獲取文字最長一行的寬度，避免 QLabel 提前縮小
        self.message_label.setWordWrap(False)
        text_ideal_w = self.message_label.sizeHint().width()
        
        # 3. 判斷是否需要換行 (考慮到氣泡內邊距與緩衝，約 25px)
        label_max_allowed_w = max_bubble_w - 25
        
        if text_ideal_w > label_max_allowed_w:
            # 文字太長，開啟換行並限制在 80%
            self.message_label.setWordWrap(True)
            self.message_label.setFixedWidth(label_max_allowed_w)
        else:
            # 文字尚短，關閉換行並讓寬度剛好貼合文字
            self.message_label.setWordWrap(False)
            self.message_label.setFixedWidth(text_ideal_w)
            
        # 4. 關鍵：手動將最小高度設定為 sizeHint 的高度，強迫垂直佈局擴張
        # 因為 wordWrap 改變後，layout 可能不會主動偵測新的高度需求
        h = self.message_label.sizeHint().height()
        self.message_label.setMinimumHeight(h)
        
        # 通知所有層級佈局需要重新計算
        self.message_label.updateGeometry()
        self.bubble_container.updateGeometry()
        self.updateGeometry()

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

        self.bubble_container = QFrame()
        self.bubble_container.setStyleSheet(get_waterball_bubble_style(is_me))
        self.bubble_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        content_layout = QVBoxLayout(self.bubble_container)
        content_layout.setContentsMargins(10, 6, 10, 6)
        content_layout.setSpacing(2)

        # 水球標記
        tag_label = QLabel("💧 水球")
        tag_label.setStyleSheet("color: #7EB8DA; font-size: 10px; font-weight: bold; background: transparent; border: none;")
        content_layout.addWidget(tag_label)

        # 訊息內容
        self.message_label = QLabel(text)
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.message_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        content_layout.addWidget(self.message_label)

        time_label = QLabel(time_str)
        time_label.setStyleSheet("color: #5C6773; font-size: 10px;")
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
        total_w = event.size().width()
        if total_w <= 0:
            return
        max_bubble_w = int(total_w * 0.8)
        self.message_label.setWordWrap(False)
        text_ideal_w = self.message_label.sizeHint().width()
        label_max_allowed_w = max_bubble_w - 25

        if text_ideal_w > label_max_allowed_w:
            self.message_label.setWordWrap(True)
            self.message_label.setFixedWidth(label_max_allowed_w)
        else:
            self.message_label.setWordWrap(False)
            self.message_label.setFixedWidth(text_ideal_w)

        h = self.message_label.sizeHint().height()
        self.message_label.setMinimumHeight(h)
        self.message_label.updateGeometry()
        self.bubble_container.updateGeometry()
        self.updateGeometry()


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

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #1A2332;
                border: 1px solid #3D4F63;
                border-radius: 8px;
            }
        """)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 8, 12, 8)
        card_layout.setSpacing(6)

        # 標題列：✉️ 圖示 + 主旨 + 時間
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)

        icon_label = QLabel("✉️")
        icon_label.setStyleSheet("font-size: 14px; border: none;")
        icon_label.setFixedWidth(20)

        subject_label = QLabel(subject if subject else "(無主旨)")
        subject_label.setStyleSheet("""
            font-weight: bold;
            font-size: 13px;
            color: #A0C4B4;
            border: none;
        """)
        subject_label.setWordWrap(False)

        time_label = QLabel(time_str)
        time_label.setStyleSheet("color: #5C6773; font-size: 10px; border: none;")
        time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        header_layout.addWidget(icon_label)
        header_layout.addWidget(subject_label, 1)
        header_layout.addWidget(time_label)

        # 分隔線
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("background-color: #3D4F63; border: none; max-height: 1px;")

        # 內文預覽 (最多 MAX_LINES 行)
        lines = text.splitlines()
        preview_text = "\n".join(lines[:self.MAX_LINES])
        content_label = QLabel(preview_text if preview_text else " ")
        content_label.setWordWrap(True)
        content_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        content_label.setStyleSheet("color: #CDD5DF; font-size: 13px; border: none;")

        card_layout.addLayout(header_layout)
        card_layout.addWidget(divider)
        card_layout.addWidget(content_label)

        # 若超過 MAX_LINES 行，顯示「展開全文」按鈕
        if len(lines) > self.MAX_LINES:
            expand_btn = QPushButton("展開全文 ▾")
            expand_btn.setStyleSheet("""
                QPushButton {
                    color: #A0C4B4;
                    background: transparent;
                    border: none;
                    font-size: 12px;
                    text-align: left;
                    padding: 0;
                }
                QPushButton:hover {
                    color: #C5DDD4;
                    text-decoration: underline;
                }
            """)
            expand_btn.setCursor(Qt.PointingHandCursor)
            expand_btn.clicked.connect(self._show_full_content)
            card_layout.addWidget(expand_btn)

        main_layout.addWidget(card)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def _show_full_content(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"✉️  {self.subject if self.subject else '信件內容'}")
        dialog.setMinimumSize(520, 420)
        dialog.setStyleSheet("background-color: #0D1117; color: #CDD5DF;")

        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(self.full_text)
        text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #161B22;
                color: #CDD5DF;
                border: 1px solid #3D4F63;
                border-radius: 4px;
                font-size: 13px;
                font-family: "JetBrains Mono", "Cascadia Code", "SF Mono", "Menlo", "Consolas", "DejaVu Sans Mono", monospace;
                padding: 8px;
            }
        """)

        close_btn = QPushButton("關閉")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #2D3748;
                color: #CDD5DF;
                border: 1px solid #4A5568;
                border-radius: 4px;
                padding: 6px 20px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #4A5568; }
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
        self.avatar_label.setFixedSize(36, 36)
        self.avatar_label.move(0, 2)
        self.avatar_label.setAlignment(Qt.AlignCenter)
        self.avatar_label.setStyleSheet("""
            background-color: #2D3B35;
            color: #A0C4B4;
            border-radius: 18px;
            font-weight: bold;
            font-size: 14px;
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
        self.id_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.id_label.setStyleSheet("""
            font-weight: bold;
            font-size: 14px;
            color: #E6EDF3;
            background: transparent;
        """)

        self.nickname_label = QLabel(f"({nickname})" if nickname else "")
        self.nickname_label.setFixedHeight(14)
        self.nickname_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.nickname_label.setWordWrap(False)
        self.nickname_label.setStyleSheet("""
            font-size: 11px;
            color: #8B949E;
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
        self.time_label.setStyleSheet("font-size: 10px; color: #484F58; background: transparent;")

        self.unread_label = QLabel()
        self.unread_label.setFixedSize(22, 22)
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
        if self._is_online:
            self.online_dot.setStyleSheet(
                "background-color: #56D364; border-radius: 5px; border: 2px solid #0D1117;"
            )
        else:
            self.online_dot.setStyleSheet(
                "background-color: #484F58; border-radius: 5px; border: 2px solid #0D1117;"
            )

    def set_online(self, is_online: bool):
        """更新在線狀態指示點。"""
        self._is_online = is_online
        self._update_online_dot_style()

    def set_online_unknown(self):
        """副 session 降級時,把在線狀態點改為「未知」淺灰色。"""
        self.online_dot.setStyleSheet(
            "background-color: #7D8590; border-radius: 5px; border: 2px solid #0D1117;"
        )
        self.online_dot.setToolTip("使用者狀態暫時無法更新")

    def _update_pin_style(self):
        if self.is_pinned:
            self.pin_bar.setStyleSheet("background-color: #A0C4B4; border-radius: 1px;")
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
            self._is_online = False
            self._update_online_dot_style()
            self.id_label.setStyleSheet("""
                font-weight: bold;
                font-size: 14px;
                color: #484F58;
                background: transparent;
            """)
            self.nickname_label.setText("(已不存在)")
            self.nickname_label.setStyleSheet("""
                font-size: 11px;
                color: #6E4040;
                background: transparent;
            """)

    def set_last_msg_time(self, time_str: str):
        self.time_label.setText(time_str)

    def update_unread_style(self, count: int):
        self.unread_count = count
        if count > 0:
            self.unread_label.setText(f"{count}")
            self.unread_label.setStyleSheet("""
                background-color: #C27474;
                color: white;
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
