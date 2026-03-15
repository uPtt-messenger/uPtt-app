import argparse
import logging
import sys
import os

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtNetwork import QLocalServer, QLocalSocket

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

    logger = logging.getLogger("uPtt")
    logger.info("uPtt 日誌系統初始化完成")


logger = logging.getLogger("uPtt")


def main():
    """uPtt GUI 應用程式進入點"""
    parser = argparse.ArgumentParser(description="uPtt - Open Source PTT Messenger")
    parser.add_argument("--debug", action="store_true", help="啟用除錯模式並記錄至檔案")
    args = parser.parse_args()

    setup_logging(args.debug)

    # 初始化 Qt 應用程式
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("uPtt")
    qt_app.setQuitOnLastWindowClosed(False)  # 允許縮小至系統匣而不退出

    # --- 單一實例檢查 (Single Instance Check) ---
    server = None
    if not args.debug:
        server_name = "uPtt_SingleInstance_Lock"

        # 嘗試連接到現有的伺服器
        socket = QLocalSocket()
        socket.connectToServer(server_name)

        # 如果連接成功，表示已有實例在執行
        if socket.waitForConnected(500):
            # 如果需要，可以透過 socket 發送訊息給現有實例
            socket.disconnectFromServer()
            logger.info("偵測到另一個實例正在執行，程式即將結束。")
            return # 直接結束

        # 如果沒有實例，則啟動自己的伺服器
        server = QLocalServer()
        # 確保在非正常結束後能重新啟動 (清理殘留的 socket 檔案)
        QLocalServer.removeServer(server_name)

        if not server.listen(server_name):
            logger.error(f"無法啟動單一實例伺服器: {server.errorString()}")
            # 如果連 listen 都失敗（且 connect 也失敗），可能是權限或其他問題
            # 這裡我們選擇繼續執行，或者拋出錯誤
    else:
        logger.info("除錯模式已啟用，略過單一實例檢查。")

    # 初始化 PTT 服務實例
    ptt_service = UPttService()

    # 建立主視窗
    main_window = MainWindow(ptt_service)
    main_window.show()

    # 當新實例嘗試啟動時，會連線到此 server，我們藉此將主視窗推至最前
    if server:
        def on_new_connection():
            new_socket = server.nextPendingConnection()
            if new_socket:
                new_socket.close()
                # 顯示視窗並置頂
                main_window.showNormal()
                main_window.activateWindow()
                main_window.raise_()
                logger.info("收到新連線請求，已將現有視窗推至前景。")

        server.newConnection.connect(on_new_connection)


    # 讓 macOS 的 Dock Quit 也走完全退出流程
    qt_app.aboutToQuit.connect(main_window.fully_quit)

    try:
        sys.exit(qt_app.exec())
    except Exception as e:
        logger.exception("App crashed unexpectedly")
        print(f"程式發生未預期錯誤: {e}")


if __name__ == "__main__":
    main()
