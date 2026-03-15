import argparse
import logging
import sys

from PySide6.QtWidgets import QApplication

from .ptt import UPttService
from .ui.screens import MainWindow


# --- 日誌設定 ---
def setup_logging(debug_mode: bool):
    """設定日誌系統，確保同時輸出到終端機與檔案 (如果開啟除錯)"""
    # 建立處理器 (同時輸出到終端機)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    console_handler.setFormatter(formatter)

    # 取得根紀錄器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    root_logger.addHandler(console_handler)

    if debug_mode:
        file_handler = logging.FileHandler("uptt_debug.log", mode="w")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)
        logging.info("已啟用除錯模式，日誌將同步紀錄至 uptt_debug.log")

    logger = logging.getLogger("uPttTerm")
    logger.info("uPttTerm 日誌系統初始化完成")


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
    qt_app.setQuitOnLastWindowClosed(False)  # 允許縮小至系統匣而不退出

    # 初始化 PTT 服務實例
    ptt_service = UPttService()

    # 建立主視窗 (內部會處理 Login 與 Main Chat 的切換)
    main_window = MainWindow(ptt_service)
    main_window.show()

    # 讓 macOS 的 Dock Quit 也走完全退出流程
    qt_app.aboutToQuit.connect(main_window.fully_quit)

    try:
        sys.exit(qt_app.exec())
    except Exception as e:
        logger.exception("App crashed unexpectedly")
        print(f"程式發生未預期錯誤: {e}")


if __name__ == "__main__":
    main()
