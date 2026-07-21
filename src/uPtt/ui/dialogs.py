from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QSpinBox, QVBoxLayout,
)

from uPtt import config
from uPtt.ui import styles
from uPtt.ui.widgets import ThemeCard, ToggleSwitch
from uPtt.utils import decode_reply


def _make_section_title(text: str) -> QLabel:
    """SectionGroup 標題：10px faint、字距加大營造大寫感（中文無大小寫，僅拉字距）。"""
    label = QLabel(text)
    t = styles.theme()
    label.setStyleSheet(f"color: {t['faint']}; font-size: 10px; font-weight: 600; background: transparent;")
    font = label.font()
    font.setLetterSpacing(QFont.PercentageSpacing, 114)
    label.setFont(font)
    return label


def _make_section_card():
    """回傳 (card, layout)：surface 底、1px divider 邊框、radius 6 的區塊卡片容器。"""
    t = styles.theme()
    card = QFrame()
    card.setStyleSheet(
        f"QFrame {{ background-color: {t['surface']}; border: 1px solid {t['divider']}; border-radius: 6px; }}"
    )
    layout = QVBoxLayout(card)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    return card, layout


def _add_row(card_layout: QVBoxLayout, label_text: str, control, hint_text: str = ""):
    """在區塊卡片內加入一列 Row：左側 label(+hint)、右側控制元件。
    首列無上分隔線，其餘列上緣加 1px divider。"""
    t = styles.theme()
    row = QFrame()
    row_style = "background: transparent;"
    if card_layout.count() > 0:
        row_style = f"border-top: 1px solid {t['divider']}; background: transparent;"
    row.setStyleSheet(row_style)

    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(14, 10, 14, 10)
    row_layout.setSpacing(10)

    text_layout = QVBoxLayout()
    text_layout.setSpacing(2)
    label = QLabel(label_text)
    label.setStyleSheet(f"font-size: 12px; font-weight: 500; color: {t['ink']}; background: transparent;")
    text_layout.addWidget(label)
    if hint_text:
        hint = QLabel(hint_text)
        hint.setStyleSheet(f"font-size: 10.5px; color: {t['muted']}; background: transparent;")
        hint.setWordWrap(True)
        text_layout.addWidget(hint)

    row_layout.addLayout(text_layout, 1)
    row_layout.addWidget(control, 0, Qt.AlignVCenter)

    card_layout.addWidget(row)
    return row


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


class MessageSearchDialog(QDialog):
    """全域訊息搜尋：跨當前帳號所有對話搜尋訊息內容，點選結果跳轉到該則訊息。"""
    result_activated = Signal(str, int)  # (session_id, msg_id)

    def __init__(self, db, account_id: str, parent=None):
        super().__init__(parent)
        self.db = db
        self.account_id = account_id
        self.setWindowTitle("搜尋訊息")
        self.setMinimumSize(460, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("輸入關鍵字後按 Enter 搜尋...")
        self.search_input.returnPressed.connect(self._do_search)
        layout.addWidget(self.search_input)

        self.result_list = QListWidget()
        self.result_list.itemClicked.connect(self._on_item_activated)
        layout.addWidget(self.result_list, 1)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {styles.theme()['muted']}; font-size: 12px;")
        layout.addWidget(self.status_label)

    def _do_search(self):
        query = self.search_input.text().strip()
        self.result_list.clear()
        if not query:
            self.status_label.setText("")
            return
        results = self.db.search_messages(self.account_id, query)
        if not results:
            self.status_label.setText("找不到符合的訊息")
            return
        self.status_label.setText(f"找到 {len(results)} 則訊息")
        for r in results:
            _, text = decode_reply(r.get('content', ''))
            snippet = text.replace('\n', ' ').strip()
            if len(snippet) > 50:
                snippet = snippet[:50] + "…"
            ts = r.get('timestamp', '')
            ts_disp = _format_contact_time(ts) if isinstance(ts, str) else ""
            session_id = r.get('session_id', '')
            item = QListWidgetItem(f"{session_id}  ·  {snippet}    {ts_disp}")
            item.setData(Qt.UserRole, (session_id, r.get('id', -1)))
            self.result_list.addItem(item)

    def _on_item_activated(self, item):
        data = item.data(Qt.UserRole)
        if not data:
            return
        session_id, msg_id = data
        self.result_activated.emit(session_id, msg_id)
        self.accept()


class SettingsDialog(QDialog):
    """設定對話框：分區卡片版面（外觀 / 通知與輪詢）。
    存檔／套用邏輯與 db key 沿用既有設計，只重整外觀與控制元件
    （主題下拉 → 三張主題預覽卡；通知 QCheckBox → 滑動 ToggleSwitch）。"""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("設定")
        self.setMinimumWidth(440)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 32, 20)
        outer.setSpacing(14)

        # ── 外觀 ──
        outer.addWidget(_make_section_title("外觀"))
        appearance_card, appearance_layout = _make_section_card()
        outer.addWidget(appearance_card)

        current_theme = db.get_config(config.SETTING_THEME, styles.DEFAULT_THEME)
        self._selected_theme = current_theme if current_theme in styles.THEMES else styles.DEFAULT_THEME
        self._theme_cards = {}

        theme_row = QFrame()
        theme_row.setStyleSheet("background: transparent;")
        theme_row_layout = QVBoxLayout(theme_row)
        theme_row_layout.setContentsMargins(14, 12, 14, 12)
        theme_row_layout.setSpacing(8)

        theme_label = QLabel("選擇主題")
        t = styles.theme()
        theme_label.setStyleSheet(f"font-size: 12px; font-weight: 500; color: {t['ink']}; background: transparent;")
        theme_row_layout.addWidget(theme_label)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(10)
        for theme_id, theme_dict in styles.THEMES.items():
            card = ThemeCard(theme_id, theme_dict)
            card.set_selected(theme_id == self._selected_theme)
            card.clicked.connect(self._on_theme_card_clicked)
            self._theme_cards[theme_id] = card
            cards_layout.addWidget(card)
        cards_layout.addStretch(1)
        theme_row_layout.addLayout(cards_layout)

        appearance_layout.addWidget(theme_row)

        # ── 通知與輪詢 ──
        outer.addWidget(_make_section_title("通知與輪詢"))
        poll_card, poll_layout = _make_section_card()
        outer.addWidget(poll_card)

        self.notify_checkbox = ToggleSwitch()
        self.notify_checkbox.setChecked(bool(db.get_config(config.SETTING_NOTIFY_ENABLED, True)))
        _add_row(poll_layout, "桌面通知", self.notify_checkbox, "有新訊息時彈出系統通知")

        self.mail_spin = self._make_spin(
            config.SETTING_MAIL_INTERVAL, config.CHECK_PTT_MAIL_INTERVAL, config.MAIL_INTERVAL_MIN)
        _add_row(poll_layout, "信件輪詢間隔", self.mail_spin, "秒，數值越小越即時")

        self.waterball_spin = self._make_spin(
            config.SETTING_WATERBALL_INTERVAL, config.CHECK_WATERBALL_INTERVAL, config.WATERBALL_INTERVAL_MIN)
        _add_row(poll_layout, "水球輪詢間隔", self.waterball_spin, "秒")

        self.online_spin = self._make_spin(
            config.SETTING_ONLINE_INTERVAL, config.CHECK_ONLINE_STATUS_INTERVAL, config.ONLINE_INTERVAL_MIN)
        _add_row(poll_layout, "在線狀態輪詢間隔", self.online_spin, "秒")

        note = QLabel("輪詢間隔越短越即時，但過於頻繁可能被 PTT 限流。變更儲存後立即套用。")
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {styles.theme()['muted']}; font-size: 11px; background: transparent;")
        outer.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _on_theme_card_clicked(self, theme_id: str):
        self._selected_theme = theme_id
        for key, card in self._theme_cards.items():
            card.set_selected(key == theme_id)

    def _make_spin(self, key, default, minimum):
        t = styles.theme()
        spin = QSpinBox()
        spin.setRange(minimum, 3600)  # 下限即為避免限流的最小間隔
        spin.setValue(config.get_setting_interval(self.db, key, default, minimum))
        spin.setFixedWidth(84)
        spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: {t['surface2']};
                color: {t['ink']};
                border: 1px solid {t['border']};
                border-radius: 5px;
                padding: 3px 6px;
            }}
        """)
        return spin

    def _save(self):
        self.db.set_config(config.SETTING_THEME, self._selected_theme)
        self.db.set_config(config.SETTING_NOTIFY_ENABLED, self.notify_checkbox.isChecked())
        self.db.set_config(config.SETTING_MAIL_INTERVAL,
                           config.clamp_interval(self.mail_spin.value(), config.MAIL_INTERVAL_MIN))
        self.db.set_config(config.SETTING_WATERBALL_INTERVAL,
                           config.clamp_interval(self.waterball_spin.value(), config.WATERBALL_INTERVAL_MIN))
        self.db.set_config(config.SETTING_ONLINE_INTERVAL,
                           config.clamp_interval(self.online_spin.value(), config.ONLINE_INTERVAL_MIN))
        self.accept()
