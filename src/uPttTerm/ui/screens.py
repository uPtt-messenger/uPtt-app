import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

import PyPtt
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Header, Footer, Input, Button, Label, ListView, ListItem, Static
)

from uPttTerm import config, contant, utils
from uPttTerm.contant import LOGO
from uPttTerm.ui.widgets import ChatMessage
from uPttTerm.ui.modals import HelpModal, NewChatModal

logger = logging.getLogger("uPttTerm")

class LoginScreen(Screen):
    """登入畫面"""
    BINDINGS = [Binding("escape", "app.exit", "離開")]

    def compose(self) -> ComposeResult:
        with Vertical(id="login-dialog"):
            yield Static(LOGO, id="logo")
            yield Label("PTT 帳號", classes="input-label")
            yield Input(placeholder="Account ID", id="username")
            yield Label("PTT 密碼", classes="input-label")
            yield Input(placeholder="Password", password=True, id="password")
            yield Label("", id="login-error")
            yield Button("登入 PTT", variant="primary", id="login-btn")

    def on_mount(self):
        self.query_one("#username").focus()

    @work(exclusive=True)
    async def handle_login(self):
        username = self.query_one("#username", Input).value.strip()
        password = self.query_one("#password", Input).value.strip()
        if not username or not password:
            self.show_error("請輸入帳號與密碼")
            return

        btn = self.query_one("#login-btn", Button)
        btn.disabled = True
        self.show_error("正在建立獨立連線...", color="cyan")

        try:
            # 呼叫 App 層級的獨立 PTT 實例
            await asyncio.to_thread(self.app.ptt.login, username, password)
            logger.info(f"User {username} logged in successfully.")
            self.app.ptt_id = username
            self.app.push_screen(MainChatScreen())
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            self.show_error(f"登入失敗: {str(e)}")
            btn.disabled = False

    def show_error(self, message: str, color: str = "red"):
        err_label = self.query_one("#login-error", Label)
        err_label.update(message)
        err_label.styles.color = color
        err_label.display = True

    @on(Button.Pressed, "#login-btn")
    @on(Input.Submitted)
    def on_submit(self):
        self.handle_login()

class MainChatScreen(Screen):
    """主聊天畫面"""
    BINDINGS = [
        Binding("f1", "help", "說明"),
        Binding("ctrl+n", "new_chat", "新對話"),
        Binding("ctrl+w", "close_chat", "關閉對話"),
        Binding("ctrl+l", "focus_sidebar", "清單"),
        Binding("ctrl+i", "focus_input", "輸入"),
        Binding("escape", "back", "返回/離開", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.chat_histories: Dict[str, List[Dict]] = {} 
        self.unread_counts: Dict[str, int] = {}
        self.current_target: Optional[str] = None
        self.last_mail_time: Optional[datetime] = None
        self.polling = True

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-container"):
            with Vertical(id="sidebar"):
                yield Label("對話清單", id="sidebar-title")
                yield ListView(id="chat-list")
            with Vertical(id="chat-area"):
                yield ScrollableContainer(id="messages-container")
                with Vertical(id="input-container"):
                    yield Input(placeholder="> 請輸入訊息... (按下 Enter 發送)", id="message-input")
        yield Footer()

    def on_mount(self):
        self.query_one(Header).tall = True
        self.update_header()
        self.start_polling()

    def update_header(self):
        total_unread = sum(self.unread_counts.values())
        status = f" [red]{total_unread} 未讀[/]" if total_unread > 0 else " 狀態: 獨立連線中"
        self.app.title = f"uPttTerm | 帳號: {self.app.ptt_id}"
        self.app.sub_title = status

    def refresh_sidebar(self):
        list_view = self.query_one("#chat-list", ListView)
        current_idx = list_view.index
        list_view.clear()
        for target_id in self.chat_histories.keys():
            unread = self.unread_counts.get(target_id, 0)
            prefix = "[red]*[/] " if unread > 0 else "  "
            list_view.append(ListItem(Label(f"{prefix}{target_id}")))
        list_view.index = current_idx

    @work(exclusive=True)
    async def start_polling(self):
        """背景輪詢新信件"""
        first_run = True
        while self.polling:
            await asyncio.sleep(config.CHECK_PTT_MAIL_INTERVAL)
            try:
                newest_idx = await asyncio.to_thread(self.app.ptt.call, 'get_newest_index', {'index_type': PyPtt.NewIndex.MAIL})
                if not newest_idx: continue

                # 初次啟動檢查較多封數
                lookback = 50 if first_run else 10
                first_run = False
                
                mails_to_process = []
                for mail_idx in range(max(1, newest_idx - lookback), newest_idx + 1):
                    mail = await asyncio.to_thread(self.app.ptt.call, 'get_mail', {'index': mail_idx})
                    if not mail or mail.get(PyPtt.MailField.title) != contant.PTT_MSG_TITLE: continue
                    
                    msg_time = datetime.strptime(mail[PyPtt.MailField.date], '%a %b %d %H:%M:%S %Y')
                    if self.last_mail_time and msg_time <= self.last_mail_time: continue
                    
                    sender = mail[PyPtt.MailField.author].split(' ')[0]
                    content = mail[PyPtt.MailField.content]
                    
                    mails_to_process.append({
                        'index': mail_idx,
                        'sender': sender,
                        'content': content,
                        'time': msg_time
                    })

                # 依序處理訊息
                for mail_data in mails_to_process:
                    content = mail_data['content']
                    try:
                        start = content.find(contant.PTT_MSG_DIVISION_LINE) + len(contant.PTT_MSG_DIVISION_LINE)
                        end = content.rfind(contant.PTT_MSG_DIVISION_LINE)
                        if start < end:
                            self.receive_message(mail_data['sender'], content[start:end].strip(), mail_data['time'])
                        self.last_mail_time = mail_data['time']
                    except Exception as e:
                        logger.error(f"Parse mail error: {e}")

                # 反向刪除，避免索引移位
                for mail_data in sorted(mails_to_process, key=lambda x: x['index'], reverse=True):
                    await asyncio.to_thread(self.app.ptt.call, 'del_mail', {'index': mail_data['index']})

            except Exception as e:
                logger.error(f"Polling error: {e}")

    def receive_message(self, sender: str, text: str, msg_time: datetime):
        # PTT ID 是不分大小寫的，統一使用小寫作為 Key
        sender_key = sender.strip().lower()
        if sender_key not in self.chat_histories:
            self.chat_histories[sender_key] = []
            self.unread_counts[sender_key] = 0
            self.refresh_sidebar()
        
        time_str = msg_time.strftime("%H:%M")
        self.chat_histories[sender_key].append({"text": text, "is_me": False, "time": time_str})
        
        if self.current_target and self.current_target.lower() == sender_key:
            container = self.query_one("#messages-container", ScrollableContainer)
            container.mount(ChatMessage(sender, text, is_me=False, time_str=time_str))
            container.scroll_end(animate=True)
        else:
            self.unread_counts[sender_key] += 1
            self.refresh_sidebar()
            self.update_header()

    def select_chat(self, target_id: str):
        target_key = target_id.strip().lower()
        self.current_target = target_id # 保留原始輸入用於顯示
        self.unread_counts[target_key] = 0
        self.refresh_sidebar()
        self.update_header()
        container = self.query_one("#messages-container", ScrollableContainer)
        container.query("*").remove()
        for msg in self.chat_histories[target_key]:
            container.mount(ChatMessage(
                self.app.ptt_id if msg["is_me"] else target_id, 
                msg["text"], msg["is_me"], msg["time"]
            ))
        container.scroll_end(animate=False)
        self.query_one("#message-input").focus()

    def add_new_chat(self, target_id: str):
        if not target_id: return
        target_key = target_id.strip().lower()
        if target_key not in self.chat_histories:
            self.chat_histories[target_key] = []
            self.unread_counts[target_key] = 0
        self.select_chat(target_id)

    @on(ListView.Selected)
    def on_chat_selected(self, event: ListView.Selected):
        # 取得 Label 的文字內容並過濾掉 Rich 標記與前綴符號
        raw_text = str(event.item.query_one(Label).renderable)
        # 移除 Rich 標記與可能的前綴 (* 或空格)
        target_id = raw_text.replace("[red]*[/] ", "").lstrip("* ").strip()
        self.select_chat(target_id)

    @on(Input.Submitted, "#message-input")
    @work
    async def handle_send(self, event: Input.Submitted):
        text = event.value.strip()
        if not text or not self.current_target: return
        
        target_key = self.current_target.lower()
        self.query_one("#message-input", Input).value = ""
        time_str = datetime.now().strftime("%H:%M")
        self.chat_histories[target_key].append({"text": text, "is_me": True, "time": time_str})
        
        container = self.query_one("#messages-container", ScrollableContainer)
        container.mount(ChatMessage(self.app.ptt_id or "我", text, is_me=True, time_str=time_str))
        container.scroll_end(animate=True)
        
        try:
            ptt_msg = utils.msg_to_mail(contant.pkg_name, self.app.ptt_id or "uPttUser", text)
            await asyncio.to_thread(self.app.ptt.call, 'mail', {
                'ptt_id': self.current_target, 
                'title': contant.PTT_MSG_TITLE, 
                'content': ptt_msg, 
                'backup': False
            })
        except Exception as e:
            container.mount(ChatMessage("系統", f"發送失敗: {str(e)}", is_me=False))
            container.scroll_end(animate=True)

    def action_new_chat(self):
        self.app.push_screen(NewChatModal(), self.add_new_chat)

    def action_close_chat(self):
        if self.current_target:
            target_key = self.current_target.lower()
            if target_key in self.chat_histories:
                del self.chat_histories[target_key]
            if target_key in self.unread_counts:
                del self.unread_counts[target_key]
            self.current_target = None
            self.refresh_sidebar()
            self.query_one("#messages-container").query("*").remove()
            self.update_header()

    def action_focus_sidebar(self): self.query_one("#chat-list").focus()
    def action_focus_input(self): self.query_one("#message-input").focus()
    def action_help(self): self.app.push_screen(HelpModal())
    def action_back(self):
        if self.focused == self.query_one("#message-input"):
            self.action_focus_sidebar()
        else:
            self.app.exit()
