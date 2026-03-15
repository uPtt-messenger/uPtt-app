import logging
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QFrame, QSizePolicy, QStyle, QListWidgetItem
)
from PySide6.QtCore import Qt, QSize
from uPttTerm.ui.styles import get_bubble_style

logger = logging.getLogger("uPttTerm.ui.widgets")

class ChatBubble(QWidget):
    """
    自訂對話氣泡元件 (極致緊湊與貼合版)。
    """
    def __init__(self, text: str, time_str: str, is_me: bool = False, parent=None):
        super().__init__(parent)
        self.is_me = is_me
        
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 1, 0, 1)
        self.main_layout.setSpacing(4)
        
        self.bubble_container = QFrame()
        self.bubble_container.setStyleSheet(get_bubble_style(is_me))
        self.bubble_container.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        
        self.content_layout = QVBoxLayout(self.bubble_container)
        self.content_layout.setContentsMargins(10, 6, 10, 6)
        self.content_layout.setSpacing(0)
        
        self.message_label = QLabel(text)
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.message_label.setMaximumWidth(500)
        self.message_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.content_layout.addWidget(self.message_label)
        
        self.time_label = QLabel(time_str)
        self.time_label.setStyleSheet("color: #5C6773; font-size: 10px;")
        self.time_label.setAlignment(Qt.AlignBottom)
        
        if is_me:
            self.main_layout.addStretch()
            self.main_layout.addWidget(self.time_label)
            self.main_layout.addWidget(self.bubble_container)
        else:
            self.main_layout.addWidget(self.bubble_container)
            self.main_layout.addWidget(self.time_label)
            self.main_layout.addStretch()
            
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

class ContactItem(QWidget):
    """
    自訂會話清單項目 (優化排版與字型相容性，全動態置中平衡版)。
    """
    def __init__(self, ptt_id: str, nickname: str = "", unread_count: int = 0, parent=None):
        super().__init__(parent)
        self.ptt_id_display = ptt_id
        self.ptt_id = ptt_id.lower()

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 0, 10, 0) 
        main_layout.setSpacing(0)

        # 1. 左側伸展：將內容推向中央
        main_layout.addStretch()

        # 2. 中央文字區域 (ID + 暱稱)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 0, 0, 0)

        # 垂直置中：上下加入 Stretch
        text_layout.addStretch()

        # ID 顯示 (水平置中)
        self.id_label = QLabel(self.ptt_id_display)
        self.id_label.setAlignment(Qt.AlignCenter)
        self.id_label.setStyleSheet("""
            font-weight: bold; 
            font-size: 15px; 
            color: #F0F6FC; 
            background: transparent;
        """)
        
        # 暱稱標籤 (水平置中)
        self.nickname_label = QLabel(f"({nickname})" if nickname else "")
        self.nickname_label.setFixedHeight(16) 
        self.nickname_label.setAlignment(Qt.AlignCenter)
        self.nickname_label.setStyleSheet("""
            font-size: 11px; 
            color: #8B949E; 
            background: transparent;
        """)
        self.nickname_label.setWordWrap(False)

        text_layout.addWidget(self.id_label)
        text_layout.addWidget(self.nickname_label)
        
        text_layout.addStretch()

        main_layout.addLayout(text_layout)

        # 3. 右側伸展：將內容推向中央，同時把未讀標記留給最右邊
        main_layout.addStretch()

        # 4. 右側未讀標記 (固定在右側，垂直置中)
        self.unread_label = QLabel(f"{unread_count}" if unread_count > 0 else "")
        self.unread_label.setFixedSize(20, 20)
        self.unread_label.setAlignment(Qt.AlignCenter)
        self.update_unread_style(unread_count)
        
        main_layout.addWidget(self.unread_label, alignment=Qt.AlignVCenter)
        
        # 維持穩定的總高度
        self.setMinimumHeight(65)

    def set_nickname(self, nickname: str):
        if nickname:
            self.nickname_label.setText(f"({nickname})")
            logger.debug(f"UI 已更新暱稱: {self.ptt_id} -> {nickname}")
        else:
            self.nickname_label.setText("")

    def update_unread_style(self, count: int):
        if count > 0:
            self.unread_label.setText(f"{count}")
            self.unread_label.setStyleSheet("""
                background-color: #C27474;
                color: white;
                border-radius: 10px;
                font-size: 10px;
                font-weight: bold;
            """)
        else:
            self.unread_label.setText("")
            self.unread_label.setStyleSheet("background: transparent;")

    def set_unread(self, count: int):
        self.update_unread_style(count)
