import sys
import os
import multiprocessing
import subprocess

# 支援 PyInstaller 打包後的多行程
multiprocessing.freeze_support()

# 確保 src 目錄在路徑中
sys.path.insert(0, os.path.dirname(__file__))

def log_debug(message):
    """將訊息寫入家目錄下的 log 檔以利除錯"""
    try:
        log_path = os.path.expanduser("~/uPttTerm_launcher.log")
        with open(log_path, "a") as f:
            f.write(f"{message}\n")
    except Exception:
        pass

def start_ui():
    from uPttTerm.app import main
    try:
        main()
    except Exception as e:
        log_debug(f"UI 崩潰: {e}")
        print(f"\n發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        input("\n按下 Enter 鍵結束...")

def start_server(port):
    from uPttTerm.server import run_server
    # 伺服器模式下，徹底保護 TUI，避免任何輸出
    try:
        f = open(os.devnull, 'w')
        sys.stdout = f
        sys.stderr = f
        run_server("127.0.0.1", int(port))
    except Exception as e:
        log_debug(f"伺服器啟動失敗: {e}")

def ensure_terminal():
    """
    確保程式在終端機中執行。
    """
    # 如果已經有 TTY (或是伺服器模式)，就直接執行
    if sys.stdin.isatty() or "--server" in sys.argv:
        return False

    log_debug(f"偵測到非 TTY 啟動，嘗試開啟 Terminal。引數: {sys.argv}")

    # 判斷是否為打包環境
    if getattr(sys, 'frozen', False):
        executable = sys.executable
        log_debug(f"執行檔路徑: {executable}")
        
        # 使用引號包裹路徑以處理空格，並加入 activate 確保視窗跳出
        # 加上 'exit' 讓程式結束後自動關閉分頁（可選）
        applescript = f'''
            tell application "Terminal"
                activate
                do script "'{executable}'"
            end tell
        '''
        try:
            subprocess.Popen(["osascript", "-e", applescript])
            log_debug("osascript 指令已發送。")
            return True
        except Exception as e:
            log_debug(f"osascript 執行失敗: {e}")
            return False
    
    return False

if __name__ == "__main__":
    # 清理舊日誌並開始新紀錄
    if not "--server" in sys.argv:
        log_debug("--- 程式啟動 ---")

    # 偵測是否為伺服器模式
    if len(sys.argv) > 2 and sys.argv[1] == "--server":
        start_server(sys.argv[2])
    else:
        # 嘗試確保有終端機
        if ensure_terminal():
            log_debug("已啟動新終端機，原行程退出。")
            sys.exit(0)
        start_ui()
