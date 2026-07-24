# ⌘K 搜尋 / 指令面板（artboard 27）。
# 跨當前帳號搜尋：聯絡人（ptt_id / nickname / custom_name 子字串）＋ 訊息內容
# （接後端 db.search_messages）。選取結果即開啟該對話。
#
# 所有顏色一律讀 theme.active()，不在此檔硬寫 hex（比照 settings.py 慣例）。
import logging

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QLabel,
)

from uPtt.ui import theme
from uPtt.ui.theme import FONT_STACK
from uPtt.utils import resolve_display_name, decode_reply

logger = logging.getLogger("uPtt.ui.search_palette")

# 訊息內容預覽最大字數（超過截斷加省略號）。
_PREVIEW_MAX = 48
# 訊息結果每次最多撈幾筆（面板不做無限捲動，夠用即可）。
_MSG_LIMIT = 50
# 輸入去抖動延遲（ms）：連打時避免每個 keystroke 都打 DB。
_DEBOUNCE_MS = 140


def _restyle_container(w):
    t = theme.active()
    w.setStyleSheet(
        f"#search-palette {{ background: {t['surface']}; border: 1px solid "
        f"{t['border_strong']}; border-radius: 12px; }}"
    )


def _restyle_input(w):
    t = theme.active()
    w.setStyleSheet(
        f"background: {t['bg']}; color: {t['text']}; border: 1px solid "
        f"{t['border']}; border-radius: 8px; padding: 10px 12px; "
        f"font-family: {FONT_STACK}; font-size: 14px;"
    )


def _restyle_list(w):
    t = theme.active()
    w.setStyleSheet(
        f"QListWidget {{ background: transparent; border: none; "
        f"font-family: {FONT_STACK}; }}"
        f"QListWidget::item {{ color: {t['text']}; padding: 7px 10px; "
        f"border-radius: 8px; }}"
        f"QListWidget::item:selected {{ background: {t['surface_2']}; }}"
        f"QListWidget::item:hover {{ background: {t['surface_hover']}; }}"
    )


def _restyle_hint(w):
    t = theme.active()
    w.setStyleSheet(
        f"color: {t['text_faint']}; font-size: 11px; background: transparent; "
        f"font-family: {FONT_STACK};"
    )


def _preview(content: str) -> str:
    """把訊息內容剝除 uPtt 回覆包裝、壓成單行預覽並截斷。"""
    _reply_info, text = decode_reply(content or "")
    text = " ".join(text.split())
    if len(text) > _PREVIEW_MAX:
        text = text[:_PREVIEW_MAX].rstrip() + "…"
    return text


class SearchPalette(QWidget):
    """⌘K 搜尋面板。以無邊框浮層置中於父視窗；Enter/點擊開啟對話，Esc 關閉。

    session_selected(session_id) 於選取結果時發出，由 MainWindow 接去 add_or_select_contact。
    """

    session_selected = Signal(str)

    def __init__(self, db, account_id: str, contacts_provider, parent=None):
        """db: DatabaseManager；account_id: 當前帳號；contacts_provider: 無參
        callable，回傳 [{'ptt_id','ptt_id_display','nickname','custom_name'}, ...]。"""
        super().__init__(parent)
        self.db = db
        self.account_id = account_id
        self._contacts_provider = contacts_provider

        self.setObjectName("search-palette")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setWindowModality(Qt.ApplicationModal)
        self.setFixedWidth(560)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._run_search)

        self._build_ui()
        theme.register_restyle(self, _restyle_container)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 12)
        root.setSpacing(10)

        self.input = QLineEdit()
        self.input.setPlaceholderText("搜尋訊息 · 聯絡人")
        self.input.textChanged.connect(lambda _: self._debounce.start())
        theme.register_restyle(self.input, _restyle_input)
        root.addWidget(self.input)

        self.results = QListWidget()
        self.results.setUniformItemSizes(False)
        self.results.itemActivated.connect(self._on_item_chosen)
        self.results.itemClicked.connect(self._on_item_chosen)
        theme.register_restyle(self.results, _restyle_list)
        root.addWidget(self.results)

        self.hint = QLabel("↑↓ 選擇 · ↵ 開啟 · esc 關閉")
        self.hint.setAlignment(Qt.AlignRight)
        theme.register_restyle(self.hint, _restyle_hint)
        root.addWidget(self.hint)

    # ---- 搜尋邏輯（純資料，供測試直接呼叫）----
    def compute_results(self, query: str) -> list:
        """回傳結果 dict 清單。每筆：
        {'kind': 'contact'|'message', 'session_id': str, 'label': str}。
        聯絡人結果排在訊息之前。空查詢回傳空清單。"""
        q = (query or "").strip()
        if not q:
            return []
        ql = q.lower()
        out = []

        for c in (self._contacts_provider() or []):
            pid = c.get("ptt_id", "")
            display = c.get("ptt_id_display", pid)
            nickname = c.get("nickname", "") or ""
            custom = c.get("custom_name", "") or ""
            hay = f"{pid} {display} {nickname} {custom}".lower()
            if ql in hay:
                name = resolve_display_name(display, nickname, custom)
                label = display if name == display else f"{display}  ({name})"
                out.append({"kind": "contact", "session_id": pid, "label": f"👤  {label}"})

        for m in self.db.search_messages(self.account_id, q, limit=_MSG_LIMIT):
            sid = m.get("session_id", "")
            preview = _preview(m.get("content", ""))
            out.append({
                "kind": "message",
                "session_id": sid,
                "label": f"💬  {preview}   ·  @{sid}",
            })
        return out

    def _run_search(self):
        self.results.clear()
        for r in self.compute_results(self.input.text()):
            item = QListWidgetItem(r["label"])
            item.setData(Qt.UserRole, r["session_id"])
            self.results.addItem(item)
        if self.results.count():
            self.results.setCurrentRow(0)

    def _on_item_chosen(self, item):
        if item is None:
            return
        session_id = item.data(Qt.UserRole)
        if session_id:
            self.session_selected.emit(session_id)
        self.close()

    # ---- 開窗 / 鍵盤 ----
    def open_centered(self):
        """置中於父視窗、清空並取得焦點後顯示。"""
        self.input.clear()
        self.results.clear()
        parent = self.parentWidget()
        if parent is not None:
            pg = parent.frameGeometry()
            self.adjustSize()
            x = pg.center().x() - self.width() // 2
            y = pg.top() + max(80, pg.height() // 6)
            self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            self.close()
            return
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self._on_item_chosen(self.results.currentItem())
            return
        # ↑↓ 轉給結果清單，讓輸入框保有焦點也能移動選取。
        if key in (Qt.Key_Down, Qt.Key_Up) and self.results.count():
            row = self.results.currentRow()
            row += 1 if key == Qt.Key_Down else -1
            row = max(0, min(self.results.count() - 1, row))
            self.results.setCurrentRow(row)
            return
        super().keyPressEvent(event)
