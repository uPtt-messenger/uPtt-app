import sys
import logging
import argparse
from PySide6.QtWidgets import QApplication
from uPttTerm.ptt import UPttService
from uPttTerm.ui.screens import MainWindow

# --- 日誌設定 ---
def setup_logging(debug_mode: bool):
    if debug_mode:
        logging.basicConfig(
            filename="uptt_debug.log",
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            filemode="w"
        )
        logging.info("Debug mode enabled. Switched to PySide6 GUI architecture.")
    else:
        # 預設只記錄嚴重錯誤
        logging.basicConfig(level=logging.ERROR)

logger = logging.getLogger("uPttTerm")

def main():
    """uPttTerm GUI 應用程式進入點"""
    parser = argparse.ArgumentParser(description="uPttTerm - PTT GUI Messenger")
    parser.add_argument("--debug", action="store_true", help="啟用除錯模式並記錄至檔案")
    args = parser.parse_args()

    setup_logging(args.debug)
    
    # 初始化 Qt 應用程式
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("uPttTerm")
    qt_app.setQuitOnLastWindowClosed(False) # 允許縮小至系統匣而不退出

    # 初始化 PTT 服務實例
    ptt_service = UPttService()

    # 建立主視窗 (內部會處理 Login 與 Main Chat 的切換)
    main_window = MainWindow(ptt_service)
    main_window.show()

    try:
        sys.exit(qt_app.exec())
    except Exception as e:
        logger.exception("App crashed unexpectedly")
        print(f"程式發生未預期錯誤: {e}")

if __name__ == "__main__":
    main()
