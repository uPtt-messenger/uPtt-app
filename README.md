# uPttTerm

[![PyPI version](https://badge.fury.io/py/uPttTerm.svg)](https://badge.fury.io/py/uPttTerm)
[![Python Version](https://img.shields.io/pypi/pyversions/uPttTerm.svg)](https://pypi.org/project/uPttTerm/)

這是一個使用 Python 開發的終端機介面（TUI）應用程式，讓使用者可以只透過批踢踢伺服器與另一位使用者進行**即時聊天**。

## 需求

- Python 3.8 ~ 3.12
- 一個有效的 PTT 帳號

## 安裝與使用

### PyPi

1.  建立並啟動虛擬環境（可選）：
    ```bash
    python -m venv .venv
    source venv/bin/activate  # Linux 或 macOS
    venv\Scripts\activate     # Windows
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

5.  若要離開程式，請在輸入區輸入 `exit` 並按 `Enter`，或直接按下 `Ctrl+C`。

## 功能特色

- [x] 即時聊天功能
- [x] 終端機介面
- [ ] 新訊息通知
- [ ] 新信件通知