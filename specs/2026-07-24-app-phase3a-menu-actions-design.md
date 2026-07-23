# uPtt App Phase 3A — 右鍵選單 action(核心 4 項)

- Date: 2026-07-24
- Branch: `feature/app-redesign`
- Status: 設計已確認,待實作計畫
- 前置: Phase 1 / Phase 2 已完成;beta #25 後端 audit 修正已移植(commit `63d6a71`)
- 來源: `to-do.md` §3A(artboard 17/32);設計畫布為探索稿,已逐項 triage

## 範圍(與使用者確認)

本輪只做 3A 的**核心 4 項**,全部本機、低成本、不改 PTT 傳輸語意:

1. **刪除(僅本機)** — 訊息右鍵選單
2. **重新命名聯絡人**(本機 alias) — 聯絡人右鍵選單
3. **靜音通知**(含聯絡人列 icon) — 聯絡人右鍵選單
4. **匯出對話紀錄**(純文字) — 聯絡人右鍵選單

**本輪砍(triage 結論)**:
- 轉寄給…(§3A):1-1 PTT-mail 需求薄弱、需新聯絡人選擇 UI → 延後。
- 釘選訊息(§3A):session 級 pin 已有;message 級需新欄位 + 釘選面板 → 延後。
- 標記為未讀(§3A):可選,本輪不做。
- 選單 destructive 紅字(§3A #8):需 QWidgetAction 自訂上色,純外觀 → 延後(`styles.py:250` 註解已記)。

## 已定決策(與使用者確認)

- 刪除:**要確認對話**(不可逆,防誤刪)。
- 重新命名:輸入**空字串 = 清除本機 alias、還原 PTT 暱稱**。
- 靜音:**做**聯絡人列常駐 icon(對應 artboard 17),非只選單 toggle。
- 匯出:格式**純文字 `.txt`**(砍 JSON/HTML)。

## 現況(Explore 盤點,附檔案:行號)

- **單則刪除**:無;只有 `delete_session`(`db.py:253`)。messages PK `id INTEGER PRIMARY KEY AUTOINCREMENT`(`db.py:66`)可定位單則。
- **暱稱**:落 `sessions.nickname`(`db.py:53`),來源 `get_user_info` → `upsert_session(nickname=...)`(`worker.py:895-898`);**`upsert_session` 會用 PTT 值覆寫非空 nickname**(`db.py:171`)→ 直接寫 nickname 會被下次查詢蓋掉,故需獨立 alias 欄位。
- **未讀**:`sessions.unread_count`(`db.py:56`),`mark_as_read` 只能歸零(`db.py:414`)。
- **通知**:`screens.py:2063` `tray_icon.showMessage(...)`;送前判斷在 `screens.py:2060-2061`(`not isActiveWindow and not is_me and NOTIFY_ENABLED`)→ mute 判斷掛此處。
- **撈訊息**:`get_messages(account_id, session_id, limit=50)`(`db.py:397`,`SELECT * FROM messages WHERE account_id=? AND session_id=?`)→ 匯出需去/放大 limit。
- **選單建構點**:訊息 `widgets.py:174` `_build_context_menu()`(QMenu:複製文字、引用回覆);聯絡人 `screens.py:2276` `_build_contact_context_menu(ptt_id, is_pinned)`(QMenu:釘選/取消、封鎖、隱藏、刪除),觸發 `show_contact_context_menu`(`screens.py:2308`)。兩處皆有 ponytail 註解列 Phase 3 待接項(`widgets.py:185-188`、`screens.py:2284-2286`)。
- **migration 機制**:`db.py:94-109` 有 `migrations` list(`ALTER TABLE ... ADD COLUMN` + try/except 忽略 duplicate column)→ 加新欄位只需 append。
- **表欄位**:
  - `sessions`:account_id, id, display_id, nickname, last_message_text, last_message_time, unread_count, is_visible, is_pinned, pin_order, is_archived
  - `messages`:id, account_id, session_id, sender_id, receiver_id, content, timestamp, is_read, is_me, send_status, mail_type, subject

## 架構(無新架構 / 無新依賴,全沿用既有 pattern)

### DB 遷移(`db.py:100` 後 append)

```
ALTER TABLE sessions ADD COLUMN custom_name TEXT DEFAULT ''
ALTER TABLE sessions ADD COLUMN is_muted BOOLEAN DEFAULT 0
```

### ① 刪除(僅本機)

- **db** `delete_message(account_id, message_id)`:`DELETE FROM messages WHERE account_id=? AND id=?`。刪後若該則為 session 最後一則 → 重算 `last_message_text/last_message_time`(撈次新一則;無訊息則清空為預設)。回傳受影響 session_id 供 UI 刷新。
- **UI**(`widgets.py:174` 訊息選單):加「刪除(僅本機)」QAction → 確認對話(`QMessageBox`)→ 呼叫 db → emit signal 讓 MainWindow 移除該泡泡並刷新該聯絡人列 preview。
- **定位鍵**:優先用 message `id`。**實作待確認**:ChatBubble 是否已帶 `id`;若無,兩選一——(a) 建泡泡時把 `id` 存進 widget,或 (b) 用既有 UNIQUE 鍵(`sender_id+content+timestamp`)刪。兩路皆可,留給實作計畫定,不阻塞設計。

### ② 重新命名聯絡人(本機 alias)

- **db** `set_custom_name(account_id, session_id, name)`:寫 `sessions.custom_name`(空字串 = 清除)。**`upsert_session` 不得寫 `custom_name`**(維持 PTT 只碰 `nickname`)。
- **顯示優先序**:`custom_name`(非空) > `nickname`(PTT) > `display_id`。集中在聯絡人列 / 聊天標題的顯示名組裝點改讀此序(找出並統一該組裝邏輯,避免各處各判)。
- **UI**(聯絡人選單):加「重新命名…」→ `QInputDialog` 預填目前顯示名 → 寫 db → 刷新聯絡人列 + 若正開著該對話則刷新標題。

### ③ 靜音通知(含聯絡人列 icon)

- **db** `set_muted(account_id, session_id, muted)` + 讀取(`is_muted`,或併入既有 session 讀取)。
- **通知 gate**(`screens.py:2060`):條件加 `and not <session is_muted>`。
- **UI 選單**(聯絡人選單):toggle「靜音通知」/「取消靜音」(依現狀顯示文字,同 pin toggle 寫法)。
- **UI icon**(ContactItem 列):靜音時於聯絡人列顯示常駐靜音 icon(trailing 端,與既有在線點 / 暱稱固定高度 / `setSpacing(2)` 佈局相容);mute 變更時重繪;**經 `render_svg` + 讀 `theme.active()` 上色**,三主題皆正確(遵 CLAUDE.md UI 標準)。icon 來源用最簡合適者(SVG 或 muted-bell glyph),與該列既有 icon 風格一致。

### ④ 匯出對話紀錄(純文字)

- **db**:`get_messages` 的 `limit=50` 改為 `limit=None` 時不套 `LIMIT`(全撈);既有呼叫維持 50 不變。
- **UI**(聯絡人選單):加「匯出對話紀錄…」→ `QFileDialog.getSaveFileName`,預設檔名 `對話_{顯示名}_{YYYYMMDD}.txt` → 全撈該 session 訊息 → 寫純文字(每行 `[時間] 傳送者: 內容`,多行內容原樣保留)。純 DB→檔,不碰 PTT。

## 測試 / 驗收

- 既有 188 測試不變紅。
- **db 單元**:
  - `delete_message`:刪除生效;刪最後一則後 `last_message_*` 重算為次新(或空)。
  - `set_custom_name`:round-trip;寫後呼叫 `upsert_session(nickname=...)` **不覆寫** `custom_name`;空字串清除。
  - `set_muted`:round-trip。
  - `get_messages(limit=None)`:回傳全部(>50 筆時不截斷);`limit=50` 行為不變。
- **顯示優先序**單元:custom_name > nickname > display_id。
- 沿用既有 pytest-qt 模式(qtbot 訊號斷言)。
- **手動驗收**:訊息刪除(確認框、泡泡消失、preview 更新);改名(即時反映、空字串還原、下次線上查詢不被蓋回);靜音(選單 toggle、被靜音者無桌面通知、列上 icon 三主題正確);匯出(檔案內容完整、含時間/傳送者)。

## 交付分解(供 writing-plans)

1. **DB 層**:migration 兩欄 + `delete_message`(含 last_message 重算) + `set_custom_name` + `set_muted` + `get_messages` limit 可選 + `upsert_session` 不碰 custom_name。含單元測試。獨立、可先行。
2. **顯示優先序**:統一聯絡人列 / 聊天標題顯示名為 `custom_name > nickname > display_id`。依賴 #1 欄位。
3. **訊息選單 · 刪除**:`widgets.py` 選單項 + 確認框 + 定位鍵 + emit → MainWindow 移除泡泡 / 刷新 preview。依賴 #1。
4. **聯絡人選單 · 改名 / 靜音 toggle / 匯出**:`screens.py` 三個選單項接 db + 對應刷新;通知 gate 加 mute 判斷。依賴 #1、#2。
5. **靜音 icon**:ContactItem 列 icon + 三主題上色 + mute 變更重繪。依賴 #1、#4。

依賴:#2#3#4 依賴 #1;#5 依賴 #4。
