<p align="center">
  <img src="src/uPtt/ui/assets/logo_horizontal.svg" alt="uPtt Logo" width="400">
</p>

<h1 align="center">uPtt Messenger</h1>

<p align="center">
  <a href="https://github.com/uPtt-messenger/uPttTerm/releases"><img src="https://img.shields.io/github/v/release/uPtt-messenger/uPttTerm?label=latest%20release" alt="GitHub release"></a>
  <a href="https://pypi.org/project/uPtt/"><img src="https://img.shields.io/pypi/pyversions/uPtt.svg" alt="Python Version"></a>
  <a href="https://github.com/uPtt-messenger/uPttTerm/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-GPL--3.0--only-blue.svg" alt="License"></a>
</p>

---

**uPtt** 是一個使用 Python (PySide6) 開發的**圖形介面 (GUI)** 應用程式。旨在讓使用者能直接透過 PTT (批踢踢實業坊) 伺服器，與其他使用者進行**即時私訊聊天**，無需再切換回傳統的終端機畫面。

## ✨ 功能特色

- [x] **即時聊天：** 透過 PTT 內建私訊系統實現流暢的對話。
- [x] **圖形化介面：** 基於 PySide6 打造，提供更直覺的操作體驗。
- [x] **自動登入：** 支援安全儲存憑據，快速進入聊天室。
- [x] **聯絡人管理：** 輕鬆新增、搜尋並管理您的 PTT 好友。
- [ ] **新訊息通知：** 即時桌面通知，不錯過任何訊息。
- [ ] **新信件通知：** 整合 PTT 站內信提醒功能。

## 📸 實際畫面

### 登入視窗
<img width="480" alt="Login Screen" src="https://i.meee.com.tw/0RXU0Vt.png" />

## 📋 需求條件

- 一個有效的 **PTT 帳號**
- 作業系統：Windows / macOS

## 🚀 下載與安裝

### 取得最新發行版

請前往 [GitHub Releases](https://github.com/uPtt-messenger/uPttTerm/releases) 下載適用於您作業系統的最新版本：

1. **Windows/macOS:** 下載對應的壓縮檔或安裝檔，解壓縮後即可執行。

---

## 🛠 開發與測試

Test with Python 3.12。

如果您想參與開發或自行編譯，請參考以下步驟：

1. **複製專案：**
   ```bash
   git clone https://github.com/uPtt-messenger/uPttTerm.git
   cd uPttTerm
   ```

2. **安裝相依套件：**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

3. **執行應用程式：**
   ```bash
   python3 src/run_app.py
   ```

4. **執行單元測試：**
   ```bash
   pytest --cov=src/uPtt tests/
   ```

## 📜 授權條款

本專案採用 [GPL-3.0-only](https://github.com/uPtt-messenger/uPttTerm/blob/main/LICENSE) 授權。

---
<p align="center">
  由 <a href="mailto:pttcodingman@gmail.com">CodingMan</a> 製作
</p>
