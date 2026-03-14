import logging
from datetime import datetime
from typing import Dict, List, Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QStackedWidget, QListWidget, QListWidgetItem, QSplitter,
    QScrollArea, QTextEdit, QSystemTrayIcon, QMenu, QMessageBox, QInputDialog
)
from PySide6.QtCore import Qt, Signal, Slot, QThread, QSize, QEvent
from PySide6.QtGui import QIcon, QAction, QShortcut, QKeySequence

from uPttTerm import __version__, contant
from uPttTerm.ui.styles import MAIN_STYLE
from uPttTerm.ui.widgets import ChatBubble, ContactItem
from uPttTerm.worker import PTTWorker
from uPttTerm.ptt import UPttService

logger = logging.getLogger("uPttTerm.ui.screens")

class LoginWindow(QWidget):
    """登入畫面"""
    login_requested = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.setObjectName("login-window")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(15)

        self.logo_label = QLabel("uPttTerm")
        self.logo_label.setObjectName("logo-label")
        self.logo_label.setAlignment(Qt.AlignCenter)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("PTT 帳號")
        self.username_input.setFixedWidth(280)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("PTT 密碼")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFixedWidth(280)
        
        self.login_btn = QPushButton("登入 PTT")
        self.login_btn.setFixedWidth(280)
        self.login_btn.clicked.connect(self.handle_login)
        
        self.error_label = QLabel("")
        self.error_label.setObjectName("error-label")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.hide()
        
        layout.addWidget(self.logo_label)
        layout.addWidget(self.username_input)
        layout.addWidget(self.password_input)
        layout.addWidget(self.error_label)
        layout.addWidget(self.login_btn)
        
        # 綁定 Enter 鍵
        self.username_input.returnPressed.connect(self.password_input.setFocus)
        self.password_input.returnPressed.connect(self.handle_login)

    def handle_login(self):
        user = self.username_input.text().strip()
        pw = self.password_input.text().strip()
        if not user or not pw:
            self.show_error("請輸入完整帳號密碼")
            return
        
        self.login_btn.setEnabled(False)
        self.login_btn.setText("正在連線...")
        self.login_requested.emit(user, pw)

    def show_error(self, message: str):
        self.error_label.setText(message)
        self.error_label.show()
        self.login_btn.setEnabled(True)
        self.login_btn.setText("登入 PTT")

class MainWindow(QMainWindow):
    """主聊天畫面"""
    send_requested = Signal(str, str)

    def __init__(self, ptt_service: UPttService):
        super().__init__()
        self.setWindowTitle("uPttTerm")
        self.setMinimumSize(900, 600)
        self.ptt_service = ptt_service
        self.current_chat_id = None
        self.chat_histories: Dict[str, List[Dict]] = {}
        self.unread_counts: Dict[str, int] = {}
        
        # 初始背景執行緒
        self.init_worker()
        self.init_ui()
        self.init_tray()
        self.init_shortcuts()
        
        self.setStyleSheet(MAIN_STYLE)

    def init_worker(self):
        """啟動 PTT 背景 Worker"""
        self.ptt_thread = QThread()
        self.worker = PTTWorker(self.ptt_service)
        self.worker.moveToThread(self.ptt_thread)
        
        # 連接發信訊號 (跨執行緒會自動排程)
        self.send_requested.connect(self.worker.send_message)
        
        # 連接 Worker 訊號
        self.worker.new_message_received.connect(self.on_new_message)
        self.worker.send_result.connect(self.on_send_result)
        self.worker.status_updated.connect(lambda s: logger.info(f"Worker Status: {s}"))
        self.worker.login_result.connect(self.on_login_result)
        
        # 啟動執行緒
        self.ptt_thread.start()

    def init_ui(self):
        # 使用 QStackedWidget 切換登入與主畫面
        self.central_stack = QStackedWidget()
        self.setCentralWidget(self.central_stack)
        
        # 1. 登入畫面
        self.login_screen = LoginWindow()
        # 這裡也改用訊號連接，確保在背景執行緒登入
        self.login_screen.login_requested.connect(self.worker.do_login)
        
        # 2. 聊天畫面 (使用 Splitter)
        self.chat_screen = QWidget()
        chat_layout = QHBoxLayout(self.chat_screen)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)
        
        self.splitter = QSplitter(Qt.Horizontal)
        
        # 左側: 會話清單
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        sidebar_vbox = QVBoxLayout(self.sidebar)
        sidebar_vbox.setContentsMargins(0, 0, 0, 0)
        
        sidebar_header = QHBoxLayout()
        sidebar_header.setContentsMargins(10, 10, 10, 10)
        self.sidebar_title = QLabel("會話清單")
        self.sidebar_title.setObjectName("sidebar-title")
        self.new_chat_btn = QPushButton("+")
        self.new_chat_btn.setFixedSize(30, 30)
        self.new_chat_btn.clicked.connect(self.on_new_chat_clicked)
        sidebar_header.addWidget(self.sidebar_title)
        sidebar_header.addWidget(self.new_chat_btn)
        
        self.contact_list = QListWidget()
        self.contact_list.itemClicked.connect(self.on_contact_selected)
        
        sidebar_vbox.addLayout(sidebar_header)
        sidebar_vbox.addWidget(self.contact_list)
        
        # 右側: 對話區
        self.chat_area = QWidget()
        self.chat_area.setObjectName("chat-area")
        chat_vbox = QVBoxLayout(self.chat_area)
        chat_vbox.setContentsMargins(0, 0, 0, 0)
        chat_vbox.setSpacing(0)
        
        # 歷史訊息滾動區
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("messages-scroll")
        self.scroll_area.setWidgetResizable(True)
        self.messages_widget = QWidget()
        self.messages_widget.setObjectName("messages-container")
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.messages_widget)
        
        # 輸入區
        self.input_area = QWidget()
        self.input_area.setObjectName("input-area")
        input_vbox = QVBoxLayout(self.input_area)
        
        self.message_edit = QTextEdit()
        self.message_edit.setObjectName("message-edit")
        self.message_edit.setFixedHeight(80)
        self.message_edit.setPlaceholderText("輸入訊息... (Enter 發送, Shift+Enter 換行)")
        # 安裝事件過濾器處理 Enter 鍵
        self.message_edit.installEventFilter(self)
        
        input_vbox.addWidget(self.message_edit)
        
        chat_vbox.addWidget(self.scroll_area)
        chat_vbox.addWidget(self.input_area)
        
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.chat_area)
        self.splitter.setStretchFactor(1, 4)
        
        chat_layout.addWidget(self.splitter)
        
        self.central_stack.addWidget(self.login_screen)
        self.central_stack.addWidget(self.chat_screen)

    def init_tray(self):
        """初始化系統匣"""
        self.tray_icon = QSystemTrayIcon(self)
        # 這裡需要一個圖示，暫時使用內建
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation) if hasattr(self, 'style') else QIcon())
        
        tray_menu = QMenu()
        show_action = QAction("顯示主畫面", self)
        show_action.triggered.connect(self.showNormal)
        quit_action = QAction("完全退出", self)
        quit_action.triggered.connect(self.fully_quit)
        
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(self.on_tray_activated)

    def init_shortcuts(self):
        """初始化快捷鍵"""
        QShortcut(QKeySequence("Ctrl+N"), self, self.on_new_chat_clicked)
        QShortcut(QKeySequence("Ctrl+Q"), self, self.fully_quit)
        QShortcut(QKeySequence("Ctrl+W"), self, self.close_current_chat)

    def eventFilter(self, obj, event):
        """過濾 QTextEdit 的按鍵事件，處理發送邏輯"""
        if obj is self.message_edit and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                if event.modifiers() & Qt.ShiftModifier:
                    # Shift+Enter -> 正常換行
                    return False
                else:
                    # Enter -> 發送
                    self.handle_send()
                    return True
        return super().eventFilter(obj, event)

    @Slot(bool, str)
    def on_login_result(self, success, message):
        if success:
            self.central_stack.setCurrentIndex(1)
            self.setWindowTitle(f"uPttTerm - {self.ptt_service.ptt_id}")
        else:
            self.login_screen.show_error(message)

    def on_new_chat_clicked(self):
        target_id, ok = QInputDialog.getText(self, "新增對話", "請輸入 PTT ID:")
        if ok and target_id:
            target_id = target_id.strip().lower()
            self.add_or_select_contact(target_id)

    def add_or_select_contact(self, ptt_id):
        ptt_id = ptt_id.lower()
        # 檢查是否已在清單中
        for i in range(self.contact_list.count()):
            item = self.contact_list.item(i)
            widget = self.contact_list.itemWidget(item)
            if widget.ptt_id == ptt_id:
                self.contact_list.setCurrentItem(item)
                self.on_contact_selected(item)
                return
        
        # 新增至清單
        item = QListWidgetItem(self.contact_list)
        item.setSizeHint(QSize(0, 50))
        widget = ContactItem(ptt_id)
        self.contact_list.addItem(item)
        self.contact_list.setItemWidget(item, widget)
        
        if ptt_id not in self.chat_histories:
            self.chat_histories[ptt_id] = []
            self.unread_counts[ptt_id] = 0
            
        self.contact_list.setCurrentItem(item)
        self.on_contact_selected(item)

    def on_contact_selected(self, item):
        widget = self.contact_list.itemWidget(item)
        self.current_chat_id = widget.ptt_id
        self.unread_counts[self.current_chat_id] = 0
        widget.set_unread(0)
        self.refresh_chat_display()
        self.message_edit.setFocus()

    def refresh_chat_display(self):
        """重新渲染右側訊息區域，並根據時間戳記排序"""
        # 清除現有訊息
        while self.messages_layout.count():
            child = self.messages_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if not self.current_chat_id:
            return
            
        history = self.chat_histories.get(self.current_chat_id, [])
        # --- 新增排序邏輯：確保訊息依照時間戳記從小到大排列 ---
        history.sort(key=lambda x: x.get('timestamp', datetime.min))
        
        for msg in history:
            bubble = ChatBubble(msg['text'], msg['time'], msg['is_me'])
            self.messages_layout.addWidget(bubble)
        
        # 滾動到底部
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )

    def handle_send(self):
        text = self.message_edit.toPlainText().strip()
        if not text or not self.current_chat_id:
            return
            
        # 1. 立即顯示在 UI (這部分仍在主執行緒)
        now = datetime.now()
        now_str = now.strftime("%H:%M")
        self.chat_histories[self.current_chat_id].append({
            'text': text, 
            'time': now_str, 
            'timestamp': now,  # 儲存完整的 datetime
            'is_me': True
        })
        self.refresh_chat_display()
        self.message_edit.clear()
        
        # 2. 透過訊號觸發 Worker 背景發送 (跨執行緒安全)
        self.send_requested.emit(self.current_chat_id, text)

    @Slot(dict)
    def on_new_message(self, data):
        sender = data['sender'].lower()
        if sender not in self.chat_histories:
            self.chat_histories[sender] = []
            self.unread_counts[sender] = 0
            # 如果是新聯絡人，新增到清單
            self.add_or_select_contact(sender)
            
        self.chat_histories[sender].append({
            'text': data['text'], 
            'time': data['time'], 
            'timestamp': data.get('timestamp', datetime.now()), # 優先使用 Worker 傳來的時間
            'is_me': False
        })
        
        if self.current_chat_id == sender:
            self.refresh_chat_display()
        else:
            self.unread_counts[sender] += 1
            # 更新清單中的未讀計數
            for i in range(self.contact_list.count()):
                item = self.contact_list.item(i)
                widget = self.contact_list.itemWidget(item)
                if widget.ptt_id == sender:
                    widget.set_unread(self.unread_counts[sender])
                    break
        
        # 桌面通知
        if not self.isActiveWindow():
            self.tray_icon.showMessage(
                f"新訊息: {sender}",
                data['text'][:50],
                QSystemTrayIcon.Information,
                3000
            )

    @Slot(bool, str)
    def on_send_result(self, success, error_msg):
        if not success:
            QMessageBox.warning(self, "發送失敗", f"無法發送訊息: {error_msg}")

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.showNormal()
            self.activateWindow()

    def closeEvent(self, event):
        """關閉視窗時改為隱藏至系統匣"""
        if self.tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            self.fully_quit()

    def close_current_chat(self):
        if self.current_chat_id:
            # 簡單處理，這裡可以加入確認對話框
            self.current_chat_id = None
            self.refresh_chat_display()

    def fully_quit(self):
        """徹底退出程式，確保 PTT 登出與執行緒釋放"""
        logger.info("正在執行完全退出程序...")
        try:
            # 1. 停止 Worker (使用訊號通知)
            if hasattr(self, 'worker'):
                # 這裡可以直接呼叫，因為 Worker 的 stop 有加 @Slot 並受 QThread 事件循環保護
                # 但更保險的做法是透過 QMetaObject.invokeMethod
                from PySide6.QtCore import QMetaObject
                QMetaObject.invokeMethod(self.worker, "stop", Qt.AutoConnection)
            
            # 2. 等待執行緒結束 (給予 1.5 秒緩衝)
            if hasattr(self, 'ptt_thread') and self.ptt_thread.isRunning():
                self.ptt_thread.quit()
                if not self.ptt_thread.wait(1500):
                    logger.warning("Worker 執行緒未在預期時間內結束，強制終止。")
                    self.ptt_thread.terminate()
            
            # 3. 隱藏系統匣 (避免在工作列留殘影)
            if hasattr(self, 'tray_icon'):
                self.tray_icon.hide()
            
            logger.info("退出程序完成。")
            QApplication.quit()
            
            # 如果 QApplication.quit() 沒能成功殺掉進程 (有時發生在 macOS)，作為最後保險：
            import os
            os._exit(0)
            
        except Exception as e:
            logger.error(f"退出程式時發生異常: {e}")
            import os
            os._exit(1)

# 為了讓 QSystemTrayIcon 能找到 QStyle，需要引入 QApplication
from PySide6.QtWidgets import QApplication, QStyle
