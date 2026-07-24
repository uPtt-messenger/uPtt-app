import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QStackedWidget, QListWidget, QListWidgetItem, QSplitter,
    QScrollArea, QTextEdit, QSystemTrayIcon, QMenu, QMessageBox, QInputDialog,
    QCheckBox, QFileDialog
)
from PySide6.QtCore import Qt, Signal, Slot, QThread, QSize, QEvent, QUrl, QTimer, QSettings
from PySide6.QtGui import QIcon, QAction, QShortcut, QKeySequence, QPixmap, QPainter, QFontMetrics, QDesktopServices, QIntValidator
from PySide6.QtSvg import QSvgRenderer

from uPtt import __version__, config, contant
from uPtt.ui import theme
from uPtt.ui.settings import SettingsWindow
from uPtt.ui.search_palette import SearchPalette
from uPtt.ui.styles import build_main_style
from .theme import FONT_STACK, ASSETS_DIR, render_svg
from uPtt.ui.widgets import ChatBubble, WaterballBubble, MailCard, ContactItem, ContactListWidget
from uPtt.utils import encode_reply, decode_reply, VersionCheckWorker, resolve_display_name
from uPtt.worker import PTTWorker, QueryWorker
from uPtt.ptt import UPttService

logger = logging.getLogger("uPtt.ui.screens")

# config 目前無「訊息字數上限」常數（MAX_MESSAGES 是記憶體訊息筆數），沿用設計稿的顯示上限
INPUT_CHAR_LIMIT = 2000

# 聯絡人清單 item 的一般 sizeHint 高度，需與 widgets.py 建立 item 時的 QSize(0, 70) 一致
CONTACT_ROW_HEIGHT = 70
# 釘選區「最後一項」在此基礎上加高的量，讓中段「最近·RECENT」標頭有專屬空間，
# 落於此加高範圍內，絕不覆蓋任何聯絡人（釘選或未釘選）的頭像/ID
MID_HEADER_ROW_GAP = 22


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


class LoginWindow(QWidget):
    """登入畫面"""
    login_requested = Signal(str, str)

    _BTN_TEXT = "連線  ↵"
    _REMEMBER_KEY = "login/remembered_id"

    def __init__(self):
        super().__init__()
        self.setObjectName("login-window")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowTitle("uPtt — 連線 ptt.cc")
        self.setMinimumSize(720, 440)
        self._settings = QSettings("uPtt", "uPtt")
        self._mono = f"font-family: {FONT_STACK};"
        self.init_ui()
        self._load_remembered()
        theme.register_restyle(self, lambda w: w._apply_theme())

    def init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 頂部終端列：$ uptt --connect ptt.cc  ·  版本 ──
        top_bar = QWidget()
        top_bar.setStyleSheet("background: transparent;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(26, 18, 26, 0)
        self.term_label = QLabel("$ uptt --connect ptt.cc")
        self.version_label = QLabel(f"v{__version__}")
        self.version_label.setObjectName("version-label")
        top_layout.addWidget(self.term_label)
        top_layout.addStretch()
        top_layout.addWidget(self.version_label)

        # ── 中段：左品牌牆 + 右登入卡 ──
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(26, 8, 26, 8)
        content_layout.setSpacing(30)

        content_layout.addWidget(self._build_brand(), 1)
        right_col = QVBoxLayout()
        right_col.addStretch()
        right_col.addWidget(self._build_card())
        right_col.addStretch()
        content_layout.addLayout(right_col, 0)

        # ── 底部狀態列 ──
        self.bottom_bar = QWidget()
        bottom_layout = QHBoxLayout(self.bottom_bar)
        bottom_layout.setContentsMargins(26, 12, 26, 14)
        self.footer_label = QLabel("SQLite · GPL-3.0")

        # 更新提示 (初始隱藏，可點擊開啟下載頁)
        self.update_label = QLabel()
        self.update_label.setCursor(Qt.PointingHandCursor)
        self.update_label.hide()
        self.update_label.mousePressEvent = lambda _: QDesktopServices.openUrl(
            QUrl(contant.DOWNLOAD_URL)
        )
        bottom_layout.addWidget(self.footer_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.update_label)

        root.addWidget(top_bar)
        root.addWidget(content, 1)
        root.addWidget(self.bottom_bar)

        # 綁定 Enter 鍵
        self.username_input.returnPressed.connect(self.password_input.setFocus)
        self.password_input.returnPressed.connect(self.handle_login)
        self.username_input.setFocus()

    def _build_brand(self) -> QWidget:
        """左側品牌牆：終端字標 uPtt▪、標語、連線狀態。"""
        brand = QWidget()
        brand.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(brand)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)
        layout.addStretch()

        # 字標 uPtt + accent 綠方塊
        wordmark_row = QWidget()
        wordmark_row.setStyleSheet("background: transparent;")
        wm_layout = QHBoxLayout(wordmark_row)
        wm_layout.setContentsMargins(0, 0, 0, 0)
        wm_layout.setSpacing(4)
        self.logo_label = QLabel()
        self.logo_label.setObjectName("logo-label")
        self.logo_label.setTextFormat(Qt.RichText)
        # 終端游標：直立長方 caret（設計稿 38×66 @84px 字標，按 66px 等比 → 30×52），直角、深綠
        self.accent_square = QLabel()
        self.accent_square.setFixedSize(30, 52)
        # 閃爍：550ms 硬切換（設計稿 1.1s steps(2)），固定尺寸不影響排版
        self._cursor_timer = QTimer(self)
        self._cursor_on = True
        def _blink():
            self._cursor_on = not self._cursor_on
            self._apply_cursor_style()
        self._cursor_timer.timeout.connect(_blink)
        self._cursor_timer.start(550)
        wm_layout.addWidget(self.logo_label)
        wm_layout.addWidget(self.accent_square, 0, Qt.AlignBottom)
        wm_layout.addStretch()

        self.tagline_label = QLabel("讓 PTT 的溫柔，\n在現代桌面重新綻放。")

        # 連線狀態（登入前為中性「尚未連線」，不謊稱已連線）
        status_row = QWidget()
        status_row.setStyleSheet("background: transparent;")
        status_layout = QHBoxLayout(status_row)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(6)
        self.status_dot = QLabel("●")
        self.status_hint = QLabel("尚未連線 · 準備連線至 ptt.cc")
        status_layout.addWidget(self.status_dot)
        status_layout.addWidget(self.status_hint)
        status_layout.addStretch()

        layout.addWidget(wordmark_row)
        layout.addSpacing(22)
        layout.addWidget(self.tagline_label)
        layout.addSpacing(26)
        layout.addWidget(status_row)
        layout.addStretch()
        return brand

    def _build_card(self) -> QFrame:
        """右側登入卡：標題 / 帳號 / 密碼 / 記住帳號 / 連線鈕 / 註記。"""
        card = QFrame()
        card.setObjectName("login-card")
        card.setFixedWidth(320)
        self.login_card = card
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(0)

        self.card_title = QLabel("登入 · LOGIN")

        self.id_label = QLabel("PTT 帳號")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("輸入您的 PTT ID")
        self.username_input.setFixedHeight(40)

        self.pw_label = QLabel("密碼")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("••••••••")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFixedHeight(40)

        self.remember_check = QCheckBox("記住帳號")
        self.remember_check.setCursor(Qt.PointingHandCursor)

        self.error_label = QLabel("")
        self.error_label.setObjectName("error-label")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        self.login_btn = QPushButton(self._BTN_TEXT)
        self.login_btn.setObjectName("login-btn")
        self.login_btn.setFixedHeight(42)
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.clicked.connect(self.handle_login)

        self.note1_label = QLabel("僅連線 ptt.cc · 不經第三方")
        self.note2_label = QLabel("記住帳號只保存 PTT 代號，不儲存密碼")

        layout.addWidget(self.card_title)
        layout.addSpacing(18)
        layout.addWidget(self.id_label)
        layout.addSpacing(6)
        layout.addWidget(self.username_input)
        layout.addSpacing(14)
        layout.addWidget(self.pw_label)
        layout.addSpacing(6)
        layout.addWidget(self.password_input)
        layout.addSpacing(14)
        layout.addWidget(self.remember_check)
        layout.addSpacing(6)
        layout.addWidget(self.error_label)
        layout.addSpacing(10)
        layout.addWidget(self.login_btn)
        layout.addSpacing(14)
        layout.addWidget(self.note1_label)
        layout.addSpacing(2)
        layout.addWidget(self.note2_label)
        return card

    def _apply_cursor_style(self):
        """套用終端游標方塊的目前明/滅狀態顏色（依 self._cursor_on）。"""
        c = theme.active()
        on = f"background-color: {c['accent_hover']}; border-radius: 0px; margin-bottom: 10px;"
        off = "background-color: transparent; border-radius: 0px; margin-bottom: 10px;"
        self.accent_square.setStyleSheet(on if self._cursor_on else off)

    def _apply_theme(self):
        """重新套用當前主題色票到本畫面所有元件（供 theme.register_restyle 即時切換用）。"""
        c = theme.active()
        mono = self._mono
        label_style = f"color: {c['text_muted']}; {mono} font-size: 11px; letter-spacing: 1px; background: transparent;"
        input_style = (
            f"QLineEdit {{ background-color: {c['bg']}; border: 1px solid {c['border']};"
            f" border-radius: 7px; padding: 0 12px; color: {c['text']}; {mono} font-size: 14px; }}"
            f"QLineEdit:focus {{ border: 1px solid {c['accent']}; }}"
        )
        note_style = f"color: {c['text_faint']}; {mono} font-size: 11px; background: transparent;"

        self.setStyleSheet(f"QWidget#login-window {{ background-color: {c['bg']}; }}")

        self.term_label.setStyleSheet(f"color: {c['text_faint']}; {mono} font-size: 12px; background: transparent;")
        self.version_label.setStyleSheet(f"color: {c['text_faint']}; {mono} font-size: 12px; background: transparent;")

        self.logo_label.setText(
            f'<span style="color:{c["text_muted"]};">u</span>'
            f'<span style="color:{c["text"]};">Ptt</span>'
        )
        self.logo_label.setStyleSheet(f"{mono} font-size: 66px; font-weight: 700; background: transparent;")
        self._apply_cursor_style()

        self.tagline_label.setStyleSheet(f"color: {c['text_muted']}; {mono} font-size: 15px; line-height: 1.6; background: transparent;")

        self.status_dot.setStyleSheet(f"color: {c['text_faint']}; font-size: 9px; background: transparent;")
        self.status_hint.setStyleSheet(f"color: {c['text_faint']}; {mono} font-size: 12px; background: transparent;")

        self.bottom_bar.setStyleSheet(f"background: transparent; border-top: 1px solid {c['border']};")
        self.footer_label.setStyleSheet(f"color: {c['text_faint']}; {mono} font-size: 11px; background: transparent;")
        self.update_label.setStyleSheet(
            f"color: {c['accent']}; {mono} font-size: 12px;"
            " text-decoration: underline; background: transparent;"
        )

        self.login_card.setStyleSheet(
            f"QFrame#login-card {{ background-color: {c['surface']};"
            f" border: 1px solid {c['border']}; border-radius: 10px; }}"
        )
        self.card_title.setStyleSheet(
            f"color: {c['text']}; {mono} font-size: 15px; font-weight: 700;"
            " letter-spacing: 1px; background: transparent;"
        )
        self.id_label.setStyleSheet(label_style)
        self.username_input.setStyleSheet(input_style)
        self.pw_label.setStyleSheet(label_style)
        self.password_input.setStyleSheet(input_style)
        self.remember_check.setStyleSheet(
            f"QCheckBox {{ color: {c['text_muted']}; {mono} font-size: 13px;"
            " spacing: 8px; background: transparent; }"
            f"QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px;"
            f" border: 1px solid {c['border_strong']}; background: {c['bg']}; }}"
            f"QCheckBox::indicator:checked {{ background: {c['accent']}; border-color: {c['accent']}; }}"
        )
        self.error_label.setStyleSheet(f"color: {c['danger']}; {mono} font-size: 12px; background: transparent;")
        self.login_btn.setStyleSheet(
            f"QPushButton#login-btn {{ background-color: {c['accent']}; color: {c['bg']};"
            f" border: none; border-radius: 8px; {mono} font-size: 14px; font-weight: 700;"
            " letter-spacing: 1px; }"
            f"QPushButton#login-btn:hover {{ background-color: {c['accent_hover']}; color: {c['text']}; }}"
            f"QPushButton#login-btn:disabled {{ background-color: {c['accent_bg']}; color: {c['text_muted']}; }}"
        )
        self.note1_label.setStyleSheet(note_style)
        self.note2_label.setStyleSheet(note_style)

    def _load_remembered(self):
        """若上次勾選記住帳號，預填 PTT 代號並勾選（僅代號，永不含密碼）。"""
        remembered = self._settings.value(self._REMEMBER_KEY, "", type=str)
        if remembered:
            self.username_input.setText(remembered)
            self.remember_check.setChecked(True)
            self.password_input.setFocus()

    def handle_login(self):
        user = self.username_input.text().strip()
        pw = self.password_input.text()
        if not user or not pw:
            self.show_error("請輸入完整帳號密碼")
            return

        # 持久化「是否記住代號」：勾選存代號、取消則清除（不涉及密碼）
        if self.remember_check.isChecked():
            self._settings.setValue(self._REMEMBER_KEY, user)
        else:
            self._settings.remove(self._REMEMBER_KEY)
        self._settings.sync()  # macOS/cfprefsd 需強制落盤，否則硬退出時新值遺失

        self.login_btn.setEnabled(False)
        self.login_btn.setText("正在連線...")
        self.login_requested.emit(user, pw)

    def show_error(self, message: str):
        self.error_label.setText(message)
        self.error_label.show()
        self.login_btn.setEnabled(True)
        self.login_btn.setText(self._BTN_TEXT)

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
        self.init_ui()
        theme.register_restyle(self, lambda w: w._apply_theme())

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
        self.title_label = QLabel("信箱掃描")
        self.title_label.setAlignment(Qt.AlignCenter)

        self.desc_label = QLabel("uPtt 需要掃描您的 PTT 信箱，\n才能載入過去的對話紀錄。")
        self.desc_label.setAlignment(Qt.AlignCenter)
        self.desc_label.setWordWrap(True)

        self.subtitle_label = QLabel("選擇要載入的信件範圍")
        self.subtitle_label.setAlignment(Qt.AlignCenter)

        self.sep_line = QFrame()
        self.sep_line.setFrameShape(QFrame.HLine)

        # 快速選擇按鈕
        btn_row = QWidget()
        btn_row.setStyleSheet("background: transparent;")
        btn_row_layout = QHBoxLayout(btn_row)
        btn_row_layout.setContentsMargins(0, 0, 0, 0)
        btn_row_layout.setSpacing(12)

        self.btn_7d = QPushButton("7 天")
        self.btn_7d.setFixedHeight(42)
        self.btn_7d.clicked.connect(lambda: self._start_scan(7))

        self.btn_30d = QPushButton("30 天")
        self.btn_30d.setFixedHeight(42)
        self.btn_30d.clicked.connect(lambda: self._start_scan(30))

        self.btn_all = QPushButton("全部")
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

        self.custom_label = QLabel("自訂：")

        self.custom_input = QLineEdit()
        self.custom_input.setPlaceholderText("天數")
        self.custom_input.setValidator(QIntValidator(1, 3650))
        self.custom_input.setFixedWidth(80)
        self.custom_input.setFixedHeight(38)

        self.day_label = QLabel("天")

        self.btn_custom = QPushButton("開始掃描")
        self.btn_custom.setFixedHeight(38)
        self.btn_custom.clicked.connect(self._start_custom_scan)
        self.custom_input.returnPressed.connect(self._start_custom_scan)

        custom_layout.addWidget(self.custom_label)
        custom_layout.addWidget(self.custom_input)
        custom_layout.addWidget(self.day_label)
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

        self.progress_count = QLabel("0 / 0")
        self.progress_count.setAlignment(Qt.AlignCenter)

        self.progress_title = QLabel("")
        self.progress_title.setAlignment(Qt.AlignCenter)
        self.progress_title.setWordWrap(True)
        self.progress_title.setMaximumWidth(360)

        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_count)
        progress_layout.addWidget(self.progress_title)
        self.progress_widget.hide()

        # 跳過按鈕
        self.skip_btn = QPushButton("跳過，之後再掃描")
        self.skip_btn.setCursor(Qt.PointingHandCursor)
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
        layout.addWidget(self.title_label)
        layout.addSpacing(8)
        layout.addWidget(self.desc_label)
        layout.addSpacing(12)
        layout.addWidget(self.subtitle_label)
        layout.addSpacing(20)
        layout.addWidget(self.sep_line)
        layout.addSpacing(20)
        layout.addWidget(self.options_widget)
        layout.addWidget(self.progress_widget)

        main_layout.addWidget(container)

    def _apply_theme(self):
        """重新套用當前主題色票到本畫面所有元件（供 theme.register_restyle 即時切換用）。"""
        c = theme.active()
        self.setStyleSheet(f"background-color: {c['bg']};")

        self.title_label.setStyleSheet(f"color: {c['text']}; font-size: 18px; font-weight: bold; background: transparent;")
        self.desc_label.setStyleSheet(f"color: {c['text_muted']}; font-size: 13px; background: transparent; line-height: 1.5;")
        self.subtitle_label.setStyleSheet(f"color: {c['text_faint']}; font-size: 13px; background: transparent;")
        self.sep_line.setStyleSheet(f"background-color: {c['border']}; border: none; max-height: 1px;")

        # 注意：QSS 不允許「無 selector 的裸宣告」與「有 selector 的規則」混在同一份
        # stylesheet（會觸發 "Could not parse stylesheet"）。btn_style 也要包 QPushButton{} selector。
        btn_style = f"""
            QPushButton {{
                background-color: {c['accent_bg']}; color: {c['accent']};
                border: 1px solid {c['accent_hover']}; border-radius: 8px;
                font-weight: bold; font-size: 14px; padding: 10px 20px;
            }}
        """
        btn_hover_style = f"""
            QPushButton:hover {{ background-color: {c['accent_bg_hover']}; color: {c['accent_tint_hover']}; border-color: {c['accent']}; }}
        """
        for btn in (self.btn_7d, self.btn_30d, self.btn_all, self.btn_custom):
            btn.setStyleSheet(btn_style + btn_hover_style)

        self.custom_label.setStyleSheet(f"color: {c['text_muted']}; font-size: 13px; background: transparent;")
        self.custom_input.setStyleSheet(
            f"padding: 8px; border: 1px solid {c['border']}; border-radius: 7px;"
            f"background-color: {c['surface']}; color: {c['text']}; font-size: 14px;"
        )
        self.day_label.setStyleSheet(f"color: {c['text_muted']}; font-size: 13px; background: transparent;")

        self.progress_label.setStyleSheet(f"color: {c['accent']}; font-size: 14px; font-weight: bold; background: transparent;")
        self.progress_count.setStyleSheet(f"color: {c['text']}; font-size: 24px; font-weight: bold; background: transparent;")
        self.progress_title.setStyleSheet(f"color: {c['text_faint']}; font-size: 12px; background: transparent;")

        self.skip_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {c['text_faint']}; font-size: 12px; padding: 6px 0;
            }}
            QPushButton:hover {{ color: {c['text_muted']}; }}
        """)

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


# --- MainWindow 狀態相依的重套色函式 -------------------------------------
#
# theme.register_restyle(widget, fn) 要求 fn 只吃參數 w、不得 capture
# self / 其他 widget（否則 _restyles 會強引用 fn 進而洩漏 self）。以下函式
# 一律只讀寫傳入的 widget 自身屬性（狀態暫存在 widget 上），供 MainWindow
# 建構時登記、也供狀態變化時的 slot 直接呼叫以立即套用。

def _restyle_conn_status_dot(w):
    """主連線狀態指示點：狀態存於 w._conn_state（'connecting' | 'online'）。"""
    state = getattr(w, "_conn_state", "online")
    t = theme.active()
    color = t["status_connecting"] if state == "connecting" else t["status_online"]
    w.setStyleSheet(f"color: {color}; font-size: 9px; background: transparent;")


def _restyle_chat_header_online_text(w):
    """聊天標題列在線狀態文字：狀態存於 w._online_state（bool 或 None＝尚無狀態，視同離線）。"""
    state = getattr(w, "_online_state", None)
    t = theme.active()
    color = t["status_online"] if state else t["text_faint"]
    w.setStyleSheet(f"font-size: 10px; color: {color}; background: transparent;")


def _restyle_chat_header_online_dot(w):
    """聊天標題列在線狀態圓點：狀態存於 w._online_state（bool 或 None＝尚無狀態）。"""
    state = getattr(w, "_online_state", None)
    t = theme.active()
    color = t["status_online"] if state else t["text_faint"]
    w.setStyleSheet(
        f"background-color: {color}; border-radius: 5px; border: 2px solid {t['surface']};"
    )


class MainWindow(QMainWindow):
    """主聊天畫面"""
    send_requested = Signal(str, str, object, int)  # (receiver_id, text, timestamp, db_msg_id)
    user_info_requested = Signal(str)
    priority_online_requested = Signal(str)
    scan_requested = Signal(int)  # scan_days
    skip_scan_requested = Signal()
    set_active_chat_requested = Signal(str)
    query_login_requested = Signal(str, str)  # (ptt_id, ptt_pw) — 觸發副 session 延遲登入

    def __init__(self, ptt_service: UPttService, ptt_query_service: UPttService, db):
        super().__init__()
        self.setWindowTitle("uPtt")

        # 設定視窗圖示
        icon_path = os.path.join(ASSETS_DIR, "logo_icon.svg")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # 初始大小設為適合登入視窗的大小
        self.setFixedSize(760, 500)
        self.ptt_service = ptt_service
        self.ptt_query_service = ptt_query_service
        self.db = db
        self.current_chat_id = None
        self.chat_histories: Dict[str, List[Dict]] = {}
        self.unread_counts: Dict[str, int] = {}
        self.blocked_users: set = set()
        self.pinned_ids: set = set()
        self.reply_to: Optional[Dict] = None  # {'sender': str, 'preview': str}
        self._user_info_cache: Dict[str, Dict] = {}  # ptt_id_lower -> user info dict
        self.session_drafts: Dict[str, str] = {}  # ptt_id_lower -> draft text
        self._quitting = False  # 退出程序旗標，防止遞迴
        self._settings_window: Optional[SettingsWindow] = None  # 單例，重複開就 raise/activate
        self._search_palette: Optional[SearchPalette] = None  # ⌘K 搜尋面板，單例

        # 初始化 UI 與背景執行緒
        self.init_ui()
        self.init_worker()
        self.init_tray()
        self.init_shortcuts()

        theme.register_restyle(self, lambda w: w.setStyleSheet(build_main_style()))

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
        """啟動 PTT 背景 Worker(主收送 + 副查詢 兩條獨立 thread)"""
        # 確保清理舊的訊號連線 (避免重複)
        if getattr(self, "_worker_signals_connected", False):
            self.send_requested.disconnect()
            self.user_info_requested.disconnect()
            self.priority_online_requested.disconnect()
            self.set_active_chat_requested.disconnect()
            self.scan_requested.disconnect()
            self.skip_scan_requested.disconnect()
            try:
                self.query_login_requested.disconnect()
            except RuntimeError:
                pass

        # 斷開舊 Worker → MainWindow 方向的訊號，防止記憶體洩漏
        if hasattr(self, 'worker'):
            for sig in [
                self.worker.new_message_received,
                self.worker.send_result,
                self.worker.status_updated,
                self.worker.login_result,
                self.worker.connection_lost,
                self.worker.connection_restored,
                self.worker.first_time_detected,
                self.worker.scan_progress,
                self.worker.scan_complete,
            ]:
                try:
                    sig.disconnect()
                except RuntimeError:
                    pass  # 已斷開

        if hasattr(self, 'query_worker'):
            for sig in [
                self.query_worker.user_info_result,
                self.query_worker.user_info_error,
                self.query_worker.online_status_updated,
                self.query_worker.session_archived,
                self.query_worker.query_session_degraded,
                self.query_worker.query_session_restored,
            ]:
                try:
                    sig.disconnect()
                except RuntimeError:
                    pass

        # 主 worker(收送訊息)
        self.ptt_thread = QThread()
        self.worker = PTTWorker(self.ptt_service, self.db)
        self.worker.moveToThread(self.ptt_thread)

        # 副 worker(使用者狀態查詢)
        self.query_thread = QThread()
        self.query_worker = QueryWorker(self.ptt_query_service, self.db)
        self.query_worker.moveToThread(self.query_thread)

        # 連接發信訊號 (跨執行緒會自動排程)
        self.send_requested.connect(self.worker.send_message)
        self.scan_requested.connect(self.worker.do_initial_scan)
        self.skip_scan_requested.connect(self.worker.do_skip_scan)

        # 連接查詢訊號到副 worker
        self.user_info_requested.connect(self.query_worker.get_user_info)
        self.priority_online_requested.connect(self.query_worker.check_online_priority)
        self.set_active_chat_requested.connect(self.query_worker.set_active_chat)
        self.query_login_requested.connect(self.query_worker.do_login)
        self._worker_signals_connected = True

        # 這裡也改用訊號連接，確保在背景執行緒登入 (且在登出重啟 Worker 後能重新連向新實例)
        if hasattr(self, "login_screen"):
            if getattr(self, "_login_signal_connected", False):
                self.login_screen.login_requested.disconnect()
            self.login_screen.login_requested.connect(self.worker.do_login)
            self._login_signal_connected = True

        # 連接主 Worker 訊號
        self.worker.new_message_received.connect(self.on_new_message)
        self.worker.send_result.connect(self.on_send_result)
        self.worker.status_updated.connect(lambda s: logger.info(f"Worker Status: {s}"))
        self.worker.disconnected.connect(self._handle_disconnected)
        self.worker.login_result.connect(self.on_login_result)
        self.worker.connection_lost.connect(self.on_connection_lost)
        self.worker.connection_restored.connect(self.on_connection_restored)
        self.worker.first_time_detected.connect(self._on_first_time_detected)
        self.worker.scan_progress.connect(self.scan_setup_screen.update_progress)
        self.worker.scan_complete.connect(self._on_scan_complete)

        # 連接副 Worker 訊號
        self.query_worker.user_info_result.connect(self.on_user_info_result)
        self.query_worker.user_info_error.connect(self.on_user_info_error)
        self.query_worker.online_status_updated.connect(self.on_online_status_updated)
        self.query_worker.session_archived.connect(self.on_session_archived)
        self.query_worker.query_session_degraded.connect(self.on_query_session_degraded)
        self.query_worker.query_session_restored.connect(self.on_query_session_restored)

        # 掃描設定畫面的訊號
        if hasattr(self, 'scan_setup_screen'):
            if getattr(self, '_scan_signal_connected', False):
                self.scan_setup_screen.scan_days_selected.disconnect()
                self.scan_setup_screen.scan_skipped.disconnect()
            self.scan_setup_screen.scan_days_selected.connect(self._on_scan_days_selected)
            self.scan_setup_screen.scan_skipped.connect(self._on_scan_skipped)
            self._scan_signal_connected = True

        # 啟動兩條執行緒
        self.ptt_thread.start()
        self.query_thread.start()

    def init_ui(self):
        # 使用 QStackedWidget 切換登入與主畫面
        self.central_stack = QStackedWidget()
        self.setCentralWidget(self.central_stack)
        
        # 1. 登入畫面
        self.login_screen = LoginWindow()
        
        # 2. 聊天畫面 (使用 Splitter)
        self.chat_screen = QWidget()
        chat_layout = QVBoxLayout(self.chat_screen)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)
        
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(1)
        theme.register_restyle(
            self.splitter,
            lambda w: w.setStyleSheet(f"QSplitter::handle {{ background-color: {theme.active()['border']}; }}"),
        )
        
        self._build_sidebar()
        self._build_chat_pane()

        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.chat_area)
        self.splitter.setStretchFactor(1, 4)

        chat_layout.addWidget(self.splitter, stretch=1)
        chat_layout.addWidget(self.status_bar_widget)

        self.central_stack.addWidget(self.login_screen)     # index 0
        self.central_stack.addWidget(self.chat_screen)      # index 1
        self.scan_setup_screen = ScanSetupScreen()
        self.central_stack.addWidget(self.scan_setup_screen) # index 2

    def _build_sidebar(self):
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
        theme.register_restyle(self.user_profile, lambda w: w.setStyleSheet(f"""
            background-color: {theme.active()['surface']};
            border-bottom: 1px solid {theme.active()['border']};
        """))
        user_layout = QHBoxLayout(self.user_profile)
        user_layout.setContentsMargins(15, 0, 15, 0)

        # 狀態指示點（連線中/已連線兩態，狀態記錄在 widget 上供切換主題時重繪）
        status_dot = QLabel("●")
        status_dot._conn_state = "online"
        theme.register_restyle(status_dot, _restyle_conn_status_dot)
        status_dot.hide()
        self._status_dot = status_dot

        self.user_id_label = QLabel("uPtt")
        theme.register_restyle(
            self.user_id_label,
            lambda w: w.setStyleSheet(f"font-weight: bold; font-size: 13px; color: {theme.active()['text']}; background: transparent;"),
        )
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
        theme.register_restyle(self.logout_btn, lambda w: w.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {theme.active()['text_faint']};
                font-size: 16px;
                padding: 0;
            }}
            QPushButton:hover {{
                color: {theme.active()['danger']};
            }}
        """))
        user_layout.addWidget(self.logout_btn)
        
        sidebar_vbox.addWidget(self.user_profile)
        
        sidebar_header = QVBoxLayout() # 改為垂直排列
        sidebar_header.setContentsMargins(12, 15, 12, 12)
        sidebar_header.setSpacing(10)
        
        # 整合式新增對話輸入框
        self.new_chat_input = QLineEdit()
        self.new_chat_input.setPlaceholderText("搜尋對話 · 聯絡人")
        self.new_chat_input.setFixedHeight(32)
        self.new_chat_input.setObjectName("new-chat-input")
        theme.register_restyle(self.new_chat_input, lambda w: w.setStyleSheet(f"""
            QLineEdit#new-chat-input {{
                background-color: {theme.active()['bg']};
                border: 1px solid {theme.active()['border']};
                border-radius: 4px;
                padding: 0 8px;
                color: {theme.active()['text']};
                font-size: 13px;
            }}
            QLineEdit#new-chat-input:focus {{
                border-color: {theme.active()['accent']};
            }}
        """))
        self.new_chat_input.returnPressed.connect(self.handle_add_chat)

        # ⌘K 提示徽章（純外觀，不接搜尋邏輯；於 eventFilter 的 Resize 事件重新定位）
        self._search_hint = QLabel("⌘K", self.new_chat_input)
        self._search_hint.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        theme.register_restyle(self._search_hint, lambda w: w.setStyleSheet(f"""
            color: {theme.active()['text_faint']};
            background-color: {theme.active()['surface_2']};
            border: 1px solid {theme.active()['border']};
            border-radius: 3px;
            font-size: 10px;
            padding: 1px 4px;
        """))
        self._search_hint.adjustSize()
        self.new_chat_input.installEventFilter(self)
        sidebar_header.addWidget(self.new_chat_input)
        
        self.contact_list = ContactListWidget()
        self.contact_list.setObjectName("contact-list")
        self.contact_list.itemClicked.connect(self.on_contact_selected)
        self.contact_list.items_reordered.connect(self._on_items_reordered)

        # 開啟右鍵選單
        self.contact_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.contact_list.customContextMenuRequested.connect(self.show_contact_context_menu)

        # 側欄分組標頭（釘選 / 最近）——以覆蓋層實作，不插入清單模型，
        # 避免破壞 ContactListWidget 的 _pinned_count / dropEvent 索引與拖放釘選邏輯。
        self.contact_list.setViewportMargins(0, 22, 0, 0)

        def _restyle_group_header(w):
            w.setStyleSheet(
                f"color: {theme.active()['text_muted']}; background-color: {theme.active()['surface']};"
                f" font-size: 10px; font-weight: bold;"
            )

        self._group_header_top = QLabel(self.contact_list)
        theme.register_restyle(self._group_header_top, _restyle_group_header)
        self._group_header_top.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._group_header_top.hide()
        self._group_header_mid = QLabel(self.contact_list)
        theme.register_restyle(self._group_header_mid, _restyle_group_header)
        self._group_header_mid.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._group_header_mid.hide()
        # 追蹤目前被加高（為中段標頭預留空間）的釘選區最後一項之 row index，None 表示無
        self._mid_header_gap_row = None
        self.contact_list.model().rowsInserted.connect(self._on_contact_rows_changed)
        self.contact_list.model().rowsRemoved.connect(self._on_contact_rows_changed)
        self.contact_list.verticalScrollBar().valueChanged.connect(
            lambda _v: self._refresh_group_headers()
        )
        self.contact_list.viewport().installEventFilter(self)

        sidebar_vbox.addLayout(sidebar_header)
        sidebar_vbox.addWidget(self.contact_list)
        
    def _build_chat_pane(self):
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
        self._force_scroll_to_bottom = False
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
        theme.register_restyle(self.reply_bar, lambda w: w.setStyleSheet(f"""
            QWidget#reply-bar {{
                background-color: {theme.active()['surface']};
                border-top: 1px solid {theme.active()['accent']};
                border-left: 3px solid {theme.active()['accent']};
            }}
        """))
        reply_bar_layout = QHBoxLayout(self.reply_bar)
        reply_bar_layout.setContentsMargins(8, 4, 8, 4)
        reply_bar_layout.setSpacing(8)

        self.reply_bar_label = QLabel()
        theme.register_restyle(
            self.reply_bar_label,
            lambda w: w.setStyleSheet(f"color: {theme.active()['text_muted']}; font-size: 12px;"),
        )
        self.reply_bar_label.setWordWrap(False)

        cancel_reply_btn = QPushButton("✕")
        cancel_reply_btn.setFixedSize(20, 20)
        theme.register_restyle(cancel_reply_btn, lambda w: w.setStyleSheet(f"""
            QPushButton {{ color: {theme.active()['text_muted']}; background: transparent; border: none; font-size: 14px; }}
            QPushButton:hover {{ color: {theme.active()['text']}; }}
        """))
        cancel_reply_btn.setCursor(Qt.PointingHandCursor)
        cancel_reply_btn.clicked.connect(self.cancel_reply)

        reply_bar_layout.addWidget(self.reply_bar_label, 1)
        reply_bar_layout.addWidget(cancel_reply_btn)

        self.message_edit = QLineEdit() # 改用 QLineEdit 實現真正單行
        self.message_edit.setObjectName("message-edit")
        self.message_edit.setFixedHeight(36) # 標準單行高度
        self.message_edit.setPlaceholderText("輸入訊息並按下 Enter 發送...")
        self.message_edit.returnPressed.connect(self.handle_send)

        # 輸入列：輸入框（伸展佔滿）+ 字數計數 + 送出鈕同列排列，精簡版面高度
        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 6, 0, 0)
        input_row.setSpacing(8)

        self.char_count_label = QLabel(f"0 / {INPUT_CHAR_LIMIT}")
        theme.register_restyle(
            self.char_count_label,
            lambda w: w.setStyleSheet(f"color: {theme.active()['text_faint']}; font-size: 11px; background: transparent;"),
        )
        self.send_button = QPushButton("送出")
        self.send_button.setCursor(Qt.PointingHandCursor)
        self.send_button.setFixedHeight(26)
        theme.register_restyle(self.send_button, lambda w: w.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.active()['accent_bg']};
                color: {theme.active()['accent']};
                border: 1px solid {theme.active()['border']};
                border-radius: 4px;
                padding: 0 14px;
                font-size: 12px;
            }}
            QPushButton:hover {{ background-color: {theme.active()['accent_bg_hover']}; }}
            QPushButton:disabled {{ color: {theme.active()['text_faint']}; background-color: {theme.active()['surface_2']}; }}
        """))
        self.send_button.clicked.connect(self.handle_send)
        self.message_edit.textChanged.connect(self._update_char_count)

        input_row.addWidget(self.message_edit, 1, Qt.AlignVCenter)
        input_row.addWidget(self.char_count_label, 0, Qt.AlignVCenter)
        input_row.addWidget(self.send_button, 0, Qt.AlignVCenter)

        input_vbox.addWidget(self.reply_bar)
        input_vbox.addLayout(input_row)

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
        theme.register_restyle(self.chat_header_avatar, lambda w: w.setStyleSheet(f"""
            background-color: {theme.active()['accent_bg']};
            color: {theme.active()['accent']};
            border-radius: 18px;
            font-weight: bold;
            font-size: 15px;
        """))

        self.chat_header_online_dot = QLabel(chat_header_avatar_container)
        self.chat_header_online_dot.setFixedSize(10, 10)
        self.chat_header_online_dot.move(27, 28)
        theme.register_restyle(self.chat_header_online_dot, _restyle_chat_header_online_dot)
        self.chat_header_online_dot.hide()

        chat_header_text = QWidget()
        chat_header_text.setStyleSheet("background: transparent;")
        chat_header_text_layout = QVBoxLayout(chat_header_text)
        chat_header_text_layout.setContentsMargins(10, 0, 0, 0)
        chat_header_text_layout.setSpacing(1)

        self.chat_header_id = QLabel()
        theme.register_restyle(
            self.chat_header_id,
            lambda w: w.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {theme.active()['text']}; background: transparent;"),
        )
        self.chat_header_nick = QLabel()
        theme.register_restyle(
            self.chat_header_nick,
            lambda w: w.setStyleSheet(f"font-size: 11px; color: {theme.active()['text_muted']}; background: transparent;"),
        )
        self.chat_header_nick.hide()

        chat_header_text_layout.addWidget(self.chat_header_id)
        chat_header_text_layout.addWidget(self.chat_header_nick)

        # 聊天標題列在線狀態文字
        self.chat_header_online = QLabel()
        theme.register_restyle(self.chat_header_online, _restyle_chat_header_online_text)
        self.chat_header_online.hide()
        chat_header_text_layout.addWidget(self.chat_header_online)

        chat_header_layout.addWidget(chat_header_avatar_container)
        chat_header_layout.addWidget(chat_header_text, 1)

        # 標題列右側：搜尋圖示（focus 側欄搜尋框）。設計另有 ⋯ 圖示，但無現成
        # 對應動作，為避免死鈕此處略過不放。
        self.header_search_btn = QPushButton("⌕")
        self.header_search_btn.setFixedSize(30, 30)
        self.header_search_btn.setCursor(Qt.PointingHandCursor)
        self.header_search_btn.setToolTip("搜尋對話 · 聯絡人")
        theme.register_restyle(self.header_search_btn, lambda w: w.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; color: {theme.active()['text_muted']}; font-size: 18px; }}
            QPushButton:hover {{ color: {theme.active()['text']}; }}
        """))
        self.header_search_btn.clicked.connect(self.new_chat_input.setFocus)
        chat_header_layout.addWidget(self.header_search_btn)

        chat_vbox.addWidget(self.chat_header)
        chat_vbox.addWidget(self.scroll_area, stretch=1) # 給予最大拉伸權重
        chat_vbox.addWidget(self.input_area, stretch=0) # 輸入區不拉伸
        chat_vbox.setSpacing(0)

        # 底部狀態列（全寬）：左為對話/未讀計數，右為靜態資訊
        self.status_bar_widget = QWidget()
        self.status_bar_widget.setObjectName("status-bar")
        self.status_bar_widget.setFixedHeight(24)
        theme.register_restyle(
            self.status_bar_widget,
            lambda w: w.setStyleSheet(f"background-color: {theme.active()['surface']}; border-top: 1px solid {theme.active()['border']};"),
        )
        status_layout = QHBoxLayout(self.status_bar_widget)
        status_layout.setContentsMargins(14, 0, 14, 0)
        status_layout.setSpacing(0)
        self._status_left = QLabel("")
        theme.register_restyle(
            self._status_left,
            lambda w: w.setStyleSheet(f"color: {theme.active()['text_muted']}; font-size: 11px; background: transparent;"),
        )
        self._status_right = QLabel(f"uPtt v{__version__}")
        theme.register_restyle(
            self._status_right,
            lambda w: w.setStyleSheet(f"color: {theme.active()['text_faint']}; font-size: 11px; background: transparent;"),
        )
        status_layout.addWidget(self._status_left)
        status_layout.addStretch()
        status_layout.addWidget(self._status_right)

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
        settings_action = QAction("設定…", self)
        settings_action.triggered.connect(self.open_settings)
        logout_action = QAction("登出", self)
        logout_action.triggered.connect(self.handle_logout)
        quit_action = QAction("關閉", self)
        quit_action.triggered.connect(self.fully_quit)
        
        rescan_action = QAction("重新掃描信箱", self)
        rescan_action.triggered.connect(self._start_rescan)

        tray_menu.addAction(show_action)
        tray_menu.addAction(settings_action)
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
        QShortcut(QKeySequence("Ctrl+K"), self, self.open_search_palette)
        QShortcut(QKeySequence("Ctrl+Q"), self, self.fully_quit)
        QShortcut(QKeySequence("Ctrl+W"), self, self.close_current_chat)
        QShortcut(QKeySequence("Ctrl+,"), self, self.open_settings)

    def open_settings(self):
        """開啟偏好設定視窗（單例：重複觸發只 raise/activate 既有視窗，不重建）。"""
        if self._settings_window is None:
            self._settings_window = SettingsWindow(
                self.db, worker=getattr(self, 'worker', None), query_worker=getattr(self, 'query_worker', None)
            )
        self._settings_window.show()
        self._settings_window.raise_()
        self._settings_window.activateWindow()

    def _current_contacts(self) -> List[Dict]:
        """供搜尋面板取當前聯絡人清單（每筆含 ptt_id/ptt_id_display/nickname/custom_name）。"""
        out = []
        for i in range(self.contact_list.count()):
            widget = self.contact_list.itemWidget(self.contact_list.item(i))
            if widget:
                out.append(widget.get_data())
        return out

    def open_search_palette(self):
        """開啟 ⌘K 搜尋面板（單例）。選取結果後開啟該對話。"""
        if self._search_palette is None:
            self._search_palette = SearchPalette(
                self.db, self.ptt_service.ptt_id, self._current_contacts, parent=self
            )
            self._search_palette.session_selected.connect(self.add_or_select_contact)
        # 帳號可能於登入後才確定，開窗時同步一次
        self._search_palette.account_id = self.ptt_service.ptt_id
        self._search_palette.open_centered()

    def eventFilter(self, obj, event):
        """過濾按鍵/尺寸事件：處理發送邏輯，並在尺寸變動時重新定位覆蓋層元件。"""
        # new_chat_input / contact_list 的覆蓋層在 init_ui 中先於 message_edit 建立，
        # 建構期即可能收到 Resize 事件，故用 getattr 防止存取尚未建立的屬性。
        if event.type() == QEvent.Resize:
            cl = getattr(self, 'contact_list', None)
            if cl is not None and obj is cl.viewport():
                self._refresh_group_headers()
            elif obj is getattr(self, 'new_chat_input', None):
                self._reposition_search_hint()
        if obj is getattr(self, 'message_edit', None) and event.type() == QEvent.KeyPress:
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
            self.send_button.setEnabled(False)
        else:
            self.message_edit.setEnabled(True)
            self.message_edit.setPlaceholderText("輸入訊息並按下 Enter 發送...")
            self.send_button.setEnabled(True)

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

            # 上次執行若崩潰／強制結束，pending 訊息可能沒被更新狀態；登入後立刻
            # 標記為 failed，避免 ⏳ bubble 永久殘留。
            reaped = self.db.fail_dangling_pending(corrected_id)
            if reaped:
                logger.info(f"已將 {reaped} 筆殘留 pending 訊息標記為 failed")

            # 延遲 10 秒觸發副 session 登入,避開 LoginTooOften 且不影響 UI
            QTimer.singleShot(10000, self._trigger_query_login)

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

    def _trigger_query_login(self):
        """延遲觸發副 session 登入，在執行時才從 ptt_service 讀取憑證。"""
        ptt_id = self.ptt_service.ptt_id
        ptt_pw = self.ptt_service.ptt_pw
        if ptt_id and ptt_pw:
            self.query_login_requested.emit(ptt_id, ptt_pw)

    @Slot()
    def on_connection_lost(self):
        """連線中斷時更新 UI 狀態"""
        logger.warning("UI: 偵測到連線中斷")
        self._status_dot._conn_state = "connecting"
        _restyle_conn_status_dot(self._status_dot)
        self._status_dot.setToolTip("連線中斷，正在重新連線...")
        self.setWindowTitle(f"uPtt - {self.ptt_service.ptt_id} (重新連線中...)")

    @Slot()
    def on_connection_restored(self):
        """連線恢復時更新 UI 狀態"""
        logger.info("UI: 連線已恢復")
        self._status_dot._conn_state = "online"
        _restyle_conn_status_dot(self._status_dot)
        self._status_dot.setToolTip("")
        self.setWindowTitle(f"uPtt - {self.ptt_service.ptt_id}")

    @Slot()
    def on_query_session_degraded(self):
        """副 session 降級:使用者狀態資料暫時無法更新,但訊息收發不受影響。"""
        logger.warning("UI: 副 session 降級,使用者狀態暫時無法更新")
        # 把所有聯絡人的在線點點改灰色「未知」
        for i in range(self.contact_list.count()):
            item = self.contact_list.item(i)
            widget = self.contact_list.itemWidget(item)
            if widget:
                widget.set_online_unknown()
        current_tooltip = self._status_dot.toolTip()
        if "訊息收發正常" not in current_tooltip:
            self._status_dot.setToolTip("使用者狀態暫時無法更新(訊息收發正常)")

    @Slot()
    def on_query_session_restored(self):
        """副 session 恢復,使用者狀態功能重新可用。"""
        logger.info("UI: 副 session 已恢復")
        if self._status_dot.toolTip() == "使用者狀態暫時無法更新(訊息收發正常)":
            self._status_dot.setToolTip("")

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
            self.chat_header_online._online_state = is_online
            _restyle_chat_header_online_text(self.chat_header_online)
            self.chat_header_online.show()
            self.chat_header_online_dot._online_state = is_online
            _restyle_chat_header_online_dot(self.chat_header_online_dot)
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
                custom_name=s.get('custom_name') or "",
            )
            # 更新顯示大小寫
            widget.update_info(s['display_id'], s['nickname'] or "")
            if s.get('is_archived'):
                widget.set_archived(True)
            if s.get('is_muted'):
                widget.set_muted(True)
            self.contact_list.addItem(item)
            self.contact_list.setItemWidget(item, widget)

            # 初始化本地快取
            self.chat_histories[s['id']] = []
            self.unread_counts[s['id']] = s['unread_count'] or 0

        self.contact_list.blockSignals(False)
        logger.info(f"從資料庫載入 {len(sessions)} 個對話會話 (其中 {len(self.pinned_ids)} 個已釘選)")
        
        # 載入完成後，根據內容調整寬度，並更新分組標頭與底部計數
        self.update_sidebar_width()
        self._refresh_group_headers()
        self._update_status_bar()

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

    def _on_contact_rows_changed(self, *args):
        """清單列數變動時（新增/移除/拖放重建）重整分組標頭與底部計數。"""
        QTimer.singleShot(0, self._refresh_group_headers)
        QTimer.singleShot(0, self._update_status_bar)

    def _refresh_group_headers(self):
        """依釘選/未釘選分界，定位覆蓋式分組標頭。不觸碰清單模型。"""
        lw = self.contact_list
        total = lw.count()
        if total == 0:
            self._group_header_top.hide()
            self._group_header_mid.hide()
            self._set_mid_header_gap_row(None)
            return
        pinned_count = lw._pinned_count()
        vw = lw.viewport().width()
        # 頂端標頭：有釘選項顯示「釘選」，否則此區即未釘選群，顯示「最近」
        self._group_header_top.setText("釘選 · PINNED" if pinned_count > 0 else "最近 · RECENT")
        self._group_header_top.setGeometry(14, 4, max(0, vw - 20), 16)
        self._group_header_top.show()
        self._group_header_top.raise_()
        # 中段標頭：僅在同時有釘選與未釘選項時，於分界處顯示「最近」。
        # 做法：把釘選區「最後一項」的 sizeHint 加高 MID_HEADER_ROW_GAP，讓標頭落在
        # 該項下方新增的專屬空間內（該項本身內容仍是原本 62px 高、置頂對齊，不受影響），
        # 因此絕不會覆蓋任何聯絡人（釘選或未釘選）的頭像/ID。
        if pinned_count > 0 and total > pinned_count:
            gap_row = pinned_count - 1
            self._set_mid_header_gap_row(gap_row)
            rect = lw.visualItemRect(lw.item(gap_row))
            y = lw.viewport().y() + rect.top() + CONTACT_ROW_HEIGHT + 3
            self._group_header_mid.setText("最近 · RECENT")
            self._group_header_mid.setGeometry(14, y, max(0, vw - 20), 16)
            self._group_header_mid.show()
            self._group_header_mid.raise_()
        else:
            self._set_mid_header_gap_row(None)
            self._group_header_mid.hide()

    def _set_mid_header_gap_row(self, row: Optional[int]):
        """調整釘選區最後一項的 sizeHint，為中段標頭預留/收回空間。

        只動「最後一個釘選項目」這一列的高度（加高 MID_HEADER_ROW_GAP），
        絕不觸碰任何未釘選項目，因此不會影響 _pinned_count() 判斷或
        dropEvent 的索引/拖放釘選邏輯。
        """
        if row == self._mid_header_gap_row:
            return
        lw = self.contact_list
        old_row = self._mid_header_gap_row
        if old_row is not None and 0 <= old_row < lw.count():
            old_item = lw.item(old_row)
            if old_item is not None:
                old_item.setSizeHint(QSize(0, CONTACT_ROW_HEIGHT))
        if row is not None and 0 <= row < lw.count():
            new_item = lw.item(row)
            if new_item is not None:
                new_item.setSizeHint(QSize(0, CONTACT_ROW_HEIGHT + MID_HEADER_ROW_GAP))
        self._mid_header_gap_row = row

    def _reposition_search_hint(self):
        """將 ⌘K 徽章對齊搜尋框右緣。"""
        w = self.new_chat_input.width()
        h = self.new_chat_input.height()
        self._search_hint.adjustSize()
        self._search_hint.move(w - self._search_hint.width() - 8,
                               (h - self._search_hint.height()) // 2)

    def _update_char_count(self, _text: str = ""):
        """更新輸入框字數計數（顯示層，不改資料流）。"""
        n = len(self.message_edit.text())
        self.char_count_label.setText(f"{n} / {INPUT_CHAR_LIMIT}")

    def _update_status_bar(self):
        """更新底部狀態列左側的對話/未讀計數（用既有資料計算）。"""
        n = self.contact_list.count()
        unread = sum(self.unread_counts.values())
        self._status_left.setText(f"{n} 個對話 · {unread} 未讀")

    def _make_date_separator(self, dt: datetime) -> QWidget:
        """建立訊息區的置中日期分隔列（今天/昨天/日期）。"""
        d = dt.date()
        delta = (datetime.now().date() - d).days
        if delta == 0:
            label = f"今天 · {dt.strftime('%Y/%m/%d')}"
        elif delta == 1:
            label = f"昨天 · {dt.strftime('%Y/%m/%d')}"
        else:
            label = dt.strftime('%Y/%m/%d')
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 8, 0, 8)
        row_layout.setSpacing(0)
        lbl = QLabel(label)
        theme.register_restyle(
            lbl,
            lambda w: w.setStyleSheet(f"color: {theme.active()['text_faint']}; font-size: 11px; background: transparent;"),
        )
        row_layout.addStretch()
        row_layout.addWidget(lbl)
        row_layout.addStretch()
        return row

    def _ensure_contact_in_list(self, ptt_id: str, nickname: str = "") -> bool:
        """確保聯絡人已在側邊欄清單中，但不選取。回傳 True 表示新增。"""
        ptt_id_lower = ptt_id.lower()
        # 禁止與自己聊天 (self-chat forbidden)
        if ptt_id_lower == (self.ptt_service.ptt_id or "").lower():
            return False
        for i in range(self.contact_list.count()):
            widget = self.contact_list.itemWidget(self.contact_list.item(i))
            if widget and widget.ptt_id == ptt_id_lower:
                return False  # 已存在
        item = QListWidgetItem(self.contact_list)
        item.setSizeHint(QSize(0, 70))
        widget = ContactItem(ptt_id, nickname)
        self.contact_list.addItem(item)
        self.contact_list.setItemWidget(item, widget)
        if ptt_id_lower not in self.chat_histories:
            self.chat_histories[ptt_id_lower] = []
            self.unread_counts[ptt_id_lower] = 0
        self.user_info_requested.emit(ptt_id_lower)
        self.update_sidebar_width()
        return True

    def add_or_select_contact(self, ptt_id, nickname=""):
        ptt_id_lower = ptt_id.lower()

        # 禁止與自己聊天 (self-chat forbidden)
        if ptt_id_lower == (self.ptt_service.ptt_id or "").lower():
            logger.info(f"略過與自己聊天：{ptt_id}")
            return

        # 檢查是否已在清單中 (不分大小寫邏輯比較)
        found_item = None
        for i in range(self.contact_list.count()):
            item = self.contact_list.item(i)
            widget = self.contact_list.itemWidget(item)
            if widget and widget.ptt_id == ptt_id_lower:
                if widget.ptt_id_display != ptt_id:
                    widget.update_info(ptt_id, nickname)
                found_item = item
                break

        if found_item:
            self.contact_list.setCurrentItem(found_item)
            self.on_contact_selected(found_item)
            self.user_info_requested.emit(ptt_id_lower)
            return

        # 新增至清單
        self._ensure_contact_in_list(ptt_id, nickname)
        # 選取新增的項目
        for i in range(self.contact_list.count()):
            item = self.contact_list.item(i)
            widget = self.contact_list.itemWidget(item)
            if widget and widget.ptt_id == ptt_id_lower:
                self.contact_list.setCurrentItem(item)
                self.on_contact_selected(item)
                break

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
        self._update_status_bar()
        
        # 從資料庫載入歷史訊息
        messages = self.db.get_messages(current_acc, self.current_chat_id)
        parsed = []
        for m in messages:
            ts = datetime.fromisoformat(m['timestamp']) if isinstance(m['timestamp'], str) else m['timestamp']
            reply_info, actual_text = decode_reply(m['content'])
            entry = {
                'text': actual_text,
                'time': ts.strftime("%H:%M"),
                'timestamp': ts,
                'is_me': bool(m['is_me']),
                'mail_type': m.get('mail_type', 'uptt'),
                'subject': m.get('subject', ''),
                'reply_info': reply_info,
                'msg_id': m.get('id', -1),
            }
            if entry['is_me']:
                entry['send_status'] = m.get('send_status') or 'sent'
            parsed.append(entry)
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
        resolved_secondary = resolve_display_name(widget.ptt_id_display, widget._nickname, widget._custom_name)
        nickname = resolved_secondary if resolved_secondary != widget.ptt_id_display else ""
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
            self.chat_header_online.setText("● 在線上" if is_online else "● 離線")
            self.chat_header_online._online_state = is_online
            _restyle_chat_header_online_text(self.chat_header_online)
            self.chat_header_online_dot._online_state = is_online
            _restyle_chat_header_online_dot(self.chat_header_online_dot)
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
        """只在使用者已接近底部時才自動捲動，避免閱讀歷史時被強制拉回。
        切換對話或重新載入時會強制捲到底部。"""
        sb = self.scroll_area.verticalScrollBar()
        if self._force_scroll_to_bottom:
            self._force_scroll_to_bottom = False
            sb.setValue(_max)
        elif _max - sb.value() <= 50:
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

        last_date = None
        for msg in history:
            # 依日期分組，於不同日期間插入置中日期分隔列
            ts = msg.get('timestamp')
            if isinstance(ts, datetime) and ts.date() != last_date:
                self.messages_layout.addWidget(self._make_date_separator(ts))
                last_date = ts.date()
            if msg.get('mail_type') == 'waterball':
                widget = WaterballBubble(msg['text'], msg['time'], msg.get('is_me', False))
            elif msg.get('mail_type') == 'mail':
                widget = MailCard(msg.get('subject', ''), msg['text'], msg['time'])
            else:
                widget = ChatBubble(msg['text'], msg['time'], msg['is_me'],
                                    reply_info=msg.get('reply_info'),
                                    send_status=msg.get('send_status'),
                                    message_id=msg.get('msg_id'))
                widget.reply_requested.connect(self.set_reply_to)
                widget.delete_requested.connect(self.handle_delete_message)
            self.messages_layout.addWidget(widget)
        
        # 標記強制捲到底部，待 rangeChanged 信號觸發時執行
        self._force_scroll_to_bottom = True

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

    def handle_delete_message(self, message_id: int):
        """刪除單則本機訊息（僅本機，不影響 PTT 上的信件），需使用者確認。"""
        confirm = QMessageBox.question(
            self, "確認刪除", "確定要刪除這則訊息嗎？\n(僅從本機刪除，不影響 PTT 上的信件)",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        current_acc = self.ptt_service.ptt_id
        session_id = self.db.delete_message(current_acc, message_id)
        if session_id is None:
            return

        history = self.chat_histories.get(session_id, [])
        self.chat_histories[session_id] = [m for m in history if m.get('msg_id') != message_id]

        if self.current_chat_id == session_id:
            self.refresh_chat_display()

        sessions = self.db.get_all_sessions(current_acc)
        row = next((s for s in sessions if s['id'] == session_id), None)
        for i in range(self.contact_list.count()):
            widget = self.contact_list.itemWidget(self.contact_list.item(i))
            if widget and widget.ptt_id == session_id:
                widget.set_last_msg_time(_format_contact_time(row.get('last_message_time', '') if row else ''))
                break

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

        # 若有待回覆訊息，編碼回覆前綴。先快照下 reply_to 以便後續 UNIQUE 衝突
        # 時還原（避免使用者重複按 Enter 後 reply context 被吞掉）。
        reply_info = None
        saved_reply_to = self.reply_to.copy() if self.reply_to else None
        if self.reply_to:
            encoded_text = encode_reply(self.reply_to['sender'], self.reply_to['preview'], text)
            reply_info = self.reply_to.copy()
            self.cancel_reply()
        else:
            encoded_text = text

        # 1. 立即顯示在 UI (這部分仍在主執行緒)
        now = datetime.now()
        now_str = now.strftime("%H:%M")
        receiver_id = self.current_chat_id
        current_acc = self.ptt_service.ptt_id

        # 預先寫入 DB 為 pending，取得 row id 作為訊息識別子；切換對話 / 重啟後仍可
        # 還原此訊息與其狀態。
        self.db.upsert_session(account_id=current_acc, display_id=receiver_id)
        msg_id = self.db.save_pending_message(
            account_id=current_acc,
            session_id=receiver_id,
            sender_id=current_acc,
            receiver_id=receiver_id,
            content=encoded_text,
            timestamp=now,
        )
        if msg_id is None:
            # UNIQUE 衝突（同 account/session/sender/content/timestamp）—— 視為重複按下，
            # 直接吞掉此次發送，避免在 UI 留下永遠不會更新狀態的 ⏳ bubble。
            # 此處輸入框尚未 clear，保留使用者原文方便其調整後再送；同時還原 reply
            # 預覽（已在前面被 cancel_reply 隱藏）。
            logger.warning(
                f"重複的發送請求被略過（receiver={receiver_id}, ts={now.isoformat()}）"
            )
            if saved_reply_to:
                self.reply_to = saved_reply_to
                display_id = self._get_contact_display_id(saved_reply_to['sender'])
                preview = saved_reply_to['preview']
                self.reply_bar_label.setText(f"↩ @{display_id}: {preview[:60]}")
                self.reply_bar.show()
            return

        self.chat_histories[receiver_id].append({
            'text': text,
            'time': now_str,
            'timestamp': now,
            'is_me': True,
            'reply_info': reply_info,
            'send_status': 'pending',
            'msg_id': msg_id,
        })
        self.refresh_chat_display()
        self.message_edit.clear()

        # 更新聯絡人列表上的最後訊息時間
        for i in range(self.contact_list.count()):
            w = self.contact_list.itemWidget(self.contact_list.item(i))
            if w and w.ptt_id == receiver_id:
                w.set_last_msg_time(now_str)
                break

        # 送出後將此聯絡人拉到非釘選區頂端(次高)，與收訊息路徑一致
        self._move_contact_to_top(receiver_id)

        # 2. 將發送請求放入 thread-safe 佇列（繞過 Qt 事件佇列，避免被阻塞操作卡住）
        #    同時 emit signal 作為後備喚醒（worker 閒置時由 slot 觸發 drain）
        self.worker.enqueue_send(receiver_id, encoded_text, now, msg_id)
        self.send_requested.emit(receiver_id, encoded_text, now, msg_id)

    def _append_if_not_dup(self, sender: str, msg_dict: dict) -> bool:
        """將訊息加入 chat_histories，若為重複則跳過。回傳 True 表示已新增。"""
        msg_ts = msg_dict.get('timestamp')
        msg_ts_sec = msg_ts.replace(microsecond=0) if msg_ts else None
        is_dup = any(
            (m.get('timestamp', datetime.min).replace(microsecond=0) if m.get('timestamp') else None) == msg_ts_sec
            and m.get('text') == msg_dict.get('text') and m.get('is_me', False) == msg_dict.get('is_me', False)
            for m in self.chat_histories.get(sender, [])
        )
        if is_dup:
            return False
        self.chat_histories.setdefault(sender, []).append(msg_dict)
        return True

    @Slot(dict)
    def on_new_message(self, data):
        sender_id_display = data['sender']
        sender = sender_id_display.lower()

        if sender in self.blocked_users:
            logger.info(f"忽略來自已封鎖使用者 '{sender}' 的訊息")
            return

        # 從 full_author 提取暱稱
        full_author = data.get('full_author', '')
        nickname = ""
        if '(' in full_author and ')' in full_author:
            nickname = full_author[full_author.find('(')+1 : full_author.rfind(')')]

        # 確保聯絡人在側邊欄中（不強制選取，避免搶走使用者焦點）
        self._ensure_contact_in_list(sender_id_display, nickname)

        # 更新聯絡人資訊與最後訊息時間（只在 nickname 非空時更新，避免水球清除暱稱）
        now_time = datetime.now().strftime("%H:%M")
        for i in range(self.contact_list.count()):
            widget = self.contact_list.itemWidget(self.contact_list.item(i))
            if widget and widget.ptt_id == sender:
                if nickname:
                    widget.update_info(sender_id_display, nickname)
                elif widget.ptt_id_display != sender_id_display:
                    # 只更新大小寫，保留現有暱稱（讀 _nickname 快取，避免誤讀 nickname_label
                    # 顯示的 resolve_display_name 結果——若有 custom_name 會污染 PTT 暱稱）
                    widget.update_info(sender_id_display, widget._nickname)
                widget.set_last_msg_time(now_time)
                break

        # 解析回覆資訊並去重
        reply_info, actual_text = decode_reply(data['text'])
        is_me = data.get('is_me', False)
        msg_dict = {
            'text': actual_text,
            'time': data['time'],
            'timestamp': data.get('timestamp', datetime.now()),
            'is_me': is_me,
            'mail_type': data.get('mail_type', 'uptt'),
            'subject': data.get('subject', ''),
            'reply_info': reply_info,
            'msg_id': data.get('msg_id'),
        }
        # PTT 可能會把自己寄出的信透過輪詢路徑回送（多裝置 backup 等情境）；補上
        # send_status 才能在 UI 顯示 ✓，保持與 handle_send 路徑一致。
        if is_me:
            msg_dict['send_status'] = 'sent'

        if self._append_if_not_dup(sender, msg_dict):
            if self.current_chat_id == sender:
                self.refresh_chat_display()
            else:
                self.unread_counts[sender] = self.unread_counts.get(sender, 0) + 1
                for i in range(self.contact_list.count()):
                    widget = self.contact_list.itemWidget(self.contact_list.item(i))
                    if widget and widget.ptt_id == sender:
                        widget.set_unread(self.unread_counts[sender])
                        break
                self._update_status_bar()

        self._move_contact_to_top(sender)

        # 桌面通知 (僅限收到的訊息，排除自己發出的，使用者未關閉桌面通知，且該聯絡人未被靜音)
        if (not self.isActiveWindow() and not data.get('is_me', False)
                and self.db.get_config(config.SETTING_NOTIFY_ENABLED, True)
                and not self.db.is_session_muted(self.ptt_service.ptt_id, sender)):
            _, notify_text = decode_reply(data['text'])
            self.tray_icon.showMessage(
                f"新訊息: {sender_id_display}",
                notify_text[:50],
                QSystemTrayIcon.Information,
                3000
            )

    @Slot(int, bool, str)
    def on_send_result(self, msg_id, success, error_msg):
        new_status = 'sent' if success else 'failed'
        # 以 msg_id 對應到實際的 chat_histories 項目（可能不在當前對話）
        updated_chat: Optional[str] = None
        if msg_id > 0:
            for chat_id, history in self.chat_histories.items():
                for msg in history:
                    if msg.get('msg_id') == msg_id:
                        msg['send_status'] = new_status
                        updated_chat = chat_id
                        break
                if updated_chat:
                    break
        if updated_chat == self.current_chat_id:
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
            self.db.hide_session(current_acc, ptt_id_lower)
            self.chat_histories.pop(ptt_id_lower, None)
            self.unread_counts.pop(ptt_id_lower, None)
            self.session_drafts.pop(ptt_id_lower, None)
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
                self.session_drafts.pop(ptt_id_lower, None)
                self.remove_contact_from_sidebar(ptt_id_lower)
                logger.info(f"已從資料庫與介面刪除對話與紀錄: {ptt_id_lower}")

        elif action_type == "CLOSE":
            # 僅隱藏，不刪除訊息
            self.db.hide_session(current_acc, ptt_id_lower)
            self.session_drafts.pop(ptt_id_lower, None)
            self.remove_contact_from_sidebar(ptt_id_lower)

    def _rebuild_contact_item(self, data: dict, insert_pos: int, is_pinned: bool) -> QListWidgetItem:
        """從 data dict 重建 ContactItem 並插入至指定位置。回傳新的 QListWidgetItem。"""
        new_item = QListWidgetItem()
        new_item.setSizeHint(QSize(0, 70))
        new_widget = ContactItem(
            ptt_id=data['ptt_id_display'],
            nickname=data['nickname'],
            unread_count=data.get('unread_count', 0),
            is_pinned=is_pinned,
            last_msg_time=data.get('last_msg_time', ''),
            custom_name=data.get('custom_name', ''),
        )
        new_widget.set_online(data.get('is_online', False))
        if data.get('is_archived'):
            new_widget.set_archived(True)
        if data.get('is_muted'):
            new_widget.set_muted(True)
        self.contact_list.insertItem(insert_pos, new_item)
        self.contact_list.setItemWidget(new_item, new_widget)
        return new_item

    def _move_contact_to_top(self, sender: str):
        """將指定非釘選聯絡人移至非釘選區頂端 (sender 為小寫)"""
        if sender in self.pinned_ids:
            return

        pinned_count = self.contact_list._pinned_count()

        for i in range(self.contact_list.count()):
            item = self.contact_list.item(i)
            widget = self.contact_list.itemWidget(item)
            if widget and widget.ptt_id == sender:
                if i == pinned_count:
                    return
                was_selected = (self.contact_list.currentItem() == item)
                data = widget.get_data()
                self.contact_list.removeItemWidget(item)
                self.contact_list.takeItem(i)
                new_item = self._rebuild_contact_item(data, pinned_count, False)
                unread = self.unread_counts.get(sender, 0)
                if unread > 0:
                    self.contact_list.itemWidget(new_item).set_unread(unread)
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

        # _move_to_pinned_area/_move_pinned_to_unpinned_area 若項目本就在邊界位置，
        # 只會翻轉 is_pinned 旗標而不觸發 rowsInserted/Removed，標頭不會自動重整，
        # 故顯式呼叫一次確保釘選/取消釘選後標頭文字與中段留白位置都正確。
        self._refresh_group_headers()

    def _find_contact_widget(self, ptt_id_lower: str) -> Optional[ContactItem]:
        """依小寫 ptt_id 找出側邊欄對應的 ContactItem，找不到回傳 None。"""
        for i in range(self.contact_list.count()):
            widget = self.contact_list.itemWidget(self.contact_list.item(i))
            if widget and widget.ptt_id == ptt_id_lower:
                return widget
        return None

    def rename_contact(self, ptt_id: str):
        """重新命名聯絡人（本機 alias）。輸入空字串 = 清除自訂名稱，還原為 PTT 暱稱。"""
        ptt_id_lower = ptt_id.lower()
        widget = self._find_contact_widget(ptt_id_lower)
        if not widget:
            return
        current_acc = self.ptt_service.ptt_id
        current_name = resolve_display_name(widget.ptt_id_display, widget._nickname, widget._custom_name)
        text, ok = QInputDialog.getText(
            self, "重新命名聯絡人", "顯示名稱（留空還原為 PTT 暱稱）：",
            QLineEdit.Normal, current_name
        )
        if not ok:
            return
        new_name = text.strip()
        self.db.set_custom_name(current_acc, ptt_id_lower, new_name)
        widget.set_custom_name(new_name)
        if self.current_chat_id == ptt_id_lower:
            resolved_secondary = resolve_display_name(widget.ptt_id_display, widget._nickname, widget._custom_name)
            nickname = resolved_secondary if resolved_secondary != widget.ptt_id_display else ""
            self._update_chat_header(widget.ptt_id_display, nickname, widget._is_online)

    def toggle_mute(self, ptt_id: str):
        """切換聯絡人的靜音通知狀態。"""
        ptt_id_lower = ptt_id.lower()
        widget = self._find_contact_widget(ptt_id_lower)
        if not widget:
            return
        current_acc = self.ptt_service.ptt_id
        new_state = not widget._is_muted
        self.db.set_muted(current_acc, ptt_id_lower, new_state)
        widget.set_muted(new_state)

    def export_chat_history(self, ptt_id: str):
        """匯出與該聯絡人的完整對話紀錄為純文字檔。"""
        ptt_id_lower = ptt_id.lower()
        current_acc = self.ptt_service.ptt_id
        widget = self._find_contact_widget(ptt_id_lower)
        display_name = (
            resolve_display_name(widget.ptt_id_display, widget._nickname, widget._custom_name)
            if widget else ptt_id
        )
        default_name = f"對話_{display_name}_{datetime.now().strftime('%Y%m%d')}.txt"
        path, _ = QFileDialog.getSaveFileName(self, "匯出對話紀錄", default_name, "文字檔 (*.txt)")
        if not path:
            return

        messages = self.db.get_messages(current_acc, ptt_id_lower, limit=None)
        lines = []
        for m in messages:
            ts = m['timestamp']
            ts_dt = datetime.fromisoformat(ts) if isinstance(ts, str) else ts
            ts_str = ts_dt.strftime('%Y-%m-%d %H:%M:%S')
            sender = current_acc if m['is_me'] else display_name
            _, text = decode_reply(m['content'])
            lines.append(f"[{ts_str}] {sender}: {text}")

        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
        except OSError as e:
            QMessageBox.warning(self, "匯出失敗", f"無法寫入檔案：{e}")

    def _move_to_pinned_area(self, ptt_id_lower: str):
        """將項目移至釘選區末尾並標記為釘選。"""
        insert_pos = self.contact_list._pinned_count()

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
                new_item = self._rebuild_contact_item(data, insert_pos, True)
                if was_selected:
                    self.contact_list.setCurrentItem(new_item)
                return

    def _move_pinned_to_unpinned_area(self, ptt_id_lower: str):
        """將取消釘選的項目移至非釘選區頂端。"""
        insert_pos = self.contact_list._pinned_count() - 1

        for i in range(self.contact_list.count()):
            item = self.contact_list.item(i)
            widget = self.contact_list.itemWidget(item)
            if widget and widget.ptt_id == ptt_id_lower:
                was_selected = (self.contact_list.currentItem() == item)
                data = widget.get_data()
                self.contact_list.removeItemWidget(item)
                self.contact_list.takeItem(i)
                new_item = self._rebuild_contact_item(data, insert_pos, False)
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

    def _build_contact_context_menu(self, ptt_id: str, is_pinned: bool, is_muted: bool) -> QMenu:
        """建立聯絡人右鍵選單（依設計稿排序：釘選 → 改名/靜音/匯出 → destructive 群）。"""
        menu = QMenu(self)

        pin_action = QAction("取消釘選" if is_pinned else "釘選對話\t⌘D", self)
        pin_action.triggered.connect(lambda: self.toggle_pin(ptt_id))
        menu.addAction(pin_action)

        rename_action = QAction("重新命名…", self)
        rename_action.triggered.connect(lambda: self.rename_contact(ptt_id))
        menu.addAction(rename_action)

        mute_action = QAction("取消靜音" if is_muted else "靜音通知", self)
        mute_action.triggered.connect(lambda: self.toggle_mute(ptt_id))
        menu.addAction(mute_action)

        export_action = QAction("匯出對話紀錄…", self)
        export_action.triggered.connect(lambda: self.export_chat_history(ptt_id))
        menu.addAction(export_action)

        # ponytail: 設計稿另有「標記為未讀 ⌘U」，需要可手動設非零的未讀旗標新後端，本輪不做。

        menu.addSeparator()

        block_action = QAction("封鎖此使用者", self)
        block_action.triggered.connect(lambda: self.handle_contact_action(ptt_id, "BLOCK"))
        menu.addAction(block_action)

        # CLOSE 動作呼叫 db.hide_session（is_visible=0，僅隱藏不刪訊息），語意即設計稿的「隱藏對話」
        hide_action = QAction("隱藏對話", self)
        hide_action.triggered.connect(lambda: self.handle_contact_action(ptt_id, "CLOSE"))
        menu.addAction(hide_action)

        delete_action = QAction("刪除…", self)
        delete_action.triggered.connect(lambda: self.handle_contact_action(ptt_id, "DELETE"))
        menu.addAction(delete_action)

        # danger 紅字（封鎖/隱藏/刪除）per-item 上色：QMenu::item 屬性選取器對 Qt 無效
        # （見 styles.py 選單註解），最短解做不到，本步延後；要做需改 QWidgetAction 自訂上色。

        return menu

    def show_contact_context_menu(self, pos):
        """顯示聯絡人清單的右鍵選單"""
        item = self.contact_list.itemAt(pos)
        if not item:
            return

        widget = self.contact_list.itemWidget(item)
        is_pinned = widget.ptt_id in self.pinned_ids
        menu = self._build_contact_context_menu(widget.ptt_id, is_pinned, widget._is_muted)
        menu.exec(self.contact_list.mapToGlobal(pos))

    def _stop_all_threads(self):
        """停止所有背景執行緒 (query worker → main worker → version check)。"""
        from PySide6.QtCore import QMetaObject
        if hasattr(self, 'query_worker') and hasattr(self, 'query_thread') and self.query_thread.isRunning():
            QMetaObject.invokeMethod(self.query_worker, "stop", Qt.BlockingQueuedConnection)
        if hasattr(self, 'query_thread') and self.query_thread.isRunning():
            self.query_thread.quit()
            if not self.query_thread.wait(3000):
                self.query_thread.terminate()
                self.query_thread.wait()
        if hasattr(self, 'worker') and hasattr(self, 'ptt_thread') and self.ptt_thread.isRunning():
            QMetaObject.invokeMethod(self.worker, "stop", Qt.BlockingQueuedConnection)
        if hasattr(self, 'ptt_thread') and self.ptt_thread.isRunning():
            self.ptt_thread.quit()
            if not self.ptt_thread.wait(3000):
                self.ptt_thread.terminate()
                self.ptt_thread.wait()
        if hasattr(self, '_ver_thread') and self._ver_thread.isRunning():
            self._ver_thread.quit()
            self._ver_thread.wait(11000)

    def handle_logout(self):
        """登出並回到登入畫面（需使用者確認）"""
        confirm = QMessageBox.question(
            self, "確認登出", "確定要登出目前的帳號嗎？",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.No:
            return
        self._do_logout()

    @Slot(str)
    def _handle_disconnected(self, reason):
        """處理非預期斷線（如信箱已滿導致 PyPtt 自動登出）"""
        logger.warning(f"非預期斷線: {reason}")
        QMessageBox.warning(self, "連線中斷", reason)
        self._do_logout()

    def _do_logout(self):
        """執行登出清理流程（停止 Worker、重設 PTT、清除 UI、切回登入畫面）"""
        logger.info("執行登出程序...")
        outgoing_acc = self.ptt_service.ptt_id
        try:
            try:
                self._stop_all_threads()
            finally:
                # _stop_all_threads 可能 terminate worker，未完成的 send 會留下殘留
                # pending row；放在 finally 確保即使 stop 拋例外也會清理。
                if outgoing_acc:
                    reaped = self.db.fail_dangling_pending(outgoing_acc)
                    if reaped:
                        logger.info(f"登出時清理 {reaped} 筆殘留 pending 訊息")

            self.ptt_service = UPttService()
            self.ptt_query_service = UPttService(kick_on_reconnect=False)

            # 清除 UI 狀態
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

            self.setMinimumSize(0, 0)
            self.setMaximumSize(16777215, 16777215)
            self.setFixedSize(760, 500)

            # 5. 切換畫面
            self.central_stack.setCurrentIndex(0)
            self.login_screen.login_btn.setEnabled(True)
            self.login_screen.login_btn.setText(self.login_screen._BTN_TEXT)
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
        if self._quitting:
            return
        self._quitting = True

        logger.info("正在執行完全退出程序...")
        try:
            self._stop_all_threads()

            if hasattr(self, 'tray_icon'):
                self.tray_icon.hide()

            logger.info("退出程序完成，關閉應用程式。")
            QApplication.quit()

        except Exception as e:
            logger.error(f"退出程式時發生異常: {e}")
            QApplication.quit()

# 為了讓 QSystemTrayIcon 能找到 QStyle，需要引入 QApplication
from PySide6.QtWidgets import QApplication, QStyle
