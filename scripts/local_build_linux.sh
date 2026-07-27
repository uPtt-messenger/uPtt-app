#!/bin/bash
# scripts/local_build_linux.sh
set -euo pipefail

# 確保在專案根目錄執行
cd "$(dirname "$0")/.."

# 檢查系統是否有 patchelf (Nuitka Standalone Linux 必備)
if ! command -v patchelf &> /dev/null; then
    echo "錯誤: 系統未安裝 'patchelf'。"
    echo "Nuitka 於 Linux 建立獨立執行檔 (standalone) 時需要此工具。"
    echo "請執行以下指令進行安裝："
    echo "  sudo apt update && sudo apt install -y patchelf"
    exit 1
fi

# 檢查虛擬環境是否存在，若無則自動建立並安裝依賴
if [ ! -d ".venv" ]; then
    echo "偵測到找不到 .venv，正在自動建立虛擬環境並安裝依賴套件 (這可能需要一點時間)..."
    python3 -m venv .venv || {
        echo "錯誤: 建立虛擬環境失敗。請確保系統已安裝 python3-venv。"
        exit 1
    }
    source .venv/bin/activate
    echo "正在升級 pip..."
    pip install --upgrade pip
    echo "正在安裝專案依賴項目..."
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    echo "正在安裝編譯器相關套件..."
    pip install nuitka zstandard
else
    # 啟動虛擬環境
    source .venv/bin/activate
fi

# 設定路徑讓 Nuitka 能找到原始碼
export PYTHONPATH=src

# 清除舊的編譯快取與產出，避免分支切換或舊檔案干擾
rm -rf dist_local/*.build dist_local/*.onefile-build dist_local/uPtt dist_local/uptt

# 執行 Nuitka 編譯 (onefile 模式)
echo "正在開始本地編譯 (onefile 模式)..."
# 注意：使用 --output-filename 指定執行檔名稱，避免手動改名導致路徑偵測失敗
python -m nuitka \
    --onefile \
    --plugin-enable=pyside6 \
    --include-qt-plugins=sensible \
    --include-package=PyPtt \
    --include-package=websockets \
    --include-package=qasync \
    --include-package-data=uPtt.ui.assets \
    --output-dir=dist_local \
    --output-filename=uptt \
    --assume-yes-for-downloads \
    src/run_app.py

# 整理產出物名稱 (與 CI/CD 流程一致)
echo "正在整理產出物..."
# 建立一個 uPtt 目錄來存放這唯一的執行檔，保持與 CI 流程結構一致
rm -rf dist_local/uPtt
mkdir -p dist_local/uPtt

# onefile 產出的檔案會直接位於 --output-dir 下
if [ -f "dist_local/uptt" ]; then
    mv dist_local/uptt dist_local/uPtt/
fi

# 確保執行檔具備執行權限 (雖然 Nuitka 預設會給)
if [ -f "dist_local/uPtt/uptt" ]; then
    chmod +x dist_local/uPtt/uptt
fi

# 打包為 .tar.gz (與 CI 流程一致)
echo "正在打包為 uPtt-Linux.tar.gz..."
tar -czf dist_local/uPtt-Linux.tar.gz -C dist_local uPtt/

echo "===================================================="
echo "編譯完成！"
echo "1. 執行檔路徑：dist_local/uPtt/uptt"
echo "2. 壓縮檔路徑：dist_local/uPtt-Linux.tar.gz"
echo ""
echo "您可以執行以下命令啟動測試 (debug 模式)："
echo "  ./dist_local/uPtt/uptt --debug"
echo "===================================================="
