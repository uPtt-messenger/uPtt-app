import logging
import argparse
from textual.app import App
from uPttTerm.ptt import UPttService
from uPttTerm.ui.styles import CSS
from uPttTerm.ui.screens import LoginScreen


# --- 日誌設定 ---
def setup_logging(debug_mode: bool):
    if debug_mode:
        logging.basicConfig(
            filename="uptt_debug.log",
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            filemode="w"
        )
        logging.info("Debug mode enabled. Using modular architecture.")
    else:
        logging.basicConfig(level=logging.CRITICAL)


logger = logging.getLogger("uPttTerm")


class UPttTermApp(App):
    """uPttTerm - 現代化的 PTT TUI 即時通訊"""
    CSS = CSS
    TITLE = "uPttTerm"

    def __init__(self):
        super().__init__()
        self.ptt_id = None
        self.ptt = UPttService()  # 初始化專屬獨立連線實例

    def on_mount(self):
        self.push_screen(LoginScreen())

    def on_unmount(self):
        try:
            self.ptt.close()  # 確保連線釋放
        except:
            pass


def main():
    """應用程式進入點"""
    parser = argparse.ArgumentParser(description="uPttTerm - PTT TUI Messenger")
    parser.add_argument("--debug", action="store_true", help="啟用除錯模式並記錄至檔案")
    args = parser.parse_args()

    setup_logging(args.debug)
    
    app = UPttTermApp()
    try:
        app.run()
    except Exception as e:
        logger.exception("App crashed unexpectedly")
        print(f"程式發生未預期錯誤，請查看 uptt_debug.log: {e}")

if __name__ == "__main__":
    main()
