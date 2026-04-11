import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QStackedWidget, QListWidget, QListWidgetItem, QSplitter,
    QScrollArea, QTextEdit, QSystemTrayIcon, QMenu, QMessageBox, QInputDialog
)
from PySide6.QtCore import Qt, Signal, Slot, QThread, QSize, QEvent, QUrl
from PySide6.QtGui import QIcon, QAction, QShortcut, QKeySequence, QPixmap, QPainter, QFontMetrics, QDesktopServices, QIntValidator
from PySide6.QtSvg import QSvgRenderer

from uPtt import __version__, contant
from uPtt.ui.styles import MAIN_STYLE
from uPtt.ui.widgets import ChatBubble, WaterballBubble, MailCard, ContactItem, ContactListWidget
from uPtt.utils import encode_reply, decode_reply, VersionCheckWorker
from uPtt.worker import PTTWorker
from uPtt.ptt import UPttService

logger = logging.getLogger("uPtt.ui.screens")


def _format_contact_time(time_str: str) -> str:
    """將 DATETIME 字串格式化為聯絡人列表用的簡短時間（今天顯示 HH:MM，其他顯示 M/D）。"""
    if not time_str:
        return ""
    try:
        dt = datetime.fromisoformat(str(time_str))
        if dt.date() == datetime.now().date():
            return dt.strftime("%H:%M")
        return f"{dt.month}/{dt.day}"
    except (ValueError, TypeError):
        return ""

# 資源目錄定義 (相容 PyInstaller 與 Nuitka)
if hasattr(sys, '_MEIPASS'):
    # PyInstaller 執行環境
    ASSETS_DIR = os.path.join(sys._MEIPASS, "uPtt", "ui", "assets")
elif 'nuitka' in sys.modules:
    # Nuitka 執行環境 (通常 __file__ 會指向 .app 內部的正確位置)
    # 這裡使用 os.path.dirname(__file__) 通常就能在 Nuitka 編譯後找到 assets
    ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
else:
    # 一般開發環境
    ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")


def render_svg(path: str, width: int, height: int, dpr: float = 1.0) -> QPixmap:
    """高畫質渲染 SVG 檔案到 QPixmap (支援 High-DPI)"""
    renderer = QSvgRenderer(path)
    if not renderer.isValid():
        return QPixmap()
    
    # 根據 DPR 放大實際像素大小
    pixmap = QPixmap(int(width * dpr), int(height * dpr))
    pixmap.fill(Qt.transparent)
    
    painter = QPainter(pixmap)
    # 開啟抗鋸齒與高品質渲染
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()
    
    # 設定邏輯大小，以便在 Qt 佈局中正確顯示
    pixmap.setDevicePixelRatio(dpr)
    return pixmap

class LoginWindow(QWidget):
    """登入畫面"""
    login_requested = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.setObjectName("login-window")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)

        # ── 表單容器 (無卡片，直接浮在背景上) ─────────────────────
        form = QWidget()
        form.setFixedWidth(320)
        form.setStyleSheet("background: transparent;")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(0)

        # Logo
        self.logo_label = QLabel()
        self.logo_label.setObjectName("logo-label")
        self.logo_label.setAlignment(Qt.AlignCenter)
        logo_path = os.path.join(ASSETS_DIR, "logo_horizontal.svg")
        if os.path.exists(logo_path):
            dpr = self.devicePixelRatioF() if hasattr(self, 'devicePixelRatioF') else 1.0
            self.logo_label.setPixmap(render_svg(logo_path, 220, 73, dpr))
        else:
            self.logo_label.setText("[ uPtt ]")

        subtitle = QLabel("開源 PTT 即時通訊系統")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #5C6773; font-size: 13px; letter-spacing: 2px; background: transparent;")

        # 分隔線
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #2D333B; border: none; max-height: 1px;")

        # 帳號欄位
        id_label = QLabel("PTT 代號")
        id_label.setStyleSheet("color: #8B949E; font-size: 11px; background: transparent;")

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("輸入您的 PTT ID")
        self.username_input.setFixedHeight(42)

        # 密碼欄位
        pw_label = QLabel("密碼")
        pw_label.setStyleSheet("color: #8B949E; font-size: 11px; background: transparent;")

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("••••••••")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFixedHeight(42)

        # 錯誤訊息
        self.error_label = QLabel("")
        self.error_label.setObjectName("error-label")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.hide()

        # 登入按鈕
        self.login_btn = QPushButton("連線至 PTT")
        self.login_btn.setObjectName("login-btn")
        self.login_btn.setFixedHeight(42)
        self.login_btn.clicked.connect(self.handle_login)

        # 版本
        self.version_label = QLabel(f"v{__version__}")
        self.version_label.setObjectName("version-label")
        self.version_label.setAlignment(Qt.AlignCenter)
        self.version_label.setStyleSheet("color: #484F58; font-size: 11px; background: transparent;")

        form_layout.addWidget(self.logo_label)
        form_layout.addSpacing(5)
        form_layout.addWidget(subtitle)
        form_layout.addSpacing(20)
        form_layout.addWidget(sep)
        form_layout.addSpacing(20)
        form_layout.addWidget(id_label)
        form_layout.addSpacing(5)
        form_layout.addWidget(self.username_input)
        form_layout.addSpacing(12)
        form_layout.addWidget(pw_label)
        form_layout.addSpacing(5)
        form_layout.addWidget(self.password_input)
        form_layout.addSpacing(5)
        form_layout.addWidget(self.error_label)
        form_layout.addSpacing(14)
        form_layout.addWidget(self.login_btn)
        form_layout.addSpacing(14)
        form_layout.addWidget(self.version_label)

        # 更新提示 (初始隱藏)
        self.update_label = QLabel()
        self.update_label.setAlignment(Qt.AlignCenter)
        self.update_label.setStyleSheet(
            "color: #A0C4B4; font-size: 12px; background: transparent;"
            "text-decoration: underline; padding-top: 4px;"
        )
        self.update_label.setCursor(Qt.PointingHandCursor)
        self.update_label.hide()
        self.update_label.mousePressEvent = lambda _: QDesktopServices.openUrl(
            QUrl(contant.DOWNLOAD_URL)
        )
        form_layout.addWidget(self.update_label)

        main_layout.addWidget(form)

        # 綁定 Enter 鍵
        self.username_input.returnPressed.connect(self.password_input.setFocus)
        self.password_input.returnPressed.connect(self.handle_login)

        # 預設聚焦帳號輸入
        self.username_input.setFocus()

    def handle_login(self):
        user = self.username_input.text().strip()
        pw = self.password_input.text()
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
        self.login_btn.setText("連線至 PTT")

    @Slot(str)
    def show_update_available(self, latest_version: str):
        self.update_label.setText(f"新版本 v{latest_version} 可供下載")
        self.update_label.show()

class ScanSetupScreen(QWidget):
    """首次登入信箱掃描設定畫面"""
    scan_days_selected = Signal(int)
    scan_skipped = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("scan-setup-screen")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: #0D1117;")
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)

        container = QWidget()
        container.setFixedWidth(360)
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 標題
        title = QLabel("信箱掃描")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #E6EDF3; font-size: 18px; font-weight: bold; background: transparent;")

        desc = QLabel("uPtt 需要掃描您的 PTT 信箱，\n才能載入過去的對話紀錄。")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8B949E; font-size: 13px; background: transparent; line-height: 1.5;")

        subtitle = QLabel("選擇要載入的信件範圍")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #5C6773; font-size: 13px; background: transparent;")

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #2D333B; border: none; max-height: 1px;")

        # 快速選擇按鈕
        btn_style = """
            background-color: #2D3B35; color: #A0C4B4;
            border: 1px solid #3E5149; border-radius: 8px;
            font-weight: bold; font-size: 14px; padding: 10px 20px;
        """
        btn_hover_style = """
            QPushButton:hover { background-color: #3A4D43; color: #B5D4C6; border-color: #4E6358; }
        """

        btn_row = QWidget()
        btn_row.setStyleSheet("background: transparent;")
        btn_row_layout = QHBoxLayout(btn_row)
        btn_row_layout.setContentsMargins(0, 0, 0, 0)
        btn_row_layout.setSpacing(12)

        self.btn_7d = QPushButton("7 天")
        self.btn_7d.setStyleSheet(btn_style + btn_hover_style)
        self.btn_7d.setFixedHeight(42)
        self.btn_7d.clicked.connect(lambda: self._start_scan(7))

        self.btn_30d = QPushButton("30 天")
        self.btn_30d.setStyleSheet(btn_style + btn_hover_style)
        self.btn_30d.setFixedHeight(42)
        self.btn_30d.clicked.connect(lambda: self._start_scan(30))

        self.btn_all = QPushButton("全部")
        self.btn_all.setStyleSheet(btn_style + btn_hover_style)
        self.btn_all.setFixedHeight(42)
        self.btn_all.clicked.connect(lambda: self._start_scan(0))

        btn_row_layout.addWidget(self.btn_7d)
        btn_row_layout.addWidget(self.btn_30d)
        btn_row_layout.addWidget(self.btn_all)

        # 自訂天數
        custom_row = QWidget()
        custom_row.setStyleSheet("background: transparent;")
        custom_layout = QHBoxLayout(custom_row)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.setSpacing(8)

        custom_label = QLabel("自訂：")
        custom_label.setStyleSheet("color: #8B949E; font-size: 13px; background: transparent;")

        self.custom_input = QLineEdit()
        self.custom_input.setPlaceholderText("天數")
        self.custom_input.setValidator(QIntValidator(1, 3650))
        self.custom_input.setFixedWidth(80)
        self.custom_input.setFixedHeight(38)
        self.custom_input.setStyleSheet(
            "padding: 8px; border: 1px solid #2D333B; border-radius: 7px;"
            "background-color: #161B22; color: #E6EDF3; font-size: 14px;"
        )

        day_label = QLabel("天")
        day_label.setStyleSheet("color: #8B949E; font-size: 13px; background: transparent;")

        self.btn_custom = QPushButton("開始掃描")
        self.btn_custom.setStyleSheet(btn_style + btn_hover_style)
        self.btn_custom.setFixedHeight(38)
        self.btn_custom.clicked.connect(self._start_custom_scan)
        self.custom_input.returnPressed.connect(self._start_custom_scan)

        custom_layout.addWidget(custom_label)
        custom_layout.addWidget(self.custom_input)
        custom_layout.addWidget(day_label)
        custom_layout.addStretch()
        custom_layout.addWidget(self.btn_custom)

        # 進度區塊（初始隱藏）
        self.progress_widget = QWidget()
        self.progress_widget.setStyleSheet("background: transparent;")
        progress_layout = QVBoxLayout(self.progress_widget)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(6)

        self.progress_label = QLabel("正在掃描信件...")
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setStyleSheet("color: #A0C4B4; font-size: 14px; font-weight: bold; background: transparent;")

        self.progress_count = QLabel("0 / 0")
        self.progress_count.setAlignment(Qt.AlignCenter)
        self.progress_count.setStyleSheet("color: #E6EDF3; font-size: 24px; font-weight: bold; background: transparent;")

        self.progress_title = QLabel("")
        self.progress_title.setAlignment(Qt.AlignCenter)
        self.progress_title.setStyleSheet("color: #5C6773; font-size: 12px; background: transparent;")
        self.progress_title.setWordWrap(True)
        self.progress_title.setMaximumWidth(360)

        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_count)
        progress_layout.addWidget(self.progress_title)
        self.progress_widget.hide()

        # 跳過按鈕
        self.skip_btn = QPushButton("跳過，之後再掃描")
        self.skip_btn.setCursor(Qt.PointingHandCursor)
        self.skip_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
                color: #484F58; font-size: 12px; padding: 6px 0;
            }
            QPushButton:hover { color: #8B949E; }
        """)
        self.skip_btn.clicked.connect(lambda: self.scan_skipped.emit())

        # 選項區塊
        self.options_widget = QWidget()
        self.options_widget.setStyleSheet("background: transparent;")
        options_layout = QVBoxLayout(self.options_widget)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setSpacing(14)
        options_layout.addWidget(btn_row)
        options_layout.addWidget(custom_row)
        options_layout.addWidget(self.skip_btn, alignment=Qt.AlignCenter)

        # 組裝
        layout.addWidget(title)
        layout.addSpacing(8)
        layout.addWidget(desc)
        layout.addSpacing(12)
        layout.addWidget(subtitle)
        layout.addSpacing(20)
        layout.addWidget(sep)
        layout.addSpacing(20)
        layout.addWidget(self.options_widget)
        layout.addWidget(self.progress_widget)

        main_layout.addWidget(container)

    def _start_scan(self, days):
        self.show_progress()
        self.scan_days_selected.emit(days)

    def _start_custom_scan(self):
        text = self.custom_input.text().strip()
        if not text:
            return
        days = int(text)
        if days < 1:
            return
        self._start_scan(days)

    def show_progress(self):
        self.options_widget.hide()
        self.progress_count.setText("0 / 0")
        self.progress_title.setText("")
        self.progress_widget.show()

    @Slot(int, int, str)
    def update_progress(self, current, total, title):
        self.progress_count.setText(f"{current} / {total}")
        # 截斷過長標題
        display_title = title if len(title) <= 40 else title[:37] + "..."
        self.progress_title.setText(display_title)

    def reset(self):
        self.options_widget.show()
        self.progress_widget.hide()
        self.custom_input.clear()
        self.progress_count.setText("0 / 0")
        self.progress_title.setText("")


class MainWindow(QMainWindow):
    """主聊天畫面"""
    send_requested = Signal(str, str, object)
    user_info_requested = Signal(str)
    priority_online_requested = Signal(str)
    scan_requested = Signal(int)  # scan_days
    skip_scan_requested = Signal()
    set_active_chat_requested = Signal(str)

    def __init__(self, ptt_service: UPttService, db):
        super().__init__()
        self.setWindowTitle("uPtt")
        
        # 設定視窗圖示
        icon_path = os.path.join(ASSETS_DIR, "logo_icon.svg")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        # 初始大小設為適合登入視窗的大小
        self.setFixedSize(440, 480)
        self.ptt_service = ptt_service
        self.db = db
        self.current_chat_id = None
        self.chat_histories: Dict[str, List[Dict]] = {}
        self.unread_counts: Dict[str, int] = {}
        self.blocked_users: set = set()
        self.pinned_ids: set = set()
        self.reply_to: Optional[Dict] = None  # {'sender': str, 'preview': str}
        self._user_info_cache: Dict[str, Dict] = {}  # ptt_id_lower -> user info dict
        self.session_drafts: Dict[str, str] = {}  # ptt_id_lower -> draft text
        
        # 初始化 UI 與背景執行緒
        self.init_ui()
        self.init_worker()
        self.init_tray()
        self.init_shortcuts()

        self.setStyleSheet(MAIN_STYLE)

        # 背景版本檢查
        self._start_version_check()

    def _start_version_check(self):
        self._ver_thread = QThread()
        self._ver_worker = VersionCheckWorker()
        self._ver_worker.moveToThread(self._ver_thread)
        self._ver_thread.started.connect(self._ver_worker.check)
        self._ver_worker.update_available.connect(self.login_screen.show_update_available)
        self._ver_worker.finished.connect(self._ver_thread.quit)
        self._ver_thread.start()

    def init_worker(self):
        """啟動 PTT 背景 Worker"""
        # 確保清理舊的訊號連線 (避免重複)
        if getattr(self, "_worker_signals_connected", False):
            self.send_requested.disconnect()
            self.user_info_requested.disconnect()
            self.priority_online_requested.disconnect()
            self.set_active_chat_requested.disconnect()
            self.scan_requested.disconnect()
            self.skip_scan_requested.disconnect()

        # 斷開舊 Worker → MainWindow 方向的訊號，防止記憶體洩漏
        if hasattr(self, 'worker'):
            for sig in [
                self.worker.new_message_received,
                self.worker.send_result,
                self.worker.user_info_result,
                self.worker.user_info_error,
                self.worker.status_updated,
                self.worker.login_result,
                self.worker.connection_lost,
                self.worker.connection_restored,
                self.worker.online_status_updated,
                self.worker.session_archived,
                self.worker.first_time_detected,
                self.worker.scan_progress,
                self.worker.scan_complete,
            ]:
                try:
                    sig.disconnect()
                except RuntimeError:
                    pass  # 已斷開

        self.ptt_thread = QThread()
        self.worker = PTTWorker(self.ptt_service, self.db)
        self.worker.moveToThread(self.ptt_thread)
        
        # 連接發信訊號 (跨執行緒會自動排程)
        self.send_requested.connect(self.worker.send_message)
        self.user_info_requested.connect(self.worker.get_user_info)
        self.priority_online_requested.connect(self.worker.check_online_priority)
        self.set_active_chat_requested.connect(self.worker.set_active_chat)
        self.scan_requested.connect(self.worker.do_initial_scan)
        self.skip_scan_requested.connect(self.worker.do_skip_scan)
        self._worker_signals_connected = True

        # 這裡也改用訊號連接，確保在背景執行緒登入 (且在登出重啟 Worker 後能重新連向新實例)
        if hasattr(self, "login_screen"):
            if getattr(self, "_login_signal_connected", False):
                self.login_screen.login_requested.disconnect()
            self.login_screen.login_requested.connect(self.worker.do_login)
            self._login_signal_connected = True

        # 連接 Worker 訊號
        self.worker.new_message_received.connect(self.on_new_message)
        self.worker.send_result.connect(self.on_send_result)
        self.worker.user_info_result.connect(self.on_user_info_result)
        self.worker.user_info_error.connect(self.on_user_info_error)
        self.worker.status_updated.connect(lambda s: logger.info(f"Worker Status: {s}"))
        self.worker.login_result.connect(self.on_login_result)
        self.worker.connection_lost.connect(self.on_connection_lost)
        self.worker.connection_restored.connect(self.on_connection_restored)
        self.worker.online_status_updated.connect(self.on_online_status_updated)
        self.worker.session_archived.connect(self.on_session_archived)
        self.worker.first_time_detected.connect(self._on_first_time_detected)
        self.worker.scan_progress.connect(self.scan_setup_screen.update_progress)
        self.worker.scan_complete.connect(self._on_scan_complete)

        # 掃描設定畫面的訊號
        if hasattr(self, 'scan_setup_screen'):
            if getattr(self, '_scan_signal_connected', False):
                self.scan_setup_screen.scan_days_selected.disconnect()
                self.scan_setup_screen.scan_skipped.disconnect()
            self.scan_setup_screen.scan_days_selected.connect(self._on_scan_days_selected)
            self.scan_setup_screen.scan_skipped.connect(self._on_scan_skipped)
            self._scan_signal_connected = True

        # 啟動執行緒
        self.ptt_thread.start()

    def init_ui(self):
        # 使用 QStackedWidget 切換登入與主畫面
        self.central_stack = QStackedWidget()
        self.setCentralWidget(self.central_stack)
        
        # 1. 登入畫面
        self.login_screen = LoginWindow()
        
        # 2. 聊天畫面 (使用 Splitter)
        self.chat_screen = QWidget()
        chat_layout = QHBoxLayout(self.chat_screen)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)
        
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(1)
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #21262D; }")
        
        # 左側: 會話清單
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setMinimumWidth(200)
        self.sidebar.setMaximumWidth(450)
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
        
        # 狀態指示點
        status_dot = QLabel("●")
        status_dot.setStyleSheet("color: #56D364; font-size: 9px; background: transparent;")
        status_dot.hide()
        self._status_dot = status_dot

        self.user_id_label = QLabel("uPtt")
        self.user_id_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #E6EDF3; background: transparent;")
        user_layout.addWidget(status_dot)
        user_layout.addSpacing(4)
        user_layout.addWidget(self.user_id_label)
        user_layout.addStretch()

        # 登出按鈕
        self.logout_btn = QPushButton("↪")
        self.logout_btn.setFixedSize(28, 28)
        self.logout_btn.setToolTip("登出")
        self.logout_btn.hide()
        self.logout_btn.clicked.connect(self.handle_logout)
        self.logout_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #484F58;
                font-size: 16px;
                padding: 0;
            }
            QPushButton:hover {
                color: #C27474;
            }
        """)
        user_layout.addWidget(self.logout_btn)
        
        sidebar_vbox.addWidget(self.user_profile)
        
        sidebar_header = QVBoxLayout() # 改為垂直排列
        sidebar_header.setContentsMargins(12, 15, 12, 12)
        sidebar_header.setSpacing(10)
        
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
        sidebar_header.addWidget(self.new_chat_input)
        
        self.contact_list = ContactListWidget()
        self.contact_list.setObjectName("contact-list")
        self.contact_list.itemClicked.connect(self.on_contact_selected)
        self.contact_list.items_reordered.connect(self._on_items_reordered)

        # 開啟右鍵選單
        self.contact_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.contact_list.customContextMenuRequested.connect(self.show_contact_context_menu)
        
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
        
        # 自動捲動到底部 (僅在使用者已接近底部時才觸發，避免閱讀歷史時被強制拉回)
        self.scroll_area.verticalScrollBar().rangeChanged.connect(
            self._on_scroll_range_changed
        )
        
        self.messages_widget = QWidget()
        self.messages_widget.setObjectName("messages-container")
        self.messages_layout = QVBoxLayout(self.messages_widget)
        # 移除對齊底端，改用 addStretch() 撐開空間以確保子元件寬度正確
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
        
        # 回覆預覽條 (預設隱藏)
        self.reply_bar = QWidget()
        self.reply_bar.setObjectName("reply-bar")
        self.reply_bar.hide()
        self.reply_bar.setStyleSheet("""
            QWidget#reply-bar {
                background-color: #161B22;
                border-top: 1px solid #A0C4B4;
                border-left: 3px solid #A0C4B4;
            }
        """)
        reply_bar_layout = QHBoxLayout(self.reply_bar)
        reply_bar_layout.setContentsMargins(8, 4, 8, 4)
        reply_bar_layout.setSpacing(8)

        self.reply_bar_label = QLabel()
        self.reply_bar_label.setStyleSheet("color: #8B949E; font-size: 12px;")
        self.reply_bar_label.setWordWrap(False)

        cancel_reply_btn = QPushButton("✕")
        cancel_reply_btn.setFixedSize(20, 20)
        cancel_reply_btn.setStyleSheet("""
            QPushButton { color: #8B949E; background: transparent; border: none; font-size: 14px; }
            QPushButton:hover { color: #CDD5DF; }
        """)
        cancel_reply_btn.setCursor(Qt.PointingHandCursor)
        cancel_reply_btn.clicked.connect(self.cancel_reply)

        reply_bar_layout.addWidget(self.reply_bar_label, 1)
        reply_bar_layout.addWidget(cancel_reply_btn)

        self.message_edit = QLineEdit() # 改用 QLineEdit 實現真正單行
        self.message_edit.setObjectName("message-edit")
        self.message_edit.setFixedHeight(36) # 標準單行高度
        self.message_edit.setPlaceholderText("輸入訊息並按下 Enter 發送...")
        self.message_edit.returnPressed.connect(self.handle_send)

        input_vbox.addWidget(self.reply_bar)
        input_vbox.addWidget(self.message_edit)
        
        # 聊天標題列 (選擇聯絡人後顯示)
        self.chat_header = QWidget()
        self.chat_header.setObjectName("chat-header")
        self.chat_header.setFixedHeight(52)
        self.chat_header.hide()
        chat_header_layout = QHBoxLayout(self.chat_header)
        chat_header_layout.setContentsMargins(14, 0, 14, 0)
        chat_header_layout.setSpacing(0)

        chat_header_avatar_container = QWidget()
        chat_header_avatar_container.setFixedSize(40, 40)
        chat_header_avatar_container.setStyleSheet("background: transparent;")

        self.chat_header_avatar = QLabel(chat_header_avatar_container)
        self.chat_header_avatar.setFixedSize(36, 36)
        self.chat_header_avatar.move(0, 2)
        self.chat_header_avatar.setAlignment(Qt.AlignCenter)
        self.chat_header_avatar.setStyleSheet("""
            background-color: #2D3B35;
            color: #A0C4B4;
            border-radius: 18px;
            font-weight: bold;
            font-size: 15px;
        """)

        self.chat_header_online_dot = QLabel(chat_header_avatar_container)
        self.chat_header_online_dot.setFixedSize(10, 10)
        self.chat_header_online_dot.move(27, 28)
        self.chat_header_online_dot.setStyleSheet(
            "background-color: #484F58; border-radius: 5px; border: 2px solid #0D1117;"
        )
        self.chat_header_online_dot.hide()

        chat_header_text = QWidget()
        chat_header_text.setStyleSheet("background: transparent;")
        chat_header_text_layout = QVBoxLayout(chat_header_text)
        chat_header_text_layout.setContentsMargins(10, 0, 0, 0)
        chat_header_text_layout.setSpacing(1)

        self.chat_header_id = QLabel()
        self.chat_header_id.setStyleSheet(
            "font-weight: bold; font-size: 14px; color: #E6EDF3; background: transparent;"
        )
        self.chat_header_nick = QLabel()
        self.chat_header_nick.setStyleSheet(
            "font-size: 11px; color: #8B949E; background: transparent;"
        )
        self.chat_header_nick.hide()

        chat_header_text_layout.addWidget(self.chat_header_id)
        chat_header_text_layout.addWidget(self.chat_header_nick)

        # 聊天標題列在線狀態文字
        self.chat_header_online = QLabel()
        self.chat_header_online.setStyleSheet(
            "font-size: 10px; color: #484F58; background: transparent;"
        )
        self.chat_header_online.hide()
        chat_header_text_layout.addWidget(self.chat_header_online)

        chat_header_layout.addWidget(chat_header_avatar_container)
        chat_header_layout.addWidget(chat_header_text, 1)

        chat_vbox.addWidget(self.chat_header)
        chat_vbox.addWidget(self.scroll_area, stretch=1) # 給予最大拉伸權重
        chat_vbox.addWidget(self.input_area, stretch=0) # 輸入區不拉伸
        chat_vbox.setSpacing(0)
        
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.chat_area)
        self.splitter.setStretchFactor(1, 4)
        
        chat_layout.addWidget(self.splitter)
        
        self.central_stack.addWidget(self.login_screen)     # index 0
        self.central_stack.addWidget(self.chat_screen)      # index 1
        self.scan_setup_screen = ScanSetupScreen()
        self.central_stack.addWidget(self.scan_setup_screen) # index 2

    def init_tray(self):
        """初始化系統匣"""
        self.tray_icon = QSystemTrayIcon(self)
        
        # 使用新的圖示
        icon_path = os.path.join(ASSETS_DIR, "logo_icon.svg")
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation) if hasattr(self, 'style') else QIcon())
        
        tray_menu = QMenu()
        show_action = QAction("顯示聊天", self)
        show_action.triggered.connect(self.showNormal)
        logout_action = QAction("登出", self)
        logout_action.triggered.connect(self.handle_logout)
        quit_action = QAction("關閉", self)
        quit_action.triggered.connect(self.fully_quit)
        
        rescan_action = QAction("重新掃描信箱", self)
        rescan_action.triggered.connect(self._start_rescan)

        tray_menu.addAction(show_action)
        tray_menu.addAction(rescan_action)
        tray_menu.addAction(logout_action)
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
        is_online = data.get('is_online', False)
        logger.info(f"收到使用者資訊回傳: ID='{ptt_id}', 暱稱='{nickname}', 在線={is_online}")

        # 快取使用者詳細資訊（用於 tooltip 顯示）
        self._user_info_cache[ptt_id.lower()] = data

        # 更新清單中的資訊 (包含正確大小寫的 ID 與在線狀態)
        found = False
        for i in range(self.contact_list.count()):
            item = self.contact_list.item(i)
            widget = self.contact_list.itemWidget(item)
            if widget and widget.ptt_id == ptt_id.lower():
                widget.update_info(ptt_id, nickname)
                widget.set_online(is_online)
                logger.debug(f"成功更新介面清單項目: {ptt_id}")
                self.update_sidebar_width() # 更新寬度
                found = True
                break
        if found and self.current_chat_id == ptt_id.lower():
            self._update_chat_header(ptt_id, nickname, is_online)
            self._update_chat_header_tooltip(ptt_id.lower())
        if not found:
            logger.warning(f"在目前會話清單中找不到對應 ID: {ptt_id}")

    @Slot(str, str)
    def on_user_info_error(self, ptt_id, message):
        logger.warning(f"使用者資訊獲取失敗: {ptt_id} -> {message}")

        # 彈出警告
        QMessageBox.warning(self, "查詢失敗", f"無法取得使用者 '{ptt_id}' 的資訊：\n{message}")

    @Slot(str)
    def on_session_archived(self, ptt_id_lower: str):
        """使用者不存在，將會話封存：禁止輸入、不再更新在線狀態。"""
        logger.info(f"會話封存: {ptt_id_lower}")

        # 更新聯絡人列表項目的外觀
        for i in range(self.contact_list.count()):
            item = self.contact_list.item(i)
            widget = self.contact_list.itemWidget(item)
            if widget and widget.ptt_id == ptt_id_lower:
                widget.set_archived(True)
                break

        # 如果目前正在與此 ID 對話，禁用輸入區
        if self.current_chat_id == ptt_id_lower:
            self._set_input_archived(True)

    def _set_input_archived(self, archived: bool):
        """設定輸入區的封存狀態。"""
        if archived:
            self.message_edit.setEnabled(False)
            self.message_edit.setPlaceholderText("此使用者已不存在，對話已封存")
        else:
            self.message_edit.setEnabled(True)
            self.message_edit.setPlaceholderText("輸入訊息並按下 Enter 發送...")

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

    @Slot()
    def _on_first_time_detected(self):
        """Worker 偵測到首次登入（無 last_poll_time）"""
        self._is_first_time_login = True

    def _on_scan_days_selected(self, scan_days):
        """使用者選擇掃描天數後觸發"""
        self.scan_requested.emit(scan_days)

    def _on_scan_skipped(self):
        """使用者跳過首次掃描"""
        self.skip_scan_requested.emit()

    def _on_scan_complete(self):
        """掃描完成，切換到聊天畫面"""
        self.central_stack.setCurrentIndex(1)
        self.scan_setup_screen.reset()
        self.load_sessions_from_db()
        self.message_edit.setFocus()

    def _start_rescan(self):
        """使用者從主畫面觸發重新掃描"""
        from PySide6.QtCore import QMetaObject
        QMetaObject.invokeMethod(self.worker, "stop_polling", Qt.AutoConnection)
        self.scan_setup_screen.reset()
        self.central_stack.setCurrentIndex(2)

    def on_login_result(self, success, message):
        if success:
            # 登入成功，解除固定大小並調整為聊天視窗大小
            self.setMinimumSize(800, 600)
            self.setMaximumSize(16777215, 16777215)
            self.resize(800, 600)

            corrected_id = self.ptt_service.ptt_id
            self.setWindowTitle(f"uPtt - {corrected_id}")
            self.user_id_label.setText(corrected_id)
            self._status_dot.show()
            self.logout_btn.show()

            if getattr(self, '_is_first_time_login', False):
                # 首次登入：顯示掃描設定畫面
                self._is_first_time_login = False
                self.central_stack.setCurrentIndex(2)
            else:
                # 回訪使用者：直接進入聊天畫面
                self.central_stack.setCurrentIndex(1)
                self.load_sessions_from_db()
                self.message_edit.setFocus()
        else:
            self.login_screen.show_error(message)

    @Slot()
    def on_connection_lost(self):
        """連線中斷時更新 UI 狀態"""
        logger.warning("UI: 偵測到連線中斷")
        self._status_dot.setStyleSheet("color: #D29922; font-size: 9px; background: transparent;")
        self._status_dot.setToolTip("連線中斷，正在重新連線...")
        self.setWindowTitle(f"uPtt - {self.ptt_service.ptt_id} (重新連線中...)")

    @Slot()
    def on_connection_restored(self):
        """連線恢復時更新 UI 狀態"""
        logger.info("UI: 連線已恢復")
        self._status_dot.setStyleSheet("color: #56D364; font-size: 9px; background: transparent;")
        self._status_dot.setToolTip("")
        self.setWindowTitle(f"uPtt - {self.ptt_service.ptt_id}")

    @Slot(str, bool)
    def on_online_status_updated(self, ptt_id: str, is_online: bool):
        """收到聯絡人在線狀態更新"""
        ptt_id_lower = ptt_id.lower()
        for i in range(self.contact_list.count()):
            item = self.contact_list.item(i)
            widget = self.contact_list.itemWidget(item)
            if widget and widget.ptt_id == ptt_id_lower:
                widget.set_online(is_online)
                break
        # 若正在檢視此聯絡人的對話，同步更新聊天標題列
        if self.current_chat_id == ptt_id_lower:
            self.chat_header_online.setText("● 在線上" if is_online else "● 離線")
            self.chat_header_online.setStyleSheet(
                f"font-size: 10px; color: {'#56D364' if is_online else '#484F58'}; background: transparent;"
            )
            self.chat_header_online.show()
            self.chat_header_online_dot.setStyleSheet(
                f"background-color: {'#56D364' if is_online else '#484F58'}; border-radius: 5px; border: 2px solid #0D1117;"
            )
            self.chat_header_online_dot.show()

    def load_sessions_from_db(self):
        """從資料庫載入所有可見的歷史對話。"""
        current_acc = self.ptt_service.ptt_id
        sessions = self.db.get_all_sessions(current_acc)

        # 暫時關閉信號以加速加載
        self.contact_list.blockSignals(True)
        for s in sessions:
            is_pinned = bool(s.get('is_pinned', 0))
            if is_pinned:
                self.pinned_ids.add(s['id'])

            item = QListWidgetItem(self.contact_list)
            item.setSizeHint(QSize(0, 70))
            widget = ContactItem(
                ptt_id=s['id'],
                nickname=s['nickname'] or "",
                unread_count=s['unread_count'] or 0,
                is_pinned=is_pinned,
                last_msg_time=_format_contact_time(s.get('last_message_time', '')),
            )
            # 更新顯示大小寫
            widget.update_info(s['display_id'], s['nickname'] or "")
            if s.get('is_archived'):
                widget.set_archived(True)
            self.contact_list.addItem(item)
            self.contact_list.setItemWidget(item, widget)

            # 初始化本地快取
            self.chat_histories[s['id']] = []
            self.unread_counts[s['id']] = s['unread_count'] or 0

        self.contact_list.blockSignals(False)
        logger.info(f"從資料庫載入 {len(sessions)} 個對話會話 (其中 {len(self.pinned_ids)} 個已釘選)")
        
        # 載入完成後，根據內容調整寬度
        self.update_sidebar_width()

    def update_sidebar_width(self):
        """根據清單內容的最長文字寬度，動態調整側邊欄大小。"""
        if self.contact_list.count() == 0:
            self.splitter.setSizes([200, 600])
            return

        max_w = 180 # 基本寬度
        
        # 取得字體度量物件，用於精確計算像素寬度
        # ID 使用 bold 15px, 暱稱使用 11px (QSS font-size 是 px，需用 setPixelSize)
        id_font = self.font()
        id_font.setPixelSize(15)
        id_font.setBold(True)
        id_metrics = QFontMetrics(id_font)

        nick_font = self.font()
        nick_font.setPixelSize(11)
        nick_metrics = QFontMetrics(nick_font)

        for i in range(self.contact_list.count()):
            item = self.contact_list.item(i)
            widget = self.contact_list.itemWidget(item)
            if widget:
                # 計算 ID 寬度
                id_w = id_metrics.horizontalAdvance(widget.ptt_id_display)

                # 計算暱稱寬度 (包含括號)
                nick_text = widget.nickname_label.text()
                nick_w = nick_metrics.horizontalAdvance(nick_text)

                # 固定佔用: 8(左邊距) + 3(pin_bar) + 8(spacing) + 36(avatar) + 10(spacing)
                #           + 4(spacing) + 38(right_container) + 10(右邊距) + 15(scrollbar) + 20(緩衝)
                item_w = max(id_w, nick_w) + 152
                if item_w > max_w:
                    max_w = item_w
        
        # 限制在合理範圍內
        final_w = max(150, min(max_w, 450))
        logger.debug(f"動態調整側邊欄寬度至: {final_w}px (內容最寬: {max_w}px)")
        
        # 取得 splitter 實際寬度，以精確分配比例
        current_total_w = self.splitter.width()
        if current_total_w > 0:
            self.splitter.setSizes([final_w, current_total_w - final_w])

    def add_or_select_contact(self, ptt_id, nickname=""):
        ptt_id_lower = ptt_id.lower()
        
        # 檢查是否已在清單中 (不分大小寫邏輯比較)
        found_item = None
        for i in range(self.contact_list.count()):
            item = self.contact_list.item(i)
            widget = self.contact_list.itemWidget(item)
            if widget and widget.ptt_id == ptt_id_lower:
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
        self.update_sidebar_width() # 立即嘗試更新一次寬度

    def on_contact_selected(self, item):
        widget = self.contact_list.itemWidget(item)
        if not widget:
            return

        # 儲存當前對話的草稿
        if self.current_chat_id:
            self.session_drafts[self.current_chat_id] = self.message_edit.text()

        self.current_chat_id = widget.ptt_id
        current_acc = self.ptt_service.ptt_id

        # 通知 worker 開始高頻在線輪詢
        self.set_active_chat_requested.emit(self.current_chat_id)

        # 標記已讀並重置計數
        self.db.mark_as_read(current_acc, self.current_chat_id)
        self.unread_counts[self.current_chat_id] = 0
        widget.set_unread(0)
        
        # 從資料庫載入歷史訊息
        messages = self.db.get_messages(current_acc, self.current_chat_id)
        parsed = []
        for m in messages:
            ts = datetime.fromisoformat(m['timestamp']) if isinstance(m['timestamp'], str) else m['timestamp']
            reply_info, actual_text = decode_reply(m['content'])
            parsed.append({
                'text': actual_text,
                'time': ts.strftime("%H:%M"),
                'timestamp': ts,
                'is_me': bool(m['is_me']),
                'mail_type': m.get('mail_type', 'uptt'),
                'subject': m.get('subject', ''),
                'reply_info': reply_info,
            })
        self.chat_histories[self.current_chat_id] = parsed

        # 切換聯絡人時清除回覆狀態並還原草稿
        self.cancel_reply()
        self.message_edit.setText(self.session_drafts.get(self.current_chat_id, ""))
        self.refresh_chat_display()

        # 檢查是否為封存會話
        is_archived = getattr(widget, '_is_archived', False)
        self._set_input_archived(is_archived)

        if not is_archived:
            self.message_edit.setFocus()

        # 每次切換聯絡人時更新視窗標題與聊天標題列
        self.setWindowTitle(f"uPtt - 與 {widget.ptt_id_display} 對話中")
        nick_text = widget.nickname_label.text()
        nickname = nick_text[1:-1] if nick_text.startswith("(") and nick_text.endswith(")") else ""
        self._update_chat_header(widget.ptt_id_display, nickname, widget._is_online)
        self._update_chat_header_tooltip(widget.ptt_id)

        # 封存會話不需要查詢在線狀態
        if not is_archived:
            self.priority_online_requested.emit(widget.ptt_id)

    def _update_chat_header(self, display_id: str, nickname: str, is_online: Optional[bool] = None):
        """更新聊天標題列的聯絡人資訊。"""
        first_letter = display_id[0].upper() if display_id else "?"
        self.chat_header_avatar.setText(first_letter)
        self.chat_header_id.setText(display_id)
        if nickname:
            self.chat_header_nick.setText(nickname)
            self.chat_header_nick.show()
        else:
            self.chat_header_nick.hide()
        if is_online is not None:
            if is_online:
                self.chat_header_online.setText("● 在線上")
                self.chat_header_online.setStyleSheet(
                    "font-size: 10px; color: #56D364; background: transparent;"
                )
                self.chat_header_online_dot.setStyleSheet(
                    "background-color: #56D364; border-radius: 5px; border: 2px solid #0D1117;"
                )
            else:
                self.chat_header_online.setText("● 離線")
                self.chat_header_online.setStyleSheet(
                    "font-size: 10px; color: #484F58; background: transparent;"
                )
                self.chat_header_online_dot.setStyleSheet(
                    "background-color: #484F58; border-radius: 5px; border: 2px solid #0D1117;"
                )
            self.chat_header_online_dot.show()
            self.chat_header_online.show()
        self.chat_header.show()

    def _update_chat_header_tooltip(self, ptt_id_lower: str):
        """根據快取的使用者資訊更新聊天標題列的 tooltip。"""
        info = self._user_info_cache.get(ptt_id_lower)
        if not info:
            self.chat_header.setToolTip("")
            return
        lines = []
        lines.append(f"ID：{info.get('ptt_id', ptt_id_lower)}")
        if info.get('nickname'):
            lines.append(f"暱稱：{info['nickname']}")
        activity = info.get('activity', '')
        lines.append(f"動態：{activity if activity else '未知'}")
        if info.get('login_count'):
            lines.append(f"登入次數：{info['login_count']}")
        if info.get('last_login_date'):
            lines.append(f"最後登入：{info['last_login_date']}")
        if info.get('legal_post'):
            lines.append(f"文章數量：{info['legal_post']}")
        if info.get('money'):
            lines.append(f"P 幣：{info['money']}")
        self.chat_header.setToolTip("\n".join(lines))

    def _on_scroll_range_changed(self, _min, _max):
        """只在使用者已接近底部時才自動捲動，避免閱讀歷史時被強制拉回。"""
        sb = self.scroll_area.verticalScrollBar()
        if _max - sb.value() <= 50:
            sb.setValue(_max)

    def refresh_chat_display(self):
        """重新渲染右側訊息區域，並根據時間戳記排序"""
        # 清除現有訊息
        while self.messages_layout.count():
            child = self.messages_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if not self.current_chat_id:
            self.chat_header.hide()
            return

        history = self.chat_histories.get(self.current_chat_id, [])
        # --- 新增排序邏輯：確保訊息依照時間戳記從小到大排列 ---
        history.sort(key=lambda x: x.get('timestamp', datetime.min))
        
        # 底部對齊：先加一個彈性空間，將訊息推向下方
        self.messages_layout.addStretch(1)
        
        for msg in history:
            if msg.get('mail_type') == 'waterball':
                widget = WaterballBubble(msg['text'], msg['time'], msg.get('is_me', False))
            elif msg.get('mail_type') == 'mail':
                widget = MailCard(msg.get('subject', ''), msg['text'], msg['time'])
            else:
                widget = ChatBubble(msg['text'], msg['time'], msg['is_me'],
                                    reply_info=msg.get('reply_info'),
                                    send_status=msg.get('send_status'))
                widget.reply_requested.connect(self.set_reply_to)
            self.messages_layout.addWidget(widget)
        
        # 滾動到底部
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )

    def set_reply_to(self, text: str, is_me: bool):
        """設定目前要回覆的訊息，顯示回覆預覽條。"""
        if not self.current_chat_id:
            return
        if is_me:
            quoted_sender = self.ptt_service.ptt_id.lower()
            display_id = self.ptt_service.ptt_id
        else:
            quoted_sender = self.current_chat_id
            display_id = self._get_contact_display_id(self.current_chat_id)

        preview = text[:80].replace('\n', ' ')
        self.reply_to = {'sender': quoted_sender, 'preview': preview}
        self.reply_bar_label.setText(f"↩ @{display_id}: {text[:60].replace(chr(10), ' ')}")
        self.reply_bar.show()
        self.message_edit.setFocus()

    def cancel_reply(self):
        """取消回覆，隱藏預覽條。"""
        self.reply_to = None
        self.reply_bar.hide()

    def _get_contact_display_id(self, ptt_id_lower: str) -> str:
        for i in range(self.contact_list.count()):
            w = self.contact_list.itemWidget(self.contact_list.item(i))
            if w and w.ptt_id == ptt_id_lower:
                return w.ptt_id_display
        return ptt_id_lower

    def handle_send(self):
        text = self.message_edit.text().strip()
        if not text or not self.current_chat_id:
            return

        # 若有待回覆訊息，編碼回覆前綴
        reply_info = None
        if self.reply_to:
            encoded_text = encode_reply(self.reply_to['sender'], self.reply_to['preview'], text)
            reply_info = self.reply_to.copy()
            self.cancel_reply()
        else:
            encoded_text = text

        # 1. 立即顯示在 UI (這部分仍在主執行緒)
        now = datetime.now()
        now_str = now.strftime("%H:%M")
        self.chat_histories[self.current_chat_id].append({
            'text': text,
            'time': now_str,
            'timestamp': now,
            'is_me': True,
            'reply_info': reply_info,
            'send_status': 'pending',
            'send_target': self.current_chat_id,
        })
        self.refresh_chat_display()
        self.message_edit.clear()

        # 更新聯絡人列表上的最後訊息時間
        for i in range(self.contact_list.count()):
            w = self.contact_list.itemWidget(self.contact_list.item(i))
            if w and w.ptt_id == self.current_chat_id:
                w.set_last_msg_time(now_str)
                break

        self._last_send_target = self.current_chat_id

        # 2. 將發送請求放入 thread-safe 佇列（繞過 Qt 事件佇列，避免被阻塞操作卡住）
        #    同時 emit signal 作為後備喚醒（worker 閒置時由 slot 觸發 drain）
        self.worker.enqueue_send(self.current_chat_id, encoded_text, now)
        self.send_requested.emit(self.current_chat_id, encoded_text, now)

    @Slot(dict)
    def on_new_message(self, data):
        # sender_id_display 是原始大小寫，sender 是用來當字典 Key 的小寫
        sender_id_display = data['sender']
        sender = sender_id_display.lower()
        
        # 檢查是否在封鎖名單
        if sender in self.blocked_users:
            logger.info(f"忽略來自已封鎖使用者 '{sender}' 的訊息")
            return

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

            # add_or_select_contact 內部的 on_contact_selected 會從 DB 載入歷史並覆寫 chat_histories，
            # 但觸發此訊號的那條訊息可能已在 DB 中（worker 先寫 DB 再 emit），
            # 所以需要去重後 append，確保當前 session 能看到。
            reply_info, actual_text = decode_reply(data['text'])
            is_me = data.get('is_me', False)
            msg_ts = data.get('timestamp', datetime.now())
            msg_ts_sec = msg_ts.replace(microsecond=0) if msg_ts else None
            is_dup = any(
                (m.get('timestamp', datetime.min).replace(microsecond=0) if m.get('timestamp') else None) == msg_ts_sec
                and m.get('text') == actual_text and m.get('is_me', False) == is_me
                for m in self.chat_histories.get(sender, [])
            )
            if not is_dup:
                self.chat_histories.setdefault(sender, []).append({
                    'text': actual_text,
                    'time': data['time'],
                    'timestamp': msg_ts,
                    'is_me': is_me,
                    'mail_type': data.get('mail_type', 'uptt'),
                    'subject': data.get('subject', ''),
                    'reply_info': reply_info,
                })
                if self.current_chat_id == sender:
                    self.refresh_chat_display()

            self._move_contact_to_top(sender)
        else:
            # 如果已存在，更新暱稱、ID 與最後訊息時間
            now_time = datetime.now().strftime("%H:%M")
            for i in range(self.contact_list.count()):
                item = self.contact_list.item(i)
                widget = self.contact_list.itemWidget(item)
                if widget and widget.ptt_id == sender:
                    widget.update_info(sender_id_display, nickname)
                    widget.set_last_msg_time(now_time)
                    break

            reply_info, actual_text = decode_reply(data['text'])
            is_me = data.get('is_me', False)
            msg_ts = data.get('timestamp', datetime.now())

            # 去重：避免 on_contact_selected 從 DB 載入後，signal 又重複 append
            msg_ts_sec = msg_ts.replace(microsecond=0) if msg_ts else None
            is_dup = any(
                (m.get('timestamp', datetime.min).replace(microsecond=0) if m.get('timestamp') else None) == msg_ts_sec
                and m.get('text') == actual_text and m.get('is_me', False) == is_me
                for m in self.chat_histories[sender]
            )
            if not is_dup:
                self.chat_histories[sender].append({
                    'text': actual_text,
                    'time': data['time'],
                    'timestamp': msg_ts,
                    'is_me': is_me,
                    'mail_type': data.get('mail_type', 'uptt'),
                    'subject': data.get('subject', ''),
                    'reply_info': reply_info,
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

            self._move_contact_to_top(sender)

        # 桌面通知 (僅限收到的訊息，排除自己從其他終端發出的)
        if not self.isActiveWindow() and not data.get('is_me', False):
            _, notify_text = decode_reply(data['text'])
            self.tray_icon.showMessage(
                f"新訊息: {sender_id_display}",
                notify_text[:50],
                QSystemTrayIcon.Information,
                3000
            )

    @Slot(bool, str)
    def on_send_result(self, success, error_msg):
        new_status = 'sent' if success else 'failed'
        # 只搜尋上次發送目標的 session，避免跨 session 誤判
        target = getattr(self, '_last_send_target', None)
        updated = False
        if target and target in self.chat_histories:
            for msg in reversed(self.chat_histories[target]):
                if msg.get('is_me') and msg.get('send_status') == 'pending':
                    msg['send_status'] = new_status
                    updated = True
                    break
        if updated:
            self.refresh_chat_display()
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
            self.handle_contact_action(self.current_chat_id, "CLOSE")

    def handle_contact_action(self, ptt_id: str, action_type: str):
        """
        處理對話動作：CLOSE (關閉)、BLOCK (封鎖)、DELETE (刪除)
        """
        ptt_id_lower = ptt_id.lower()
        current_acc = self.ptt_service.ptt_id
        logger.info(f"執行對話動作: {action_type} -> {ptt_id_lower}")

        if action_type == "BLOCK":
            self.blocked_users.add(ptt_id_lower)
            # 封鎖後也隱藏對話
            self.db.hide_session(current_acc, ptt_id_lower)
            self.remove_contact_from_sidebar(ptt_id_lower)
            QMessageBox.information(self, "已封鎖", f"已將使用者 '{ptt_id}' 加入封鎖名單。")
            
        elif action_type == "DELETE":
            confirm = QMessageBox.question(
                self, "確認刪除", f"確定要刪除與 '{ptt_id}' 的對話及所有紀錄嗎？\n(這將從本地資料庫徹底移除)",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                self.db.delete_session(current_acc, ptt_id_lower)

                if ptt_id_lower in self.chat_histories:
                    del self.chat_histories[ptt_id_lower]
                if ptt_id_lower in self.unread_counts:
                    del self.unread_counts[ptt_id_lower]
                self.remove_contact_from_sidebar(ptt_id_lower)
                logger.info(f"已從資料庫與介面刪除對話與紀錄: {ptt_id_lower}")
                
        elif action_type == "CLOSE":
            # 僅隱藏，不刪除訊息
            self.db.hide_session(current_acc, ptt_id_lower)
            self.remove_contact_from_sidebar(ptt_id_lower)

    def _move_contact_to_top(self, sender: str):
        """將指定非釘選聯絡人移至非釘選區頂端 (sender 為小寫)"""
        if sender in self.pinned_ids:
            return  # 釘選的聯絡人不需移動

        pinned_count = self.contact_list._pinned_count()

        for i in range(self.contact_list.count()):
            item = self.contact_list.item(i)
            widget = self.contact_list.itemWidget(item)
            if widget and widget.ptt_id == sender:
                if i == pinned_count:
                    return  # 已在非釘選區頂端
                was_selected = (self.contact_list.currentItem() == item)
                data = widget.get_data()
                self.contact_list.removeItemWidget(item)
                self.contact_list.takeItem(i)
                new_item = QListWidgetItem()
                new_item.setSizeHint(QSize(0, 70))
                new_widget = ContactItem(
                    ptt_id=data['ptt_id_display'],
                    nickname=data['nickname'],
                    is_pinned=False,
                    last_msg_time=data.get('last_msg_time', ''),
                )
                new_widget.set_online(data.get('is_online', False))
                if data.get('is_archived'):
                    new_widget.set_archived(True)
                self.contact_list.insertItem(pinned_count, new_item)
                self.contact_list.setItemWidget(new_item, new_widget)
                unread = self.unread_counts.get(sender, 0)
                if unread > 0:
                    new_widget.set_unread(unread)
                if was_selected:
                    self.contact_list.setCurrentItem(new_item)
                return

    def remove_contact_from_sidebar(self, ptt_id_lower: str):
        """僅從側邊欄清單中移除指定 ID"""
        self.pinned_ids.discard(ptt_id_lower)
        for i in range(self.contact_list.count()):
            item = self.contact_list.item(i)
            widget = self.contact_list.itemWidget(item)
            if widget and widget.ptt_id == ptt_id_lower:
                row = self.contact_list.row(item)
                self.contact_list.removeItemWidget(item)
                self.contact_list.takeItem(row)

                # 如果正在與此人對話，清空對話顯示
                if self.current_chat_id == ptt_id_lower:
                    self.current_chat_id = None
                    self.set_active_chat_requested.emit("")
                    self.refresh_chat_display()
                    self.setWindowTitle(f"uPtt - {self.ptt_service.ptt_id}")
                break

    def toggle_pin(self, ptt_id: str):
        """釘選或取消釘選指定聯絡人。"""
        ptt_id_lower = ptt_id.lower()
        current_acc = self.ptt_service.ptt_id

        if ptt_id_lower in self.pinned_ids:
            # 取消釘選
            self.pinned_ids.discard(ptt_id_lower)
            self.db.set_pin_session(current_acc, ptt_id_lower, False)
            self._move_pinned_to_unpinned_area(ptt_id_lower)
            logger.info(f"取消釘選: {ptt_id_lower}")
        else:
            # 釘選：加在釘選區末尾
            pin_order = len(self.pinned_ids)
            self.pinned_ids.add(ptt_id_lower)
            self.db.set_pin_session(current_acc, ptt_id_lower, True, pin_order)
            self._move_to_pinned_area(ptt_id_lower)
            logger.info(f"釘選: {ptt_id_lower} (order={pin_order})")

    def _move_to_pinned_area(self, ptt_id_lower: str):
        """將項目移至釘選區末尾並標記為釘選。"""
        insert_pos = self.contact_list._pinned_count()  # 以視覺列表為準

        for i in range(self.contact_list.count()):
            item = self.contact_list.item(i)
            widget = self.contact_list.itemWidget(item)
            if widget and widget.ptt_id == ptt_id_lower:
                if i == insert_pos:
                    widget.set_pinned(True)
                    return
                was_selected = (self.contact_list.currentItem() == item)
                data = widget.get_data()
                self.contact_list.removeItemWidget(item)
                self.contact_list.takeItem(i)

                new_item = QListWidgetItem()
                new_item.setSizeHint(QSize(0, 70))
                new_widget = ContactItem(
                    ptt_id=data['ptt_id_display'],
                    nickname=data['nickname'],
                    unread_count=data['unread_count'],
                    is_pinned=True,
                    last_msg_time=data.get('last_msg_time', ''),
                )
                new_widget.set_online(data.get('is_online', False))
                if data.get('is_archived'):
                    new_widget.set_archived(True)
                self.contact_list.insertItem(insert_pos, new_item)
                self.contact_list.setItemWidget(new_item, new_widget)
                if was_selected:
                    self.contact_list.setCurrentItem(new_item)
                return

    def _move_pinned_to_unpinned_area(self, ptt_id_lower: str):
        """將取消釘選的項目移至非釘選區頂端。"""
        insert_pos = self.contact_list._pinned_count() - 1  # 以視覺列表為準，扣除即將取消的項目

        for i in range(self.contact_list.count()):
            item = self.contact_list.item(i)
            widget = self.contact_list.itemWidget(item)
            if widget and widget.ptt_id == ptt_id_lower:
                was_selected = (self.contact_list.currentItem() == item)
                data = widget.get_data()
                self.contact_list.removeItemWidget(item)
                self.contact_list.takeItem(i)

                new_item = QListWidgetItem()
                new_item.setSizeHint(QSize(0, 70))
                new_widget = ContactItem(
                    ptt_id=data['ptt_id_display'],
                    nickname=data['nickname'],
                    unread_count=data['unread_count'],
                    is_pinned=False,
                    last_msg_time=data.get('last_msg_time', ''),
                )
                new_widget.set_online(data.get('is_online', False))
                if data.get('is_archived'):
                    new_widget.set_archived(True)
                self.contact_list.insertItem(insert_pos, new_item)
                self.contact_list.setItemWidget(new_item, new_widget)
                if was_selected:
                    self.contact_list.setCurrentItem(new_item)
                return

    def _on_items_reordered(self, new_order: list):
        """拖放排序後，儲存釘選項目的新順序至資料庫。"""
        pinned_in_order = [pid for pid in new_order if pid in self.pinned_ids]
        if pinned_in_order:
            current_acc = self.ptt_service.ptt_id
            self.db.update_pin_orders(current_acc, pinned_in_order)
            logger.info(f"已更新釘選排序: {pinned_in_order}")

    def show_contact_context_menu(self, pos):
        """顯示聯絡人清單的右鍵選單"""
        item = self.contact_list.itemAt(pos)
        if not item:
            return

        widget = self.contact_list.itemWidget(item)
        menu = QMenu(self)

        # 釘選 / 取消釘選
        is_pinned = widget.ptt_id in self.pinned_ids
        pin_action = QAction("取消釘選" if is_pinned else "釘選對話", self)
        pin_action.triggered.connect(lambda: self.toggle_pin(widget.ptt_id))

        close_action = QAction("關閉對話", self)
        close_action.triggered.connect(lambda: self.handle_contact_action(widget.ptt_id, "CLOSE"))

        delete_action = QAction("刪除對話", self)
        delete_action.triggered.connect(lambda: self.handle_contact_action(widget.ptt_id, "DELETE"))

        block_action = QAction("封鎖使用者", self)
        block_action.triggered.connect(lambda: self.handle_contact_action(widget.ptt_id, "BLOCK"))

        menu.addAction(pin_action)
        menu.addSeparator()
        menu.addAction(close_action)
        menu.addAction(delete_action)
        menu.addSeparator()
        menu.addAction(block_action)

        menu.exec(self.contact_list.mapToGlobal(pos))

    def handle_logout(self):
        """登出並回到登入畫面"""
        confirm = QMessageBox.question(
            self, "確認登出", "確定要登出目前的帳號嗎？",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.No:
            return

        logger.info("執行登出程序...")
        try:
            # 1. 停止目前的 Worker 與執行緒
            if hasattr(self, 'worker'):
                from PySide6.QtCore import QMetaObject
                QMetaObject.invokeMethod(self.worker, "stop", Qt.QueuedConnection)

            if hasattr(self, 'ptt_thread') and self.ptt_thread.isRunning():
                self.ptt_thread.quit()
                if not self.ptt_thread.wait(3000):
                    self.ptt_thread.terminate()
                    self.ptt_thread.wait()

            # 1.5 停止版本檢查執行緒
            if hasattr(self, '_ver_thread') and self._ver_thread.isRunning():
                self._ver_thread.quit()
                self._ver_thread.wait(11000)

            # 2. Worker thread 已確認停止，worker.stop() 已呼叫 ptt.close()，直接重建實例
            self.ptt_service = UPttService()

            # 3. 清除 UI 狀態
            self._is_first_time_login = False
            self.scan_setup_screen.reset()
            self.cancel_reply()
            self.contact_list.clear()
            self.chat_histories.clear()
            self.unread_counts.clear()
            self.pinned_ids.clear()
            self.current_chat_id = None
            self.refresh_chat_display()
            self.user_id_label.setText("uPtt")
            self._status_dot.hide()
            self.logout_btn.hide()
            self.chat_header.hide()
            self.setWindowTitle("uPtt")

            # 4. 重設視窗為登入大小
            self.setMinimumSize(0, 0)
            self.setMaximumSize(16777215, 16777215)
            self.setFixedSize(440, 480)
            
            # 5. 切換畫面
            self.central_stack.setCurrentIndex(0)
            self.login_screen.login_btn.setEnabled(True)
            self.login_screen.login_btn.setText("連線至 PTT")
            self.login_screen.password_input.clear()
            self.login_screen.username_input.setFocus()
            
            # 6. 重新初始化新的 Worker 與執行緒 (準備下次登入)
            self.init_worker()
            
            logger.info("登出成功，已回到登入視窗。")
            
        except Exception as e:
            logger.error(f"登出時發生異常: {e}")
            QMessageBox.critical(self, "登出錯誤", f"登出時發生非預期錯誤: {e}")

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

            # 2.5 停止版本檢查執行緒
            if hasattr(self, '_ver_thread') and self._ver_thread.isRunning():
                self._ver_thread.quit()
                self._ver_thread.wait(11000)

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
