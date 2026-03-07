# uPttTerm

[![PyPI version](https://badge.fury.io/py/uPttTerm.svg)](https://badge.fury.io/py/uPttTerm)
[![Python Version](https://img.shields.io/pypi/pyversions/uPttTerm.svg)](https://pypi.org/project/uPttTerm/)

這是一個使用 Python 開發的終端機介面（TUI）應用程式，讓使用者可以只透過批踢踢伺服器與另一位使用者進行**即時聊天**。

## 實際畫面

### 登入視窗
<img width="480" height="701" alt="image" src="https://github.com/user-attachments/assets/784da131-f637-4c82-8408-146a32643a21" />

### 對話視窗
<img width="435" height="448" alt="image" src="https://github.com/user-attachments/assets/65680862-f313-4cc8-a2e3-f04fcc625940" />

## 需求

- Python 3.10 以上
- 一個有效的 PTT 帳號

## 安裝與使用

### PyPi

1.  建立並啟動虛擬環境（可選）：
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # Linux 或 macOS
    .venv\Scripts\activate     # Windows
    ```
    
2.  安裝套件
    ```bash
    # 正式版本
    pip install uPttTerm
    
    # 測試版本
    pip install --extra-index-url https://test.pypi.org/simple/ uPttTerm
    ```
    

## 使用方式

1.  在終端機中執行應用程式：
    ```bash
    uptt
    ```

2.  依照提示輸入您的 PTT ID 與密碼以登入。

3.  輸入您想對話的使用者 ID。

4.  成功後，即可開始聊天。在輸入區輸入訊息後按 `Enter` 即可發送。

5.  若要離開程式，請在輸入區輸入 `/exit` 並按 `Enter`，或直接按下 `Ctrl+C`。

## 開發測試

1.  下載原始碼並進入專案目錄：
    ```bash
    git clone
    ```
    
2. 建立並啟動虛擬環境（可選）：
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # Linux 或 macOS
    .venv\Scripts\activate     # Windows
    ```
   
3. 安裝開發需求：
    ```bash
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    ```

4. 執行應用程式：
    ```bash
    PYTHONPATH=src python3 -m uPttTerm.app
    ```


## 功能特色

- [x] 即時聊天功能
- [x] 終端機介面
- [ ] 新訊息通知
- [ ] 新信件通知
