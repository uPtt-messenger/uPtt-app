import asyncio
import os
import sys
from datetime import datetime

import PyPtt
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import (
    DynamicContainer,
    FloatContainer,
    HSplit,
    VSplit,
    Window,
    WindowAlign,
)
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.layout.dimension import Dimension as D
from prompt_toolkit.layout.processors import PasswordProcessor
from prompt_toolkit.widgets import Frame
from wcwidth import wcswidth

from . import __name__ as pkg_name, __version__
from . import config, contant, utils
from .contant import MsgType, CMD
from .ptt import UPttService


class UPttApp:
    """
    一個使用 prompt_toolkit 的 PTT 終端聊天應用程式。

    這個類別封裝了所有 UI、狀態管理（登入、選擇對象、聊天）以及
    與 PTT 服務的互動邏輯。
    """

    def __init__(self):
        # --- 核心屬性 ---
        self.app = None
        self.background_tasks = []

        # --- 狀態管理 ---
        self.state = 'LOGIN'
        self.ptt_id = ''
        self.target = ''
        self.messages = []
        self.alert_message = None
        self.last_mail_time = None
        self.last_msg_time = None
        self.id = utils.gen_random_string(16)

        # --- UI 元件 ---
        self.message_queue = asyncio.Queue()
        self.id_buffer = Buffer(name="id_buffer")
        self.pw_buffer = Buffer(name="pw_buffer")
        self.target_buffer = Buffer(name="target_buffer")
        self.input_buffer = Buffer(multiline=False, name="input_buffer")
        self.id_window = None
        self.pw_window = None

        # --- 初始化 UI ---
        self.bindings = KeyBindings()
        self._setup_key_bindings()
        self.container = HSplit(self._get_login_windows())
        self.framed_container = Frame(body=self.container)
        self.layout = Layout(
            container=FloatContainer(
                content=self.framed_container,
                floats=[]
            ),
            focused_element=self.id_window
        )
        self.app = Application(
            layout=self.layout,
            key_bindings=self.bindings,
            full_screen=True,
            mouse_support=False
        )

    # --- 私有方法: 狀態與 UI 管理 ---

    def _set_state(self, new_state: str):
        """設定應用程式狀態，並更新 UI 和焦點。"""
        self.state = new_state
        self._update_layout()

        # 根據新狀態設定焦點
        if self.state == 'SELECT_TARGET':
            self.app.layout.focus(self.target_buffer)
        elif self.state == 'CHATTING':
            self.app.layout.focus(self.input_buffer)

    def _set_error(self, message: str):
        """設定錯誤訊息並觸發 UI 重繪。"""
        self.alert_message = ('fg:red', message)
        self.app.invalidate()

    def _update_layout(self):
        """根據當前狀態更新顯示的視窗。"""
        if self.state == 'LOGIN':
            self.container.children = self._get_login_windows()
        elif self.state == 'SELECT_TARGET':
            self.container.children = self._get_select_target_windows()
        elif self.state == 'CHATTING':
            self.container.children = self._get_chat_windows()
        self.app.invalidate()

    def _setup_key_bindings(self):
        """設定全域按鍵綁定。"""

        @self.bindings.add('c-c')
        def _(event):
            """Ctrl+C: 離開程式。"""
            event.app.exit()

        @self.bindings.add('enter')
        def _(event):
            """Enter: 根據當前狀態執行不同操作。"""
            if self.state == 'LOGIN':
                if event.app.layout.current_buffer == self.id_buffer:
                    event.app.layout.focus(self.pw_window)
                elif event.app.layout.current_buffer == self.pw_buffer:
                    self.login()
            elif self.state == 'SELECT_TARGET':
                self.select_target()
            elif self.state == 'CHATTING':
                self.send_message()

    # --- 私有方法: 視窗產生器 ---

    def _get_login_windows(self) -> list:
        """產生登入畫面的視窗元件。"""

        # check update

        if utils.is_update_available():
            self.alert_message = ('fg:green', '有版本更新！')

        self.id_window = Window(
            content=BufferControl(buffer=self.id_buffer),
            height=1,
            align=WindowAlign.CENTER
        )

        self.pw_window = Window(
            content=BufferControl(buffer=self.pw_buffer, input_processors=[PasswordProcessor()]),
            height=1,
            align=WindowAlign.CENTER
        )

        return [
            Window(height=D(weight=1)),
            Window(FormattedTextControl(contant.LOGO), align=WindowAlign.CENTER),
            Window(height=2),
            Window(FormattedTextControl("批踢踢帳號"), align=WindowAlign.CENTER, height=1),
            self.id_window,
            Window(height=1),
            Window(FormattedTextControl("批踢踢密碼"), align=WindowAlign.CENTER, height=1),
            self.pw_window,
            Window(height=1),
            Window(
                FormattedTextControl(
                    lambda: [self.alert_message] if self.alert_message else []
                ),
                height=1,
                align=WindowAlign.CENTER
            ),
            HSplit([
                Window(height=D(weight=1)),
                VSplit([
                    Window(width=D(weight=1)),
                    Window(
                        FormattedTextControl(f'v{__version__}'),
                        height=1,
                        width=len(f'v{__version__}')
                    )
                ], height=1)
            ])
        ]

    def _get_select_target_windows(self) -> list:
        """產生選擇對話對象畫面的視窗元件。"""

        return [
            Window(height=D(weight=1)),
            Window(FormattedTextControl("請輸入你要對話的使用者"), height=1, align=WindowAlign.CENTER),
            Window(
                content=BufferControl(buffer=self.target_buffer),
                height=1,
                align=WindowAlign.CENTER
            ),
            Window(height=1),
            Window(
                FormattedTextControl(self.alert_message), align=WindowAlign.CENTER,
                height=lambda: 0 if not self.alert_message else 1,
            ),
            Window(height=D(weight=1)),
        ]

    def _get_chat_windows(self) -> list:
        """產生聊天畫面的視窗元件。"""

        def get_display_text():
            terminal_lines = os.get_terminal_size().lines

            self.messages.sort(key=lambda x: x[1] if isinstance(x[1], datetime) else datetime.min)

            # 限制訊息數量，避免過多佔用記憶體
            while len(self.messages) > config.MAX_MESSAGES:
                self.messages.pop(0)

            chat_area = []

            # 可用行數 = 總行數 - 頂部保留行 - 底部保留行（調整為 -7 確保空間）
            available_lines = max(0, terminal_lines - 7)
            # 只顯示終端機可容納的最新訊息
            for msg_type, msg_time, msg in self.messages[-available_lines:]:

                msg_time = msg_time.strftime('[%m.%d %H:%M]')

                if self.last_msg_time is None or (msg_time != self.last_msg_time):
                    self.last_msg_time = msg_time
                    chat_area.append(
                        Window(
                            FormattedTextControl(msg_time),
                            align=WindowAlign.CENTER,
                            height=1, wrap_lines=False
                        ))

                if msg_type == MsgType.TARGET:
                    text = f"[{self.target}] {msg}"

                    align = WindowAlign.LEFT
                elif msg_type == MsgType.USER:
                    text = f"{msg}"
                    align = WindowAlign.RIGHT
                else:
                    continue  # 忽略無效類型

                chat_area.append(Window(
                    FormattedTextControl(text),
                    align=align,
                    height=1,
                    wrap_lines=False
                ))

            return chat_area

        return [

            Window(FormattedTextControl(f"[系統] 這是與 {self.target} 的對話視窗。"), height=1),
            Window(FormattedTextControl(f"[系統] 輸入 '{CMD.EXIT}' 來離開。"), height=1),
            Window(FormattedTextControl(lambda: contant.DIVISION_TYPE * os.get_terminal_size().columns), height=1),
            DynamicContainer(lambda: HSplit(get_display_text(), height=D(weight=1))),
            Window(FormattedTextControl(lambda: contant.DIVISION_TYPE * os.get_terminal_size().columns), height=1),
            Window(content=BufferControl(buffer=self.input_buffer), height=D.exact(1), wrap_lines=False)
        ]

    # --- 公開方法: 核心邏輯 ---

    def _handle_login_failure(self, message: str):
        """處理登入失敗的通用邏輯。"""
        self._set_error(message)
        self.id_buffer.reset()
        self.pw_buffer.reset()
        self.app.layout.focus(self.id_buffer)

    def login(self):
        """處理登入邏輯。"""
        self.ptt_id = self.id_buffer.text
        ptt_pw = self.pw_buffer.text
        self.alert_message = None
        try:
            self.ptt_service.login(self.ptt_id, ptt_pw)
            self._set_state('SELECT_TARGET')
        except PyPtt.exceptions.WrongIDorPassword:
            self._handle_login_failure('帳號密碼錯誤')
        except PyPtt.exceptions.OnlySecureConnection:
            self._handle_login_failure('只能使用安全連線')
        except PyPtt.exceptions.ResetYourContactEmail:
            self._handle_login_failure('請先至信箱設定連絡信箱')
        except PyPtt.exceptions.LoginError as e:
            self._handle_login_failure(f'登入失敗: {e}')

    def select_target(self):
        """處理選擇對話對象的邏輯。"""
        target_id = self.target_buffer.text
        self.alert_message = None
        try:
            target_info = self.ptt_service.call('get_user', {'user_id': target_id})
            self.target = target_info['ptt_id'].split(' ')[0]
            self._set_state('CHATTING')
            self.start_chat()
        except PyPtt.exceptions.NoSuchUser:
            self._set_error('查無此人')

    def send_message(self):
        """處理傳送訊息的邏輯。"""
        text = self.input_buffer.text.strip()
        if not text:
            return

        self.input_buffer.reset()
        if text.lower() == CMD.EXIT:
            self.app.exit()
            return
        if text.lower() == CMD.CLEAR:
            self.messages.clear()
            self.app.invalidate()
            return

        text_time = datetime.now()

        self.messages.append((MsgType.USER, text_time, text))
        self.app.invalidate()

        ptt_msg = utils.msg_to_mail(pkg_name, self.ptt_id, text)
        self.ptt_service.call('mail',
                              {'ptt_id': self.target, 'title': contant.PTT_MSG_TITLE, 'content': ptt_msg,
                               'backup': False})

    def start_chat(self):
        """初始化聊天視窗並啟動背景任務。"""
        sys.stdout.write(f"\x1b]2;與 {self.target} 的對話視窗\x07")

        # 建立並啟動背景任務
        printer = self.app.create_background_task(self._message_printer_task())
        generator = self.app.create_background_task(self._message_generator_task())
        self.background_tasks.extend([printer, generator])

    async def run(self):
        """執行應用程式主迴圈並處理資源清理。"""
        print(f"歡迎使用 {pkg_name} v{__version__}")
        sys.stdout.write(f"\x1b]2;{pkg_name} v{__version__}\x07")
        self._update_layout()
        try:
            await self.app.run_async()
        finally:
            print("正在離開程式...")
            for task in self.background_tasks:
                task.cancel()
            if self.background_tasks:
                await asyncio.gather(*self.background_tasks, return_exceptions=True)

            # self.ptt_service.call('logout')
            # self.ptt_service.close()

            await asyncio.sleep(1)  # 確保所有背景任務有時間完成

            print("程式已終止。")
            print(contant.DIVISION_TYPE * os.get_terminal_size().columns)
            goodbye_message = f"由衷感謝您使用 {pkg_name}！"
            terminal_width = os.get_terminal_size().columns - 2
            message_width = wcswidth(goodbye_message)
            padding = max(0, (terminal_width - message_width) // 2)
            print(' ' * padding + goodbye_message)
            print(contant.DIVISION_TYPE * os.get_terminal_size().columns)

    # --- 私有方法: 背景任務 ---

    async def _message_printer_task(self):
        """從佇列中取出訊息並附加到 UI。"""
        while True:
            msg_time, message = await self.message_queue.get()
            self.messages.append((MsgType.TARGET, msg_time, message))
            self.app.invalidate()
            self.message_queue.task_done()

    async def _message_generator_task(self):
        """定期檢查 PTT 信箱並將新訊息放入佇列。"""
        self.check_offline_msg = True
        while True:
            await asyncio.sleep(config.CHECK_PTT_MAIL_INTERVAL)

            if not self.target:
                continue

            try:
                cur_mail_idx = self.ptt_service.call('get_newest_index', {'index_type': PyPtt.NewIndex.MAIL})
                if cur_mail_idx == 0:
                    continue

                del_mail_list = []
                lookback_limit = 10 if not self.check_offline_msg else 50
                self.check_offline_msg = False

                for mail_idx in range(max(1, cur_mail_idx - lookback_limit), cur_mail_idx + 1):
                    try:
                        mail_info = self.ptt_service.call('get_mail', {'index': mail_idx})

                        if PyPtt.MailField.date not in mail_info:
                            continue

                        if mail_info[PyPtt.MailField.date] is None:
                            continue

                        msg_time = datetime.strptime(mail_info[PyPtt.MailField.date], '%a %b %d %H:%M:%S %Y')
                        if self.last_mail_time and msg_time <= self.last_mail_time:
                            continue
                        self.last_mail_time = msg_time

                        if PyPtt.MailField.title not in mail_info:
                            continue

                        if PyPtt.MailField.author not in mail_info:
                            continue

                        if mail_info[PyPtt.MailField.title] != contant.PTT_MSG_TITLE:
                            continue

                        if not mail_info[PyPtt.MailField.author].lower().startswith(self.target.lower()):
                            continue

                        content = mail_info[PyPtt.MailField.content]
                        start = content.find(contant.PTT_MSG_DIVISION_LINE) + len(
                            contant.PTT_MSG_DIVISION_LINE)
                        end = content.rfind(contant.PTT_MSG_DIVISION_LINE)

                        self.message_queue.put_nowait(
                            (msg_time, content[start:end].strip()))

                        del_mail_list.append(mail_idx)

                    except PyPtt.exceptions.Error:
                        continue

                # 從後往前刪除已處理的信件
                for cur_mail_idx in sorted(del_mail_list, reverse=True):
                    self.ptt_service.call('del_mail', {'index': cur_mail_idx})

            except PyPtt.exceptions.Error:
                # 在檢查信箱的過程中可能發生任何 PTT 錯誤 (例如斷線)，忽略並等待下一輪
                continue


def main():
    """應用程式進入點。"""
    app = UPttApp()
    try:
        asyncio.run(app.run())
    except (KeyboardInterrupt, Exception):
        # 錯誤已在 app.run() 方法的 finally 區塊中處理
        pass


if __name__ == '__main__':
    main()
