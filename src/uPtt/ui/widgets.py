import logging
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QSizePolicy, QStyle, QListWidgetItem, QListWidget, QAbstractItemView
)
from PySide6.QtCore import Qt, QSize, Signal
from uPtt.ui.styles import get_bubble_style

logger = logging.getLogger("uPtt.ui.widgets")

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
        self.bubble_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        
        self.content_layout = QVBoxLayout(self.bubble_container)
        self.content_layout.setContentsMargins(10, 6, 10, 6)
        self.content_layout.setSpacing(0)
        
        self.message_label = QLabel(text)
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # 移除硬編碼寬度，改由 resizeEvent 動態控制
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
            
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

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

class ContactItem(QWidget):
    """
    自訂會話清單項目 (全能適配、極致緊緻專業版)。
    """
    def __init__(self, ptt_id: str, nickname: str = "", unread_count: int = 0, is_pinned: bool = False, parent=None):
        super().__init__(parent)
        self.ptt_id_display = ptt_id
        self.ptt_id = ptt_id.lower()
        self.is_pinned = is_pinned
        self.unread_count = unread_count

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        # 主佈局：左右排列
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 0, 12, 0)
        main_layout.setSpacing(10)

        # 0. 釘選指示條 (左側細條)
        self.pin_bar = QFrame()
        self.pin_bar.setFixedWidth(3)
        self.pin_bar.setFixedHeight(30)
        self._update_pin_style()
        main_layout.addWidget(self.pin_bar, alignment=Qt.AlignVCenter)

        # 1. 中央文字區域 (ID + 暱稱) - 左對齊以容納長 ID
        text_container = QWidget()
        text_container.setStyleSheet("background: transparent;")
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        # ID 標籤 (左對齊)
        self.id_label = QLabel(self.ptt_id_display)
        self.id_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.id_label.setStyleSheet("""
            font-weight: bold;
            font-size: 15px;
            color: #F0F6FC;
            background: transparent;
        """)

        # 暱稱標籤 (左對齊)
        self.nickname_label = QLabel(f"({nickname})" if nickname else "")
        self.nickname_label.setFixedHeight(14)
        self.nickname_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.nickname_label.setStyleSheet("""
            font-size: 11px;
            color: #8B949E;
            background: transparent;
        """)
        self.nickname_label.setWordWrap(False)

        text_layout.addWidget(self.id_label)
        text_layout.addWidget(self.nickname_label)

        main_layout.addWidget(text_container, alignment=Qt.AlignVCenter)

        # 2. 彈性空間：將未讀標記推向右側
        main_layout.addStretch()

        # 3. 右側未讀標記
        self.unread_label = QLabel(f"{unread_count}" if unread_count > 0 else "")
        self.unread_label.setFixedSize(24, 24)
        self.unread_label.setAlignment(Qt.AlignCenter)
        self.update_unread_style(unread_count)

        main_layout.addWidget(self.unread_label, alignment=Qt.AlignVCenter)

        # 設定固定高度
        self.setFixedHeight(62)

    def update_info(self, ptt_id_display: str, nickname: str):
        """
        更新聯絡人資訊，包含正確大小寫的 ID 與暱稱。
        """
        if ptt_id_display:
            self.ptt_id_display = ptt_id_display
            self.id_label.setText(ptt_id_display)
        
        if nickname:
            self.nickname_label.setText(f"({nickname})")
        else:
            self.nickname_label.setText("")
            
        logger.debug(f"UI 已更新資訊: {self.ptt_id} -> ID={ptt_id_display}, Nick={nickname}")

    def set_nickname(self, nickname: str):
        self.update_info(self.ptt_id_display, nickname)

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
        }

    def update_unread_style(self, count: int):
        self.unread_count = count
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
            )
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
