import os

from PySide6.QtCore import Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from uPtt import __version__, contant
from uPtt.ui import styles
from uPtt.ui._render import ASSETS_DIR, render_svg

class LoginWindow(QWidget):
    """登入畫面"""
    login_requested = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.setObjectName("login-window")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._password_danger = False  # 目前密碼欄是否呈現 danger 紅框，供切主題時重繪
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

        self.subtitle_label = QLabel("開源 PTT 即時通訊系統")
        self.subtitle_label.setAlignment(Qt.AlignCenter)

        # 分隔線
        self.sep_line = QFrame()
        self.sep_line.setFrameShape(QFrame.HLine)

        # 帳號欄位
        self.id_label = QLabel("PTT 代號")

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("輸入您的 PTT ID")
        self.username_input.setFixedHeight(42)

        # 密碼欄位
        self.pw_label = QLabel("密碼")

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

        form_layout.addWidget(self.logo_label)
        form_layout.addSpacing(5)
        form_layout.addWidget(self.subtitle_label)
        form_layout.addSpacing(20)
        form_layout.addWidget(self.sep_line)
        form_layout.addSpacing(20)
        form_layout.addWidget(self.id_label)
        form_layout.addSpacing(5)
        form_layout.addWidget(self.username_input)
        form_layout.addSpacing(12)
        form_layout.addWidget(self.pw_label)
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

        # 使用者重新輸入時清除先前的錯誤狀態（紅框 + 錯誤行）
        self.username_input.textChanged.connect(self.clear_error)
        self.password_input.textChanged.connect(self.clear_error)

        # 預設聚焦帳號輸入
        self.username_input.setFocus()

        # 套用目前主題的顏色與 logo（初始化與後續 refresh_theme() 共用同一份邏輯）
        self.refresh_theme()

    def refresh_theme(self):
        """重新套用 inline 樣式的文字顏色與 logo。初始化時與 MainWindow.apply_theme()
        切換主題時都會呼叫——這些 QLabel/QFrame 用 setStyleSheet 直接設色，不受父層
        QSS 的主題切換影響，必須手動 refresh。"""
        t = styles.theme()
        self.subtitle_label.setStyleSheet(
            f"color: {t['muted']}; font-size: 13px; letter-spacing: 2px; background: transparent;"
        )
        self.sep_line.setStyleSheet(f"background-color: {t['divider']}; border: none; max-height: 1px;")
        self.id_label.setStyleSheet(f"color: {t['muted']}; font-size: 11px; background: transparent;")
        self.pw_label.setStyleSheet(f"color: {t['muted']}; font-size: 11px; background: transparent;")
        self.version_label.setStyleSheet(f"color: {t['faint']}; font-size: 11px; background: transparent;")
        self.update_label.setStyleSheet(
            f"color: {t['accent']}; font-size: 12px; background: transparent;"
            "text-decoration: underline; padding-top: 4px;"
        )
        self._render_logo()
        self._set_password_danger(self._password_danger)  # 切主題時保留目前的錯誤狀態

    def _render_logo(self):
        """依目前主題重新渲染 logo。"""
        logo_path = os.path.join(ASSETS_DIR, "logo_horizontal.svg")
        if os.path.exists(logo_path):
            dpr = self.devicePixelRatioF() if hasattr(self, 'devicePixelRatioF') else 1.0
            self.logo_label.setPixmap(render_svg(logo_path, 220, 73, dpr))
        else:
            self.logo_label.setText("[ uPtt ]")

    def handle_login(self):
        self.clear_error()
        user = self.username_input.text().strip()
        pw = self.password_input.text()
        if not user or not pw:
            self.show_error("請輸入完整帳號密碼")
            return

        self.login_btn.setEnabled(False)
        self.login_btn.setText("正在連線...")
        self.login_requested.emit(user, pw)

    def show_error(self, message: str, kind: str = "unknown"):
        """顯示登入錯誤。kind 決定呈現方式：
        - 'auth'：密碼欄位加上 danger 邊框 + ✕ 前綴
        - 'network'：錯誤行加上提示圖示前綴
        - 'unknown'（含未分類/前端驗證錯誤）：一般 danger 錯誤行
        """
        icon = {"auth": "✕ ", "network": "⚠ "}.get(kind, "")
        self.error_label.setText(f"{icon}{message}")
        self.error_label.show()
        self._set_password_danger(kind == "auth")
        self.login_btn.setEnabled(True)
        self.login_btn.setText("連線至 PTT")

    def clear_error(self):
        """清除錯誤行與密碼欄位的紅框（使用者重新輸入或再次送出時呼叫）。"""
        self.error_label.hide()
        self.error_label.setText("")
        self._set_password_danger(False)

    def _set_password_danger(self, is_danger: bool):
        """切換密碼輸入框的 danger 邊框。當下取 styles.theme()，確保跨主題正確；
        狀態存於 self._password_danger，供 refresh_theme() 於切主題時重繪。"""
        self._password_danger = is_danger
        if not is_danger:
            self.password_input.setStyleSheet("")
            return
        t = styles.theme()
        self.password_input.setStyleSheet(
            f"padding: 9px 13px; border: 1px solid {t['danger']}; border-radius: 7px;"
            f"background-color: {t['surface']}; color: {t['ink']}; font-size: 14px;"
        )

    @Slot(str)
    def show_update_available(self, latest_version: str):
        self.update_label.setText(f"新版本 v{latest_version} 可供下載")
        self.update_label.show()
