# --- uPtt 偏好設定視窗 ---
#
# 從 fix/audit-findings 分支的 SettingsDialog 移植而來，改為獨立頂層視窗
# （無 OK/取消，每個控制項變更即存即套），並把存取器改接現行的
# uPtt.ui.theme 主題引擎。所有顏色一律讀 theme.active()，不在此檔硬寫 hex。

import logging

from PySide6.QtCore import Qt, QMetaObject, Signal
from PySide6.QtGui import QFont, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QLabel,
    QSpinBox, QTabWidget, QToolTip, QVBoxLayout, QWidget,
)

from uPtt import __version__, config, contant
from uPtt.ui import theme
from uPtt.ui.styles import build_main_style

logger = logging.getLogger("uPtt.settings")


# 主題卡片顯示用的 name/tag 中繼資料。theme.py 的 THEMES 只存色票 token，不含展示文字，
# 刻意不塞進 theme.py（該檔只管色票與切換引擎），故獨立放在此檔。
_THEME_META = {
    'graphite': {'name': 'Graphite', 'tag': '深色 · 冷灰中性 + 鼠尾草綠'},
    'bone': {'name': 'Bone', 'tag': '淺色 · 冷灰白'},
    'kraft': {'name': '再生紙', 'tag': 'VIP 專屬 · 暖色 · 再生紙感', 'vip_only': True},
}


# --- 重套色函式（供 theme.register_restyle 登記；只吃參數 w，不得 capture self）---

def _restyle_section_title(w):
    t = theme.active()
    w.setStyleSheet(f"color: {t['text_faint']}; font-size: 10px; font-weight: 600; background: transparent;")


def _restyle_card(w):
    t = theme.active()
    w.setStyleSheet(
        f"QFrame {{ background-color: {t['surface']}; border: 1px solid {t['border']}; border-radius: 6px; }}"
    )


def _restyle_row(w):
    """設定列容器：首列無上緣分隔線，其餘列有。是否有分隔線存於 w._has_divider。"""
    t = theme.active()
    if getattr(w, "_has_divider", False):
        w.setStyleSheet(f"border-top: 1px solid {t['border']}; background: transparent;")
    else:
        w.setStyleSheet("background: transparent;")


def _restyle_row_label(w):
    t = theme.active()
    w.setStyleSheet(f"font-size: 12px; font-weight: 500; color: {t['text']}; background: transparent;")


def _restyle_row_hint(w):
    t = theme.active()
    w.setStyleSheet(f"font-size: 10.5px; color: {t['text_muted']}; background: transparent;")


def _restyle_note(w):
    t = theme.active()
    w.setStyleSheet(f"color: {t['text_muted']}; font-size: 11px; background: transparent;")


def _restyle_spin(w):
    t = theme.active()
    w.setStyleSheet(f"""
        QSpinBox {{
            background-color: {t['surface_2']};
            color: {t['text']};
            border: 1px solid {t['border']};
            border-radius: 5px;
            padding: 3px 6px;
        }}
    """)


def _restyle_toggle(w):
    """ToggleSwitch 的顏色在 paintEvent 內即時取色，這裡只需要求它重繪。"""
    w.update()


def _restyle_theme_card(w):
    w.set_selected(w._selected)


class ToggleSwitch(QCheckBox):
    """滑動式開關（設定頁用），取代預設 QCheckBox 外觀。
    軌道 32x18、radius 999，on=accent、off=中性灰；把手 14x14 白圓。
    繼承 QCheckBox 只為維持 isChecked()/setChecked()/toggled 等標準 API，
    好讓既有的存讀邏輯（db.get_config/set_config 讀寫 bool）不必改動；
    外觀完全由 paintEvent 自行繪製，不呼叫 super().paintEvent()。"""

    _W, _H = 32, 18
    _KNOB = 14
    _MARGIN = (_H - _KNOB) // 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self._W, self._H)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("background: transparent;")
        self.toggled.connect(lambda _checked: self.update())
        theme.register_restyle(self, _restyle_toggle)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, event):
        t = theme.active()  # 當下取色，不快取，切主題後下次重繪即生效
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)

        track_rect = self.rect()
        track_color = QColor(t['accent']) if self.isChecked() else QColor(t['text_faint'])
        painter.setBrush(track_color)
        painter.drawRoundedRect(track_rect, self._H / 2, self._H / 2)

        knob_x = (track_rect.width() - self._MARGIN - self._KNOB) if self.isChecked() else self._MARGIN
        # ponytail: 把手固定白圓，設計稿三主題通用（在 accent/faint 軌道上皆有對比），刻意不 token 化
        painter.setBrush(QColor(Qt.white))
        painter.drawEllipse(knob_x, self._MARGIN, self._KNOB, self._KNOB)
        painter.end()


class ThemeCard(QFrame):
    """單張主題預覽卡：name + tag + bg/surface/accent 色票，選中時套 accent 邊框。
    點擊發射 clicked(theme_id)；選中狀態由外層容器（SettingsWindow）透過 set_selected() 控制。
    locked=True（VIP 專屬主題但帳號非 VIP）時：卡片半透明、游標變禁止圖示、點擊不會
    emit clicked，只彈出提示文字，不會套用/儲存該主題。"""

    clicked = Signal(str)

    def __init__(self, theme_id: str, theme_dict: dict, locked: bool = False, parent=None):
        super().__init__(parent)
        self.theme_id = theme_id
        self.locked = locked
        self._selected = False
        self.setCursor(Qt.ForbiddenCursor if locked else Qt.PointingHandCursor)
        self.setFixedSize(116, 116)  # tag 最長兩行需要的高度（如 graphite 的「深色‧冷灰中性 + 鼠尾草綠」）

        if locked:
            opacity = QGraphicsOpacityEffect(self)
            opacity.setOpacity(0.5)
            self.setGraphicsEffect(opacity)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 8)
        layout.setSpacing(6)

        swatch = QWidget()
        swatch.setFixedHeight(24)
        swatch.setStyleSheet("background: transparent;")
        swatch_layout = QHBoxLayout(swatch)
        swatch_layout.setContentsMargins(0, 0, 0, 0)
        swatch_layout.setSpacing(0)
        for i, color_key in enumerate(('bg', 'surface', 'accent')):
            chip = QFrame()
            radius_css = ""
            if i == 0:
                radius_css = "border-top-left-radius: 4px; border-bottom-left-radius: 4px;"
            elif i == 2:
                radius_css = "border-top-right-radius: 4px; border-bottom-right-radius: 4px;"
            chip.setStyleSheet(
                f"background-color: {theme_dict[color_key]}; border: none; {radius_css}"
            )
            swatch_layout.addWidget(chip, 1)
        layout.addWidget(swatch)

        meta = _THEME_META.get(theme_id, {'name': theme_id, 'tag': ''})
        name_text = f"{meta['name']} 🔒" if locked else meta['name']
        self._name_label = QLabel(name_text)
        layout.addWidget(self._name_label)

        self._tag_label = QLabel(meta['tag'])
        self._tag_label.setWordWrap(True)
        layout.addWidget(self._tag_label)

        theme.register_restyle(self, _restyle_theme_card)

    def mousePressEvent(self, event):
        if self.locked:
            QToolTip.showText(event.globalPosition().toPoint(), "VIP 專屬主題", self)
            return
        self.clicked.emit(self.theme_id)
        super().mousePressEvent(event)

    def set_selected(self, is_selected: bool):
        """套用選中/未選中外觀。卡片外框與文字一律用「目前作用中 UI 主題」
        （非卡片代表的主題）的 token 當下取色，確保在任何主題下都清晰可讀；
        只有色票 swatch 才顯示該卡代表的主題本身的顏色。"""
        self._selected = is_selected
        t = theme.active()
        border_color = t['accent'] if is_selected else t['border']
        border_width = 2 if is_selected else 1
        self.setStyleSheet(
            f"QFrame {{ background-color: {t['surface']}; "
            f"border: {border_width}px solid {border_color}; border-radius: 8px; }}"
        )
        self._name_label.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {t['text']}; background: transparent;"
        )
        self._tag_label.setStyleSheet(
            f"font-size: 10px; color: {t['text_muted']}; background: transparent;"
        )


def _make_section_title(text: str) -> QLabel:
    """SectionGroup 標題：10px faint、字距加大營造大寫感（中文無大小寫，僅拉字距）。"""
    label = QLabel(text)
    theme.register_restyle(label, _restyle_section_title)
    font = label.font()
    font.setLetterSpacing(QFont.PercentageSpacing, 114)
    label.setFont(font)
    return label


def _make_section_card():
    """回傳 (card, layout)：surface 底、1px divider 邊框、radius 6 的區塊卡片容器。"""
    card = QFrame()
    theme.register_restyle(card, _restyle_card)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    return card, layout


def _add_row(card_layout: QVBoxLayout, label_text: str, control, hint_text: str = ""):
    """在區塊卡片內加入一列 Row：左側 label(+hint)、右側控制元件。
    首列無上分隔線，其餘列上緣加 1px divider。"""
    row = QFrame()
    row._has_divider = card_layout.count() > 0
    theme.register_restyle(row, _restyle_row)

    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(14, 10, 14, 10)
    row_layout.setSpacing(10)

    text_layout = QVBoxLayout()
    text_layout.setSpacing(2)
    label = QLabel(label_text)
    theme.register_restyle(label, _restyle_row_label)
    text_layout.addWidget(label)
    if hint_text:
        hint = QLabel(hint_text)
        theme.register_restyle(hint, _restyle_row_hint)
        hint.setWordWrap(True)
        text_layout.addWidget(hint)

    row_layout.addLayout(text_layout, 1)
    row_layout.addWidget(control, 0, Qt.AlignVCenter)

    card_layout.addWidget(row)
    return row


# 快捷鍵分頁的靜態對照表（與 screens.py MainWindow 綁定的 QShortcut 一致）。
_SHORTCUTS = [
    ("⌘K / Ctrl+K", "搜尋訊息 · 聯絡人"),
    ("⌘N / Ctrl+N", "新對話"),
    ("⌘I / Ctrl+I", "個人資料"),
    ("⌘, / Ctrl+,", "開啟設定"),
    ("⌘W / Ctrl+W", "關閉目前對話"),
    ("⌘Q / Ctrl+Q", "結束 uPtt"),
]


def _make_tab_page():
    """建立一個分頁內容 QWidget，回傳 (page, 內容 VBox)。"""
    page = QWidget()
    page.setAttribute(Qt.WA_StyledBackground, True)
    page.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(20, 18, 24, 18)
    layout.setSpacing(12)
    return page, layout


def _restyle_tabs(w):
    t = theme.active()
    w.setStyleSheet(
        f"QTabWidget::pane {{ border: none; background: transparent; }}"
        f"QTabBar::tab {{ background: transparent; color: {t['text_muted']}; "
        f"padding: 8px 14px; margin-right: 2px; border: none; "
        f"border-bottom: 2px solid transparent; }}"
        f"QTabBar::tab:selected {{ color: {t['text']}; "
        f"border-bottom: 2px solid {t['accent']}; }}"
        f"QTabBar::tab:hover {{ color: {t['text']}; }}"
    )


def _restyle_shortcut_key(w):
    t = theme.active()
    w.setStyleSheet(
        f"color: {t['accent']}; font-size: 12px; font-weight: 600; "
        f"background: transparent;"
    )


def _restyle_about_title(w):
    t = theme.active()
    w.setStyleSheet(
        f"color: {t['text']}; font-size: 18px; font-weight: 700; "
        f"background: transparent;"
    )


class SettingsWindow(QWidget):
    """偏好設定視窗：分區卡片版面（外觀 / 通知與輪詢）。
    無 OK/取消，每個控制項變更即存即套：
      - 主題：點 ThemeCard → theme.apply_theme() + db.set_config
      - 桌面通知：ToggleSwitch → db.set_config
      - 信件／水球／在線輪詢間隔：QSpinBox → db.set_config，並跨執行緒
        通知對應 worker 的 apply_poll_intervals() 立即套用到執行中的計時器。
    """

    def __init__(self, db, worker=None, query_worker=None, is_vip: bool = False, parent=None):
        super().__init__(parent)
        self.db = db
        self.worker = worker
        self.query_worker = query_worker
        self.is_vip = is_vip

        self.setWindowTitle("設定")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumWidth(440)

        self.setMinimumSize(480, 440)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.tabs = QTabWidget()
        theme.register_restyle(self.tabs, _restyle_tabs)
        outer.addWidget(self.tabs)

        self.tabs.addTab(self._build_appearance_tab(db), "外觀")
        self.tabs.addTab(self._build_notify_tab(db), "通知")
        self.tabs.addTab(self._build_sync_tab(db), "連線 · 同步")
        self.tabs.addTab(self._build_shortcuts_tab(), "快捷鍵")
        self.tabs.addTab(self._build_about_tab(), "關於")

        theme.register_restyle(self, lambda w: w.setStyleSheet(build_main_style()))

    # ── 分頁建構 ──

    def _build_appearance_tab(self, db) -> QWidget:
        page, layout = _make_tab_page()
        card, card_layout = _make_section_card()

        current_theme = db.get_config(config.SETTING_THEME, theme.current_theme())
        self._selected_theme = current_theme if current_theme in theme.THEMES else theme.current_theme()
        self._theme_cards = {}

        theme_row = QFrame()
        theme_row.setStyleSheet("background: transparent;")
        theme_row_layout = QVBoxLayout(theme_row)
        theme_row_layout.setContentsMargins(14, 12, 14, 12)
        theme_row_layout.setSpacing(8)

        theme_label = QLabel("選擇主題")
        theme.register_restyle(theme_label, _restyle_row_label)
        theme_row_layout.addWidget(theme_label)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(10)
        for theme_id, theme_dict in theme.THEMES.items():
            meta = _THEME_META.get(theme_id, {})
            locked = meta.get('vip_only', False) and not self.is_vip
            tcard = ThemeCard(theme_id, theme_dict, locked=locked)
            tcard.set_selected(theme_id == self._selected_theme)
            tcard.clicked.connect(self._on_theme_card_clicked)
            self._theme_cards[theme_id] = tcard
            cards_layout.addWidget(tcard)
        cards_layout.addStretch(1)
        theme_row_layout.addLayout(cards_layout)

        card_layout.addWidget(theme_row)
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _build_notify_tab(self, db) -> QWidget:
        page, layout = _make_tab_page()
        card, card_layout = _make_section_card()

        self.notify_toggle = ToggleSwitch()
        self.notify_toggle.setChecked(bool(db.get_config(config.SETTING_NOTIFY_ENABLED, True)))
        self.notify_toggle.toggled.connect(self._on_notify_toggled)
        _add_row(card_layout, "桌面通知", self.notify_toggle, "有新訊息時彈出系統通知")

        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _build_sync_tab(self, db) -> QWidget:
        page, layout = _make_tab_page()
        card, card_layout = _make_section_card()

        self.mail_spin = self._make_spin(
            config.SETTING_MAIL_INTERVAL, config.CHECK_PTT_MAIL_INTERVAL, config.MAIL_INTERVAL_MIN)
        self.mail_spin.valueChanged.connect(self._on_mail_interval_changed)
        _add_row(card_layout, "信件輪詢間隔", self.mail_spin, "秒，數值越小越即時")

        self.waterball_spin = self._make_spin(
            config.SETTING_WATERBALL_INTERVAL, config.CHECK_WATERBALL_INTERVAL, config.WATERBALL_INTERVAL_MIN)
        self.waterball_spin.valueChanged.connect(self._on_waterball_interval_changed)
        _add_row(card_layout, "水球輪詢間隔", self.waterball_spin, "秒")

        self.online_spin = self._make_spin(
            config.SETTING_ONLINE_INTERVAL, config.CHECK_ONLINE_STATUS_INTERVAL, config.ONLINE_INTERVAL_MIN)
        self.online_spin.valueChanged.connect(self._on_online_interval_changed)
        _add_row(card_layout, "在線狀態輪詢間隔", self.online_spin, "秒")

        layout.addWidget(card)
        note = QLabel("輪詢間隔越短越即時，但過於頻繁可能被 PTT 限流。變更後立即套用，免重啟。")
        note.setWordWrap(True)
        theme.register_restyle(note, _restyle_note)
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    def _build_shortcuts_tab(self) -> QWidget:
        page, layout = _make_tab_page()
        card, card_layout = _make_section_card()

        grid = QGridLayout()
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(9)
        grid.setColumnStretch(1, 1)
        for r, (keys, action) in enumerate(_SHORTCUTS):
            key_label = QLabel(keys)
            theme.register_restyle(key_label, _restyle_shortcut_key)
            act_label = QLabel(action)
            theme.register_restyle(act_label, _restyle_row_label)
            grid.addWidget(key_label, r, 0, Qt.AlignLeft)
            grid.addWidget(act_label, r, 1)
        card_layout.addLayout(grid)

        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _build_about_tab(self) -> QWidget:
        page, layout = _make_tab_page()
        card, card_layout = _make_section_card()

        inner = QVBoxLayout()
        inner.setContentsMargins(14, 14, 14, 14)
        inner.setSpacing(6)
        name = QLabel(contant.pkg_name)
        theme.register_restyle(name, _restyle_about_title)
        ver = QLabel(f"版本 {__version__}")
        theme.register_restyle(ver, _restyle_row_label)
        lic = QLabel("授權：GPL-3.0 · 儲存：SQLite")
        theme.register_restyle(lic, _restyle_note)
        link = QLabel(f'<a href="{contant.DOWNLOAD_URL}">{contant.DOWNLOAD_URL}</a>')
        link.setOpenExternalLinks(True)
        theme.register_restyle(link, _restyle_row_label)
        for w in (name, ver, lic, link):
            inner.addWidget(w)
        card_layout.addLayout(inner)

        layout.addWidget(card)
        layout.addStretch(1)
        return page

    # ── 主題 ──

    def _on_theme_card_clicked(self, theme_id: str):
        self._selected_theme = theme_id
        theme.apply_theme(theme_id)
        self.db.set_config(config.SETTING_THEME, theme_id)
        for key, card in self._theme_cards.items():
            card.set_selected(key == theme_id)

    # ── 通知 ──

    def _on_notify_toggled(self, checked: bool):
        self.db.set_config(config.SETTING_NOTIFY_ENABLED, bool(checked))

    # ── 輪詢間隔 ──

    def _make_spin(self, key, default, minimum):
        spin = QSpinBox()
        spin.setRange(minimum, 3600)  # 下限即為避免限流的最小間隔
        spin.setValue(config.get_setting_interval(self.db, key, default, minimum))
        spin.setFixedWidth(84)
        theme.register_restyle(spin, _restyle_spin)
        return spin

    def _on_mail_interval_changed(self, value: int):
        self.db.set_config(config.SETTING_MAIL_INTERVAL, config.clamp_interval(value, config.MAIL_INTERVAL_MIN))
        self._apply_worker_intervals()

    def _on_waterball_interval_changed(self, value: int):
        self.db.set_config(
            config.SETTING_WATERBALL_INTERVAL, config.clamp_interval(value, config.WATERBALL_INTERVAL_MIN))
        self._apply_worker_intervals()

    def _on_online_interval_changed(self, value: int):
        self.db.set_config(
            config.SETTING_ONLINE_INTERVAL, config.clamp_interval(value, config.ONLINE_INTERVAL_MIN))
        self._apply_query_worker_intervals()

    def _apply_worker_intervals(self):
        """通知 PTTWorker（信件／水球輪詢）跨執行緒重讀 DB 設定並套用到執行中的計時器。"""
        if self.worker is not None:
            QMetaObject.invokeMethod(self.worker, "apply_poll_intervals", Qt.QueuedConnection)

    def _apply_query_worker_intervals(self):
        """通知 QueryWorker（在線狀態輪詢）跨執行緒重讀 DB 設定並套用到執行中的計時器。"""
        if self.query_worker is not None:
            QMetaObject.invokeMethod(self.query_worker, "apply_poll_intervals", Qt.QueuedConnection)
