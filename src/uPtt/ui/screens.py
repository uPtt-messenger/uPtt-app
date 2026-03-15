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

from uPtt import __version__, contant
from uPtt.ui.styles import MAIN_STYLE
from uPtt.ui.widgets import ChatBubble, ContactItem
from uPtt.worker import PTTWorker
from uPtt.ptt import UPttService

logger = logging.getLogger("uPtt.ui.screens")

class LoginWindow(QWidget):
    """登入畫面"""
    login_requested = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.setObjectName("login-window")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.init_ui()

    def init_ui(self):
        # 外部 layout
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)

        # 內部容器
        container = QWidget()
        container.setObjectName("login-container")
        container.setFixedWidth(400)
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(15)

        # 標題與副標題
        self.logo_label = QLabel("[ uPtt ]")
        self.logo_label.setObjectName("logo-label")
        self.logo_label.setAlignment(Qt.AlignCenter)
        
        self.subtitle_label = QLabel("開源批踢踢即時通訊軟體")
        self.subtitle_label.setObjectName("subtitle-label")
        self.subtitle_label.setAlignment(Qt.AlignCenter)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("請輸入批踢踢代號")
        self.username_input.setFixedHeight(45)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("請輸入批踢踢密碼")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFixedHeight(45)
        
        self.login_btn = QPushButton("登入連線 / LOGIN")
        self.login_btn.setFixedHeight(45)
        self.login_btn.clicked.connect(self.handle_login)
        
        self.error_label = QLabel("")
        self.error_label.setObjectName("error-label")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.hide()
        
        layout.addWidget(self.logo_label)
        layout.addWidget(self.subtitle_label)
        layout.addSpacing(10)
        layout.addWidget(self.username_input)
        layout.addWidget(self.password_input)
        layout.addWidget(self.error_label)
        layout.addWidget(self.login_btn)

        main_layout.addWidget(container)
        
        # 綁定 Enter 鍵
        self.username_input.returnPressed.connect(self.password_input.setFocus)
        self.password_input.returnPressed.connect(self.handle_login)
        
        # 預設聚焦帳號輸入
        self.username_input.setFocus()

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
    user_info_requested = Signal(str)

    def __init__(self, ptt_service: UPttService):
        super().__init__()
        self.setWindowTitle("uPtt")
        # 初始大小設為適合登入視窗的大小
        self.setFixedSize(500, 550)
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
        self.user_info_requested.connect(self.worker.get_user_info)
        
        # 連接 Worker 訊號
        self.worker.new_message_received.connect(self.on_new_message)
        self.worker.send_result.connect(self.on_send_result)
        self.worker.user_info_result.connect(self.on_user_info_result)
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
        sidebar_vbox.setSpacing(0)

        # 側邊欄頂部: 目前使用者資訊
        self.user_profile = QWidget()
        self.user_profile.setObjectName("user-profile")
        self.user_profile.setFixedHeight(50)
        self.user_profile.setStyleSheet("""
            background-color: #1A1D20;
            border-bottom: 1px solid #2D333B;
        """)
        user_layout = QHBoxLayout(self.user_profile)
        user_layout.setContentsMargins(15, 0, 15, 0)
        
        self.user_id_label = QLabel("未登入")
        self.user_id_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #E6EDF3;")
        user_layout.addWidget(self.user_id_label)
        user_layout.addStretch()
        
        sidebar_vbox.addWidget(self.user_profile)
        
        sidebar_header = QVBoxLayout() # 改為垂直排列
        sidebar_header.setContentsMargins(12, 15, 12, 12)
        sidebar_header.setSpacing(10)
        
        self.sidebar_title = QLabel("會話清單")
        self.sidebar_title.setObjectName("sidebar-title")
        self.sidebar_title.setStyleSheet("font-size: 11px; color: #8B949E; font-weight: bold; text-transform: uppercase;")
        
        # 整合式新增對話輸入框
        self.new_chat_input = QLineEdit()
        self.new_chat_input.setPlaceholderText("搜尋或新增 ID...")
        self.new_chat_input.setFixedHeight(32)
        self.new_chat_input.setObjectName("new-chat-input")
        self.new_chat_input.setStyleSheet("""
            QLineEdit#new-chat-input {
                background-color: #0D1117;
                border: 1px solid #30363D;
                border-radius: 4px;
                padding: 0 8px;
                color: #C9D1D9;
                font-size: 13px;
            }
            QLineEdit#new-chat-input:focus {
                border-color: #58A6FF;
            }
        """)
        self.new_chat_input.returnPressed.connect(self.handle_add_chat)
        
        sidebar_header.addWidget(self.sidebar_title)
        sidebar_header.addWidget(self.new_chat_input)
        
        self.contact_list = QListWidget()
        self.contact_list.setObjectName("contact-list")
        self.contact_list.itemClicked.connect(self.on_contact_selected)
        
        sidebar_vbox.addLayout(sidebar_header)
        sidebar_vbox.addWidget(self.contact_list)
        
        # 右側: 對話區
        self.chat_area = QWidget()
        self.chat_area.setObjectName("chat-area")
        chat_vbox = QVBoxLayout(self.chat_area)
        chat_vbox.setContentsMargins(0, 0, 0, 0)
        chat_vbox.setSpacing(0)
        
        # 歷史訊息滾動區 (最大化空間)
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("messages-scroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setContentsMargins(0, 0, 0, 0)
        
        # 自動捲動到底部 (監聽捲動範圍變化)
        self.scroll_area.verticalScrollBar().rangeChanged.connect(
            lambda: self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().maximum()
            )
        )
        
        self.messages_widget = QWidget()
        self.messages_widget.setObjectName("messages-container")
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setAlignment(Qt.AlignBottom)
        # 左右留一點間距增加閱讀舒適度，上下縮至最小
        self.messages_layout.setContentsMargins(15, 5, 15, 15)
        self.messages_layout.setSpacing(6)
        self.scroll_area.setWidget(self.messages_widget)
        
        # 輸入區 (單行緊湊版)
        self.input_area = QWidget()
        self.input_area.setObjectName("input-area")
        input_vbox = QVBoxLayout(self.input_area)
        # 移除頂部間距，讓它緊貼訊息區；縮小底部與左右間距
        input_vbox.setContentsMargins(10, 8, 10, 10)
        input_vbox.setSpacing(0)
        
        self.message_edit = QLineEdit() # 改用 QLineEdit 實現真正單行
        self.message_edit.setObjectName("message-edit")
        self.message_edit.setFixedHeight(36) # 標準單行高度
        self.message_edit.setPlaceholderText("輸入訊息並按下 Enter 發送...")
        self.message_edit.returnPressed.connect(self.handle_send)
        
        input_vbox.addWidget(self.message_edit)
        
        chat_vbox.addWidget(self.scroll_area, stretch=1) # 給予最大拉伸權重
        chat_vbox.addWidget(self.input_area, stretch=0) # 輸入區不拉伸
        chat_vbox.setSpacing(0)
        
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
        QShortcut(QKeySequence("Ctrl+N"), self, self.new_chat_input.setFocus)
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

    def mousePressEvent(self, event):
        """當使用者點擊視窗區域時，自動將焦點移回訊息輸入框"""
        if self.central_stack.currentIndex() == 1:
            self.message_edit.setFocus()
        super().mousePressEvent(event)

    @Slot(dict)
    def on_user_info_result(self, data):
        ptt_id = data['ptt_id'] # 正確大小寫的 ID
        nickname = data['nickname']
        logger.info(f"收到使用者資訊回傳: ID='{ptt_id}', 暱稱='{nickname}'")

        # 更新清單中的資訊 (包含正確大小寫的 ID)
        found = False
        for i in range(self.contact_list.count()):
            item = self.contact_list.item(i)
            widget = self.contact_list.itemWidget(item)
            if widget.ptt_id == ptt_id.lower():
                widget.update_info(ptt_id, nickname)
                logger.debug(f"成功更新介面清單項目: {ptt_id}")
                found = True
                break
        if not found:
            logger.warning(f"在目前會話清單中找不到對應 ID: {ptt_id}")

    def handle_add_chat(self):
        target_id = self.new_chat_input.text().strip()
        if target_id:
            # 阻止自己與自己對話
            if target_id.lower() == self.ptt_service.ptt_id.lower():
                logger.warning(f"不允許與自己對話: {target_id}")
                self.new_chat_input.clear()
                return

            self.add_or_select_contact(target_id)
            self.new_chat_input.clear() # 完成後自動清空

    @Slot(bool, str)
    def on_login_result(self, success, message):
        if success:
            # 登入成功，解除固定大小並調整為聊天視窗大小 (縮小預設寬度)
            self.setMinimumSize(800, 600)
            self.setMaximumSize(16777215, 16777215) # 解除最大值限制
            self.resize(800, 600)
            
            # 設定 Splitter 初始比例 (側邊欄較窄)
            self.splitter.setSizes([180, 620])
            
            self.central_stack.setCurrentIndex(1)
            self.setWindowTitle(f"uPtt - {self.ptt_service.ptt_id}")
            self.user_id_label.setText(f"目前登入: {self.ptt_service.ptt_id}") # 更新目前使用者
            self.message_edit.setFocus() # 登入後自動聚焦輸入框
        else:
            self.login_screen.show_error(message)

    def add_or_select_contact(self, ptt_id, nickname=""):
        ptt_id_lower = ptt_id.lower()
        
        # 檢查是否已在清單中 (不分大小寫邏輯比較)
        found_item = None
        for i in range(self.contact_list.count()):
            item = self.contact_list.item(i)
            widget = self.contact_list.itemWidget(item)
            if widget.ptt_id == ptt_id_lower:
                # 即使已存在，也更新其顯示文字 (避免使用者輸入了不同的大小寫但沒反應)
                if widget.ptt_id_display != ptt_id:
                    widget.update_info(ptt_id, nickname)
                
                found_item = item
                break
        
        if found_item:
            self.contact_list.setCurrentItem(found_item)
            self.on_contact_selected(found_item)
            # 即使已存在，也重新請求一次資訊以確保最新 (修正大小寫與暱稱)
            self.user_info_requested.emit(ptt_id_lower)
            return
        
        # 新增至清單 (雙行整齊版)
        item = QListWidgetItem(self.contact_list)
        item.setSizeHint(QSize(0, 70))
        widget = ContactItem(ptt_id, nickname)
        self.contact_list.addItem(item)
        self.contact_list.setItemWidget(item, widget)
        
        if ptt_id_lower not in self.chat_histories:
            self.chat_histories[ptt_id_lower] = []
            self.unread_counts[ptt_id_lower] = 0
            
        self.contact_list.setCurrentItem(item)
        self.on_contact_selected(item)
        
        # 嘗試獲取使用者資訊以更新暱稱與正確大小寫
        self.user_info_requested.emit(ptt_id_lower)

    def on_contact_selected(self, item):
        widget = self.contact_list.itemWidget(item)
        self.current_chat_id = widget.ptt_id
        self.unread_counts[self.current_chat_id] = 0
        widget.set_unread(0)
        self.refresh_chat_display()
        self.message_edit.setFocus()
        
        # 每次切換聯絡人時更新視窗標題
        self.setWindowTitle(f"uPtt - 與 {widget.ptt_id_display} 對話中")

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
        text = self.message_edit.text().strip()
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
        # sender_id_display 是原始大小寫，sender 是用來當字典 Key 的小寫
        sender_id_display = data['sender']
        sender = sender_id_display.lower()
        
        # 從 full_author 提取暱稱，例如 "CodingMan (小明)"
        full_author = data.get('full_author', '')
        nickname = ""
        if '(' in full_author and ')' in full_author:
            nickname = full_author[full_author.find('(')+1 : full_author.rfind(')')]
        
        if sender not in self.chat_histories:
            self.chat_histories[sender] = []
            self.unread_counts[sender] = 0
            # 如果是新聯絡人，新增到清單 (帶入原始大小寫 ID 與 暱稱)
            self.add_or_select_contact(sender_id_display, nickname)
        else:
            # 如果已存在，更新暱稱與 ID (以防對方改過大小寫或暱稱)
            for i in range(self.contact_list.count()):
                item = self.contact_list.item(i)
                widget = self.contact_list.itemWidget(item)
                if widget.ptt_id == sender:
                    widget.update_info(sender_id_display, nickname)
                    break
            
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
        
        # 桌面通知 (顯示原始大小寫 ID)
        if not self.isActiveWindow():
            self.tray_icon.showMessage(
                f"新訊息: {sender_id_display}",
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
                from PySide6.QtCore import QMetaObject
                QMetaObject.invokeMethod(self.worker, "stop", Qt.AutoConnection)
            
            # 2. 等待執行緒結束 (給予較長緩衝)
            if hasattr(self, 'ptt_thread') and self.ptt_thread.isRunning():
                self.ptt_thread.quit()
                if not self.ptt_thread.wait(3000):
                    logger.warning("Worker 執行緒未在預期時間內結束，跳過等待。")
            
            # 3. 隱藏系統匣
            if hasattr(self, 'tray_icon'):
                self.tray_icon.hide()
            
            logger.info("退出程序完成，關閉應用程式。")
            QApplication.quit()
            
        except Exception as e:
            logger.error(f"退出程式時發生異常: {e}")
            QApplication.quit()

# 為了讓 QSystemTrayIcon 能找到 QStyle，需要引入 QApplication
from PySide6.QtWidgets import QApplication, QStyle
