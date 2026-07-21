from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from uPtt.ui import styles
from uPtt.ui.widgets import SyncSpinner

class ScanSetupScreen(QWidget):
    """首次登入信箱掃描設定畫面"""
    scan_days_selected = Signal(int)
    scan_skipped = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("scan-setup-screen")
        self.setAttribute(Qt.WA_StyledBackground, True)
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
        self.title_label = QLabel("信箱掃描")
        self.title_label.setAlignment(Qt.AlignCenter)

        self.desc_label = QLabel("uPtt 需要掃描您的 PTT 信箱，\n才能載入過去的對話紀錄。")
        self.desc_label.setAlignment(Qt.AlignCenter)
        self.desc_label.setWordWrap(True)

        self.subtitle_label = QLabel("選擇要載入的信件範圍")
        self.subtitle_label.setAlignment(Qt.AlignCenter)

        self.sep_line = QFrame()
        self.sep_line.setFrameShape(QFrame.HLine)

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
        progress_layout.setSpacing(10)

        # 旋轉 spinner：Qt 沒有 CSS animation，SyncSpinner 內部用 QTimer + QPainter
        # 模擬旋轉（見 widgets.py），start()/stop() 由 show_progress()/reset() 控制。
        self.progress_spinner = SyncSpinner()

        self.progress_label = QLabel("正在掃描信件...")
        self.progress_label.setAlignment(Qt.AlignCenter)

        # 確定型進度條：range/value 直接對應 scanned/total，寬度依百分比自然填色
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)

        # 進度條下方兩端文字：左「已整理 x/y 封」、右「百分比」
        progress_status_row = QWidget()
        progress_status_row.setStyleSheet("background: transparent;")
        progress_status_layout = QHBoxLayout(progress_status_row)
        progress_status_layout.setContentsMargins(0, 0, 0, 0)
        progress_status_layout.setSpacing(0)

        self.progress_scanned_label = QLabel("已整理 0/0 封")
        self.progress_percent_label = QLabel("0%")
        progress_status_layout.addWidget(self.progress_scanned_label)
        progress_status_layout.addStretch()
        progress_status_layout.addWidget(self.progress_percent_label)

        self.progress_title = QLabel("")
        # 掃描中顯示的信件主旨，來源為任意 PTT 使用者，禁止 HTML 算繪
        self.progress_title.setTextFormat(Qt.TextFormat.PlainText)
        self.progress_title.setAlignment(Qt.AlignCenter)
        self.progress_title.setWordWrap(True)
        self.progress_title.setMaximumWidth(360)

        progress_layout.addWidget(self.progress_spinner, alignment=Qt.AlignHCenter)
        progress_layout.addWidget(self.progress_label)
        progress_layout.addSpacing(4)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(progress_status_row)
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

        # 套用目前主題的顏色（初始化與後續 refresh_theme() 共用同一份邏輯）
        self.refresh_theme()

    def refresh_theme(self):
        """重新套用 inline 樣式的顏色。初始化時與 MainWindow.apply_theme() 切換主題時
        都會呼叫——這些元件用 setStyleSheet 直接設色，不受父層 QSS 的主題切換影響。"""
        t = styles.theme()
        self.setStyleSheet(f"background-color: {t['bg']};")
        self.title_label.setStyleSheet(
            f"color: {t['ink']}; font-size: 18px; font-weight: bold; background: transparent;"
        )
        self.desc_label.setStyleSheet(
            f"color: {t['muted']}; font-size: 13px; background: transparent; line-height: 1.5;"
        )
        self.subtitle_label.setStyleSheet(f"color: {t['muted']}; font-size: 13px; background: transparent;")
        self.sep_line.setStyleSheet(f"background-color: {t['divider']}; border: none; max-height: 1px;")

        btn_style = f"""
            QPushButton {{
                background-color: {t['accentSoft']}; color: {t['accent']};
                border: 1px solid {t['accent']}; border-radius: 8px;
                font-weight: bold; font-size: 14px; padding: 10px 20px;
            }}
        """
        btn_hover_style = f"""
            QPushButton:hover {{ background-color: {t['accent']}; color: {t['accentInk']}; border-color: {t['accent']}; }}
        """
        for btn in (self.btn_7d, self.btn_30d, self.btn_all, self.btn_custom):
            btn.setStyleSheet(btn_style + btn_hover_style)

        self.custom_label.setStyleSheet(f"color: {t['muted']}; font-size: 13px; background: transparent;")
        self.day_label.setStyleSheet(f"color: {t['muted']}; font-size: 13px; background: transparent;")
        self.custom_input.setStyleSheet(
            f"padding: 8px; border: 1px solid {t['border']}; border-radius: 7px;"
            f"background-color: {t['surface']}; color: {t['ink']}; font-size: 14px;"
        )

        self.progress_label.setStyleSheet(f"""
            font-family: {t['fontDisplay']};
            color: {t['ink']};
            font-size: 19px;
            font-weight: 500;
            background: transparent;
        """)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {t['surface2']};
                border: 1px solid {t['divider']};
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {t['accent']};
                border-radius: 3px;
            }}
        """)
        self.progress_scanned_label.setStyleSheet(f"color: {t['muted']}; font-size: 11px; background: transparent;")
        self.progress_percent_label.setStyleSheet(f"color: {t['muted']}; font-size: 11px; background: transparent;")
        self.progress_title.setStyleSheet(f"color: {t['muted']}; font-size: 12px; background: transparent;")

        self.skip_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {t['faint']}; font-size: 12px; padding: 6px 0;
            }}
            QPushButton:hover {{ color: {t['muted']}; }}
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
        self._reset_progress_display()
        self.progress_widget.show()
        self.progress_spinner.start()

    @Slot(int, int, str)
    def update_progress(self, current, total, title):
        self.progress_bar.setRange(0, total if total > 0 else 1)
        self.progress_bar.setValue(max(0, min(current, total)) if total > 0 else 0)
        self.progress_scanned_label.setText(f"已整理 {current}/{total} 封")
        percent = int((current / total) * 100) if total > 0 else 0
        self.progress_percent_label.setText(f"{percent}%")
        # 截斷過長標題
        display_title = title if len(title) <= 40 else title[:37] + "..."
        self.progress_title.setText(display_title)

    def _reset_progress_display(self):
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_scanned_label.setText("已整理 0/0 封")
        self.progress_percent_label.setText("0%")
        self.progress_title.setText("")

    def reset(self):
        self.options_widget.show()
        self.progress_widget.hide()
        self.custom_input.clear()
        self._reset_progress_display()
        self.progress_spinner.stop()
