# --- uPtt QSS 樣式表 ---

MAIN_STYLE = """
/* 全域字體與背景 */
QWidget {
    font-family: "JetBrains Mono", "Cascadia Code", "SF Mono", "Menlo", "Consolas", "DejaVu Sans Mono", "PingFang TC", "Microsoft JhengHei", monospace;
    font-size: 14px;
    background-color: #0D1117;
    color: #E6EDF3;
}

/* 登入視窗 */
#login-window {
    background-color: #0D1117;
}


#login-window QLineEdit {
    padding: 9px 13px;
    border: 1px solid #2D333B;
    border-radius: 7px;
    background-color: #161B22;
    color: #E6EDF3;
    font-size: 14px;
}

#login-window QLineEdit:focus {
    border: 1px solid #A0C4B4;
    background-color: #161B22;
}

/* 登入按鈕 */
#login-window #login-btn {
    background-color: #2D3B35;
    color: #A0C4B4;
    border: 1px solid #3E5149;
    border-radius: 8px;
    font-weight: bold;
    font-size: 14px;
    letter-spacing: 2px;
}

#login-window #login-btn:hover {
    background-color: #3A4D43;
    color: #B5D4C6;
    border-color: #4E6358;
}

#login-window #login-btn:disabled {
    background-color: #1C2128;
    border: 1px solid #21262D;
    color: #484F58;
}

#login-window #error-label {
    color: #C27474;
    font-size: 12px;
}

/* 全域 QLineEdit */
QLineEdit {
    padding: 8px 12px;
    border: 1px solid #30363D;
    border-radius: 6px;
    background-color: #0D1117;
    color: #E6EDF3;
}

QLineEdit:focus {
    border: 1px solid #A0C4B4;
}

QLineEdit::placeholder {
    color: #484F58;
}

/* 全域 QPushButton */
QPushButton {
    padding: 8px 14px;
    background-color: #21262D;
    color: #A0C4B4;
    border: 1px solid #30363D;
    border-radius: 6px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #2D3B35;
    border-color: #3E5149;
}

QPushButton:disabled {
    background-color: #161B22;
    color: #484F58;
    border-color: #21262D;
}

/* 側邊欄 */
#sidebar {
    background-color: #161B22;
    border-right: 1px solid #21262D;
    min-width: 160px;
    max-width: 300px;
}

#user-profile {
    background-color: #161B22;
    border-bottom: 1px solid #21262D;
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
    background-color: #21262D;
}

QListWidget::item:hover:!selected {
    background-color: #1C2128;
}

/* 搜尋/新增輸入框 */
QLineEdit#new-chat-input {
    background-color: #0D1117;
    border: 1px solid #30363D;
    border-radius: 6px;
    padding: 0 8px;
    color: #C9D1D9;
    font-size: 13px;
}

QLineEdit#new-chat-input:focus {
    border-color: #A0C4B4;
}

/* 聊天區域 */
#chat-area {
    background-color: #0D1117;
}

/* 聊天標題列 */
#chat-header {
    background-color: #161B22;
    border-bottom: 1px solid #21262D;
}

/* 訊息捲動區 */
#messages-scroll {
    background-color: #0D1117;
    border: none;
}

#messages-container {
    background-color: #0D1117;
}

/* 訊息輸入區 */
#input-area {
    background-color: #161B22;
    border-top: 1px solid #21262D;
}

QLineEdit#message-edit {
    border: 1px solid #30363D;
    border-radius: 8px;
    background-color: #0D1117;
    color: #E6EDF3;
    padding: 8px 12px;
    font-size: 14px;
}

QLineEdit#message-edit:focus {
    border-color: #A0C4B4;
}

/* 回覆預覽條 */
QWidget#reply-bar {
    background-color: #161B22;
    border-top: 1px solid #30363D;
    border-left: 3px solid #A0C4B4;
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
    background: #30363D;
    border-radius: 2px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: #484F58;
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
    background-color: #161B22;
    border: 1px solid #30363D;
    border-radius: 6px;
    padding: 4px;
    color: #E6EDF3;
}

QMenu::item {
    padding: 6px 16px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #21262D;
    color: #A0C4B4;
}

QMenu::separator {
    height: 1px;
    background: #30363D;
    margin: 4px 0;
}
"""


# 對話氣泡的 inline 樣式
def get_bubble_style(is_me: bool) -> str:
    if is_me:
        return """
            background-color: #1C3A2E;
            color: #D1E5DC;
            border-radius: 14px;
            border-top-right-radius: 3px;
        """
    else:
        return """
            background-color: #21262D;
            color: #E6EDF3;
            border-radius: 14px;
            border-top-left-radius: 3px;
        """
