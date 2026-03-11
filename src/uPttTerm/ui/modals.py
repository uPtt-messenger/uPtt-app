from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

class HelpModal(ModalScreen):
    """指令說明視窗"""
    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog-box"):
            yield Label("uPttTerm 指令說明", id="logo")
            yield Static(
                "[cyan]F1[/]       - 顯示此說明\n"
                "[cyan]Ctrl+N[/]   - 開啟新對話\n"
                "[cyan]Ctrl+W[/]   - 關閉目前對話\n"
                "[cyan]Ctrl+L[/]   - 跳至對話清單\n"
                "[cyan]Ctrl+I[/]   - 跳至訊息輸入框\n"
                "[cyan]Tab[/]      - 切換焦點\n"
                "[cyan]Esc[/]      - 關閉視窗 / 返回",
                id="help-text"
            )
            yield Button("確定", variant="primary", id="close-help")

    @on(Button.Pressed, "#close-help")
    def close_help(self):
        self.dismiss()

class NewChatModal(ModalScreen[str]):
    """新增對話視窗"""
    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog-box"):
            yield Label("新增 PTT 對話", id="logo")
            yield Label("請輸入對方的 PTT ID:")
            yield Input(placeholder="例如: CodingMan", id="new-target-id")
            with Horizontal():
                yield Button("取消", variant="error", id="cancel-btn")
                yield Button("開始", variant="success", id="ok-btn")

    def on_mount(self):
        self.query_one("#new-target-id").focus()

    @on(Button.Pressed, "#cancel-btn")
    def cancel(self):
        self.dismiss(None)

    @on(Button.Pressed, "#ok-btn")
    def ok(self):
        target_id = self.query_one("#new-target-id", Input).value.strip()
        if target_id:
            self.dismiss(target_id)

    @on(Input.Submitted, "#new-target-id")
    def on_submit(self):
        self.ok()
