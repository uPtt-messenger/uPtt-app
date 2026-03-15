# **📝 開源專案 Git Flow 開發與自動化規範 (Agent 指引)**

本文件定義了本專案的雙主線（main/beta）開發流程。Agent 在進行代碼編寫、測試與分支管理時，必須嚴格遵守以下規範。

## **1\. 核心分支架構與策略 (Branching & Merging)**

| 分支名稱 | 定位 | 來源分支 | 合併策略 | 備註 |
| :---- | :---- | :---- | :---- | :---- |
| **main** | **穩定版 (Production)** | 無 | Merge Commit | 僅接收 beta 或 hotfix/\* |
| **beta** | **預發布版 (Staging)** | main | Squash / Merge | 所有功能的匯集地 |
| **feature/\*** | **新功能開發** | beta | Squash | 完成後刪除分支 |
| **hotfix/\*** | **緊急修復** | main | Merge Commit | 須同步至 main 與 beta |

## **2\. 測試與質量守門 (Unit Test Flow)**

**Agent 準則：測試失敗即任務失敗。**

1. **強制測試：** 在執行任何 git commit 或 git merge 之前，必須在本地環境執行專案既有的 **Unit Test Flow**。  
2. **驗證指令：** 執行 `pytest` 並確保獲得 PASS 結果。  
3. **環境清潔：** 測試前確保依賴已更新。

## **3\. 標準作業程序 (SOP)**

### **A. 新功能開發 (Feature Workflow)**

1. **同步遠端：** git checkout beta \-\> git pull origin beta。  
2. **建立分支：** git checkout \-b feature/your-feature-name beta。  
3. **代碼實作：** 撰寫代碼並同時撰寫/更新對應的 Unit Tests。  
4. **驗證：** 執行 **Unit Test Flow**，確保 100% 通過。  
5. **提交：** 提交 PR 回 beta 分支。

### **B. 正式發布 (Release Workflow: Beta \-\> Main)**

1. **最後確認：** 確保 beta 分支所有測試均為 PASS。  
2. **版本更新：** 根據語義化版本 (SemVer) 更新 package.json 或版本文件。  
3. **合併至 Main：** 將 beta 合併至 main (使用 \--no-ff 產生 Merge Commit)。  
4. **打標籤：** 在 main 建立 Git Tag，例如 v1.0.0。  
5. **反向合併：** 必須將 main 的版本更動同步回 beta 分支。

### **C. 緊急修復 (Hotfix Workflow)**

1. **建立分支：** 從 main 切出 hotfix/bug-description。  
2. **修復與測試：** 修復後必須通過 **Unit Test Flow**。  
3. **雙向合併：**  
   * 合併至 main 並打上補丁版本 Tag (如 v1.0.1)。  
   * 合併至 beta，若產生衝突，請立即停止操作並請求人工介入。

## **4\. 提交與衝突規範**

* **Commit Message:** 遵循 **Conventional Commits** (feat:, fix:, test:, chore:)。  
* **衝突處理：** 遇到衝突時，Agent 禁止擅自決定，必須回報人工處理。

## **5\. Agent 任務前自我檢查清單 (Pre-flight Checklist)**

* [ ] **環境同步：** 我是否已經執行了 git pull 確保是基於最新代碼？  
* [ ] **分支確認：** 我目前所在的分支是否正確？  
* [ ] **測試執行：** 我是否已執行 Unit Test 且獲得 PASS？  
* [ ] **版本更新：** 若是 Release/Hotfix，我是否已正確處理版本號？  
* [ ] **規範檢查：** Commit Message 是否符合格式？

---

## **6\. GUI 介面佈局與美學規範 (GUI UX/UI Standards)**

為了維持 `uPtt` 的專業感與操作舒適度，Agent 在調整介面時必須遵守以下規範：

### **A. 全動態置中原則 (Dynamic Centering)**
*   **水平與垂直雙向絕對置中：** 會話清單等條目式元件，應在佈局中明確使用 `Qt.AlignVCenter` 或在上下兩側使用 `addStretch()`，確保內容在容器內維持動態置中。
*   **佈局一致性：** 即使部分資訊（如暱稱）缺失，主標題（PTT ID）的垂直位置也必須保持固定（應為次要資訊標籤設定 `setFixedHeight`），避免視覺上的「跳動」或「歪斜」。

### **B. 側邊欄與視窗配置**
*   **側邊欄寬度：** 最小寬度 `160px`，最大寬度 `250px`。**目前實作固定為 `220px`** 以確保長 ID 與暱稱有足夠的顯示空間。
*   **預設比例：** 主聊天視窗啟動後的 `QSplitter` 初始比例建議維持在 `1:3.5` 左右。

### **C. 視覺美學標準 (Aesthetics)**
*   **配色風格：** 採用柔和暗色系終端風格。
*   **向量渲染：** 所有的 SVG 資源**必須**透過 `render_svg` 輔助函數進行渲染。該函數需考慮 `devicePixelRatioF()`，以確保在 Retina 或 High-DPI 螢幕上維持絕對銳利度。
*   **文字層次：**
    *   **主標題 (ID)：** 粗體、15px、亮灰色 (#F0F6FC)。
    *   **次要資訊 (暱稱)：** 常規、11px、中灰色 (#8B949E)。
*   **行間距：** ID 與暱稱之間的行距應保持緊湊（建議 `setSpacing(2)`）。

---

## **7\. PTT ID 處理機制與業務邏輯**

### **A. ID 格式化與儲存**
*   **內部唯一鍵值：** 程式內部存取、字典鍵值、歷史紀錄索引，必須統一轉換為 **全小寫** (`.lower()`) 進行操作，以確保大小寫不敏感的一致性。
*   **顯示 ID：** 在 UI 顯示上，應優先保留並使用從 PTT 伺服器取得的 **原始大小寫格式**。若尚未取得，則顯示使用者輸入的原始格式。

### **B. 業務限制 (Business Logic)**
*   **禁止自我對話：** 嚴禁建立與「目前登入帳號」相同的對話會話，程式需在新增聯絡人時過濾此行為（不分大小寫比對）。

### **C. 動態同步邏輯**
*   **資訊更新：** 當收到 `user_info` 回傳時，必須呼叫 `update_info` 方法同步更新清單項目的 ID 大小寫與暱稱。
*   **主動重整：** 即使聯絡人已存在於清單中，再次新增同一 ID 仍應發送查詢請求，以更新其最新的大小寫格式。

---

## **8．應用程式生命週期管理 (App Lifecycle)**

### **A. 單一實例檢查 (Single Instance)**
*   **鎖定機制：** 應用程式啟動時會透過 `QLocalServer` 進行全域鎖定。
*   **重複啟動行為：** 若偵測到已有實例在執行，新啟動的程序將通知原實例將視窗「喚醒並推至前景 (Bring to Front)」，隨後新程序自動退出。
*   **除錯例外：** 若使用 `--debug` 參數啟動，將自動略過單一實例檢查，允許開發者同時執行多個實例進行通訊測試。

### **B. 退出流程**
*   **完全退出 (Fully Quit)：** 必須確保所有的 PTT Worker 執行緒已停止且 `PyPtt` 服務已正確登出後，方可關閉應用程式。
