# uPtt App Phase 2 — 三主題即時切換 (Graphite / Bone / Mono)

- Date: 2026-07-23
- Branch: `feature/app-redesign`
- Status: 設計已確認,待實作計畫
- 前置: Phase 1 已完成 (commit `3bce048`)

## 目標

在 MainWindow 已登入狀態下,透過新增的最小「偏好設定視窗」即時切換三個主題;所有**當下開著**的視窗(MainWindow、設定視窗本身、tray 選單)立即重上色作為預覽;選擇立即持久化,重啟記住;登入/掃描畫面依記住的主題於**建構時**上色。

## 已定決策(與使用者確認)

- **切換方式**:即時 live switch(非重啟)。
- **Bone/Mono 色值**:從設計畫布 `docs/design/uPtt.html` 逐 token 精確萃取(getComputedStyle,優先找 CSS custom properties)。
- **切換入口**:tray 選單新增「設定…」+ `⌘,` → 開最小 `SettingsWindow`(QDialog)。
- **預覽語意**:點選 = 直接套用並記住(**無 OK/取消**);隨時可再點回。
- **持久化**:db `settings` 表 `theme` key(沿用既有 JSON config 機制)。首次預設 `graphite`。
- **砍(YAGNI)**:Logo/Wordmark 主題變體(artboard 2-10)、首次跟隨系統偏好。

## 現況(Explore 盤點)

- `theme.py`:純資料,單一 `GRAPHITE`(15 token),無套用機制。ponytail 註解已預告「多一組同 key dict + 挑切換點」。
- `styles.py` `MAIN_STYLE`:已全 token 化 f-string;**唯一套用點** `screens.py:617`(MainWindow)。
- `theme.py` 外字面 hex 共 40 處(`screens.py` 27 / `widgets.py` 13);最髒是 `ScanSetupScreen`(`screens.py:370-521`)整段舊 GitHub-dark 色。
- **兩套錯誤紅並存**:inline `#C27474` vs token `danger` `#E08070` → 統一。
- **~106 處 inline `setStyleSheet`** 在建構時直接讀 `GRAPHITE`,無重套色 hook(即時切換的工作量大宗)。
- `LoginWindow` / `ScanSetupScreen` 走本地 `c[]` 別名 QSS,**不吃** `MAIN_STYLE`。
- 既有動態重套方法可掛靠:`_update_online_dot_style`、`_update_pin_style`、`update_unread_style`;`screens.py` header/status 重套點(1327/1335/1373-1378/1703-1714)。

## 架構(4 塊)

### 1. `theme.py` — 三 palette + 當前主題 + 重套色引擎

- `GRAPHITE` / `BONE` / `MONO` 三個**同 key** dict。
- 新增 6 語意 token:`status_online`、`status_unknown`、`status_connecting`、`msg_pending`、`archived_text`、`accent_tint_hover`。統一 `danger`(汰除 inline `#C27474`)。`status_offline` 沿用 `text_faint`。
- 模組狀態 `_current`(name);`active()` → 當前 dict;`set_theme(name)` 設 `_current`。
- **重套色註冊表** `register_restyle(widget, fn)`:立即 `fn(widget)` 套一次,並以 `weakref` 登記 `(weakref(widget), fn)`。`apply_theme(name)`:`set_theme` + 走註冊表對每個存活 widget 呼叫 `fn`;weakref 已死 / C++ 已刪(`RuntimeError`)→ 丟棄該筆;最後對已登記的 top-level(MainWindow/SettingsWindow)重設 `build_main_style()`。
- `build_main_style()` 取代 `MAIN_STYLE` 常數,讀 `active()`。
- **self-check**(`__main__` assert):切 theme 後 `active()` 改變;`register_restyle` 對已銷毀 widget 不炸。

### 2. token 化(前置 · 阻塞)

- `screens.py` / `widgets.py` 全部字面 hex 改讀 `active()[key]`。
- `ScanSetupScreen` 整段舊色汰除,改主題 token(它走本地 `c[]` QSS → 建構時讀 `active()`)。
- 完成後:`theme.py` 外不應再有語意色 / accent 字面 hex。

### 3. 即時切換佈線

- MainWindow 由 `theme.apply_theme` 驅動(引擎已含 `setStyleSheet(build_main_style())`)。
- 106 處 inline:
  - **靜態一次性**(建構定色、之後不因狀態變) → 改 `register_restyle(w, lambda w: w.setStyleSheet(...active()...))`。
  - **依狀態變**(在線點 / 泡泡 / 未讀 / 連線狀態) → 沿用既有 `_update_*_style`,內部改讀 `active()`;把這些 widget register 進去、`fn` 指向對應 update 方法,切換時被註冊表呼叫。
- `Login` / `Scan`:**不進註冊表**,只在建構讀 `active()`(切換不發生在這兩畫面)。

### 4. `SettingsWindow` + 入口 + 持久化

- 新增 `SettingsWindow`(QDialog):Phase 2 只含「外觀」區 → 三主題選擇器。設計成 Phase 3B 可擴充成 7 分頁的殼(左側 nav 或 tab 佔位)。**SettingsWindow 自身 widget 註冊進重套色表**(才會即時預覽)。
- 選擇 changed → `theme.apply_theme(name)` + db 存 `theme` key。無 OK/取消。
- 入口:tray 選單加「設定…」`QAction`(置於「顯示聊天」之後)+ `⌘,` `QShortcut`。
- 啟動:app 初始化時讀 db `theme`(無 → `graphite`),`theme.set_theme` 於**建任何 UI 前**。

## 測試 / 驗收

- 既有 159 測試不變紅。
- 新增:theme registry self-check(切換後 `active` 變、死 widget 安全跳過)、持久化讀寫 round-trip。
- 手動驗收:三主題於設定頁點選即時全面變色(MainWindow + 設定視窗 + tray);重啟記住;登入/掃描依記住主題;各畫面不跑版。

## 交付分解(供 writing-plans)

1. **色值萃取**(chrome-devtools)→ `BONE`/`MONO` dict。獨立、可先行。
2. **theme.py 引擎** + Graphite 新 token(BONE/MONO 先 placeholder,待 #1 填實)。
3. **token 化** screens/widgets/ScanSetupScreen。
4. **即時切換佈線**(106 inline)。
5. **SettingsWindow** + tray 入口 + 持久化 + 啟動讀取。

依賴:#3、#4、#5 依賴 #2;BONE/MONO 值依賴 #1。
