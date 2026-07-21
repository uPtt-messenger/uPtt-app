# --- uPtt 主題與 QSS 樣式表 ---
#
# 三套主題（graphite / bone / mono）的 token 定義，逐字搬自設計稿
# scratchpad/assets/themes.jsx.js，設計稿沒有但功能上必需的補充：
#   - `danger`：dark 用 #E08070、light 用 #B33A20
#   - `warn`（重連中狀態，需與 `online`/`danger` 有色相或明度區隔）：
#     graphite #D29922（琥珀，沿用 tokenize 前的舊硬編碼色）、
#     bone #9A6700（深琥珀，淺底上維持對比）、
#     mono #8A8A8A（mono 刻意零彩度，改用中灰做明度區分，不用彩色；
#     介於 muted #6A6A6A 與 faint #A8A8A8 中間，避免與兩者混淆——
#     原本誤用 #6A6A6A 與 muted 完全同色，已修正）
#
# 鐵則：任何模組都不准在 import time 快取 token（不可 `INK = theme()['ink']`），
# 一律在需要顏色的當下呼叫 styles.theme()['ink']。

THEMES = {
    # i · Graphite — cool dark, sage accent. The daily driver.
    'graphite': {
        'id': 'graphite',
        'name': 'Graphite',
        'tag': '主推 · 日常',
        'mode': 'dark',
        'font': "'IBM Plex Mono', 'Noto Sans Mono CJK TC', 'Noto Sans TC', ui-monospace, monospace",
        'fontDisplay': "'IBM Plex Mono', 'Noto Sans TC', ui-monospace, monospace",
        'bg': '#0E1114',
        'bgGrain': 'none',
        'surface': '#15191E',
        'surface2': '#1A1F25',
        'panel': '#11151A',
        'ink': '#E6EAEF',
        'ink2': '#B8BFC8',
        'muted': '#6E7682',
        'faint': '#444B55',
        'divider': 'rgba(230,234,239,0.06)',
        'border': 'rgba(230,234,239,0.11)',
        'accent': '#8FBFA0',
        'accentInk': '#0E1114',
        'accentSoft': '#1E2D24',
        'selection': 'rgba(143,191,160,0.14)',
        'own': '#1F3528',
        'ownInk': '#D6EADD',
        'other': '#1A1F25',
        'otherInk': '#E6EAEF',
        'mail': '#161A1F',
        'mailBorder': 'rgba(230,234,239,0.14)',
        'waterball': '#1E2A33',
        'waterballInk': '#9FBCD0',
        'quoteBar': '#8FBFA0',
        'quoteBg': 'rgba(143,191,160,0.08)',
        'online': '#8FBFA0',
        'warn': '#D29922',
        'danger': '#E08070',
    },

    # ii · Bone — cool light, forest accent. Day / mail mode.
    'bone': {
        'id': 'bone',
        'name': 'Bone',
        'tag': '白天 · 收信',
        'mode': 'light',
        'font': "'JetBrains Mono', 'Noto Sans Mono CJK TC', 'Noto Sans TC', ui-monospace, monospace",
        'fontDisplay': "'JetBrains Mono', 'Noto Sans TC', ui-monospace, monospace",
        'bg': '#F3F5F5',
        'bgGrain': 'none',
        'surface': '#EAECEE',
        'surface2': '#FFFFFF',
        'panel': '#FFFFFF',
        'ink': '#14171B',
        'ink2': '#2E343C',
        'muted': '#5C6470',
        'faint': '#9098A4',
        'divider': 'rgba(20,23,27,0.08)',
        'border': 'rgba(20,23,27,0.14)',
        'accent': '#2F6B47',
        'accentInk': '#FFFFFF',
        'accentSoft': '#D6E2DA',
        'selection': 'rgba(47,107,71,0.08)',
        'own': '#1F2429',
        'ownInk': '#E8EBEF',
        'other': '#FFFFFF',
        'otherInk': '#14171B',
        'mail': '#FFFFFF',
        'mailBorder': 'rgba(20,23,27,0.18)',
        'waterball': '#E3E9EF',
        'waterballInk': '#2A4356',
        'quoteBar': '#2F6B47',
        'quoteBg': 'rgba(47,107,71,0.06)',
        'online': '#2F6B47',
        'warn': '#9A6700',
        'danger': '#B33A20',
    },

    # iii · Mono — pure monochrome editorial. Zero chroma.
    'mono': {
        'id': 'mono',
        'name': 'Mono',
        'tag': '純黑白 · 排版至上',
        'mode': 'light',
        'font': "'Geist Mono', 'JetBrains Mono', 'Noto Sans Mono CJK TC', 'Noto Sans TC', ui-monospace, monospace",
        'fontDisplay': "'Geist Mono', 'Noto Sans TC', ui-monospace, monospace",
        'bg': '#F7F7F7',
        'bgGrain': 'none',
        'surface': '#EFEFEF',
        'surface2': '#FFFFFF',
        'panel': '#FFFFFF',
        'ink': '#0A0A0A',
        'ink2': '#2E2E2E',
        'muted': '#6A6A6A',
        'faint': '#A8A8A8',
        'divider': 'rgba(0,0,0,0.08)',
        'border': 'rgba(0,0,0,0.16)',
        'accent': '#0A0A0A',
        'accentInk': '#FFFFFF',
        'accentSoft': '#E4E4E4',
        'selection': 'rgba(0,0,0,0.06)',
        'own': '#0A0A0A',
        'ownInk': '#FFFFFF',
        'other': '#FFFFFF',
        'otherInk': '#0A0A0A',
        'mail': '#FFFFFF',
        'mailBorder': 'rgba(0,0,0,0.20)',
        'waterball': '#EFEFEF',
        'waterballInk': '#0A0A0A',
        'quoteBar': '#0A0A0A',
        'quoteBg': 'rgba(0,0,0,0.04)',
        'online': '#0A0A0A',
        'warn': '#8A8A8A',
        'danger': '#B33A20',
    },
}

DEFAULT_THEME = 'graphite'

# 目前生效中的主題名稱（僅存 name，不快取任何 token 值）
_active_theme = DEFAULT_THEME


def set_theme(name: str) -> None:
    """切換 active theme；未知 name fallback 到 DEFAULT_THEME。"""
    global _active_theme
    _active_theme = name if name in THEMES else DEFAULT_THEME


def theme() -> dict:
    """取得 active theme 的 token dict —— 所有 widget 只走這個，不得於 import time 快取結果。"""
    return THEMES.get(_active_theme, THEMES[DEFAULT_THEME])


def build_style() -> str:
    """回傳 active theme 的整窗 QSS。"""
    return MAIN_STYLE_TEMPLATE % theme()


# QSS 樣板：用 %(token)s 佔位（不能用 str.format 的 {} ，QSS 選擇器本身就用花括號）。
MAIN_STYLE_TEMPLATE = """
/* 全域字體與背景 */
QWidget {
    font-family: %(font)s;
    font-size: 14px;
    background-color: %(bg)s;
    color: %(ink)s;
}

/* 登入視窗 */
#login-window {
    background-color: %(bg)s;
}


#login-window QLineEdit {
    padding: 9px 13px;
    border: 1px solid %(border)s;
    border-radius: 7px;
    background-color: %(surface)s;
    color: %(ink)s;
    font-size: 14px;
}

#login-window QLineEdit:focus {
    border: 1px solid %(accent)s;
    background-color: %(surface)s;
}

/* 登入按鈕 */
#login-window #login-btn {
    background-color: %(accentSoft)s;
    color: %(accent)s;
    border: 1px solid %(accent)s;
    border-radius: 8px;
    font-weight: bold;
    font-size: 14px;
    letter-spacing: 2px;
}

#login-window #login-btn:hover {
    background-color: %(accent)s;
    color: %(accentInk)s;
    border-color: %(accent)s;
}

#login-window #login-btn:disabled {
    background-color: %(panel)s;
    border: 1px solid %(divider)s;
    color: %(faint)s;
}

#login-window #error-label {
    color: %(danger)s;
    font-size: 12px;
}

/* 全域 QLineEdit */
QLineEdit {
    padding: 8px 12px;
    border: 1px solid %(border)s;
    border-radius: 6px;
    background-color: %(bg)s;
    color: %(ink)s;
}

QLineEdit:focus {
    border: 1px solid %(accent)s;
}

QLineEdit::placeholder {
    color: %(faint)s;
}

/* 全域 QPushButton */
QPushButton {
    padding: 8px 14px;
    background-color: %(surface)s;
    color: %(accent)s;
    border: 1px solid %(border)s;
    border-radius: 6px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: %(accentSoft)s;
    border-color: %(accent)s;
}

QPushButton:disabled {
    background-color: %(panel)s;
    color: %(faint)s;
    border-color: %(divider)s;
}

/* 側邊欄 */
#sidebar {
    background-color: %(panel)s;
    border-right: 1px solid %(divider)s;
    min-width: 160px;
    max-width: 450px;
}

#user-profile {
    background-color: %(panel)s;
    border-bottom: 1px solid %(divider)s;
}

/* 對話清單 */
QListWidget {
    border: none;
    background-color: transparent;
    outline: none;
}

QListWidget::item {
    border: none;
    padding: 0px;
    margin: 0px;
}

QListWidget::item:selected {
    background-color: %(selection)s;
}

QListWidget::item:hover:!selected {
    background-color: %(surface2)s;
}

/* 搜尋/新增輸入框 */
QLineEdit#new-chat-input {
    background-color: %(bg)s;
    border: 1px solid %(border)s;
    border-radius: 6px;
    padding: 0 8px;
    color: %(ink2)s;
    font-size: 13px;
}

QLineEdit#new-chat-input:focus {
    border-color: %(accent)s;
}

/* 聊天區域 */
#chat-area {
    background-color: %(bg)s;
}

/* 聊天標題列 */
#chat-header {
    background-color: %(panel)s;
    border-bottom: 1px solid %(divider)s;
}

/* 訊息捲動區 */
#messages-scroll {
    background-color: %(bg)s;
    border: none;
}

#messages-container {
    background-color: %(bg)s;
}

/* 訊息輸入區 */
#input-area {
    background-color: %(panel)s;
    border-top: 1px solid %(divider)s;
}

QPlainTextEdit#message-edit {
    border: 1px solid %(border)s;
    border-radius: 8px;
    background-color: %(bg)s;
    color: %(ink)s;
    padding: 6px 12px;
    font-size: 14px;
}

QPlainTextEdit#message-edit:focus {
    border-color: %(accent)s;
}

/* 回覆預覽條 */
QWidget#reply-bar {
    background-color: %(panel)s;
    border-top: 1px solid %(divider)s;
    border-left: 3px solid %(accent)s;
}

/* 捲軸 */
QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 5px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: %(border)s;
    border-radius: 2px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: %(muted)s;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
}

/* 右鍵選單 */
QMenu {
    background-color: %(panel)s;
    border: 1px solid %(border)s;
    border-radius: 6px;
    padding: 4px;
    color: %(ink)s;
}

QMenu::item {
    padding: 6px 16px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: %(selection)s;
    color: %(accent)s;
}

QMenu::separator {
    height: 1px;
    background: %(divider)s;
    margin: 4px 0;
}
"""


# 水球氣泡的 inline 樣式（is_me 目前共用同一組 waterball/waterballInk token，
# 僅靠上方 main_layout 的左右對齊與尾角方向區分自己/對方）
def get_waterball_bubble_style(is_me: bool) -> str:
    t = theme()
    if is_me:
        return f"""
            background-color: {t['waterball']};
            color: {t['waterballInk']};
            border-radius: 14px;
            border-top-right-radius: 3px;
            border: 1px solid {t['border']};
        """
    else:
        return f"""
            background-color: {t['waterball']};
            color: {t['waterballInk']};
            border-radius: 14px;
            border-top-left-radius: 3px;
            border: 1px solid {t['border']};
        """


# 對話氣泡的 inline 樣式
def get_bubble_style(is_me: bool) -> str:
    t = theme()
    if is_me:
        return f"""
            background-color: {t['own']};
            color: {t['ownInk']};
            border-radius: 14px;
            border-top-right-radius: 3px;
        """
    else:
        return f"""
            background-color: {t['other']};
            color: {t['otherInk']};
            border-radius: 14px;
            border-top-left-radius: 3px;
        """
