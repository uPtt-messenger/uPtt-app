<p align="center">
  <img src="src/uPtt/ui/assets/logo_horizontal.svg" alt="uPtt Logo" width="450">
</p>

<p align="center">
  <strong>讓 PTT 的溫柔，在現代桌面重新綻放</strong><br>
  一個為「批踢踢實業坊」量身打造的現代化即時通訊終端。
</p>

<p align="center">
  <a href="https://github.com/uPtt-messenger/uPttTerm/releases"><img src="https://img.shields.io/github/v/release/uPtt-messenger/uPttTerm?label=最新發布版本&color=blue" alt="GitHub release"></a>
  <a href="https://github.com/uPtt-messenger/uPttTerm/blob/main/LICENSE"><img src="https://img.shields.io/badge/授權條款-GPL--3.0-green.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/平台-Windows%20|%20macOS-lightgrey" alt="Platform">
</p>

---

### 🌟 專案願景：跨越三十年的技術橋樑

PTT（批踢踢）是台灣最具生命力的網路社群，但傳統的 Telnet 黑白畫面與站內信系統，在即時通訊盛行的今天顯得有些孤獨。

**uPtt** 的誕生，是為了讓這份舊時代的技術得以延續。我們運用 Python 與現代化圖形介面（GUI）技術，將 PTT 站內信系統重塑為如同 Telegram 或 LINE 一般的**流暢聊天體驗**。無需學習複雜的鍵盤指令，讓您在 PTT 上的對話如同呼吸般自然。

---

## ✨ 核心功能：舊傳統與新科技的完美結合

### 🚀 即時通訊體驗 (Instant Messaging)
*   **郵件轉對話：** 自動將瑣碎的「站內信」轉換為直覺的「對話氣泡」，溝通不再斷斷續續。
*   **訊息引用回覆：** 右鍵點擊任意訊息即可引用回覆，輸入框上方會顯示引用預覽，讓對話脈絡一目了然。
*   **智慧輪詢 (Smart Polling)：** 採用精準的背景偵測技術，確保訊息即時傳達，同時將系統負載降至最低。
*   **多帳號管理：** 獨家資料庫隔離技術，支援多個 PTT 帳號切換，對話紀錄井然有序。
*   **一般站內信整合：** 非 uPtt 格式的普通站內信也會以信件卡片形式顯示在聊天紀錄中，超過 5 行可一鍵展開全文。

### 🗂️ 聯絡人管理
*   **釘選對話：** 右鍵聯絡人 → 釘選，重要對話永遠固定在清單頂端。
*   **拖放排序：** 直接拖拉調整聯絡人順序，釘選區與未釘選區各自獨立排列。
*   **封鎖 / 刪除：** 右鍵選單提供關閉（隱藏）、刪除（清除本地紀錄）、封鎖（忽略往後訊息）三種層級操作。

### 🔔 背景通知
*   **系統匣常駐：** 關閉視窗後程式仍在背景運作，不中斷訊息接收。
*   **桌面通知：** 非使用中時收到新訊息，系統匣會即時彈出通知預覽。

### ⌨️ 鍵盤快捷鍵
| 按鍵 | 功能 |
|------|------|
| `Ctrl+N` | 聚焦新增對話輸入框 |
| `Ctrl+W` | 關閉目前對話 |
| `Ctrl+Q` | 完全退出程式 |
| `Enter` | 發送訊息 |

### 🎨 現代化視覺美學 (Modern UI/UX)
*   **Retina 級解析度：** 全向量 SVG 圖示渲染，無論在 4K 螢幕或 MacBook 的 Retina 螢幕上都絕對銳利。
*   **極簡暗色模式：** 傳承 PTT 的黑色靈魂，搭配精緻的字體層次，給您最舒適的閱讀體驗。
*   **極速本地快取：** 歷史訊息秒開，無需等待 PTT 伺服器緩慢載入。

### 🛡️ 安全與隱私 (Security)
*   **本地加密存儲：** 您的對話紀錄與帳號資訊僅保存在您的電腦中，絕不上傳第三方伺服器。
*   **原生通訊協議：** 直接與 PTT 官方伺服器連線，純淨、安全。
*   **自動化防洩漏機制：** CI 流程整合 `TruffleHog` 掃描與動態密碼攔截技術，確保敏感資訊在開發、測試與 Log 紀錄中絕不外洩。

---

## 📸 介面預覽

### 現代化的登入體驗
<img width="520" alt="Login Screen" src="https://i.meee.com.tw/0RXU0Vt.png" />

---

## ⚠️ 重要運行機制說明

為了提供如同通訊軟體的流暢體驗，uPtt 採用了以下機制：

1.  **訊息即時處理：** 系統成功解析訊息並存入本地資料庫後，會**自動刪除**該筆 PTT 站內信，以維持信箱整潔。
2.  **一般站內信顯示：** 非 uPtt 格式的普通站內信（例如系統公告、其他人寄來的一般信）**不會被刪除**，但同樣會以信件卡片的形式顯示在對應聯絡人的對話紀錄中。
3.  **安全性建議：** 本程式內建嚴謹的判斷邏輯，僅自動刪除 uPtt 專屬格式訊息。若您對自動刪除機制有所疑慮，請在 PTT 系統設定中開啟「外部信箱備份」。

---

## 🚀 如何開始使用？

### 取得最新發行版
無需安裝繁瑣的程式碼環境，請前往 [GitHub Releases](https://github.com/uPtt-messenger/uPttTerm/releases) 下載對應版本：

*   **Windows:** 下載 `.exe` 執行檔，執行後即可啟動。
*   **macOS:** 下載 `.dmg` 映像檔，將 `uPtt` 拖移至「應用程式」資料夾即可使用。

---

## 🛠 開發者資訊

本專案使用 **Python 3.12** 與 **PySide6** 開發。如果您想參與開發或自行編譯，請參考：

1.  **複製專案：** `git clone https://github.com/uPtt-messenger/uPttTerm.git`
2.  **安裝依賴：** `pip install -r requirements.txt`
3.  **執行：** `python3 src/run_app.py`
4.  **測試：** `pytest --cov=src/uPtt tests/`

---

## 📜 授權與感謝

*   本專案採用 **GPL-3.0** 授權。
*   特別感謝 [PyPtt](https://github.com/Ptt-Official-App/PyPtt) 提供強大的 PTT 操作支援 ~~這其實也是 CodingMan 開發的~~。

<p align="center">
  由 <a href="mailto:pttcodingman@gmail.com">CodingMan</a> 帶著對 PTT 的熱愛製作
</p>
