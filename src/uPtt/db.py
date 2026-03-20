import sqlite3
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    uPtt 資料庫管理器，支援多帳號隔離。
    """

    def __init__(self, db_path: str = "uptt_data.db"):
        self.db_path = Path(db_path)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 1. 帳號表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS accounts (
                        id TEXT PRIMARY KEY,
                        display_id TEXT NOT NULL,
                        nickname TEXT,
                        last_login DATETIME,
                        is_active BOOLEAN DEFAULT 0
                    )
                """)

                # 2. 對話會話表 (加入 account_id 隔離與可見度控制)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        account_id TEXT NOT NULL,
                        id TEXT NOT NULL,
                        display_id TEXT NOT NULL,
                        nickname TEXT,
                        last_message_text TEXT,
                        last_message_time DATETIME,
                        unread_count INTEGER DEFAULT 0,
                        is_visible BOOLEAN DEFAULT 1,
                        PRIMARY KEY (account_id, id),
                        FOREIGN KEY (account_id) REFERENCES accounts (id)
                    )
                """)

                # 3. 訊息紀錄表 (加入 account_id 隔離)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        account_id TEXT NOT NULL,
                        session_id TEXT NOT NULL,
                        sender_id TEXT NOT NULL,
                        receiver_id TEXT NOT NULL,
                        content TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        is_read BOOLEAN DEFAULT 0,
                        is_me BOOLEAN NOT NULL,
                        FOREIGN KEY (account_id, session_id) REFERENCES sessions (account_id, id),
                        UNIQUE(account_id, session_id, sender_id, content, timestamp)
                    )
                """)

                # 4. 設定表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
                
                # 索引優化
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_lookup ON messages(account_id, session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_time ON messages(timestamp)")

                # 遷移：為舊資料庫新增釘選相關欄位
                try:
                    cursor.execute("ALTER TABLE sessions ADD COLUMN is_pinned BOOLEAN DEFAULT 0")
                except sqlite3.OperationalError:
                    pass  # 欄位已存在
                try:
                    cursor.execute("ALTER TABLE sessions ADD COLUMN pin_order INTEGER DEFAULT 0")
                except sqlite3.OperationalError:
                    pass  # 欄位已存在

                # 遷移：為舊資料庫新增信件類型與主旨欄位
                try:
                    cursor.execute("ALTER TABLE messages ADD COLUMN mail_type TEXT DEFAULT 'uptt'")
                except sqlite3.OperationalError:
                    pass  # 欄位已存在
                try:
                    cursor.execute("ALTER TABLE messages ADD COLUMN subject TEXT DEFAULT ''")
                except sqlite3.OperationalError:
                    pass  # 欄位已存在

                conn.commit()
                logger.info(f"資料庫初始化成功 (已啟用帳號隔離)：{self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"資料庫初始化失敗：{e}")

    # --- 帳號相關 ---

    def upsert_account(self, ptt_id: str, display_id: str, nickname: str = ""):
        ptt_id_lower = ptt_id.lower()
        try:
            with self._get_connection() as conn:
                # 先把其他帳號設為非使用中
                conn.execute("UPDATE accounts SET is_active = 0")
                # 更新目前帳號
                conn.execute("""
                    INSERT INTO accounts (id, display_id, nickname, last_login, is_active)
                    VALUES (?, ?, ?, ?, 1)
                    ON CONFLICT(id) DO UPDATE SET
                        display_id = excluded.display_id,
                        nickname = excluded.nickname,
                        last_login = excluded.last_login,
                        is_active = 1
                """, (ptt_id_lower, display_id, nickname, datetime.now()))
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"更新帳號失敗：{e}")

    # --- 會話與聯絡人 (需傳入 account_id) ---

    def upsert_session(self, account_id: str, display_id: str, nickname: str = "", set_visible: bool = True):
        """建立或更新會話，set_visible 為 True 時會強制將該會話設為可見。"""
        acc_id_lower = account_id.lower()
        contact_id_lower = display_id.lower()
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO sessions (account_id, id, display_id, nickname, is_visible)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(account_id, id) DO UPDATE SET
                        display_id = excluded.display_id,
                        nickname = CASE WHEN excluded.nickname != '' THEN excluded.nickname ELSE sessions.nickname END,
                        is_visible = CASE WHEN ? THEN 1 ELSE sessions.is_visible END
                """, (acc_id_lower, contact_id_lower, display_id, nickname, 1 if set_visible else 1, 1 if set_visible else 0))
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"更新會話失敗：{e}")

    def hide_session(self, account_id: str, session_id: str):
        """關閉對話：將會話設為隱藏，下次登入不會顯示。"""
        try:
            with self._get_connection() as conn:
                conn.execute("UPDATE sessions SET is_visible = 0 WHERE account_id = ? AND id = ?", 
                             (account_id.lower(), session_id.lower()))
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"隱藏會話失敗：{e}")

    def get_all_sessions(self, account_id: str) -> List[Dict[str, Any]]:
        """取得特定帳號的所有「可見」會話清單。釘選項目排在最前面。"""
        try:
            with self._get_connection() as conn:
                rows = conn.execute("""
                    SELECT * FROM sessions
                    WHERE account_id = ? AND is_visible = 1
                    ORDER BY is_pinned DESC,
                             CASE WHEN is_pinned=1 THEN pin_order ELSE 9999999 END ASC,
                             last_message_time DESC,
                             id ASC
                """, (account_id.lower(),)).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error:
            return []

    def set_pin_session(self, account_id: str, session_id: str, is_pinned: bool, pin_order: int = 0):
        """設定會話的釘選狀態與順序。"""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE sessions SET is_pinned = ?, pin_order = ? WHERE account_id = ? AND id = ?",
                    (1 if is_pinned else 0, pin_order, account_id.lower(), session_id.lower())
                )
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"更新釘選狀態失敗：{e}")

    def update_pin_orders(self, account_id: str, pinned_ids_in_order: List[str]):
        """更新釘選項目的排序，pinned_ids_in_order 為已排序的小寫 ID 清單。"""
        try:
            with self._get_connection() as conn:
                for order, session_id in enumerate(pinned_ids_in_order):
                    conn.execute(
                        "UPDATE sessions SET pin_order = ? WHERE account_id = ? AND id = ? AND is_pinned = 1",
                        (order, account_id.lower(), session_id.lower())
                    )
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"更新釘選排序失敗：{e}")

    # --- 訊息相關 (需傳入 account_id) ---

    def save_message(self, account_id: str, session_id: str, sender_id: str,
                     receiver_id: str, content: str, timestamp: datetime, is_me: bool,
                     mail_type: str = 'uptt', subject: str = '') -> bool:
        acc_id_lower = account_id.lower()
        session_id_lower = session_id.lower()
        try:
            with self._get_connection() as conn:
                # 1. 插入訊息 (使用 INSERT OR IGNORE 防止重複)
                cursor = conn.execute("""
                    INSERT OR IGNORE INTO messages (account_id, session_id, sender_id, receiver_id, content, timestamp, is_me, is_read, mail_type, subject)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (acc_id_lower, session_id_lower, sender_id.lower(), receiver_id.lower(),
                      content, timestamp, 1 if is_me else 0, 1 if is_me else 0, mail_type, subject))
                
                # 如果沒有新資料插入 (rows_affected == 0), 代表是重複訊息
                if cursor.rowcount == 0:
                    return False

                # 2. 更新會話摘要並強制設為可見 (收到新訊息或發送訊息時)
                if is_me:
                    conn.execute("""
                        UPDATE sessions SET 
                            last_message_text = ?, 
                            last_message_time = ?,
                            is_visible = 1
                        WHERE account_id = ? AND id = ?
                    """, (content, timestamp, acc_id_lower, session_id_lower))
                else:
                    conn.execute("""
                        UPDATE sessions SET 
                            last_message_text = ?, 
                            last_message_time = ?,
                            unread_count = unread_count + 1,
                            is_visible = 1
                        WHERE account_id = ? AND id = ?
                    """, (content, timestamp, acc_id_lower, session_id_lower))
                
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"儲存訊息失敗：{e}")
            return False

    def get_messages(self, account_id: str, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """取得特定帳號與特定對象的歷史訊息。"""
        try:
            with self._get_connection() as conn:
                rows = conn.execute("""
                    SELECT * FROM (
                        SELECT * FROM messages 
                        WHERE account_id = ? AND session_id = ? 
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    ) ORDER BY timestamp ASC
                """, (account_id.lower(), session_id.lower(), limit)).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error:
            return []

    def mark_as_read(self, account_id: str, session_id: str):
        acc_id_lower = account_id.lower()
        session_id_lower = session_id.lower()
        try:
            with self._get_connection() as conn:
                conn.execute("UPDATE messages SET is_read = 1 WHERE account_id = ? AND session_id = ?", 
                             (acc_id_lower, session_id_lower))
                conn.execute("UPDATE sessions SET unread_count = 0 WHERE account_id = ? AND id = ?", 
                             (acc_id_lower, session_id_lower))
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"標記已讀失敗：{e}")

    # --- 設定 ---
    def set_config(self, key: str, value: Any):
        try:
            with self._get_connection() as conn:
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", 
                             (key, json.dumps(value)))
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"儲存設定失敗：{e}")

    def get_config(self, key: str, default: Any = None) -> Any:
        try:
            with self._get_connection() as conn:
                row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
                return json.loads(row['value']) if row else default
        except sqlite3.Error:
            return default
