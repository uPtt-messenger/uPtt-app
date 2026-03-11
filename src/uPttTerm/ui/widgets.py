from datetime import datetime
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label, Static

class ChatMessage(Static):
    """自訂訊息元件，支援左右對齊與時間顯示"""
    def __init__(self, sender: str, text: str, is_me: bool = False, time_str: str = ""):
        super().__init__()
        self.sender = sender
        self.text = text
        self.is_me = is_me
        self.time_str = time_str or datetime.now().strftime("%H:%M")

    def compose(self) -> ComposeResult:
        with Horizontal(classes="message-item " + ("msg-right" if self.is_me else "msg-left")):
            if self.is_me:
                # 建立一個空元件來把訊息推向右邊
                yield Static("", classes="spacer")
                yield Label(self.time_str, classes="msg-meta")
                yield Label(self.text, classes="msg-bubble")
            else:
                yield Label(self.text, classes="msg-bubble")
                yield Label(self.time_str, classes="msg-meta")
