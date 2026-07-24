# uPtt App 2026 改版 — 待辦

**設計來源**：`docs/design/uPtt.html`（App 設計畫布「視覺設計探索」，~48 artboard，三主題 Graphite/Bone/Mono）。
渲染方式：15MB 打包 Vue HTML，需用 chrome-devtools 開 `file://…/docs/design/uPtt.html` 逐 artboard 截圖。
**強調色**：sage green `#8FBFA0`（延續舊 `#A0C4B4` 同色系）——**不是** coral；coral `#D97757` 是**網站** spec（`specs/2026-07-21-website-redesign-design.md`）的，別搞混。

**Phase 1（視覺一致層，單一 Graphite）已完成** → commit `3bce048` @ `feature/app-redesign`：
登入雙欄、訊息/聯絡人右鍵選單、`src/uPtt/ui/theme.py` 色票 token 地基、主介面全補（綠泡泡/未讀徽章/水球 pill/分組標頭/日期線/狀態列/字數送出/搜尋框）。

---

## Phase 2 — 三主題切換 (Graphite / Bone / Mono) ✅ 已完成

> **已完成** @ `feature/app-redesign`（2026-07-24）：三主題引擎（`theme.py` active/apply_theme/register_restyle 重套色註冊表）+ 全 token 化（硬寫色歸零）+ 即時切換（聊天/登入/掃描/**設定視窗自身**都跟著變）+ 最小偏好設定視窗。188 測試綠、QSS 解析警告修掉。
>
> **範圍調整（施工中發現，與原計畫不同）**：
> - **設定視窗提前到 Phase 2 建**（原列 Phase 3B）——當主題切換器的永久家，免做丟棄 UI。入口：tray「設定…」+ ⌘,。目前含「外觀/主題 + 桌面通知 + 3 輪詢間隔」，Phase 3B 再往上長其餘分頁。
> - **從 beta #25（分支 `fix/audit-findings`，已上 beta 未進本線）撈回舊設定頁的 5 設定**：主題 / 桌面通知 / 信件·水球·在線輪詢間隔（接 worker 真生效 + db 持久化）。移植 `SettingsWindow`/`ToggleSwitch`/`ThemeCard` + `config.clamp_interval`/`get_setting_interval`，改接本線 theme 引擎。
> - Bone/Mono 色值取自畫布 `window.THEMES` ground-truth，並以 beta 同源 palette 校對（修正 status_connecting 用權威 warn 值）。
> - Logo/Wordmark 主題變體、首次跟隨系統偏好 → 依 YAGNI 未做。
>
> **⚠️ 待辦（merge 準備，next）**：本線分岔太早，缺 beta #25 的**非 UI 後端 audit 修正**，需移植 —— 🔴密碼遮罩（防 `str(e)` 把明文密碼寫進 log）、🔴mail anti-forgery（僅成對分隔線才准自動刪信，防被誘刪他人來信）、reconnect storm/退避（retry 3→5、LoginTooOften 60s）/通知遺失修復。清單：`scratchpad/beta-backend-fixes-to-port.md`（會過期，必要時重跑盤點）。
> **merge 策略（已與使用者確認）**：2026 重設計當基準；併 beta 時 UI 檔 take-ours（刪 beta 的 main_window/login_window/scan_setup/dialogs 拆檔）、port beta 非 UI 後端修正過來。
>
> ↓ 以下原始計畫留存作對照（勾選狀態未逐一更新，以上方摘要為準）。

> 目標：執行時可在深色 Graphite（日常）/ 淺色 Bone（收信）/ 純黑白 Mono 間切換，重啟記住。
> 對應 artboard：各畫面的 Bone/Mono 版（登入 12-13、主介面 15-16、聯絡人選單 18-19）＋ Logo/Wordmark 變體（2-10）。

**前置（阻塞，先做）**
- [ ] 把殘留的硬寫色全收成 token。Phase 1 只把 `styles.py`／部分 inline 走了 `theme.GRAPHITE`，但仍有多處 accent 用**字面 `#8FBFA0`** 而非引用 token（未來換主題不會連動），且 screens.py 尚有語意色（在線綠/錯誤紅/水球藍等）與 ScanSetupScreen 舊色未 token 化。→ 逐檔 grep 硬寫 hex，全部改引用 `theme` token。這是三主題能運作的根本前提。

**實作**
- [ ] `theme.py`：新增 `BONE`、`MONO` 兩個 palette dict（目前只有 `GRAPHITE`）。從畫布 Bone/Mono artboard 取實際色值（getComputedStyle/採樣）。
- [ ] 套色機制：一個 `current_theme` 狀態 + `apply_theme()`——重建 `MAIN_STYLE` 並通知所有 inline-styled widget 重套色。**難點**：178 處 inline 色若沒全 token 化，切換不會全面生效（見前置）。
- [ ] 切換 UI：主題選擇入口（偏好設定內、或標題列切換鈕）。選擇持久化（QSettings 或 db settings）。首次跟隨系統偏好。
- [ ] Logo/Wordmark：若要跟主題變體，需對應 asset 或字元 logo（畫布 artboard 2-10）。

**驗收**
- [ ] 三主題間切換即時生效；重啟記住選擇。
- [ ] 每個既有畫面在三主題下都正確變色、不跑版（登入/主介面/選單/mail 卡/水球/泡泡）。
- [ ] 既有 159 測試不變紅。

---

## Phase 3 — 新功能（需後端；逐項先確認真需求與 PTT 合理性）

> 提醒：設計畫布是**探索稿**，非施工令。下列每項施工前先確認是否真要做、是否適配 PTT-mail 傳輸。

### 3A 右鍵選單 action（Phase 1 已延後，需後端）

> **核心 4 項已完成 ✅** @ `feature/app-redesign`（2026-07-24，commits `083b1cd..6c2168d`，10 個 commit，232→239 測試綠，最終 opus whole-branch review = Ready to merge）。spec `specs/2026-07-24-app-phase3a-menu-actions-design.md`、計畫 `specs/2026-07-24-app-phase3a-menu-actions-plan.md`。流程：brainstorm→spec→plan→subagent-driven 逐 task（developer 實作 + fresh verifier 兩段驗收）+ opus 最終審。
> 附帶結構調整：`render_svg`/`ASSETS_DIR` 搬到 `theme.py` 解 widgets↔screens 循環 import（screens 保留 re-export）。
> ~~延後 5 個 Minor~~ **✅ 已全數處理** @ `feature/app-phase3a-minors`（2026-07-24，281 測試綠）：
> 1. `[re:@]` 剝除重複 → db.py 抽 `_strip_reply_prefix`，3 處併 1
> 2. export 自訊息 sender → 改用 `db.get_account_display_id`（權威正確大小寫）
> 3. `screens.py` import 風格混用 → 同套件一律相對、跨套件絕對（相對亦維持 render_svg re-export 同一物件）
> 4. `m.get('id',-1)` → `m.get('id')`（None；讓無 id 泡泡正確隱藏刪除項）
> 5. 刪最新訊息聯絡人列未即時重排 → 新增 `_reposition_contact_by_time`，刪後依 DB 時序即時下移

- [x] 訊息 · **刪除（僅本機）**（32）— 新增 `db.delete_message` + 確認框；無 id 的泡泡不出現刪除項
- [x] 聯絡人 · **重新命名…**（17）— 新增本機 `custom_name` 欄，顯示序 `custom_name > PTT nickname > display_id`，PTT 查詢不覆寫；空字串還原
- [x] 聯絡人 · **靜音通知**（17）— `is_muted` 欄 + 選單 toggle + 通知 gate 擋靜音 + 聯絡人列靜音 icon（三主題連動）
- [x] 聯絡人 · **匯出對話紀錄…**（17）— `get_messages(limit=None)` 全撈 → 純文字 `.txt`，`decode_reply` 剝除回覆包裝
- [ ] 訊息 · **轉寄給…**（artboard 32）— 需選對象 UI + resend 流程 · **本輪砍**（1-1 PTT-mail 需求薄弱）
- [ ] 訊息 · **釘選訊息**（32）— 需訊息級 pin 的新 DB 欄位（現只有 session 級釘選）· **本輪砍**（需求低）
- [ ] 聯絡人 · **標記為未讀**（17）— 需可手動設 unread（現 `unread_count` 只能歸零）· **本輪延後**（可選）
- [ ] 選單項 **destructive 紅字**（封鎖/隱藏/刪除）— Qt `QMenu::item` 屬性選取器無效，需改 `QWidgetAction` 自訂上色（見 `styles.py` 選單註解）· **本輪延後**

### 3B 新畫面（對應 artboard）

> **進度 @ `feature/app-phase3b`（2026-07-24）**：⌘K 搜尋、⌘N 新對話 modal、
> 個人資料面板、偏好設定分頁化 四項已完成（各含測試，全套件 270 綠）。
> 送水球 overlay **不做**（使用者確認：只需接收水球到聊天視窗，已具備）。
> 剩 compose、onboarding 兩項。

- [x] **⌘K 搜尋/指令面板** — artboard 27。接 `db.search_messages`（beta 併入）；聯絡人＋訊息，↑↓/↵/esc。`ui/search_palette.py`
- [x] **新對話 modal（⌘N）** — artboard 23。即時格式查驗（PTT ID 規則＋擋自我）；真存在性沿用 add→archived 流程。`ui/new_chat_modal.py`
- [x] **個人資料面板** — artboard 31。本人 `get_user`；QueryWorker.refresh_self_info（不落 session）；tray「個人資料…」+ ⌘I。`ui/profile_panel.py`
- [x] **偏好設定視窗** 分頁化 — 外觀/通知/連線·同步/快捷鍵/關於 五頁（承接 Phase 2 控制項）。帳號/資料·儲存/進階三頁待新 config 欄位。artboard 33-38, 45
- [ ] ~~**寫站內信 compose**~~（artboard 29）— **不做**：uPtt 格式對收件人本就是明文，非 uPtt 用戶收到照樣可讀，無需另設純信路徑。（曾實作 `2561080`，已 revert `3e6ad5d`）
- [x] **首次連線 onboarding** — artboard 20-22。ScanSetupScreen 內建「歡迎→掃描設定」兩步 wizard（首登入才顯示歡迎；reset/重掃不受影響，對外介面不變）。「完成」步沿用既有 scan_complete→聊天畫面切換，未另設畫面
- [ ] ~~**送水球 overlay**~~（artboard 30）— **不做**：只需接收水球（已具備），不需主動送。

### 3C 次要/邊角畫面（可選，優先度低）
- [ ] 連線狀態 banner（重連中/失敗）— artboard 24-25（部分已有）
- [ ] 空狀態（全新使用者）— artboard 26
- [ ] 送訊息失敗 + 重試 — artboard 28
- [ ] 系統通知 / App toast — artboard 39-40（現有 tray）
- [ ] 登入錯誤三分態（密碼錯/踢線/維護）— artboard 41-43 · **受限**：PyPtt 無法可靠區分維護/踢線（見 memory `project_pyptt_login_errors`），只能做可分辨的
- [ ] 初次同步 loading/skeleton — artboard 44

### 不做
- ~~檢舉訊息~~（artboard 32）— PTT 站內信無檢舉概念，砍。

---

_設計截圖曾抽到 session 暫存 `scratchpad/design_shots/`（會清掉）；需要時用上方渲染方式對 `docs/design/uPtt.html` 重截，或依 artboard 編號查畫布。_
