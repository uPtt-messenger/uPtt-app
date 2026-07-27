# --- uPtt QSS 樣式表 ---
#
# 所有顏色 / 字型從當前主題 token 組出，不在此硬寫 hex。

from uPtt.ui import theme
from uPtt.ui.theme import FONT_STACK


def build_main_style() -> str:
    """組出 MainWindow / LoginWindow 共用的 QSS，讀當前主題（theme.active()）。"""
    t = theme.active()
    bg = t["bg"]
    surface = t["surface"]
    surface_hover = t["surface_hover"]
    surface_2 = t["surface_2"]
    border = t["border"]
    border_strong = t["border_strong"]
    text = t["text"]
    text_muted = t["text_muted"]  # noqa: F841 (保留供未來 QSS 規則使用，與舊常數對齊)
    text_faint = t["text_faint"]
    accent = t["accent"]
    accent_hover = t["accent_hover"]
    accent_bg = t["accent_bg"]
    accent_bg_hover = t["accent_bg_hover"]
    danger = t["danger"]

    return f"""
/* 全域字體與背景 */
QWidget {{
    font-family: {FONT_STACK};
    font-size: 14px;
    background-color: {bg};
    color: {text};
}}

/* 登入視窗 */
#login-window {{
    background-color: {bg};
}}


#login-window QLineEdit {{
    padding: 9px 13px;
    border: 1px solid {border};
    border-radius: 7px;
    background-color: {surface};
    color: {text};
    font-size: 14px;
}}

#login-window QLineEdit:focus {{
    border: 1px solid {accent};
    background-color: {surface};
}}

/* 登入按鈕 */
#login-window #login-btn {{
    background-color: {accent_bg};
    color: {accent};
    border: 1px solid {accent_hover};
    border-radius: 8px;
    font-weight: bold;
    font-size: 14px;
    letter-spacing: 2px;
}}

#login-window #login-btn:hover {{
    background-color: {accent_bg_hover};
    color: {accent};
    border-color: {accent};
}}

#login-window #login-btn:disabled {{
    background-color: {surface};
    border: 1px solid {surface_2};
    color: {text_faint};
}}

#login-window #error-label {{
    color: {danger};
    font-size: 12px;
}}

/* 全域 QLineEdit */
QLineEdit {{
    padding: 8px 12px;
    border: 1px solid {border};
    border-radius: 6px;
    background-color: {bg};
    color: {text};
}}

QLineEdit:focus {{
    border: 1px solid {accent};
}}

QLineEdit::placeholder {{
    color: {text_faint};
}}

/* 全域 QPushButton */
QPushButton {{
    padding: 8px 14px;
    background-color: {surface_2};
    color: {accent};
    border: 1px solid {border};
    border-radius: 6px;
    font-weight: bold;
}}

QPushButton:hover {{
    background-color: {accent_bg};
    border-color: {accent_hover};
}}

QPushButton:disabled {{
    background-color: {surface};
    color: {text_faint};
    border-color: {surface_2};
}}

/* 側邊欄 */
#sidebar {{
    background-color: {surface};
    border-right: 1px solid {border};
    min-width: 160px;
    max-width: 450px;
}}

#user-profile {{
    background-color: {surface};
    border-bottom: 1px solid {border};
}}

/* 對話清單 */
QListWidget {{
    border: none;
    background-color: transparent;
    outline: none;
}}

QListWidget::item {{
    border: none;
    padding: 0px;
    margin: 0px;
}}

QListWidget::item:selected {{
    background-color: {surface_2};
}}

QListWidget::item:hover:!selected {{
    background-color: {surface_hover};
}}

/* 搜尋/新增輸入框 */
QLineEdit#new-chat-input {{
    background-color: {bg};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 0 8px;
    color: {text};
    font-size: 13px;
}}

QLineEdit#new-chat-input:focus {{
    border-color: {accent};
}}

/* 聊天區域 */
#chat-area {{
    background-color: {bg};
}}

/* 聊天標題列 */
#chat-header {{
    background-color: {surface};
    border-bottom: 1px solid {border};
}}

/* 訊息捲動區 */
#messages-scroll {{
    background-color: {bg};
    border: none;
}}

#messages-container {{
    background-color: {bg};
}}

/* 訊息輸入區 */
#input-area {{
    background-color: {surface};
    border-top: 1px solid {border};
}}

QLineEdit#message-edit {{
    border: 1px solid {border};
    border-radius: 8px;
    background-color: {bg};
    color: {text};
    padding: 8px 12px;
    font-size: 14px;
}}

QLineEdit#message-edit:focus {{
    border-color: {accent};
}}

/* 回覆預覽條 */
QWidget#reply-bar {{
    background-color: {surface};
    border-top: 1px solid {border};
    border-left: 3px solid {accent};
}}

/* 捲軸 */
QScrollArea {{
    border: none;
    background-color: transparent;
}}

QScrollBar:vertical {{
    border: none;
    background: transparent;
    width: 5px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {border_strong};
    border-radius: 2px;
    min-height: 24px;
}}

QScrollBar::handle:vertical:hover {{
    background: {text_faint};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: transparent;
}}

/* 右鍵選單（訊息／聯絡人／tray 共用同一套外觀）。
   註：danger 色（如刪除項）目前無法靠 QSS 屬性選取器（QMenu::item[prop="x"]）
   套用到單一 QAction ——實測 Qt 不會依 QAction 的 dynamic property 分別上色
   選單項。真的要做 per-item 上色，改用 QWidgetAction 包一個自訂上色的 QLabel。*/
QMenu {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 4px;
    color: {text};
}}

QMenu::item {{
    padding: 6px 16px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {accent};
    color: {bg};
}}

QMenu::item:disabled {{
    color: {text_faint};
}}

QMenu::separator {{
    height: 1px;
    background: {border};
    margin: 4px 4px;
}}
"""


# 水球氣泡的 inline 樣式：置中細 pill，低調表層。水球是即時提示而非左右對話
# 氣泡，設計稿不分本人/對方一律置中同款，故 is_me 保留參數（呼叫端仍傳入）但
# 不影響外觀，避免跟主要訊息氣泡的方向語意混淆。
def get_waterball_bubble_style(is_me: bool) -> str:
    t = theme.active()
    return f"""
        background-color: {t["surface_2"]};
        border: 1px solid {t["border"]};
        border-radius: 12px;
    """


# 對話氣泡的 inline 樣式（本人＝實心 accent 綠底＋深色文字，靠右；對方＝中性
# 表層底＋一般文字，靠左。兩者需一眼可辨，對齊設計稿）
def get_bubble_style(is_me: bool) -> str:
    t = theme.active()
    if is_me:
        return f"""
            background-color: {t["accent"]};
            color: {t["bg"]};
            border-radius: 14px;
            border-top-right-radius: 3px;
        """
    else:
        return f"""
            background-color: {t["surface_2"]};
            color: {t["text"]};
            border-radius: 14px;
            border-top-left-radius: 3px;
        """
