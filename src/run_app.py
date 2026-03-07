import sys
import os

# 確保 src 目錄在路徑中
sys.path.insert(0, os.path.dirname(__file__))

from uPttTerm.app import main

if __name__ == "__main__":
    main()
