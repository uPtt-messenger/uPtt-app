import sys
import os
import multiprocessing
import subprocess

# 支援 PyInstaller 打包後的多行程
multiprocessing.freeze_support()

# 確保 src 目錄在路徑中
sys.path.insert(0, os.path.dirname(__file__))

def start_ui():
    from uPttTerm.app import main
    try:
        main()
    except Exception as e:
        # 在發生未預期錯誤時，確保至少能印出訊息
        print(f"\n發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        input("\n按下 Enter 鍵結束...")

def start_server(port):
    from uPttTerm.server import run_server
    # 伺服器模式下，徹底保護 TUI，避免任何輸出
    f = open(os.devnull, 'w')
    sys.stdout = f
    sys.stderr = f
    run_server("127.0.0.1", int(port))

def ensure_terminal():
    """
    確保程式在終端機中執行。
    如果偵測到是透過 open 或連點啟動（沒有 TTY），則開啟 Terminal 執行自己。
    """
    # 如果已經有 TTY (或是伺服器模式)，就直接執行
    if sys.stdin.isatty() or "--server" in sys.argv:
        return False

    # 判斷是否為打包環境
    if getattr(sys, 'frozen', False):
        executable = sys.executable
        # 使用 AppleScript 開啟 Terminal 並執行執行檔
        applescript = f'tell application "Terminal" to do script "{executable}"'
        subprocess.Popen(["osascript", "-e", applescript])
        return True
    
    return False

if __name__ == "__main__":
    # 偵測是否為伺服器模式
    if len(sys.argv) > 2 and sys.argv[1] == "--server":
        start_server(sys.argv[2])
    else:
        # 嘗試確保有終端機，如果啟動了新視窗，則目前行程結束
        if ensure_terminal():
            sys.exit(0)
        start_ui()
