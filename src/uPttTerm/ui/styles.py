# --- uPttTerm QSS 樣式表 ---

MAIN_STYLE = """
/* 全域字體與背景 */
QWidget {
    font-family: "PingFang TC", "Lantinghei TC", "Heiti TC", "Microsoft JhengHei", "Apple LiGothic Medium", sans-serif;
    font-size: 14px;
    background-color: #F5F5F5;
    color: #333333;
}

/* 登入視窗 */
#login-window {
    background-color: #FFFFFF;
}

#logo-label {
    font-size: 24px;
    font-weight: bold;
    color: #0056b3;
    margin-bottom: 20px;
}

QLineEdit {
    padding: 8px;
    border: 1px solid #CCCCCC;
    border-radius: 4px;
    background-color: #FFFFFF;
}

QLineEdit:focus {
    border: 1px solid #0056b3;
}

QPushButton {
    padding: 10px;
    background-color: #0056b3;
    color: white;
    border: none;
    border-radius: 4px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #004494;
}

QPushButton:disabled {
    background-color: #CCCCCC;
}

#error-label {
    color: #D32F2F;
    font-size: 12px;
}

/* 主視窗 */
#sidebar {
    background-color: #FFFFFF;
    border-right: 1px solid #E0E0E0;
    min-width: 250px;
}

#sidebar-title {
    font-weight: bold;
    padding: 10px;
    background-color: #F8F9FA;
    border-bottom: 1px solid #E0E0E0;
}

QListWidget {
    border: none;
    background-color: transparent;
}

QListWidget::item {
    padding: 10px;
    border-bottom: 1px solid #F0F0F0;
}

QListWidget::item:selected {
    background-color: #E3F2FD;
    color: #1976D2;
}

#chat-area {
    background-color: #EBEBEB;
}

/* 對話氣泡 */
#messages-scroll {
    background-color: #EBEBEB;
    border: none;
}

#messages-container {
    background-color: #EBEBEB;
}

/* 訊息輸入區 */
#input-area {
    background-color: #FFFFFF;
    border-top: 1px solid #E0E0E0;
    padding: 10px;
}

QTextEdit#message-edit {
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    background-color: #FFFFFF;
}

/* 系統匣選單 */
QMenu {
    background-color: white;
    border: 1px solid #CCCCCC;
}

QMenu::item:selected {
    background-color: #0056b3;
    color: white;
}
"""

# 對話氣泡的 HTML/CSS 範本 (用於 QLabel 或自訂 Widget)
def get_bubble_style(is_me: bool) -> str:
    if is_me:
        return """
            background-color: #DCF8C6;
            color: #000000;
            border-radius: 10px;
            padding: 10px;
            margin-left: 50px;
        """
    else:
        return """
            background-color: #FFFFFF;
            color: #000000;
            border-radius: 10px;
            padding: 10px;
            margin-right: 50px;
        """
