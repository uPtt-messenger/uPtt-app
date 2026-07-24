# Phase 3A 選單 action 實作計畫

**Goal**: 在 `feature/app-redesign` 分支上，用 TDD 落地 Phase 3A 核心 4 項本機選單功能——訊息刪除、聯絡人改名、靜音通知（含列表 icon）、匯出對話紀錄——同時保持既有 188 測試全綠。

**Architecture**: 沿用現有三層結構（`db.py` SQLite CRUD → `worker.py`/`screens.py` 業務邏輯 → `widgets.py` Qt 元件），不引入新模組、新執行緒或新協定。四項功能都是「本機資料 + 本機 UI」，不改變 PTT mail 傳輸語意。唯一的結構性調整：把 `render_svg`/`ASSETS_DIR` 從 `screens.py` 搬到 `theme.py`（單一色源模組），讓 `widgets.py` 能在不造成循環 import 的前提下畫出靜音 icon 並跟著三主題上色。

**Tech Stack**: Python 3.12、PySide6 (Qt6)、SQLite3（標準庫 `sqlite3`）、pytest + pytest-qt。無新依賴。

## Global Constraints

- 既有 **188 測試不得變紅**；新增測試一律要先確認 FAIL 再讓它 PASS（TDD）。
- 執行測試一律加 `QT_QPA_PLATFORM=offscreen` 前綴（headless 環境必要）。
- 不新增任何第三方依賴；`requirements.txt` / `requirements-dev.txt` 不變。
- DB schema 變更一律走 `db.py:94-101` 既有的 `migrations` list（`ALTER TABLE ... ADD COLUMN` + try/except 忽略 duplicate column），不得手動改 `CREATE TABLE` 語句本身。
- 所有新 SQL 方法遵循既有慣用寫法：`with self._get_connection() as conn:` + `try/except sqlite3.Error as e: logger.error(...)`；`account_id`/`session_id` 一律 `.lower()` 正規化後查詢。
- PTT ID 內部鍵一律小寫；顯示层保留原始大小寫（沿用專案既有規則，本計畫不變更此行為）。
- 選單新增項一律用 `QAction`，不做 destructive 紅字上色（`styles.py:250` 已註記此限制，本輪不解）。
- 新圖示一律經 `render_svg`（畫出 pixmap）+ `theme.active()`（取色）+ `theme.register_restyle`（跟隨主題切換）三件套上色，不得寫死 hex。
- Conventional Commits：`feat:`/`test:`/`refactor:`；每個 Task 結尾各自 commit，訊息不加 Co-Authored/Session trailer。
- 範圍固定為刪除／改名／靜音／匯出 4 項，不擴充其他 Phase 3A 項目（轉寄、訊息級釘選、標記未讀、選單紅字皆不在本輪）。

---

## 前置調查結論（供理解, 不是待辦）

- `ChatBubble`（`widgets.py:41`）建構子目前**不帶** message id，也不存原始 `sender_id`/完整 timestamp（只存格式化過的 `time_str`）。因此「用既有 UNIQUE 鍵定位」不可行（缺原始欄位可比對）。本計畫選擇**補存 id**：讓 `db.save_message` 回傳新插入列的 row id（而非純 bool），並把 id 沿 `worker.py` → `screens.py` 的 `chat_histories` 一路帶到 `ChatBubble(message_id=...)`。`get_messages()` 撈出的歷史訊息與 `save_pending_message()`（自送訊息）**已經**在 `screens.py:1754`/`1961` 把 `msg_id` 放進訊息 dict；唯一缺口是即時收到訊息的路徑（`worker.py` 的 `save_message` 呼叫只回傳 bool），本計畫在 Task 3 補上。
- `render_svg`/`ASSETS_DIR` 目前定義在 `screens.py:51-83`。`widgets.py` 的 `ContactItem` 需要畫靜音 icon，但 `screens.py` 已經 `from uPtt.ui.widgets import ChatBubble, ContactItem, ...`——若 `widgets.py` 反向 import `screens.py` 會造成循環 import。兩個檔案都已 import `uPtt.ui.theme`，故 Task 5 把 `render_svg`/`ASSETS_DIR` 搬到 `theme.py`，`screens.py` 改成從 `theme.py` 匯入並保留同名符號（既有測試 `test_render_svg_exists` 的 `from src.uPtt.ui.screens import render_svg` 因此不受影響）。
- `ContactItem` 目前沒有任何「訊息預覽文字」欄位（只有 `id_label`／`nickname_label`／`time_label`／`unread_label`），故「刪除後刷新聯絡人列 preview」在本計畫中落實為刷新 `time_label`（`last_msg_time`），不是發明一個不存在的預覽欄位。

---

## Task 1: DB 層——migration + 4 個新方法 + `get_messages` 可選 limit

### Files
- Modify: `src/uPtt/db.py:94-101`（migrations list，加兩行）
- Modify: `src/uPtt/db.py:198-209`（`is_session_archived` 之後插入 `set_custom_name`/`set_muted`/`is_session_muted`）
- Modify: `src/uPtt/db.py:253-266`（`delete_session` 之後插入 `delete_message`）
- Modify: `src/uPtt/db.py:269-319`（`save_message` 回傳型別 `bool` → `Optional[int]`）
- Modify: `src/uPtt/db.py:397-412`（`get_messages` 的 `limit` 改為 `Optional[int]`）
- Test: `tests/test_db.py`（修改既有 2 個斷言 + 新增 7 個測試）

### Interfaces
**Produces**（後續 Task 依賴的簽名，务必逐字一致）：
- `DatabaseManager.delete_message(account_id: str, message_id: int) -> Optional[str]` — 回傳受影響的 session_id（小寫），找不到該訊息回傳 `None`。
- `DatabaseManager.set_custom_name(account_id: str, session_id: str, name: str) -> None` — 空字串清除。
- `DatabaseManager.set_muted(account_id: str, session_id: str, muted: bool) -> None`
- `DatabaseManager.is_session_muted(account_id: str, session_id: str) -> bool`
- `DatabaseManager.get_messages(account_id: str, session_id: str, limit: Optional[int] = 50) -> List[Dict[str, Any]]` — `limit=None` 時回傳全部（不加 `LIMIT`），行為與呼叫端相容（既有呼叫都用預設值 50，不受影響）。
- `DatabaseManager.save_message(...) -> Optional[int]`——**回傳型別變更**：成功回傳新插入列的 row id（int，恆為 truthy），UNIQUE 衝突/失敗回傳 `None`。呼叫端既有的 `if is_new:` 判斷因 truthy 語意不變而保持相容。
- `sessions` 表新增欄位：`custom_name TEXT DEFAULT ''`、`is_muted BOOLEAN DEFAULT 0`（`get_all_sessions()` 的 `SELECT *` 自動帶出，UI 端可直接讀 `s['custom_name']`/`s['is_muted']`）。

### bite-sized steps

- [ ] 寫失敗測試：在 `tests/test_db.py` 尾端加入以下測試（此時 `delete_message`/`set_custom_name`/`set_muted`/`is_session_muted` 尚不存在，`save_message` 仍回傳 bool，`get_messages(limit=None)` 會把 `None` 當成無效 LIMIT 值噴 `sqlite3.OperationalError`）：

```python
def test_delete_message_removes_row_and_recomputes_last_message(db_manager):
    account_id = "alice"
    session_id = "bob"
    db_manager.upsert_account(account_id, account_id)
    db_manager.upsert_session(account_id, session_id)

    t1 = datetime(2026, 1, 1, 12, 0, 0)
    t2 = datetime(2026, 1, 1, 12, 1, 0)
    db_manager.save_message(account_id, session_id, session_id, account_id, "first", t1, False)
    second_id = db_manager.save_message(account_id, session_id, session_id, account_id, "second", t2, False)

    sessions = db_manager.get_all_sessions(account_id)
    assert sessions[0]['last_message_text'] == "second"

    affected = db_manager.delete_message(account_id, second_id)
    assert affected == session_id

    messages = db_manager.get_messages(account_id, session_id)
    assert len(messages) == 1
    assert messages[0]['content'] == "first"

    sessions = db_manager.get_all_sessions(account_id)
    assert sessions[0]['last_message_text'] == "first"


def test_delete_message_last_one_clears_session_summary(db_manager):
    account_id = "alice"
    session_id = "bob"
    db_manager.upsert_account(account_id, account_id)
    db_manager.upsert_session(account_id, session_id)
    only_id = db_manager.save_message(account_id, session_id, session_id, account_id, "only", datetime.now(), False)

    affected = db_manager.delete_message(account_id, only_id)
    assert affected == session_id

    sessions = db_manager.get_all_sessions(account_id)
    assert sessions[0]['last_message_text'] == ''
    assert sessions[0]['last_message_time'] is None


def test_delete_message_unknown_id_returns_none(db_manager):
    account_id = "alice"
    db_manager.upsert_account(account_id, account_id)
    assert db_manager.delete_message(account_id, 999999) is None


def test_set_custom_name_round_trip_and_clear(db_manager):
    account_id = "alice"
    session_id = "bob"
    db_manager.upsert_account(account_id, account_id)
    db_manager.upsert_session(account_id, session_id)

    db_manager.set_custom_name(account_id, session_id, "老王")
    sessions = db_manager.get_all_sessions(account_id)
    assert sessions[0]['custom_name'] == "老王"

    db_manager.set_custom_name(account_id, session_id, "")
    sessions = db_manager.get_all_sessions(account_id)
    assert sessions[0]['custom_name'] == ""


def test_upsert_session_does_not_overwrite_custom_name(db_manager):
    account_id = "alice"
    session_id = "bob"
    db_manager.upsert_account(account_id, account_id)
    db_manager.upsert_session(account_id, session_id, nickname="OldNick")
    db_manager.set_custom_name(account_id, session_id, "老王")

    # 模擬下次 get_user_info 查詢再次 upsert（PTT 暱稱更新流程）
    db_manager.upsert_session(account_id, session_id, nickname="NewNick")

    sessions = db_manager.get_all_sessions(account_id)
    assert sessions[0]['custom_name'] == "老王"
    assert sessions[0]['nickname'] == "NewNick"


def test_set_muted_round_trip(db_manager):
    account_id = "alice"
    session_id = "bob"
    db_manager.upsert_account(account_id, account_id)
    db_manager.upsert_session(account_id, session_id)

    assert db_manager.is_session_muted(account_id, session_id) is False
    db_manager.set_muted(account_id, session_id, True)
    assert db_manager.is_session_muted(account_id, session_id) is True
    db_manager.set_muted(account_id, session_id, False)
    assert db_manager.is_session_muted(account_id, session_id) is False


def test_get_messages_limit_none_returns_all(db_manager):
    account_id = "alice"
    session_id = "bob"
    db_manager.upsert_account(account_id, account_id)
    db_manager.upsert_session(account_id, session_id)
    for i in range(60):
        db_manager.save_message(
            account_id, session_id, session_id, account_id,
            f"msg{i}", datetime(2025, 1, 1, 12, 0, i), False
        )

    msgs = db_manager.get_messages(account_id, session_id, limit=None)
    assert len(msgs) == 60
    assert msgs[0]['content'] == "msg0"
    assert msgs[-1]['content'] == "msg59"

    msgs_default = db_manager.get_messages(account_id, session_id)
    assert len(msgs_default) == 50
```

  同時修改 `tests/test_db.py:92-93` 與 `tests/test_db.py:101-102`（`test_save_and_get_messages` 內既有的兩個斷言，配合 `save_message` 新回傳型別）：

```python
    # 原本：
    # success = db_manager.save_message(account_id, session_id, account_id, session_id, "Hello", now, True)
    # assert success is True
    msg_id = db_manager.save_message(account_id, session_id, account_id, session_id, "Hello", now, True)
    assert isinstance(msg_id, int) and msg_id > 0
```

```python
    # 原本：
    # success = db_manager.save_message(account_id, session_id, account_id, session_id, "Hello", now, True)
    # assert success is False
    dup_id = db_manager.save_message(account_id, session_id, account_id, session_id, "Hello", now, True)
    assert dup_id is None
```

- [ ] 跑測試確認 FAIL：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_db.py -v
```
  預期：`AttributeError: 'DatabaseManager' object has no attribute 'delete_message'`（及 `set_custom_name`/`set_muted`/`is_session_muted`），加上 `test_save_and_get_messages` 的 `assert isinstance(msg_id, int)` 因 `msg_id` 仍是 `True` 而失敗（`isinstance(True, int)` 其實為 True——但 `msg_id > 0` 對 bool `True` 也成立，故此斷言在改動前**可能誤過**；用 `test_get_messages_limit_none_returns_all` 的 `sqlite3.OperationalError: near "?": syntax error`（LIMIT 綁定 None）與新方法的 `AttributeError` 作為本步驟主要的失敗證據）。

- [ ] 最小實作，`db.py:94-101` 的 migrations list 加兩行（緊接在既有 6 行之後）：

```python
                migrations = [
                    "ALTER TABLE sessions ADD COLUMN is_pinned BOOLEAN DEFAULT 0",
                    "ALTER TABLE sessions ADD COLUMN pin_order INTEGER DEFAULT 0",
                    "ALTER TABLE sessions ADD COLUMN is_archived BOOLEAN DEFAULT 0",
                    "ALTER TABLE messages ADD COLUMN mail_type TEXT DEFAULT 'uptt'",
                    "ALTER TABLE messages ADD COLUMN subject TEXT DEFAULT ''",
                    "ALTER TABLE messages ADD COLUMN send_status TEXT DEFAULT 'sent'",
                    "ALTER TABLE sessions ADD COLUMN custom_name TEXT DEFAULT ''",
                    "ALTER TABLE sessions ADD COLUMN is_muted BOOLEAN DEFAULT 0",
                ]
```

  在 `db.py:209`（`is_session_archived` 方法結尾）之後、`get_all_sessions` 之前插入：

```python
    def set_custom_name(self, account_id: str, session_id: str, name: str):
        """設定會話的本機自訂顯示名稱（空字串 = 清除，還原為讀 PTT 暱稱）。"""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE sessions SET custom_name = ? WHERE account_id = ? AND id = ?",
                    (name, account_id.lower(), session_id.lower())
                )
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"更新本機別名失敗：{e}")

    def set_muted(self, account_id: str, session_id: str, muted: bool):
        """設定會話的靜音通知狀態。"""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE sessions SET is_muted = ? WHERE account_id = ? AND id = ?",
                    (1 if muted else 0, account_id.lower(), session_id.lower())
                )
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"更新靜音狀態失敗：{e}")

    def is_session_muted(self, account_id: str, session_id: str) -> bool:
        """檢查會話是否已被靜音。"""
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT is_muted FROM sessions WHERE account_id = ? AND id = ?",
                    (account_id.lower(), session_id.lower())
                ).fetchone()
                return bool(row and row['is_muted'])
        except sqlite3.Error as e:
            logger.error(f"查詢靜音狀態失敗：{e}")
            return False
```

  在 `db.py:265`（`delete_session` 方法結尾）之後、`# --- 訊息相關 ---` 註解之前插入：

```python
    def delete_message(self, account_id: str, message_id: int) -> Optional[str]:
        """刪除單則本機訊息（僅本機，不影響 PTT 上的信件）。

        若該則為所屬 session 目前最新的一則，重算 session 的
        last_message_text/last_message_time 為次新一則（無剩餘訊息則清空為預設）。
        回傳受影響的 session_id（小寫）；找不到該訊息時回傳 None。
        """
        acc_id_lower = account_id.lower()
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT session_id FROM messages WHERE account_id = ? AND id = ?",
                    (acc_id_lower, message_id)
                ).fetchone()
                if not row:
                    return None
                session_id = row['session_id']

                conn.execute(
                    "DELETE FROM messages WHERE account_id = ? AND id = ?",
                    (acc_id_lower, message_id)
                )

                next_msg = conn.execute("""
                    SELECT content, timestamp FROM messages
                    WHERE account_id = ? AND session_id = ?
                    ORDER BY timestamp DESC, id DESC LIMIT 1
                """, (acc_id_lower, session_id)).fetchone()

                summary = next_msg['content'] if next_msg else ''
                if summary.startswith('[re:@') and ']\n' in summary:
                    summary = summary[summary.index(']\n') + 2:]
                last_time = next_msg['timestamp'] if next_msg else None

                conn.execute("""
                    UPDATE sessions SET last_message_text = ?, last_message_time = ?
                    WHERE account_id = ? AND id = ?
                """, (summary, last_time, acc_id_lower, session_id))

                conn.commit()
                return session_id
        except sqlite3.Error as e:
            logger.error(f"刪除訊息失敗 (id={message_id})：{e}")
            return None
```

  修改 `save_message`（`db.py:269-319`）的簽名與回傳：型別註記從 `-> bool` 改為 `-> Optional[int]`；`if cursor.rowcount == 0: return False` 改為 `return None`；方法最後的 `return True` 改為 `return cursor.lastrowid`。

  修改 `get_messages`（`db.py:397-412`）：

```python
    def get_messages(self, account_id: str, session_id: str, limit: Optional[int] = 50) -> List[Dict[str, Any]]:
        """取得特定帳號與特定對象的歷史訊息。limit=None 時回傳全部（不截斷）。"""
        try:
            with self._get_connection() as conn:
                if limit is None:
                    rows = conn.execute("""
                        SELECT * FROM messages
                        WHERE account_id = ? AND session_id = ?
                        ORDER BY timestamp ASC, id ASC
                    """, (account_id.lower(), session_id.lower())).fetchall()
                else:
                    rows = conn.execute("""
                        SELECT * FROM (
                            SELECT * FROM messages
                            WHERE account_id = ? AND session_id = ?
                            ORDER BY timestamp DESC, id DESC
                            LIMIT ?
                        ) ORDER BY timestamp ASC, id ASC
                    """, (account_id.lower(), session_id.lower(), limit)).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"查詢訊息失敗：{e}")
            return []
```

- [ ] 跑測試確認 PASS：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_db.py -v
```
  預期：全部通過，含新增的 7 個測試與修改後的 2 個斷言。

- [ ] 跑全套回歸，確認沒有其他檔案假設 `save_message` 回傳純 bool：
```
QT_QPA_PLATFORM=offscreen pytest -v
```
  預期：`tests/test_worker.py` 全綠（既有測試用 `db_mock.save_message.return_value = True`，mock 不受生產碼回傳型別變更影響）。

- [ ] Commit：
```
git add src/uPtt/db.py tests/test_db.py
git commit -m "feat(db): add delete_message/set_custom_name/set_muted + optional get_messages limit"
```

---

## Task 2: 顯示優先序——`custom_name > nickname > display_id` 統一組裝點

### Files
- Modify: `src/uPtt/utils.py`（`decode_reply` 之後，約行 82，新增 `resolve_display_name`）
- Modify: `src/uPtt/ui/widgets.py:407-500`（`ContactItem.__init__`：新增 `custom_name` 參數、內部快取、二級標籤組裝改用 `resolve_display_name`）
- Modify: `src/uPtt/ui/widgets.py:517-534`（`update_info`/`set_nickname` 改寫為呼叫共用的 `_refresh_secondary_label`；新增 `set_custom_name`）
- Modify: `src/uPtt/ui/widgets.py:569-582`（`get_data()` 新增 `custom_name` 欄位）
- Modify: `src/uPtt/ui/screens.py:1473-1509`（`load_sessions_from_db`：`ContactItem(...)` 帶入 `custom_name=s.get('custom_name') or ''`）
- Modify: `src/uPtt/ui/screens.py:2145-2161`（`_rebuild_contact_item`：帶入 `custom_name=data.get('custom_name', '')`）
- Modify: `src/uPtt/ui/screens.py:1774-1777`（`on_contact_selected` 的聊天標題組裝，改用 `resolve_display_name` 取代目前從 `nickname_label.text()` 解析括號字串的作法）
- Test: `tests/test_utils.py`、`tests/test_ui_widgets.py`、`tests/test_ui_screens.py`

### Interfaces
**Consumes**：無（本 Task 是 Task 1 欄位的純消費端，`s['custom_name']`／`s['is_muted']` 已可從 `get_all_sessions()` 取得）。

**Produces**（後續 Task 依賴）：
- `uPtt.utils.resolve_display_name(display_id: str, nickname: str, custom_name: str) -> str`——優先序 `custom_name`（非空）> `nickname`（非空）> `display_id`。呼叫端若要取得「二級標籤」（僅在有自訂或 PTT 暱稱時才顯示的那行），規則是：`resolved = resolve_display_name(...)`；`resolved != display_id` 時才顯示，否則視為空。
- `ContactItem.__init__(..., custom_name: str = "")`（新增參數，向後相容，預設值不影響既有呼叫）
- `ContactItem._nickname: str`、`ContactItem._custom_name: str`（實例屬性，Task 4 的 rename/mute handler 會讀取）
- `ContactItem.set_custom_name(name: str) -> None`
- `ContactItem.get_data()` 新增 `'custom_name'` 鍵（`'is_muted'` 鍵由 Task 5 補上，本 Task 不加）

### bite-sized steps

- [ ] 寫失敗測試，加到 `tests/test_utils.py`（`from src.uPtt.utils import (...)` import tuple 加入 `resolve_display_name`）：

```python
from src.uPtt.utils import (
    gen_random_string, msg_to_mail,
    get_latest_github_release_version,
    is_update_available, get_app_data_dir,
    VersionCheckWorker, resolve_display_name,
)

def test_resolve_display_name_prefers_custom_name():
    assert resolve_display_name("alice", "PTTNick", "MyAlias") == "MyAlias"

def test_resolve_display_name_falls_back_to_nickname():
    assert resolve_display_name("alice", "PTTNick", "") == "PTTNick"

def test_resolve_display_name_falls_back_to_display_id():
    assert resolve_display_name("alice", "", "") == "alice"
```

- [ ] 跑測試確認 FAIL：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_utils.py -v
```
  預期：`ImportError: cannot import name 'resolve_display_name'`。

- [ ] 最小實作，在 `src/uPtt/utils.py` 的 `decode_reply`（約行 82）之後插入：

```python
def resolve_display_name(display_id: str, nickname: str, custom_name: str) -> str:
    """本機顯示名優先序：custom_name（非空）> nickname（PTT）> display_id。"""
    if custom_name:
        return custom_name
    if nickname:
        return nickname
    return display_id
```

- [ ] 跑測試確認 PASS：`QT_QPA_PLATFORM=offscreen pytest tests/test_utils.py -v`

- [ ] Commit：
```
git add src/uPtt/utils.py tests/test_utils.py
git commit -m "feat(utils): add resolve_display_name priority helper"
```

- [ ] 寫失敗測試，加到 `tests/test_ui_widgets.py`：

```python
from src.uPtt.ui.widgets import ChatBubble, ContactItem  # 已存在，確認 import 不變

def test_contact_item_custom_name_overrides_nickname_label(qtbot):
    item = ContactItem("TestUser", "PTTNick", custom_name="MyAlias")
    qtbot.addWidget(item)
    assert "(MyAlias)" in item.nickname_label.text()
    assert "PTTNick" not in item.nickname_label.text()

def test_contact_item_set_custom_name_updates_label(qtbot):
    item = ContactItem("TestUser", "PTTNick")
    qtbot.addWidget(item)
    assert "(PTTNick)" in item.nickname_label.text()

    item.set_custom_name("MyAlias")
    assert "(MyAlias)" in item.nickname_label.text()

    item.set_custom_name("")
    assert "(PTTNick)" in item.nickname_label.text()

def test_contact_item_update_info_keeps_custom_name_priority(qtbot):
    item = ContactItem("TestUser", "OldNick", custom_name="MyAlias")
    qtbot.addWidget(item)
    item.update_info("TestUserCorrect", "NewNick")
    # PTT 暱稱查詢刷新不應蓋掉本機自訂名稱的顯示優先權
    assert "(MyAlias)" in item.nickname_label.text()

def test_contact_item_get_data_includes_custom_name(qtbot):
    item = ContactItem("TestUser", "Nick", custom_name="Alias")
    qtbot.addWidget(item)
    data = item.get_data()
    assert data['custom_name'] == "Alias"
```

- [ ] 跑測試確認 FAIL：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_ui_widgets.py -v
```
  預期：`TypeError: __init__() got an unexpected keyword argument 'custom_name'`。

- [ ] 最小實作。`widgets.py` 頂部加 import：
```python
from uPtt.utils import resolve_display_name
```

  改寫 `ContactItem.__init__`（`widgets.py:411-471` 範圍內，聚焦簽名與 nickname_label 組裝兩處）：

```python
    def __init__(self, ptt_id: str, nickname: str = "", unread_count: int = 0, is_pinned: bool = False,
                 last_msg_time: str = "", custom_name: str = "", parent=None):
        super().__init__(parent)
        self.ptt_id_display = ptt_id
        self.ptt_id = ptt_id.lower()
        self.is_pinned = is_pinned
        self.unread_count = unread_count
        self._is_online = False
        self._online_state = 'offline'
        self._is_archived = False
        self._nickname = nickname
        self._custom_name = custom_name
```

  （其餘 `__init__` 內容不變，直到 `nickname_label` 建立處）：

```python
        self.nickname_label = QLabel()
        self.nickname_label.setFixedHeight(14)
        self.nickname_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.nickname_label.setWordWrap(False)

        text_layout.addWidget(self.id_label)
        text_layout.addWidget(self.nickname_label)
```

  在 `main_layout.addSpacing(4)`（原第 474 行，`text_container` 之後）之後、`theme.register_restyle(...)`（原第 500 行）之前插入一次初始標籤刷新呼叫：

```python
        self._refresh_secondary_label()
```

  新增共用方法，緊接在 `__init__` 之後（`_apply_theme` 之前）：

```python
    def _refresh_secondary_label(self):
        """依 custom_name > nickname > display_id 優先序，重繪二級標籤（括號名）。"""
        resolved = resolve_display_name(self.ptt_id_display, self._nickname, self._custom_name)
        self.nickname_label.setText(f"({resolved})" if resolved != self.ptt_id_display else "")
```

  改寫 `update_info`（`widgets.py:517-531`）：

```python
    def update_info(self, ptt_id_display: str, nickname: str):
        """
        更新聯絡人資訊，包含正確大小寫的 ID 與暱稱。
        """
        if ptt_id_display:
            self.ptt_id_display = ptt_id_display
            self.id_label.setText(ptt_id_display)
            self.avatar_label.setText(ptt_id_display[0].upper())

        self._nickname = nickname
        self._refresh_secondary_label()

        logger.debug(f"UI 已更新資訊: {self.ptt_id} -> ID={ptt_id_display}, Nick={nickname}")

    def set_nickname(self, nickname: str):
        self._nickname = nickname
        self._refresh_secondary_label()

    def set_custom_name(self, custom_name: str):
        """設定本機自訂顯示名稱（空字串 = 清除，還原為讀 PTT 暱稱）。"""
        self._custom_name = custom_name
        self._refresh_secondary_label()
```

  改寫 `get_data()`（`widgets.py:569-582`）加入 `custom_name`：

```python
    def get_data(self) -> dict:
        """返回此項目的完整資料，供重建時使用。"""
        return {
            'ptt_id': self.ptt_id,
            'ptt_id_display': self.ptt_id_display,
            'nickname': self._nickname,
            'custom_name': self._custom_name,
            'unread_count': self.unread_count,
            'is_pinned': self.is_pinned,
            'is_online': self._is_online,
            'is_archived': self._is_archived,
            'last_msg_time': self.time_label.text(),
        }
```

- [ ] 跑測試確認 PASS：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_ui_widgets.py -v
```

- [ ] 跑既有 widgets/screens 測試防回歸：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_ui_widgets.py tests/test_ui_screens.py -v
```
  預期：全綠（`test_contact_item_init`/`test_contact_item_update_info` 等既有測試邏輯上與新版 `_refresh_secondary_label` 等價，不需修改）。

- [ ] 寫失敗測試，加到 `tests/test_ui_screens.py`（沿用檔案既有的 `ptt_service_mock`/`ptt_query_service_mock`/`db_mock` fixtures 與 4 個 `@patch` 裝饰器組合）：

```python
@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_load_sessions_uses_custom_name_priority(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    db_mock.get_all_sessions.return_value = [
        {
            'account_id': 'myid', 'id': 'bob', 'display_id': 'Bob',
            'nickname': 'PTTNick', 'custom_name': 'MyAlias',
            'last_message_text': '', 'last_message_time': None,
            'unread_count': 0, 'is_visible': 1, 'is_pinned': 0,
            'pin_order': 0, 'is_archived': 0,
        }
    ]
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.load_sessions_from_db()

        widget = window.contact_list.itemWidget(window.contact_list.item(0))
        assert "(MyAlias)" in widget.nickname_label.text()


@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_chat_header_shows_custom_name_over_nickname(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.add_or_select_contact("Bob")

        widget = window.contact_list.itemWidget(window.contact_list.item(0))
        widget.update_info("Bob", "PTTNick")
        widget.set_custom_name("MyAlias")

        window.on_contact_selected(window.contact_list.item(0))
        assert window.chat_header_nick.text() == "MyAlias"
```

- [ ] 跑測試確認 FAIL：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_ui_screens.py -k "custom_name" -v
```
  預期：`test_load_sessions_uses_custom_name_priority` 因 `load_sessions_from_db` 尚未傳入 `custom_name` 而顯示 `(PTTNick)` 非 `(MyAlias)`，斷言失敗。

- [ ] 最小實作。`screens.py:1487-1493` 的 `ContactItem(...)` 呼叫加入 `custom_name`：

```python
            widget = ContactItem(
                ptt_id=s['id'],
                nickname=s['nickname'] or "",
                unread_count=s['unread_count'] or 0,
                is_pinned=is_pinned,
                last_msg_time=_format_contact_time(s.get('last_message_time', '')),
                custom_name=s.get('custom_name') or "",
            )
```

  `screens.py:2149-2155` 的 `_rebuild_contact_item` 內 `ContactItem(...)` 呼叫同樣加入：

```python
        new_widget = ContactItem(
            ptt_id=data['ptt_id_display'],
            nickname=data['nickname'],
            unread_count=data.get('unread_count', 0),
            is_pinned=is_pinned,
            last_msg_time=data.get('last_msg_time', ''),
            custom_name=data.get('custom_name', ''),
        )
```

  改寫 `screens.py:1774-1777`（`on_contact_selected` 內聊天標題組裝，取代原本從 `nickname_label.text()` 剝括號的寫法）：

```python
        # 每次切換聯絡人時更新視窗標題與聊天標題列
        self.setWindowTitle(f"uPtt - 與 {widget.ptt_id_display} 對話中")
        resolved_secondary = resolve_display_name(widget.ptt_id_display, widget._nickname, widget._custom_name)
        nickname = resolved_secondary if resolved_secondary != widget.ptt_id_display else ""
        self._update_chat_header(widget.ptt_id_display, nickname, widget._is_online)
```

  `screens.py` 的 import 加入 `resolve_display_name`：
```python
from uPtt.utils import encode_reply, decode_reply, VersionCheckWorker, resolve_display_name
```

- [ ] 跑測試確認 PASS：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_ui_screens.py -v
```

- [ ] Commit：
```
git add src/uPtt/ui/widgets.py src/uPtt/ui/screens.py tests/test_ui_widgets.py tests/test_ui_screens.py
git commit -m "feat(ui): unify contact list / chat header display name priority"
```

---

## Task 3: 訊息選單 · 刪除（僅本機）

### Files
- Modify: `src/uPtt/ui/widgets.py:41-49`（`ChatBubble.__init__` 簽名新增 `message_id`）
- Modify: `src/uPtt/ui/widgets.py:41-45`（新增 `delete_requested = Signal(int)`）
- Modify: `src/uPtt/ui/widgets.py:174-189`（`_build_context_menu`：加刪除項）
- Modify: `src/uPtt/worker.py:25`（signal 文件註解更新）
- Modify: `src/uPtt/worker.py:299-329`（uPtt 訊息 emit_dict 加 `msg_id`）
- Modify: `src/uPtt/ui/screens.py:1867-1870`（`refresh_chat_display`：`ChatBubble(message_id=...)` + 連接 `delete_requested`）
- Modify: `src/uPtt/ui/screens.py:2031-2039`（`on_new_message`：`msg_dict` 加 `'msg_id': data.get('msg_id')`）
- Modify: `src/uPtt/ui/screens.py`（新增 `handle_delete_message` 方法，緊接在 `cancel_reply` 之後，約行 1896）
- Test: `tests/test_ui_widgets.py`、`tests/test_worker.py`、`tests/test_ui_screens.py`

### Interfaces
**Consumes**：`ContactItem`/`resolve_display_name` 不涉及本 Task；沿用 Task 1 的 `DatabaseManager.delete_message(account_id, message_id) -> Optional[str]`。

**Produces**：
- `ChatBubble.__init__(..., message_id: Optional[int] = None, parent=None)`——新增參數，`self.message_id` 存取。
- `ChatBubble.delete_requested = Signal(int)`——右鍵選單「刪除（僅本機）」觸發時 emit `self.message_id`；`message_id is None` 時該選單項不出現。
- `MainWindow.handle_delete_message(message_id: int) -> None`——確認對話框 → 呼叫 `db.delete_message` → 從 `chat_histories` 移除該筆 → 若為目前開啟對話則 `refresh_chat_display()` → 刷新聯絡人列 `time_label`。
- worker 端 `new_message_received` 訊號 dict 新增可選鍵 `'msg_id'`（僅 uPtt 訊息路徑，mail_type='uptt'）。

### bite-sized steps

- [ ] 寫失敗測試，加到 `tests/test_ui_widgets.py`：

```python
def test_chat_bubble_stores_message_id(qtbot):
    bubble = ChatBubble("Hello", "10:00", is_me=True, message_id=42)
    qtbot.addWidget(bubble)
    assert bubble.message_id == 42

def test_chat_bubble_delete_action_emits_message_id(qtbot):
    bubble = ChatBubble("Hello", "10:00", is_me=True, message_id=42)
    qtbot.addWidget(bubble)
    menu = bubble._build_context_menu()
    delete_action = next(a for a in menu.actions() if a.text().startswith("刪除"))
    with qtbot.waitSignal(bubble.delete_requested, timeout=1000) as blocker:
        delete_action.trigger()
    assert blocker.args == [42]

def test_chat_bubble_no_delete_action_without_message_id(qtbot):
    bubble = ChatBubble("Hello", "10:00", is_me=True)
    qtbot.addWidget(bubble)
    menu = bubble._build_context_menu()
    assert not any(a.text().startswith("刪除") for a in menu.actions())
```

- [ ] 跑測試確認 FAIL：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_ui_widgets.py -k "delete" -v
```
  預期：`TypeError: __init__() got an unexpected keyword argument 'message_id'`。

- [ ] 最小實作。`widgets.py:41-53`（`ChatBubble` 類別與建構子）改為：

```python
class ChatBubble(QWidget):
    """
    自訂對話氣泡元件 (極致緊湊與貼合版)。
    """
    reply_requested = Signal(str, bool)  # (message_text, is_me)
    delete_requested = Signal(int)  # message_id

    def __init__(self, text: str, time_str: str, is_me: bool = False,
                 reply_info: Optional[dict] = None, send_status: Optional[str] = None,
                 message_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.is_me = is_me
        self._text = text
        self._reply_info = reply_info
        self._send_status = send_status
        self.message_id = message_id
```

  改寫 `_build_context_menu`（`widgets.py:174-189`）：

```python
    def _build_context_menu(self) -> QMenu:
        menu = QMenu(self)

        copy_action = QAction("複製文字\t⌘C", self)
        copy_action.triggered.connect(lambda: QApplication.clipboard().setText(self._text))
        menu.addAction(copy_action)

        reply_action = QAction("引用回覆\t⇧⌘R", self)
        reply_action.triggered.connect(lambda: self.reply_requested.emit(self._text, self.is_me))
        menu.addAction(reply_action)

        if self.message_id is not None:
            menu.addSeparator()
            delete_action = QAction("刪除（僅本機）", self)
            delete_action.triggered.connect(lambda: self.delete_requested.emit(self.message_id))
            menu.addAction(delete_action)

        # ponytail: 設計稿另有「轉寄給…」「釘選訊息」，轉寄需要新聯絡人選擇 UI、
        # 釘選需要 message 級新欄位 + 釘選面板，兩者都延後至下一輪 Phase 3。
        return menu
```

- [ ] 跑測試確認 PASS：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_ui_widgets.py -v
```

- [ ] Commit：
```
git add src/uPtt/ui/widgets.py tests/test_ui_widgets.py
git commit -m "feat(widgets): add per-message local delete action to ChatBubble"
```

- [ ] 寫失敗測試，加到 `tests/test_worker.py`（緊接在既有 `test_poll_new_mails_basic` 之後，沿用同樣的 `call_side_effect` 樣式）：

```python
def test_poll_new_mails_includes_msg_id_from_save_message(qtbot, worker, ptt_service_mock, db_mock):
    """new_message_received 應攜帶 save_message 回傳的 DB row id，供 UI 端刪除訊息定位（uPtt 訊息路徑）。"""
    def call_side_effect(api, args=None):
        if api == 'get_newest_index':
            return 1
        if api == 'get_mail':
            return {
                PyPtt.MailField.title: contant.PTT_MSG_TITLE,
                PyPtt.MailField.author: "SenderID (Nick)",
                PyPtt.MailField.date: "Wed Mar 15 10:00:00 2026",
                PyPtt.MailField.content: f"Header\n{contant.PTT_MSG_DIVISION_LINE}\nTest Message Content\n{contant.PTT_MSG_DIVISION_LINE}\nFooter"
            }
        return None

    ptt_service_mock.call.side_effect = call_side_effect
    db_mock.save_message.return_value = 777  # 模擬 SQLite lastrowid

    worker.is_first_polling = False

    with qtbot.waitSignal(worker.new_message_received) as blocker:
        worker._poll_new_mails()

    assert blocker.args[0]['msg_id'] == 777
```

- [ ] 跑測試確認 FAIL：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_worker.py -k "msg_id" -v
```
  預期：`KeyError: 'msg_id'`。

- [ ] 最小實作。`worker.py:25` 訊號文件註解更新：
```python
    new_message_received = Signal(dict)  # {'sender': str, 'text': str, 'time': str, 'full_author': str, 'msg_id': Optional[int]}
```

  `worker.py:319-329`（「對方發來的 uPtt 訊息」emit_dict，成功路徑）改為：

```python
        emit_dict = None
        if is_new:
            emit_dict = {
                'sender': sender_id,
                'text': text,
                'time': msg_time.strftime("%H:%M"),
                'full_author': full_author,
                'timestamp': msg_time,
                'mail_type': 'uptt',
                'subject': '',
                'msg_id': is_new,
            }
```

  （`is_new` 此時已是 `save_message` 回傳的 row id，truthy 判斷不變；`msg_id` 直接沿用同一個值。）

- [ ] 跑測試確認 PASS：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_worker.py -v
```
  預期：全綠，含既有的 `test_poll_new_mails_basic` 等（`msg_id` 是新增鍵，不影響既有斷言）。

- [ ] Commit：
```
git add src/uPtt/worker.py tests/test_worker.py
git commit -m "feat(worker): thread DB row id through new_message_received for uPtt messages"
```

- [ ] 寫失敗測試，加到 `tests/test_ui_screens.py`：

```python
@patch('src.uPtt.ui.screens.QMessageBox')
@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_handle_delete_message_removes_from_history_and_refreshes(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, mock_msgbox, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    mock_msgbox.question.return_value = mock_msgbox.Yes
    db_mock.delete_message.return_value = "bob"
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.add_or_select_contact("Bob")
        window.chat_histories['bob'] = [
            {'text': 'Hi', 'time': '10:00', 'timestamp': datetime.now(), 'is_me': False, 'msg_id': 5},
            {'text': 'Yo', 'time': '10:01', 'timestamp': datetime.now(), 'is_me': True, 'msg_id': 6, 'send_status': 'sent'},
        ]
        window.current_chat_id = 'bob'

        window.handle_delete_message(5)

        db_mock.delete_message.assert_called_once_with("MyID", 5)
        assert [m['msg_id'] for m in window.chat_histories['bob']] == [6]


@patch('src.uPtt.ui.screens.QMessageBox')
@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_handle_delete_message_cancelled_keeps_history(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, mock_msgbox, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    mock_msgbox.question.return_value = mock_msgbox.No
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.add_or_select_contact("Bob")
        window.chat_histories['bob'] = [
            {'text': 'Hi', 'time': '10:00', 'timestamp': datetime.now(), 'is_me': False, 'msg_id': 5},
        ]
        window.current_chat_id = 'bob'

        window.handle_delete_message(5)

        db_mock.delete_message.assert_not_called()
        assert len(window.chat_histories['bob']) == 1
```

- [ ] 跑測試確認 FAIL：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_ui_screens.py -k "handle_delete_message" -v
```
  預期：`AttributeError: 'MainWindow' object has no attribute 'handle_delete_message'`。

- [ ] 最小實作。`screens.py:1867-1870`（`refresh_chat_display` 內 `ChatBubble` 建構處）改為：

```python
            else:
                widget = ChatBubble(msg['text'], msg['time'], msg['is_me'],
                                    reply_info=msg.get('reply_info'),
                                    send_status=msg.get('send_status'),
                                    message_id=msg.get('msg_id'))
                widget.reply_requested.connect(self.set_reply_to)
                widget.delete_requested.connect(self.handle_delete_message)
```

  `screens.py:2031-2039`（`on_new_message` 的 `msg_dict`）加入 `'msg_id'`：

```python
        msg_dict = {
            'text': actual_text,
            'time': data['time'],
            'timestamp': data.get('timestamp', datetime.now()),
            'is_me': is_me,
            'mail_type': data.get('mail_type', 'uptt'),
            'subject': data.get('subject', ''),
            'reply_info': reply_info,
            'msg_id': data.get('msg_id'),
        }
```

  新增方法，緊接在 `cancel_reply`（約 `screens.py:1896`）之後：

```python
    def handle_delete_message(self, message_id: int):
        """刪除單則本機訊息（僅本機，不影響 PTT 上的信件），需使用者確認。"""
        confirm = QMessageBox.question(
            self, "確認刪除", "確定要刪除這則訊息嗎？\n(僅從本機刪除，不影響 PTT 上的信件)",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        current_acc = self.ptt_service.ptt_id
        session_id = self.db.delete_message(current_acc, message_id)
        if session_id is None:
            return

        history = self.chat_histories.get(session_id, [])
        self.chat_histories[session_id] = [m for m in history if m.get('msg_id') != message_id]

        if self.current_chat_id == session_id:
            self.refresh_chat_display()

        sessions = self.db.get_all_sessions(current_acc)
        row = next((s for s in sessions if s['id'] == session_id), None)
        for i in range(self.contact_list.count()):
            widget = self.contact_list.itemWidget(self.contact_list.item(i))
            if widget and widget.ptt_id == session_id:
                widget.set_last_msg_time(_format_contact_time(row.get('last_message_time', '') if row else ''))
                break
```

- [ ] 跑測試確認 PASS：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_ui_screens.py -v
```

- [ ] 全套回歸：
```
QT_QPA_PLATFORM=offscreen pytest -v
```

- [ ] Commit：
```
git add src/uPtt/ui/screens.py tests/test_ui_screens.py
git commit -m "feat(ui): wire message delete action end-to-end (bubble -> db -> sidebar refresh)"
```

---

## Task 4: 聯絡人選單 · 改名 / 靜音 toggle / 匯出 + 通知 gate

### Files
- Modify: `src/uPtt/ui/screens.py`（imports：`QFileDialog` 加入 QtWidgets import；新增 `_find_contact_widget`/`rename_contact`/`toggle_mute`/`export_chat_history` 方法，緊接在 `toggle_pin`，即約行 2230，之後）
- Modify: `src/uPtt/ui/screens.py:2276-2306`（`_build_contact_context_menu` 簽名與內容）
- Modify: `src/uPtt/ui/screens.py:2308-2317`（`show_contact_context_menu` 傳入 `is_muted`）
- Modify: `src/uPtt/ui/screens.py:2059-2068`（通知 gate 加 mute 判斷）
- Test: `tests/test_ui_screens.py`

### Interfaces
**Consumes**：
- `DatabaseManager.set_custom_name`/`set_muted`/`is_session_muted`（Task 1）
- `resolve_display_name`（Task 2）
- `ContactItem._nickname`/`_custom_name`/`set_custom_name()`（Task 2）

**Produces**：
- `MainWindow._find_contact_widget(ptt_id_lower: str) -> Optional[ContactItem]`——DRY 小工具，供本 Task 三個 handler 共用（取代重複的清單掃描迴圈）。
- `MainWindow.rename_contact(ptt_id: str) -> None`
- `MainWindow.toggle_mute(ptt_id: str) -> None`
- `MainWindow.export_chat_history(ptt_id: str) -> None`
- `MainWindow._build_contact_context_menu(ptt_id: str, is_pinned: bool, is_muted: bool) -> QMenu`——**簽名變更**（新增 `is_muted` 參數），Task 5 沿用。
- `ContactItem._is_muted: bool`（Task 5 會補上 `set_muted()`；本 Task 先假設該屬性存在且預設 `False`——**注意**：`set_muted` 方法本體由 Task 5 建立，故本 Task 的 `toggle_mute` 呼叫 `widget.set_muted(new_state)` 時該方法尚未定義，因此 **Task 4 必須在 Task 5 之後才能整合測試通過**；本計畫的作法是 Task 4 先在 `ContactItem.__init__` 補上最小必要的 `self._is_muted = False` 屬性（不含圖示邏輯），完整 `set_muted()`/icon 邏輯留給 Task 5。見下方步驟。

### bite-sized steps

- [ ] 最小補丁（非 TDD 主體，純屬性占位）：在 `widgets.py` 的 `ContactItem.__init__`（Task 2 已改過的版本，`self._custom_name = custom_name` 之後）加入：
```python
        self._is_muted = False
```
  並新增一個最小方法（Task 5 會擴充其內容，此處先給最小可用版本讓 Task 4 能呼叫）：
```python
    def set_muted(self, muted: bool):
        self._is_muted = muted
```
  跑一次既有 widgets 測試確認未破壞：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_ui_widgets.py -v
```

- [ ] 寫失敗測試，加到 `tests/test_ui_screens.py`：

```python
@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_rename_contact_writes_custom_name_and_updates_label(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock, monkeypatch):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.add_or_select_contact("Bob")

        monkeypatch.setattr(
            'src.uPtt.ui.screens.QInputDialog.getText',
            lambda *a, **k: ("MyAlias", True)
        )
        window.rename_contact("Bob")

        db_mock.set_custom_name.assert_called_once_with("MyID", "bob", "MyAlias")
        widget = window.contact_list.itemWidget(window.contact_list.item(0))
        assert "(MyAlias)" in widget.nickname_label.text()


@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_rename_contact_empty_string_clears_custom_name(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock, monkeypatch):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.add_or_select_contact("Bob")
        widget = window.contact_list.itemWidget(window.contact_list.item(0))
        widget.set_custom_name("OldAlias")

        monkeypatch.setattr(
            'src.uPtt.ui.screens.QInputDialog.getText',
            lambda *a, **k: ("", True)
        )
        window.rename_contact("Bob")

        db_mock.set_custom_name.assert_called_once_with("MyID", "bob", "")
        assert widget._custom_name == ""


@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_toggle_mute_writes_db_and_updates_widget(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.add_or_select_contact("Bob")
        widget = window.contact_list.itemWidget(window.contact_list.item(0))
        assert widget._is_muted is False

        window.toggle_mute("Bob")
        db_mock.set_muted.assert_called_once_with("MyID", "bob", True)
        assert widget._is_muted is True

        window.toggle_mute("Bob")
        db_mock.set_muted.assert_called_with("MyID", "bob", False)
        assert widget._is_muted is False


@patch('src.uPtt.ui.screens.QFileDialog')
@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_export_chat_history_writes_txt_file(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, mock_file_dialog, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock, tmp_path):
    out_path = str(tmp_path / "export.txt")
    mock_file_dialog.getSaveFileName.return_value = (out_path, "文字檔 (*.txt)")
    db_mock.get_messages.return_value = [
        {'content': 'Hello', 'timestamp': '2026-01-01 12:00:00', 'is_me': 0},
        {'content': 'Hi back', 'timestamp': '2026-01-01 12:01:00', 'is_me': 1},
    ]
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.add_or_select_contact("Bob")

        window.export_chat_history("Bob")

        db_mock.get_messages.assert_called_with("MyID", "bob", limit=None)
        content = open(out_path, encoding="utf-8").read()
        assert "[2026-01-01 12:00:00] Bob: Hello" in content
        assert "[2026-01-01 12:01:00] MyID: Hi back" in content


@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_on_new_message_skips_notification_when_session_muted(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    """靜音的聯絡人來訊時不應觸發桌面通知（screens.py:2059 通知 gate 加 mute 判斷）。"""
    db_mock.is_session_muted.return_value = True
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.tray_icon = MagicMock()

        now = datetime.now()
        window.on_new_message({
            'sender': 'Bob', 'text': 'Hi', 'time': now.strftime("%H:%M"),
            'full_author': 'Bob', 'timestamp': now, 'mail_type': 'uptt',
        })

        window.tray_icon.showMessage.assert_not_called()
        db_mock.is_session_muted.assert_called_with("MyID", "bob")


@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_on_new_message_notifies_when_not_muted(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    """未靜音的聯絡人來訊時應維持原本的桌面通知行為（回歸測試）。"""
    db_mock.is_session_muted.return_value = False
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.tray_icon = MagicMock()

        now = datetime.now()
        window.on_new_message({
            'sender': 'Bob', 'text': 'Hi', 'time': now.strftime("%H:%M"),
            'full_author': 'Bob', 'timestamp': now, 'mail_type': 'uptt',
        })

        window.tray_icon.showMessage.assert_called_once()
```

- [ ] 跑測試確認 FAIL：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_ui_screens.py -k "rename_contact or toggle_mute or export_chat_history or session_muted" -v
```
  預期：`AttributeError: 'MainWindow' object has no attribute 'rename_contact'`（及 `toggle_mute`/`export_chat_history`）；靜音通知測試因 gate 尚未加判斷而 `showMessage` 仍被呼叫。

- [ ] 最小實作。`screens.py` 的 QtWidgets import（原第 7-12 行）加入 `QFileDialog`：
```python
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QStackedWidget, QListWidget, QListWidgetItem, QSplitter,
    QScrollArea, QTextEdit, QSystemTrayIcon, QMenu, QMessageBox, QInputDialog,
    QCheckBox, QFileDialog
)
```

  新增 `_find_contact_widget` 與三個 handler，緊接在 `toggle_pin`（約 `screens.py:2224`）之後：

```python
    def _find_contact_widget(self, ptt_id_lower: str) -> Optional[ContactItem]:
        """依小寫 ptt_id 找出側邊欄對應的 ContactItem，找不到回傳 None。"""
        for i in range(self.contact_list.count()):
            widget = self.contact_list.itemWidget(self.contact_list.item(i))
            if widget and widget.ptt_id == ptt_id_lower:
                return widget
        return None

    def rename_contact(self, ptt_id: str):
        """重新命名聯絡人（本機 alias）。輸入空字串 = 清除自訂名稱，還原為 PTT 暱稱。"""
        ptt_id_lower = ptt_id.lower()
        widget = self._find_contact_widget(ptt_id_lower)
        if not widget:
            return
        current_acc = self.ptt_service.ptt_id
        current_name = resolve_display_name(widget.ptt_id_display, widget._nickname, widget._custom_name)
        text, ok = QInputDialog.getText(
            self, "重新命名聯絡人", "顯示名稱（留空還原為 PTT 暱稱）：",
            QLineEdit.Normal, current_name
        )
        if not ok:
            return
        new_name = text.strip()
        self.db.set_custom_name(current_acc, ptt_id_lower, new_name)
        widget.set_custom_name(new_name)
        if self.current_chat_id == ptt_id_lower:
            resolved_secondary = resolve_display_name(widget.ptt_id_display, widget._nickname, widget._custom_name)
            nickname = resolved_secondary if resolved_secondary != widget.ptt_id_display else ""
            self._update_chat_header(widget.ptt_id_display, nickname, widget._is_online)

    def toggle_mute(self, ptt_id: str):
        """切換聯絡人的靜音通知狀態。"""
        ptt_id_lower = ptt_id.lower()
        widget = self._find_contact_widget(ptt_id_lower)
        if not widget:
            return
        current_acc = self.ptt_service.ptt_id
        new_state = not widget._is_muted
        self.db.set_muted(current_acc, ptt_id_lower, new_state)
        widget.set_muted(new_state)

    def export_chat_history(self, ptt_id: str):
        """匯出與該聯絡人的完整對話紀錄為純文字檔。"""
        ptt_id_lower = ptt_id.lower()
        current_acc = self.ptt_service.ptt_id
        widget = self._find_contact_widget(ptt_id_lower)
        display_name = (
            resolve_display_name(widget.ptt_id_display, widget._nickname, widget._custom_name)
            if widget else ptt_id
        )
        default_name = f"對話_{display_name}_{datetime.now().strftime('%Y%m%d')}.txt"
        path, _ = QFileDialog.getSaveFileName(self, "匯出對話紀錄", default_name, "文字檔 (*.txt)")
        if not path:
            return

        messages = self.db.get_messages(current_acc, ptt_id_lower, limit=None)
        lines = []
        for m in messages:
            ts = m['timestamp']
            ts_dt = datetime.fromisoformat(ts) if isinstance(ts, str) else ts
            ts_str = ts_dt.strftime('%Y-%m-%d %H:%M:%S')
            sender = current_acc if m['is_me'] else display_name
            _, text = decode_reply(m['content'])
            lines.append(f"[{ts_str}] {sender}: {text}")

        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
        except OSError as e:
            QMessageBox.warning(self, "匯出失敗", f"無法寫入檔案：{e}")
```

  改寫 `_build_contact_context_menu`（`screens.py:2276-2306`）：

```python
    def _build_contact_context_menu(self, ptt_id: str, is_pinned: bool, is_muted: bool) -> QMenu:
        """建立聯絡人右鍵選單（依設計稿排序：釘選 → 改名/靜音/匯出 → destructive 群）。"""
        menu = QMenu(self)

        pin_action = QAction("取消釘選" if is_pinned else "釘選對話\t⌘D", self)
        pin_action.triggered.connect(lambda: self.toggle_pin(ptt_id))
        menu.addAction(pin_action)

        rename_action = QAction("重新命名…", self)
        rename_action.triggered.connect(lambda: self.rename_contact(ptt_id))
        menu.addAction(rename_action)

        mute_action = QAction("取消靜音" if is_muted else "靜音通知", self)
        mute_action.triggered.connect(lambda: self.toggle_mute(ptt_id))
        menu.addAction(mute_action)

        export_action = QAction("匯出對話紀錄…", self)
        export_action.triggered.connect(lambda: self.export_chat_history(ptt_id))
        menu.addAction(export_action)

        # ponytail: 設計稿另有「標記為未讀 ⌘U」，需要可手動設非零的未讀旗標新後端，本輪不做。

        menu.addSeparator()

        block_action = QAction("封鎖此使用者", self)
        block_action.triggered.connect(lambda: self.handle_contact_action(ptt_id, "BLOCK"))
        menu.addAction(block_action)

        hide_action = QAction("隱藏對話", self)
        hide_action.triggered.connect(lambda: self.handle_contact_action(ptt_id, "CLOSE"))
        menu.addAction(hide_action)

        delete_action = QAction("刪除…", self)
        delete_action.triggered.connect(lambda: self.handle_contact_action(ptt_id, "DELETE"))
        menu.addAction(delete_action)

        # danger 紅字（封鎖/隱藏/刪除）per-item 上色：QMenu::item 屬性選取器對 Qt 無效
        # （見 styles.py 選單註解），最短解做不到，本步延後；要做需改 QWidgetAction 自訂上色。

        return menu

    def show_contact_context_menu(self, pos):
        """顯示聯絡人清單的右鍵選單"""
        item = self.contact_list.itemAt(pos)
        if not item:
            return

        widget = self.contact_list.itemWidget(item)
        is_pinned = widget.ptt_id in self.pinned_ids
        menu = self._build_contact_context_menu(widget.ptt_id, is_pinned, widget._is_muted)
        menu.exec(self.contact_list.mapToGlobal(pos))
```

  改寫通知 gate（`screens.py:2059-2068`）：

```python
        # 桌面通知 (僅限收到的訊息，排除自己發出的，使用者未關閉桌面通知，且該聯絡人未被靜音)
        if (not self.isActiveWindow() and not data.get('is_me', False)
                and self.db.get_config(config.SETTING_NOTIFY_ENABLED, True)
                and not self.db.is_session_muted(self.ptt_service.ptt_id, sender)):
            _, notify_text = decode_reply(data['text'])
            self.tray_icon.showMessage(
                f"新訊息: {sender_id_display}",
                notify_text[:50],
                QSystemTrayIcon.Information,
                3000
            )
```

- [ ] 跑測試確認 PASS：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_ui_screens.py -v
```

- [ ] 全套回歸：
```
QT_QPA_PLATFORM=offscreen pytest -v
```

- [ ] Commit：
```
git add src/uPtt/ui/screens.py src/uPtt/ui/widgets.py tests/test_ui_screens.py
git commit -m "feat(ui): add contact menu rename/mute/export actions and mute-aware notify gate"
```

---

## Task 5: 靜音 icon（聯絡人列常駐圖示，三主題上色）

### Files
- Modify: `src/uPtt/ui/theme.py`（新增 `import os, sys` + Qt imports；搬入 `ASSETS_DIR`/`render_svg`）
- Modify: `src/uPtt/ui/screens.py:51-83`（移除本地 `ASSETS_DIR`/`render_svg` 定義，改為從 `theme.py` 匯入）
- Create: `src/uPtt/ui/assets/icon_mute.svg`（新的靜音鈴鐺圖示，單色可被 tint）
- Modify: `src/uPtt/ui/widgets.py`（imports 加 `os`/`QColor`/`QPainter`；`ContactItem` 加入 icon label + `_update_mute_icon`/完整版 `set_muted`；`_apply_theme` 呼叫 `_update_mute_icon`）
- Modify: `src/uPtt/ui/screens.py:1473-1509`（`load_sessions_from_db`：`ContactItem` 建好後依 `s.get('is_muted')` 呼叫 `set_muted(True)`）
- Modify: `src/uPtt/ui/screens.py:2145-2161`（`_rebuild_contact_item`：依 `data.get('is_muted')` 呼叫 `set_muted`）
- Modify: `src/uPtt/ui/widgets.py:569-582`（`get_data()` 新增 `'is_muted'` 鍵）
- Create: `tests/test_theme.py`
- Test: `tests/test_ui_widgets.py`、`tests/test_ui_screens.py`

### Interfaces
**Consumes**：`ContactItem._is_muted`/最小版 `set_muted()`（Task 4 已建立占位）、`theme.active()`/`theme.register_restyle`（既有）。

**Produces**：
- `uPtt.ui.theme.ASSETS_DIR: str`、`uPtt.ui.theme.render_svg(path: str, width: int, height: int, dpr: float = 1.0) -> QPixmap`——從 `screens.py` 搬遷過來的**單一定義**；`screens.py` 之後改為 `from uPtt.ui.theme import ASSETS_DIR, render_svg`（同名再匯出，既有 `from src.uPtt.ui.screens import render_svg` 測試不受影響）。
- `ContactItem.set_muted(muted: bool) -> None`——**完整版**，覆蓋 Task 4 的占位版本：更新 `self._is_muted`、依 `theme.active()` 上色並顯示/隱藏 `mute_icon_label`。
- `ContactItem.mute_icon_label: QLabel`（測試可直接檢查 `isVisible()`/`pixmap()`）。
- `ContactItem.get_data()` 新增 `'is_muted'` 鍵（供 `_rebuild_contact_item` 重建時保留狀態）。

### bite-sized steps

- [ ] 寫失敗測試，建立 `tests/test_theme.py`：

```python
import os
from src.uPtt.ui import theme


def test_render_svg_renders_valid_svg(tmp_path):
    svg_path = tmp_path / "test.svg"
    svg_path.write_text('<svg width="10" height="10"><rect width="10" height="10" /></svg>')
    pixmap = theme.render_svg(str(svg_path), 10, 10)
    assert not pixmap.isNull()


def test_render_svg_invalid_path_returns_null_pixmap():
    pixmap = theme.render_svg("/no/such/file.svg", 10, 10)
    assert pixmap.isNull()


def test_screens_reexports_same_render_svg():
    from src.uPtt.ui import screens
    assert screens.render_svg is theme.render_svg
    assert screens.ASSETS_DIR == theme.ASSETS_DIR


def test_mute_icon_asset_exists():
    assert os.path.exists(os.path.join(theme.ASSETS_DIR, "icon_mute.svg"))
```

- [ ] 跑測試確認 FAIL：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_theme.py -v
```
  預期：`AttributeError: module 'src.uPtt.ui.theme' has no attribute 'render_svg'`。

- [ ] 最小實作。`theme.py` 開頭（`import weakref` 之後）加入：

```python
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


# 資源目錄定義（相容 PyInstaller 與 Nuitka；ui/ 目錄下與 screens.py 同層，故路徑計算一致）
if hasattr(sys, '_MEIPASS'):
    ASSETS_DIR = os.path.join(sys._MEIPASS, "uPtt", "ui", "assets")
else:
    ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")


def render_svg(path: str, width: int, height: int, dpr: float = 1.0) -> QPixmap:
    """高畫質渲染 SVG 檔案到 QPixmap (支援 High-DPI)"""
    renderer = QSvgRenderer(path)
    if not renderer.isValid():
        return QPixmap()

    pixmap = QPixmap(int(width * dpr), int(height * dpr))
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()

    pixmap.setDevicePixelRatio(dpr)
    return pixmap
```

  移除 `screens.py:51-83` 的本地 `ASSETS_DIR`（含 PyInstaller/Nuitka 分支）與 `render_svg` 定義，改為在既有 `from uPtt.ui import theme` 附近加：
```python
from uPtt.ui.theme import FONT_STACK, ASSETS_DIR, render_svg
```
  （原本的 `from uPtt.ui.theme import FONT_STACK` 一行併入上式，避免重複 import。）

  新增 SVG 資產 `src/uPtt/ui/assets/icon_mute.svg`：
```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
  <path fill="#000000" d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.89 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68c-.15.03-.29.08-.43.12L18 13.29V16l1.06 1.06L20 16.11V16h-2zM3.27 2L2 3.27l3.18 3.18C5.06 7.36 5 8.32 5 9v7l-2 2v1h13.73l1.73 1.73L19.73 19 3.27 2zM7 9c0-.42.03-.83.09-1.23L15.32 16H7V9z"/>
</svg>
```

- [ ] 跑測試確認 PASS：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_theme.py -v
```
  同時跑既有 `test_render_svg_exists` 確認再匯出未破壞：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_ui_screens.py -k "render_svg" -v
```

- [ ] Commit：
```
git add src/uPtt/ui/theme.py src/uPtt/ui/screens.py src/uPtt/ui/assets/icon_mute.svg tests/test_theme.py
git commit -m "refactor(ui): move render_svg/ASSETS_DIR into theme.py to avoid widgets<->screens circular import"
```

- [ ] 寫失敗測試，加到 `tests/test_ui_widgets.py`：

```python
def test_contact_item_set_muted_shows_and_hides_icon(qtbot):
    item = ContactItem("TestUser")
    qtbot.addWidget(item)
    assert item.mute_icon_label.isVisible() is False

    item.set_muted(True)
    assert item.mute_icon_label.isVisible() is True
    assert not item.mute_icon_label.pixmap().isNull()

    item.set_muted(False)
    assert item.mute_icon_label.isVisible() is False


def test_contact_item_get_data_includes_is_muted(qtbot):
    item = ContactItem("TestUser")
    qtbot.addWidget(item)
    item.set_muted(True)
    data = item.get_data()
    assert data['is_muted'] is True
```

- [ ] 跑測試確認 FAIL：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_ui_widgets.py -k "mute_icon or is_muted" -v
```
  預期：`AttributeError: 'ContactItem' object has no attribute 'mute_icon_label'`。

- [ ] 最小實作。`widgets.py` 檔案最頂端的 import 區塊（原第 1-13 行，含 Task 2 已加入的 `resolve_display_name`）整段改為：
```python
import os
import logging
from datetime import datetime
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QSizePolicy, QStyle, QListWidgetItem, QListWidget, QAbstractItemView,
    QPushButton, QDialog, QTextEdit, QMenu, QApplication
)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QAction, QDrag, QColor, QPainter
from uPtt.ui.styles import get_bubble_style, get_waterball_bubble_style
from uPtt.ui import theme
from uPtt.ui.theme import FONT_STACK, ASSETS_DIR, render_svg
from uPtt.utils import resolve_display_name
```

  在 `ContactItem.__init__`（`text_container` 的 `main_layout.addSpacing(4)`，Task 2 已改動的版本）之後、`right_container` 建立之前插入靜音 icon label：

```python
        # 3.5 靜音圖示（僅靜音時顯示，位於文字區與時間欄之間，trailing 端）
        self.mute_icon_label = QLabel()
        self.mute_icon_label.setFixedSize(14, 14)
        self.mute_icon_label.setVisible(False)
        main_layout.addWidget(self.mute_icon_label, alignment=Qt.AlignVCenter)
        main_layout.addSpacing(4)
```

  改寫 `_apply_theme`，在既有內容最後加一行呼叫：
```python
    def _apply_theme(self):
        t = theme.active()
        self.avatar_label.setStyleSheet(f"""
            background-color: {t['accent_bg']};
            color: {t['accent']};
            border-radius: 18px;
            font-weight: bold;
            font-size: 14px;
        """)
        self._update_online_dot_style()
        self._update_pin_style()
        self._update_text_colors()
        self.time_label.setStyleSheet(f"font-size: 10px; color: {t['text_faint']}; background: transparent;")
        self.update_unread_style(self.unread_count)
        self._update_mute_icon()
```

  新增 `_update_mute_icon` 並把 Task 4 的占位 `set_muted` 改為完整版（同一個方法名，取代原本兩行的最小版本）：

```python
    def _tinted_icon_pixmap(self, path: str, size: int, color: str) -> QPixmap:
        """把單色 SVG 依主題色重上色：先用 render_svg 取得形狀 alpha 遮罩，
        再用 SourceIn 合成模式把遮罩填成目標顏色，讓同一份 SVG 資產能套三主題。"""
        dpr = self.devicePixelRatioF()
        base = render_svg(path, size, size, dpr)
        if base.isNull():
            return base
        tinted = QPixmap(base.size())
        tinted.setDevicePixelRatio(dpr)
        tinted.fill(Qt.transparent)
        painter = QPainter(tinted)
        painter.drawPixmap(0, 0, base)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), QColor(color))
        painter.end()
        return tinted

    def _update_mute_icon(self):
        if not self._is_muted:
            self.mute_icon_label.setVisible(False)
            return
        t = theme.active()
        path = os.path.join(ASSETS_DIR, "icon_mute.svg")
        pixmap = self._tinted_icon_pixmap(path, 14, t['text_muted'])
        self.mute_icon_label.setPixmap(pixmap)
        self.mute_icon_label.setVisible(True)
        self.mute_icon_label.setToolTip("已靜音通知")

    def set_muted(self, muted: bool):
        """設定並即時反映聯絡人的靜音通知狀態（icon 隨三主題上色）。"""
        self._is_muted = muted
        self._update_mute_icon()
```

  （此版本取代 Task 4 步驟中加入的最小版 `set_muted`；請直接編輯同一個方法，不要留下重複定義。）

  改寫 `get_data()`（`widgets.py:569-582`，Task 2 已加 `custom_name`）再加 `is_muted`：
```python
    def get_data(self) -> dict:
        """返回此項目的完整資料，供重建時使用。"""
        return {
            'ptt_id': self.ptt_id,
            'ptt_id_display': self.ptt_id_display,
            'nickname': self._nickname,
            'custom_name': self._custom_name,
            'unread_count': self.unread_count,
            'is_pinned': self.is_pinned,
            'is_online': self._is_online,
            'is_archived': self._is_archived,
            'is_muted': self._is_muted,
            'last_msg_time': self.time_label.text(),
        }
```

- [ ] 跑測試確認 PASS：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_ui_widgets.py -v
```

- [ ] 寫失敗測試，加到 `tests/test_ui_screens.py`：

```python
@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_load_sessions_shows_mute_icon_for_muted_session(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    db_mock.get_all_sessions.return_value = [
        {
            'account_id': 'myid', 'id': 'bob', 'display_id': 'Bob',
            'nickname': '', 'custom_name': '', 'last_message_text': '',
            'last_message_time': None, 'unread_count': 0, 'is_visible': 1,
            'is_pinned': 0, 'pin_order': 0, 'is_archived': 0, 'is_muted': 1,
        }
    ]
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.load_sessions_from_db()

        widget = window.contact_list.itemWidget(window.contact_list.item(0))
        assert widget._is_muted is True
        assert widget.mute_icon_label.isVisible() is True
```

- [ ] 跑測試確認 FAIL：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_ui_screens.py -k "mute_icon_for_muted" -v
```
  預期：`assert widget._is_muted is True` 失敗（`load_sessions_from_db` 尚未把 `is_muted` 接進 `ContactItem`）。

- [ ] 最小實作。`screens.py:1487-1499`（`load_sessions_from_db` 迴圈內）在 `widget.update_info(...)` 之後加：
```python
            if s.get('is_muted'):
                widget.set_muted(True)
```

  `screens.py:2149-2161`（`_rebuild_contact_item`）在 `if data.get('is_archived'): new_widget.set_archived(True)` 之後加：
```python
        if data.get('is_muted'):
            new_widget.set_muted(True)
```

- [ ] 跑測試確認 PASS：
```
QT_QPA_PLATFORM=offscreen pytest tests/test_ui_screens.py -v
```

- [ ] 全套回歸（本計畫最終驗收指令）：
```
QT_QPA_PLATFORM=offscreen pytest -v
```
  預期：全部通過（既有 188 + 本計畫新增測試）。

- [ ] Commit：
```
git add src/uPtt/ui/widgets.py src/uPtt/ui/screens.py tests/test_ui_widgets.py tests/test_ui_screens.py
git commit -m "feat(ui): add themed mute icon to contact list row"
```

---

## 驗收條件對照表

| spec 條目 | 對應 Task |
|---|---|
| ①刪除（僅本機），要確認對話 | Task 3 |
| ②重新命名聯絡人（本機 alias），空字串清除還原 | Task 2（顯示優先序基礎）+ Task 4（UI action） |
| ③靜音通知（含聯絡人列 icon） | Task 4（toggle + 通知 gate）+ Task 5（icon） |
| ④匯出對話紀錄（純文字 .txt） | Task 4 |
| `delete_message`：刪除生效；重算 last_message | Task 1（db 測試）、Task 3（UI 整合測試） |
| `set_custom_name`：round-trip；`upsert_session` 不覆寫；空字串清除 | Task 1 |
| `set_muted`：round-trip | Task 1 |
| `get_messages(limit=None)` 回傳全部；`limit=50` 行為不變 | Task 1 |
| 顯示優先序單元：custom_name > nickname > display_id | Task 2 |
| 既有 188 測試不變紅 | 每個 Task 結尾的全套回歸步驟 |
