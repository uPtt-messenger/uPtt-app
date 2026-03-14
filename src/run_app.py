import sys
import os
import multiprocessing

# 支援 PyInstaller 打包後的多行程
multiprocessing.freeze_support()

# 確保 src 目錄在路徑中，以便 import uPttTerm
sys.path.insert(0, os.path.dirname(__file__))

def start_ui():
    """啟動 uPttTerm GUI 應用程式"""
    from uPttTerm.app import main
    try:
        main()
    except Exception as e:
        print(f"\n應用程式啟動失敗: {e}")
        import traceback
        traceback.print_exc()
        if sys.stdin.isatty():
            input("\n按下 Enter 鍵結束...")

if __name__ == "__main__":
    # 對於 GUI 應用程式，直接啟動即可
    start_ui()
