import asyncio
import json
import os
import subprocess
import sys
import warnings
from datetime import datetime

# 壓制 requests 的字元偵測警告，避免干擾 TUI
warnings.filterwarnings("ignore", category=UserWarning, module="requests")

import PyPtt
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition
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

from uPttTerm import __name__ as pkg_name, __version__
from uPttTerm import config, contant, utils
from uPttTerm.contant import MsgType, CMD


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
        self.server_process = None

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
        self.target_buffer = Buffer(name="target_buffer", on_text_changed=self._on_target_text_changed)
        self.input_buffer = Buffer(multiline=False, name="input_buffer")
        self.id_window = None
        self.pw_window = None

        # --- 即時搜尋功能 ---
        self.target_suggestions = []
        self.selected_suggestion_index = 0
        self.search_cache = {}

        # --- 初始化 UI ---
        self.bindings = KeyBindings()
        self._setup_key_bindings()
        self.container = HSplit(self._get_login_windows())
        self.framed_container = Frame(body=self.container)
        self.layout = Layout(
            container=FloatContainer(
                content=self.framed_container,
                floats=[]
            )
        )
        self.app = Application(
            layout=self.layout,
            key_bindings=self.bindings,
            full_screen=True,
            mouse_support=False
        )

        # 設定初始狀態和焦點
        self._set_state('LOGIN')

    # --- 私有方法: 狀態與 UI 管理 ---

    def _set_state(self, new_state: str):
        """設定應用程式狀態，並更新 UI 和焦點。"""
        self.state = new_state
        self._update_layout()

        # 確保 UI 更新後再設定焦點
        # 根據新狀態設定焦點
        try:
            if self.state == 'LOGIN':
                if self.id_window:
                    self.app.layout.focus(self.id_window)
            elif self.state == 'SELECT_TARGET':
                self.app.layout.focus(self.target_buffer)
            elif self.state == 'CHATTING':
                self.app.layout.focus(self.input_buffer)
        except Exception:
            # 如果焦點設定失敗，不影響應用程式運行
            pass

    def _set_error(self, message: str):
        """設定錯誤訊息並觸發 UI 重繪。"""
        self.alert_message = ('fg:red', message)
        self.app.invalidate()

    def _on_target_text_changed(self, buffer):
        """當目標輸入框文字改變時，過濾使用者建議清單。"""
        text = buffer.text.lower()
        if not text:
            self.target_suggestions = []
            return

        if text in self.search_cache:
            self.target_suggestions = self.search_cache[text]
            self.selected_suggestion_index = 0
            if self.app:
                self.app.invalidate()
            return

        async def _fetch_search_results():
            r = await asyncio.to_thread(
                utils.call_server_api, 'search_user',
                {'ptt_id': text, 'min_page': 1, 'max_page': 2},
                timeout=10
            )
            if "error" not in r:
                self.target_suggestions = r["result"][:5] if "result" in r else self.target_suggestions
                self.search_cache[text] = self.target_suggestions
                self.selected_suggestion_index = 0
                if self.app:
                    self.app.invalidate()

        asyncio.create_task(_fetch_search_results())

    def _update_layout(self):
        """根據當前狀態更新顯示的視窗。"""
        if self.state == 'LOGIN':
            self.container.children = self._get_login_windows()
        elif self.state == 'SELECT_TARGET':
            self.container.children = self._get_select_target_windows()
        elif self.state == 'CHATTING':
            self.container.children = self._get_chat_windows()

        # 強制重繪界面以確保更新被應用
        self.app.invalidate()

    def _setup_key_bindings(self):
        """設定全域按鍵綁定。"""
        is_selecting_target = Condition(lambda: self.state == 'SELECT_TARGET')

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
                    asyncio.create_task(self.login())
            elif self.state == 'SELECT_TARGET':
                # 如果有建議選項且目前輸入的文字與所選建議不同，則執行補全
                if self.target_suggestions and self.target_buffer.text != self.target_suggestions[self.selected_suggestion_index]:
                    self.target_buffer.text = self.target_suggestions[self.selected_suggestion_index]
                    self.target_buffer.cursor_position = len(self.target_buffer.text)
                # 否則，確認選擇並進入聊天室
                else:
                    asyncio.create_task(self.select_target())
            elif self.state == 'CHATTING':
                asyncio.create_task(self.send_message())

        @self.bindings.add('down', filter=is_selecting_target)
        def _(event):
            """在建議清單中向下移動。"""
            if self.target_suggestions:
                self.selected_suggestion_index = \
                    (self.selected_suggestion_index + 1) % len(self.target_suggestions)

        @self.bindings.add('up', filter=is_selecting_target)
        def _(event):
            """在建議清單中向上移動。"""
            if self.target_suggestions:
                self.selected_suggestion_index = \
                    (self.selected_suggestion_index - 1 + len(self.target_suggestions)) \
                    % len(self.target_suggestions)

        @self.bindings.add('tab', filter=is_selecting_target)
        def _(event):
            """自動完成選擇的建議。"""
            if self.target_suggestions:
                self.target_buffer.text = self.target_suggestions[self.selected_suggestion_index]
                self.target_buffer.cursor_position = len(self.target_buffer.text)

    # --- 私有方法: 視窗產生器 ---

    def _get_login_windows(self) -> list:
        """產生登入畫面的視窗元件。"""

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

        def get_suggestion_windows():
            """根據建議清單產生視窗元件列表。"""
            windows = []
            for i, user in enumerate(self.target_suggestions):
                if i == self.selected_suggestion_index:
                    style = 'class:reverse'
                    text = f'{user} '
                else:
                    style = ''
                    text = f'{user} '
                windows.append(Window(FormattedTextControl([(style, text)]), height=1, align=WindowAlign.CENTER))
            return windows

        return [
            Window(height=D(weight=1)),
            Window(FormattedTextControl("請輸入你要對話的使用者"), height=1, align=WindowAlign.CENTER),
            Window(
                content=BufferControl(buffer=self.target_buffer),
                height=1,
                align=WindowAlign.CENTER
            ),
            Window(height=1),
            DynamicContainer(lambda: HSplit(get_suggestion_windows())),
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

    async def login(self):
        """處理登入邏輯。"""
        self.ptt_id = self.id_buffer.text
        ptt_pw = self.pw_buffer.text
        self.alert_message = None

        r = await asyncio.to_thread(utils.login_server, self.ptt_id, ptt_pw)
        if 'error' in r:
            self._handle_login_failure(r['error'])
            return

        # 登入成功，啟動連線監控並切換畫面
        self._start_session_monitor()
        self.alert_message = None
        self.target_buffer.reset()  # 確保目標輸入框是空的
        self._set_state('SELECT_TARGET')

    async def select_target(self):
        """處理選擇對話對象的邏輯。"""

        target_id = self.target_buffer.text
        self.alert_message = None
        r = await asyncio.to_thread(utils.call_server_api, 'get_user', {'user_id': target_id})
        if 'error' in r:
            if 'NoSuchUser' in r['error']:
                 self._set_error('查無此人')
            else:
                 self._set_error(r['error'])
            return

        target_info = r.get('result')
        if not target_info or 'ptt_id' not in target_info:
            self._set_error('查無此人')
            return

        self.target = target_info['ptt_id'].split(' ')[0]
        self._set_state('CHATTING')
        self.start_chat()

    async def send_message(self):
        """處理傳送訊息的邏輯。"""
        text = self.input_buffer.text.strip()
        text_cmd = text.lower()
        if not text:
            return
        self.input_buffer.reset()

        match text_cmd:
            case CMD.CLEAR:
                self.messages.clear()
                self.app.invalidate()
                return
            case CMD.EXIT | CMD.QUIT | CMD.LOGOUT:
                self.app.exit()
                return
            case _:
                pass

        text_time = datetime.now()

        self.messages.append((MsgType.USER, text_time, text))
        self.app.invalidate()

        ptt_msg = utils.msg_to_mail(pkg_name, self.ptt_id, text)
        r = await asyncio.to_thread(utils.call_server_api, 'mail',
                              {'ptt_id': self.target, 'title': contant.PTT_MSG_TITLE, 'content': ptt_msg,
                               'backup': False})
        if 'error' in r:
            self._set_error(f"發送失敗: {r['error']}")

    def start_chat(self):
        """初始化聊天視窗並啟動背景任務。"""
        sys.stdout.write(f"\x1b]2;與 {self.target} 的對話視窗\x07")

        # 建立並啟動背景任務
        printer = self.app.create_background_task(self._message_printer_task())
        generator = self.app.create_background_task(self._message_generator_task())
        self.background_tasks.extend([printer, generator])

    def _start_session_monitor(self):
        """啟動監控連線狀態的背景任務。"""
        # 避免重複啟動監控
        for task in self.background_tasks:
            if hasattr(task, '_is_monitor') and task._is_monitor:
                return
        
        monitor = self.app.create_background_task(self._session_monitor_task())
        monitor._is_monitor = True
        self.background_tasks.append(monitor)

    async def run(self):
        """執行應用程式主迴圈並處理資源清理。"""
        sys.stdout.write(f"\x1b]2;{pkg_name} v{__version__}\x07")

        ######
        # check the core service is available here

        if not utils.is_server_running():
            # 環境變數中加入當前路徑，確保子程序能找到包
            env = os.environ.copy()
            base_dir = os.getcwd()
            src_dir = os.path.join(base_dir, "src")
            env["PYTHONPATH"] = f"{src_dir}:{env.get('PYTHONPATH', '')}"
            
            # 判斷是否在 PyInstaller 環境下
            if getattr(sys, 'frozen', False):
                cmd = [sys.executable, "--server", str(config.SERVICE_PORT)]
            else:
                # 開發環境：直接執行當前檔案路徑，確保路徑正確
                current_file = os.path.abspath(__file__)
                cmd = [sys.executable, current_file, "--server", str(config.SERVICE_PORT)]

            self.server_process = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, 
                close_fds=True, env=env
            )

            # 等待伺服器啟動，加入逾時保護
            success = False
            for _ in range(20): # 最多等待 10 秒
                if utils.is_server_running():
                    success = True
                    break
                await asyncio.sleep(0.5)
            
            if not success:
                return

        r = utils.call_server_api('get_time')
        if 'error' in r:
            if utils.is_update_available():
                self.alert_message = ('fg:green', '有版本更新！')
            self._set_state('LOGIN')
        else:
            # 已經登入，啟動連線監控
            self._start_session_monitor()
            self._set_state('SELECT_TARGET')

        ######

        # 注意：_set_state 已經會調用 _update_layout，所以這裡不需要重複調用
        try:
            await self.app.run_async()
        finally:
            # 主動呼叫伺服器登出 PTT
            try:
                # 使用 to_thread 避免在清理階段阻塞
                await asyncio.to_thread(utils.call_server_api, 'logout')
            except Exception:
                pass

            if self.server_process:
                try:
                    self.server_process.terminate()
                    self.server_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.server_process.kill()

            for task in self.background_tasks:
                task.cancel()
            if self.background_tasks:
                await asyncio.gather(*self.background_tasks, return_exceptions=True)

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

    async def _session_monitor_task(self):
        """監控伺服器端的 PTT 會話狀態。"""
        while True:
            await asyncio.sleep(config.CHECK_PTT_MAIL_INTERVAL)
            
            # 只有在非登入狀態才需要監控（因為登入後才有會話）
            if self.state == 'LOGIN':
                continue
                
            r = await asyncio.to_thread(utils.call_server_api, 'get_time')
            if 'error' in r:
                # 偵測到登入失效（表示有其他實例登出了），則關閉當前視窗
                if "login first" in r['error'].lower():
                    self.app.exit()

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

            r = await asyncio.to_thread(utils.call_server_api, 'get_newest_index', {'index_type': PyPtt.NewIndex.MAIL})
            if 'error' in r:
                # 登入失效的處理已交由 _session_monitor_task
                continue

            cur_mail_idx = r.get('result', 0)
            if cur_mail_idx == 0:
                continue

            del_mail_list = []
            lookback_limit = 10 if not self.check_offline_msg else 50
            self.check_offline_msg = False

            for mail_idx in range(max(1, cur_mail_idx - lookback_limit), cur_mail_idx + 1):
                r = await asyncio.to_thread(utils.call_server_api, 'get_mail', {'index': mail_idx})
                if 'error' in r:
                    continue

                mail_info = r.get('result')
                if not mail_info:
                    continue

                if PyPtt.MailField.date not in mail_info or mail_info[PyPtt.MailField.date] is None:
                    continue

                msg_time = datetime.strptime(mail_info[PyPtt.MailField.date], '%a %b %d %H:%M:%S %Y')
                if self.last_mail_time and msg_time <= self.last_mail_time:
                    continue
                self.last_mail_time = msg_time

                if PyPtt.MailField.title not in mail_info or PyPtt.MailField.author not in mail_info:
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

            # 從後往前刪除已處理的信件
            for cur_mail_idx in sorted(del_mail_list, reverse=True):
                await asyncio.to_thread(utils.call_server_api, 'del_mail', {'index': cur_mail_idx})


def main():
    """應用程式進入點。"""
    # 支援 --server 模式啟動伺服器
    if len(sys.argv) > 2 and sys.argv[1] == "--server":
        from uPttTerm.server import run_server
        # 靜音
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = open(os.devnull, 'w')
        run_server("127.0.0.1", int(sys.argv[2]))
        return

    app = UPttApp()
    try:
        asyncio.run(app.run())
    except (KeyboardInterrupt, Exception) as e:
        # 錯誤已在 app.run() 方法的 finally 區塊中處理
        raise e
        pass


if __name__ == '__main__':
    main()
