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

import config
import contant

import utils

ptt_service = PyPtt.Service({'log_level': PyPtt.log.SILENT})


# 改造 1：建立一個專門負責從佇列中取出訊息並附加到 UI 的任務
async def message_printer_task(message_queue: asyncio.Queue, messages: list, app: Application):
    """
    這是一個訊息消費者 (Consumer)。
    它會永遠等待佇列中出現新訊息，一旦有新訊息就將它附加到訊息列表，並更新 UI。
    """
    while True:
        message = await message_queue.get()
        messages.append((contant.TARGET_MSG, message))  # 改用 tuple
        # 觸發 UI 更新
        app.invalidate()
        message_queue.task_done()


# 改造 3：原有的 background_task 現在變成一個純粹的訊息產生器
async def demo_message_generator(log_func):
    """
    這是一個訊息生產者 (Producer) 的範例。
    它模擬週期性事件，並使用傳入的 log_func 來發送訊息。
    """

    while True:
        await asyncio.sleep(5)

        cur_mail_idx = ptt_service.call('get_newest_index', {'index_type': PyPtt.NewIndex.MAIL})
        # log_func(f"目前信件數量: {cur_mail_idx}")

        if cur_mail_idx == 0:
            continue

        try:
            mail_info = ptt_service.call('get_mail', {'index': cur_mail_idx})
        except PyPtt.exceptions.Error:
            continue

        if PyPtt.MailField.title not in mail_info:
            continue

        if mail_info[PyPtt.MailField.title] != contant.PTT_MSG_TITLE:
            continue

        ptt_service.call('del_mail', {'index': cur_mail_idx})

        cur_context = mail_info[PyPtt.MailField.content]
        cur_context = cur_context[cur_context.find(
            contant.PTT_MSG_DIVISION_LINE) + len(contant.PTT_MSG_DIVISION_LINE):].strip()
        cur_context = cur_context[:cur_context.rfind(contant.PTT_MSG_DIVISION_LINE)].strip()

        log_func(cur_context)


async def main():
    """
    主函式，設定並同時執行所有任務。
    """
    # 全域訊息列表，用來建構顯示內容（現在存原始類型：'bot' 或 'user'）
    messages = []

    # 輸入緩衝區：關鍵修改！設定 multiline=False 防止自動換行
    input_buffer = Buffer(multiline=False)

    # 建立一個 asyncio 佇列，用來在不同任務間傳遞訊息
    message_queue = asyncio.Queue()

    # 改造 2：定義我們的日誌函式 (log function)
    # 這個函式可以被程式的任何部分呼叫，以非同步的方式將訊息放入佇列
    def log_to_queue(msg: str):
        message_queue.put_nowait(msg)

    # 記錄使用者輸入的函式（直接附加到列表，並更新 UI）
    def log_user_input(text: str, app: Application):
        messages.append((contant.USER_MSG, text))  # 存為 tuple: ('user', text)
        app.invalidate()

    # 建立佈局
    def get_display():

        terminal_lines = os.get_terminal_size().lines

        while len(messages) > config.MAX_MESSAGES:
            messages.pop(0)

        lines = []
        for msg_type, msg in messages[-(terminal_lines - 1):]:  # 只顯示最近 20 行
            if msg_type == contant.SYSTEM_MSG:

                match msg:
                    case contant.DIVISION_LINE:
                        msg = contant.DIVISION_TYPE * (os.get_terminal_size().columns)
                        lines.append(msg)
                    case _:
                        lines.append(f"{contant.SYSTEM_MSG} {msg}")  # 左對齊

            elif msg_type == contant.TARGET_MSG:
                # 目標訊息靠左對齊
                lines.append(f"{target}: {msg}")  # 左對齊

            elif msg_type == contant.USER_MSG:
                # 使用者訊息靠右對齊

                # 取得終端寬度，用來 padding
                terminal_width = os.get_terminal_size().columns - 2  # 減 2 留邊距

                # 計算 padding，讓文字靠右：總寬 - 標頭長 - 訊息長，然後加標頭
                user_header = ""
                padding = max(0, terminal_width - len(user_header) - wcswidth(msg))
                lines.append(f"{user_header}{' ' * padding}{msg}")  # 右對齊

        return '\n'.join(lines)

    # 輸入視窗：現在正常左對齊
    input_window = Window(
        content=BufferControl(buffer=input_buffer),
        height=D.exact(1),
        wrap_lines=False  # 保留，強化單行
    )

    container = HSplit([
        # 上方：訊息歷史視窗
        Window(
            content=FormattedTextControl(get_display),
            height=D(weight=1),
            wrap_lines=True
        ),
        # 下方：輸入視窗（正常左對齊）
        input_window
    ])

    # 鍵綁定
    bindings = KeyBindings()

    @bindings.add('c-c')  # Ctrl+C 結束
    def exit_app(event):
        event.app.exit()

    @bindings.add('enter')  # Enter 處理輸入
    def process_input(event):
        text = input_buffer.text.strip()
        if text:
            input_buffer.reset()  # 清空輸入

            if text.lower() == 'exit':
                event.app.exit()
                return

            ptt_msg = utils.msg_to_mail(config.APP_NAME, ptt_id, text)
            # ptt_msg = utils.uniform_new_line(ptt_msg)

            ptt_service.call('mail',
                             {'ptt_id': target, 'title': contant.PTT_MSG_TITLE, 'content': ptt_msg, 'backup': False})

            log_user_input(text, event.app)
            # 可以這裡觸發其他邏輯，例如 print 或回應
        # 重新聚焦輸入

    # 建立應用程式
    app = Application(
        layout=Layout(container=container),
        key_bindings=bindings,
        full_screen=True,
        mouse_support=False  # 可選，依需求
    )

    # 初始訊息（bot 類型）
    initial_msgs = [
        f"歡迎使用 {config.APP_NAME}",
        "輸入 'exit' 來離開。",
        contant.DIVISION_LINE
    ]
    for msg in initial_msgs:
        messages.append((contant.SYSTEM_MSG, msg))
    app.invalidate()  # 更新初始顯示

    # 建立背景任務（printer 現在直接用 messages）
    printer = app.create_background_task(message_printer_task(message_queue, messages, app))
    generator = app.create_background_task(demo_message_generator(log_to_queue))

    try:
        # 運行應用程式
        await app.run_async()
    finally:
        # 結束時取消背景任務
        generator.cancel()
        printer.cancel()
        await asyncio.gather(generator, printer, return_exceptions=True)
        print("正在離開程式...")


if __name__ == "__main__":

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

    while True:
        target = input("請輸入你要對話的使用者: ")

        try:
            target_info = ptt_service.call('get_user', {'user_id': target})

            target = target_info['ptt_id'].split(' ')[0]
            break
        except PyPtt.exceptions.NoSuchUser:
            print('查無此人')
            continue

    # set terminal title
    sys.stdout.write(f"\x1b]2;與 {target} 的對話視窗\x07")

    try:
        asyncio.run(main())
    except (KeyboardInterrupt, Exception) as e:
        print("\n程式已終止。")
    finally:
        print('登出中...')
        ptt_service.call('logout')
        ptt_service.close()
