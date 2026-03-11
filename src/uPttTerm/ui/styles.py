# --- PTT 配色與 TUI 樣式 ---

CSS = """
/* 全域變數與配色 */
$ptt-blue: #0000AA;
$ptt-yellow: #FFFF55;
$ptt-cyan: #55FFFF;
$ptt-white: #FFFFFF;
$black: #000000;
$chat-bg: #121212;
$sidebar-bg: #1e1e1e;
$my-bubble: #005f87;
$other-bubble: #3a3a3a;

Screen {
    background: $chat-bg;
    color: $ptt-white;
}

/* 登入畫面樣式 */
LoginScreen {
    align: center middle;
}

#login-dialog {
    width: 65;
    height: auto;
    border: thick $primary;
    background: $surface;
    padding: 1 2;
}

#login-actions {
    margin-top: 2;
    height: 3;
    width: 100%;
}

#login-btn {
    width: 1fr;
    margin-right: 1;
}

#exit-btn {
    width: 1fr;
    margin-left: 1;
}

#version-label {
    width: 100%;
    margin-top: 1;
    text-align: right;
    color: $ptt-white 40%;
}

#logo {
    width: 100%;
    content-align: center middle;
    color: $accent;
    margin-bottom: 1;
    text-style: bold;
}

.input-label {
    margin-top: 1;
    text-style: bold;
    color: $ptt-cyan;
}

#login-error {
    color: $error;
    text-align: center;
    margin-top: 1;
    display: none;
}

/* 主畫面架構 */
MainChatScreen Header {
    background: $primary-darken-2;
    color: $ptt-white;
    text-style: bold;
}

#main-container {
    layout: horizontal;
}

#sidebar {
    width: 30;
    height: 100%;
    background: $sidebar-bg;
    border-right: solid $primary;
}

#sidebar-title {
    padding: 1;
    background: $primary-darken-3;
    color: $ptt-cyan;
    text-align: center;
    text-style: bold;
}

#chat-list {
    background: transparent;
}

#chat-list ListItem {
    padding: 0 1;
}

#chat-list ListItem:hover {
    background: $ptt-white 10%;
}

#chat-list ListItem.--highlight {
    background: $primary;
    color: $ptt-white;
}

#chat-area {
    width: 1fr;
    height: 100%;
}

/* 訊息區域 */
#messages-container {
    height: 1fr;
    padding: 1 2;
    background: $chat-bg;
    overflow-y: scroll;
}

.message-item {
    width: 100%;
    height: auto;
    margin: 0 0 1 0;
}

.spacer {
    width: 1fr;
}

.msg-left {
    content-align: left middle;
}

.msg-right {
    content-align: right middle;
}

.msg-bubble {
    padding: 0 2;
    max-width: 70%;
}

.msg-left .msg-bubble {
    background: $other-bubble;
    color: $ptt-white;
}

.msg-right .msg-bubble {
    background: $my-bubble;
    color: $ptt-white;
    text-align: right;
}

.msg-meta {
    color: $ptt-white 40%;
    margin: 0 1;
}

/* 輸入區域 */
#input-container {
    height: auto;
    border-top: solid $primary;
    background: $surface;
}

#message-input {
    border: none;
    background: transparent;
}

/* Modal 樣式 */
ModalScreen {
    align: center middle;
    background: $black 50%;
}

.dialog-box {
    width: 50;
    height: auto;
    border: thick $primary;
    background: $surface;
    padding: 1 2;
}

#help-text {
    margin: 1 0;
    color: $ptt-white;
}
"""
