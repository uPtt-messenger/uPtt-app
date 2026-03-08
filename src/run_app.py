import sys
import os
import multiprocessing

# 支援 PyInstaller 打包後的多行程
multiprocessing.freeze_support()

# 確保 src 目錄在路徑中
sys.path.insert(0, os.path.dirname(__file__))

def start_ui():
    from uPttTerm.app import main
    main()

def start_server(port):
    from uPttTerm.server import run_server
    # 伺服器模式下，將 stdout/stderr 導向空裝置，徹底保護 TUI
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')
    run_server("127.0.0.1", int(port))

if __name__ == "__main__":
    # 偵測是否為伺服器模式
    if len(sys.argv) > 2 and sys.argv[1] == "--server":
        start_server(sys.argv[2])
    else:
        start_ui()
