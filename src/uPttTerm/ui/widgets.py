import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QSize
from uPttTerm.ui.styles import get_bubble_style

logger = logging.getLogger("uPttTerm.ui.widgets")

class ChatBubble(QWidget):
    """
    自訂對話氣泡元件。
    """
    def __init__(self, text: str, time_str: str, is_me: bool = False, parent=None):
        super().__init__(parent)
        self.is_me = is_me
        
        # 主佈局
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(10, 5, 10, 5)
        
        # 氣泡內容容器
        self.bubble_container = QFrame()
        self.bubble_container.setStyleSheet(get_bubble_style(is_me))
        
        # 氣泡內的垂直佈局 (訊息內容 + 時間)
        self.content_layout = QVBoxLayout(self.bubble_container)
        self.content_layout.setContentsMargins(10, 8, 10, 8)
        self.content_layout.setSpacing(4)
        
        # 訊息文字
        self.message_label = QLabel(text)
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # 設定最大寬度，避免氣泡過長
        self.message_label.setMaximumWidth(400)
        
        # 時間標籤
        self.time_label = QLabel(time_str)
        self.time_label.setStyleSheet("color: #888888; font-size: 10px;")
        self.time_label.setAlignment(Qt.AlignRight if is_me else Qt.AlignLeft)
        
        self.content_layout.addWidget(self.message_label)
        self.content_layout.addWidget(self.time_label)
        
        # 根據是否為己方決定對齊
        if is_me:
            self.main_layout.addStretch()
            self.main_layout.addWidget(self.bubble_container)
        else:
            self.main_layout.addWidget(self.bubble_container)
            self.main_layout.addStretch()
            
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

class ContactItem(QWidget):
    """
    自訂會話清單項目。
    """
    def __init__(self, ptt_id: str, unread_count: int = 0, parent=None):
        super().__init__(parent)
        self.ptt_id = ptt_id
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.id_label = QLabel(ptt_id)
        self.id_label.setStyleSheet("font-weight: bold;")
        
        self.unread_label = QLabel(f"{unread_count}" if unread_count > 0 else "")
        self.unread_label.setFixedSize(20, 20)
        self.unread_label.setAlignment(Qt.AlignCenter)
        if unread_count > 0:
            self.unread_label.setStyleSheet("""
                background-color: #F44336;
                color: white;
                border-radius: 10px;
                font-size: 10px;
                font-weight: bold;
            """)
        
        layout.addWidget(self.id_label)
        layout.addStretch()
        layout.addWidget(self.unread_label)

    def set_unread(self, count: int):
        if count > 0:
            self.unread_label.setText(f"{count}")
            self.unread_label.setStyleSheet("""
                background-color: #F44336;
                color: white;
                border-radius: 10px;
                font-size: 10px;
                font-weight: bold;
            """)
        else:
            self.unread_label.setText("")
            self.unread_label.setStyleSheet("")
