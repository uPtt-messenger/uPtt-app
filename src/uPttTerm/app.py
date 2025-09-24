import asyncio
import os
import sys
from getpass import getpass

import PyPtt
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.layout.dimension import Dimension as D
from wcwidth import wcswidth

from . import config
from . import contant

from . import utils
from . import __name__ as pkg_name, __version__

# 初始化 PTT 服務
ptt_service = PyPtt.Service({'log_level': PyPtt.log.SILENT})


# 負責從佇列中取出訊息並附加到 UI 的任務
async def message_printer_task(message_queue: asyncio.Queue, messages: list, app: Application):
    """
    這是一個訊息消費者 (Consumer)。
    它會持續等待佇列中出現新訊息，一旦有新訊息就將它附加到訊息列表，並觸發 UI 更新。
    """
    while True:
        message = await message_queue.get()
        messages.append((contant.TARGET_MSG, message))  # 將訊息存為 (類型, 內容) 的元組
        # 觸發 UI 重新繪製
        app.invalidate()
        message_queue.task_done()


# 訊息產生器，模擬週期性事件
async def demo_message_generator(log_func):
    """
    這是一個訊息生產者 (Producer) 的範例。
    它會定期檢查 PTT 信箱，尋找特定標題的信件，並使用傳入的 log_func 將信件內容發送到訊息佇列。
    """

    first_round = True

    while True:

        # 每 CHECK_PTT_MAIL_INTERVAL 秒檢查一次 PTT 信箱
        await asyncio.sleep(config.CHECK_PTT_MAIL_INTERVAL)

        cur_mail_idx = ptt_service.call('get_newest_index', {'index_type': PyPtt.NewIndex.MAIL})

        if cur_mail_idx == 0:
            continue

        del_mail_list = []

        lookback_limit = 10
        if first_round:
            # 首次執行時，掃描較多的信件
            first_round = False
            lookback_limit = 50

        for mail_idx in range(max(1, cur_mail_idx - lookback_limit), cur_mail_idx + 1):
            try:
                mail_info = ptt_service.call('get_mail', {'index': mail_idx})
            except PyPtt.exceptions.Error:
                continue

            if PyPtt.MailField.title not in mail_info:
                continue

            # 過濾信件標題與作者
            if mail_info[PyPtt.MailField.title] != contant.PTT_MSG_TITLE:
                continue

            if not mail_info[PyPtt.MailField.author].lower().startswith(target.lower()):
                continue

            # 解析信件內容
            cur_context = mail_info[PyPtt.MailField.content]
            cur_context = cur_context[cur_context.find(
                contant.PTT_MSG_DIVISION_LINE) + len(contant.PTT_MSG_DIVISION_LINE):].strip()
            cur_context = cur_context[:cur_context.rfind(contant.PTT_MSG_DIVISION_LINE)].strip()

            log_func(cur_context)

            del_mail_list.append(mail_idx)

        # 刪除已處理的信件，從後往前刪以避免索引錯亂
        del_mail_list.sort(reverse=True)
        for cur_mail_idx in del_mail_list:
            ptt_service.call('del_mail', {'index': cur_mail_idx})


async def main_async():
    """
    主函式，負責設定 UI、事件處理及非同步任務。
    """
    # 訊息列表，用來儲存對話紀錄
    messages = []

    # 輸入緩衝區，設定為單行模式
    input_buffer = Buffer(multiline=False)

    # 建立 asyncio 佇列，用於在不同任務間安全地傳遞訊息
    message_queue = asyncio.Queue()

    # 定義日誌函式，將訊息放入佇列
    def log_to_queue(msg: str):
        message_queue.put_nowait(msg)

    # 記錄使用者輸入的函式
    def log_user_input(text: str, app: Application):
        messages.append((contant.USER_MSG, text))
        app.invalidate()

    # 建立顯示佈局
    def get_display():

        terminal_lines = os.get_terminal_size().lines

        # 限制訊息數量，避免過多佔用記憶體
        while len(messages) > config.MAX_MESSAGES:
            messages.pop(0)

        lines = []
        # 只顯示終端機可容納的最新訊息
        for msg_type, msg in messages[-(terminal_lines - 1):]:
            if msg_type == contant.SYSTEM_MSG:
                # 系統訊息
                match msg:
                    case contant.DIVISION_LINE:
                        # 分隔線
                        msg = contant.DIVISION_TYPE * (os.get_terminal_size().columns)
                        lines.append(msg)
                    case _:
                        lines.append(f"{contant.SYSTEM_MSG} {msg}")

            elif msg_type == contant.TARGET_MSG:
                # 對方訊息靠左對齊
                lines.append(f"{target}: {msg}")

            elif msg_type == contant.USER_MSG:
                # 使用者訊息靠右對齊
                terminal_width = os.get_terminal_size().columns - 2  # 減 2 留邊距
                user_header = ""
                padding = max(0, terminal_width - len(user_header) - wcswidth(msg))
                lines.append(f"{user_header}{' ' * padding}{msg}")

        return '\n'.join(lines)

    # 輸入視窗
    input_window = Window(
        content=BufferControl(buffer=input_buffer),
        height=D.exact(1),
        wrap_lines=False
    )

    # 組合訊息歷史視窗與輸入視窗
    container = HSplit([
        # 訊息歷史視窗
        Window(
            content=FormattedTextControl(get_display),
            height=D(weight=1),
            wrap_lines=True
        ),
        # 輸入視窗
        input_window
    ])

    # 設定鍵盤綁定
    bindings = KeyBindings()

    @bindings.add('c-c')  # Ctrl+C: 離開程式
    def exit_app(event):
        event.app.exit()

    @bindings.add('enter')  # Enter: 處理輸入
    def process_input(event):
        text = input_buffer.text.strip()
        if text:
            input_buffer.reset()  # 清空輸入框

            if text.lower() == 'exit':
                event.app.exit()
                return

            # 將使用者輸入轉換為 PTT 信件格式並寄出
            ptt_msg = utils.msg_to_mail(pkg_name, ptt_id, text)
            ptt_service.call('mail',
                             {'ptt_id': target, 'title': contant.PTT_MSG_TITLE, 'content': ptt_msg, 'backup': False})

            # 將使用者輸入顯示在畫面上
            log_user_input(text, event.app)

    # 建立應用程式實例
    app = Application(
        layout=Layout(container=container),
        key_bindings=bindings,
        full_screen=True,
        mouse_support=False
    )

    # 顯示對話視窗初始訊息
    initial_msgs = [
        f"這是與 {target} 的對話視窗。",
        "輸入 'exit' 來離開。",
        contant.DIVISION_LINE
    ]
    for msg in initial_msgs:
        messages.append((contant.SYSTEM_MSG, msg))
    app.invalidate()

    # 建立並啟動背景任務
    printer = app.create_background_task(message_printer_task(message_queue, messages, app))
    generator = app.create_background_task(demo_message_generator(log_to_queue))

    try:
        # 執行應用程式
        await app.run_async()
    finally:
        # 結束時確保取消背景任務
        generator.cancel()
        printer.cancel()
        await asyncio.gather(generator, printer, return_exceptions=True)
        print("正在離開程式...")


def main():
    print(f"歡迎使用 {pkg_name} v{__version__}")

    global ptt_id, target

    # 登入 PTT
    while True:
        ptt_id = input("請輸入您的 PTT ID: ")
        ptt_pw = getpass("請輸入您的 PTT 密碼: ")

        try:
            ptt_service.call('login',
                             {'ptt_id': ptt_id, 'ptt_pw': ptt_pw, 'kick_other_session': True})
            break
        except PyPtt.LoginError:
            print('登入失敗')
        except PyPtt.WrongIDorPassword:
            print('帳號密碼錯誤')
        except PyPtt.OnlySecureConnection:
            print('只能使用安全連線')
        except PyPtt.ResetYourContactEmail:
            print('請先至信箱設定連絡信箱')

    # 設定對話對象
    while True:
        target = input("請輸入你要對話的使用者: ")

        try:
            target_info = ptt_service.call('get_user', {'user_id': target})
            target = target_info['ptt_id'].split(' ')[0]
            break
        except PyPtt.exceptions.NoSuchUser:
            print('查無此人')
            continue

    # 設定終端機標題
    sys.stdout.write(f"\x1b]2;與 {target} 的對話視窗\x07")

    try:
        asyncio.run(main_async())
    except (KeyboardInterrupt, Exception) as e:
        print("\n程式已終止。")
        raise e
    finally:
        # 登出 PTT
        print('登出中...')
        ptt_service.call('logout')
        ptt_service.close()

if __name__ == '__main__':
    main()