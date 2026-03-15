# --- uPttTerm QSS 樣式表 ---

MAIN_STYLE = """
/* 全域字體與背景 (暗色系) */
QWidget {
    font-family: "SF Mono", "PingFang TC", "Microsoft JhengHei", sans-serif;
    font-size: 14px;
    background-color: #121416;
    color: #D1D5DA;
}

/* 登入視窗 (柔和暗黑終端機風格) */
#login-window {
    background-color: #121416;
}

#login-container {
    background-color: #1A1D20;
    border: 1px solid #2A2E33;
    border-radius: 12px;
}

#login-window QLabel {
    font-family: "SF Mono", "Consolas", "Courier New", monospace;
}

#logo-label {
    font-size: 26px;
    font-weight: bold;
    color: #A0C4B4; /* Muted sage green */
    margin-bottom: 5px;
    letter-spacing: 2px;
}

#subtitle-label {
    font-size: 14px;
    color: #8B9BAC;
    margin-bottom: 20px;
    letter-spacing: 1px;
}

#login-window QLineEdit {
    padding: 10px 15px;
    border: 1px solid #2A2E33;
    border-radius: 6px;
    background-color: #141619;
    color: #D1D5DA;
    font-family: "SF Mono", "Consolas", "Courier New", monospace;
    font-size: 15px;
}

#login-window QLineEdit::placeholder {
    color: #5C6773;
}

#login-window QLineEdit:focus {
    border: 1px solid #7E9CB9; /* Muted pastel blue */
    background-color: #16191D;
}

#login-window QPushButton {
    padding: 12px;
    background-color: #2D3B35; /* Dark sage green */
    color: #A0C4B4; /* Muted sage green */
    border: 1px solid #3E5149;
    border-radius: 6px;
    font-weight: bold;
    font-size: 15px;
    font-family: "SF Mono", "Consolas", "Courier New", monospace;
    letter-spacing: 1px;
}

#login-window QPushButton:hover {
    background-color: #3E5149;
    color: #B5D4C6;
}

#login-window QPushButton:disabled {
    background-color: #1A1D20;
    border: 1px solid #2A2E33;
    color: #4B5563;
}

#login-window #error-label {
    color: #C27474; /* Soft muted red */
    font-size: 13px;
    font-weight: normal;
}

/* 全域輸入框與按鈕 (保留供主視窗使用) */
QLineEdit {
    padding: 8px;
    border: 1px solid #2A2E33;
    border-radius: 4px;
    background-color: #121416;
    color: #D1D5DA;
}

QLineEdit:focus {
    border: 1px solid #7E9CB9;
}

QPushButton {
    padding: 10px;
    background-color: #2D3B35;
    color: #A0C4B4;
    border: 1px solid #3E5149;
    border-radius: 4px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #3E5149;
}

QPushButton:disabled {
    background-color: #1A1D20;
    color: #4B5563;
}

/* 主視窗 */
#sidebar {
    background-color: #1A1D20;
    border-right: 1px solid #2A2E33;
    min-width: 160px;
    max-width: 250px;
}

#sidebar-title {
    font-weight: bold;
    padding: 10px;
    background-color: #121416;
    border-bottom: 1px solid #2A2E33;
    color: #A0C4B4;
}

QListWidget {
    border: none;
    background-color: transparent;
}

QListWidget::item {
    padding: 10px;
    border-bottom: 1px solid #23272B;
}

QListWidget::item:selected {
    background-color: #2D3B35;
    color: #B5D4C6;
}

#chat-area {
    background-color: #0F1113;
}

/* 對話氣泡 */
#messages-scroll {
    background-color: #0F1113;
    border: none;
}

#messages-container {
    background-color: #0F1113;
}

/* 訊息輸入區 (極致緊湊) */
#input-area {
    background-color: #1A1D20;
    border-top: 1px solid #2A2E33;
    margin: 0px;
    padding: 0px;
}

QTextEdit#message-edit {
    border: 1px solid #2A2E33;
    border-radius: 4px;
    background-color: #121416;
    color: #D1D5DA;
    padding: 5px; /* 僅保留必要的文字內距 */
    margin: 0px;
}

/* 移除滾動條周圍可能的空白 */
QScrollArea {
    border: none;
    background-color: transparent;
}

/* 系統匣選單 */
QMenu {
    background-color: #1A1D20;
    border: 1px solid #2A2E33;
    color: #D1D5DA;
}

QMenu::item:selected {
    background-color: #2D3B35;
    color: #B5D4C6;
}
"""

# 對話氣泡的 HTML/CSS 範本 (暗色系)
def get_bubble_style(is_me: bool) -> str:
    if is_me:
        return """
            background-color: #313D36; /* Dark sage green */
            color: #D1E5DC;
            border-radius: 12px;
            border-top-right-radius: 2px;
        """
    else:
        return """
            background-color: #23272B; /* Slightly lighter than background */
            color: #D1D5DA;
            border-radius: 12px;
            border-top-left-radius: 2px;
        """
