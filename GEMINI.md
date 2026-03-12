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
2. **驗證指令：** 請確保執行 \[請在此填入您的單元測試指令，如: npm test / pytest\] 並獲得 PASS 結果。  
3. **環境清潔：** 測試前確保依賴已更新，若有必要請執行安裝指令（如 npm install）。

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
* **衝突處理：** \* Agent 若在自動合併時遇到代碼衝突 (Conflicts)，**禁止**擅自決定保留哪一方。  
  * **必須** 停止 Git 操作，並列出衝突的文件清單，回報：「偵測到合併衝突，請人工處理」。

## **5\. Agent 任務前自我檢查清單 (Pre-flight Checklist)**

* \[ \] **環境同步：** 我是否已經執行了 git pull 確保是基於最新代碼？  
* \[ \] **分支確認：** 我目前所在的分支是否正確？  
* \[ \] **測試執行：** 我是否已執行 Unit Test 且獲得 PASS？  
* \[ \] **版本更新：** 若是 Release/Hotfix，我是否已正確處理版本號？  
* \[ \] **規範檢查：** Commit Message 是否符合格式？

**指令啟動範例：**

「請依照 git\_flow\_guide.md 的規範，處理緊急修復任務：修正登入 API 的 500 錯誤。修復後請回報測試結果並執行雙向合併。」
