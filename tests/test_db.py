import pytest
import os
import sqlite3
from datetime import datetime, timedelta
from src.uPtt.db import DatabaseManager

@pytest.fixture
def db_manager(tmp_path):
    db_file = tmp_path / "test_uptt.db"
    manager = DatabaseManager(str(db_file))
    return manager

def test_db_init(tmp_path):
    db_file = tmp_path / "init_test.db"
    manager = DatabaseManager(str(db_file))
    assert db_file.exists()
    
    # Check if tables are created
    with sqlite3.connect(str(db_file)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accounts'")
        assert cursor.fetchone() is not None
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
        assert cursor.fetchone() is not None
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
        assert cursor.fetchone() is not None
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
        assert cursor.fetchone() is not None

def test_upsert_account(db_manager):
    db_manager.upsert_account("TestUser", "DisplayUser", "MyNickname")
    
    with db_manager._get_connection() as conn:
        row = conn.execute("SELECT * FROM accounts WHERE id = 'testuser'").fetchone()
        assert row is not None
        assert row['display_id'] == "DisplayUser"
        assert row['nickname'] == "MyNickname"
        assert row['is_active'] == 1

    # Update account
    db_manager.upsert_account("TestUser", "NewDisplay", "NewNickname")
    with db_manager._get_connection() as conn:
        row = conn.execute("SELECT * FROM accounts WHERE id = 'testuser'").fetchone()
        assert row['display_id'] == "NewDisplay"
        assert row['nickname'] == "NewNickname"

    # Multiple accounts, only one active
    db_manager.upsert_account("OtherUser", "OtherDisplay")
    with db_manager._get_connection() as conn:
        row1 = conn.execute("SELECT is_active FROM accounts WHERE id = 'testuser'").fetchone()
        row2 = conn.execute("SELECT is_active FROM accounts WHERE id = 'otheruser'").fetchone()
        assert row1['is_active'] == 0
        assert row2['is_active'] == 1

def test_upsert_session(db_manager):
    account_id = "testuser"
    db_manager.upsert_account(account_id, account_id)
    
    db_manager.upsert_session(account_id, "ContactA", "NicknameA")
    sessions = db_manager.get_all_sessions(account_id)
    assert len(sessions) == 1
    assert sessions[0]['id'] == "contacta"
    assert sessions[0]['display_id'] == "ContactA"
    assert sessions[0]['nickname'] == "NicknameA"
    assert sessions[0]['is_visible'] == 1

    # Update session nickname
    db_manager.upsert_session(account_id, "ContactA", "NewNicknameA")
    sessions = db_manager.get_all_sessions(account_id)
    assert sessions[0]['nickname'] == "NewNicknameA"

    # Empty nickname should not overwrite
    db_manager.upsert_session(account_id, "ContactA", "")
    sessions = db_manager.get_all_sessions(account_id)
    assert sessions[0]['nickname'] == "NewNicknameA"

def test_hide_session(db_manager):
    account_id = "testuser"
    db_manager.upsert_session(account_id, "ContactA")
    
    assert len(db_manager.get_all_sessions(account_id)) == 1
    db_manager.hide_session(account_id, "ContactA")
    assert len(db_manager.get_all_sessions(account_id)) == 0

def test_save_and_get_messages(db_manager):
    account_id = "testuser"
    session_id = "contacta"
    db_manager.upsert_session(account_id, session_id)
    
    now = datetime.now()
    # Save a message from me
    success = db_manager.save_message(account_id, session_id, account_id, session_id, "Hello", now, True)
    assert success is True
    
    messages = db_manager.get_messages(account_id, session_id)
    assert len(messages) == 1
    assert messages[0]['content'] == "Hello"
    assert messages[0]['is_me'] == 1
    
    # Save duplicate message (should fail/return False due to UNIQUE constraint)
    success = db_manager.save_message(account_id, session_id, account_id, session_id, "Hello", now, True)
    assert success is False
    
    # Save a message from contact
    later = now + timedelta(seconds=1)
    db_manager.save_message(account_id, session_id, session_id, account_id, "Hi there", later, False)
    
    messages = db_manager.get_messages(account_id, session_id)
    assert len(messages) == 2
    assert messages[1]['content'] == "Hi there"
    assert messages[1]['is_me'] == 0
    
    # Check session unread count
    sessions = db_manager.get_all_sessions(account_id)
    assert sessions[0]['unread_count'] == 1
    assert sessions[0]['last_message_text'] == "Hi there"

def test_mark_as_read(db_manager):
    account_id = "testuser"
    session_id = "contacta"
    db_manager.upsert_session(account_id, session_id)
    db_manager.save_message(account_id, session_id, session_id, account_id, "Unread", datetime.now(), False)
    
    sessions = db_manager.get_all_sessions(account_id)
    assert sessions[0]['unread_count'] == 1
    
    db_manager.mark_as_read(account_id, session_id)
    sessions = db_manager.get_all_sessions(account_id)
    assert sessions[0]['unread_count'] == 0
    
    messages = db_manager.get_messages(account_id, session_id)
    assert all(m['is_read'] == 1 for m in messages)

def test_config(db_manager):
    db_manager.set_config("theme", "dark")
    assert db_manager.get_config("theme") == "dark"
    
    db_manager.set_config("count", 42)
    assert db_manager.get_config("count") == 42
    
    db_manager.set_config("complex", {"a": 1, "b": [2, 3]})
    assert db_manager.get_config("complex") == {"a": 1, "b": [2, 3]}
    
    assert db_manager.get_config("nonexistent", "default") == "default"

def test_error_handling(db_manager, monkeypatch):
    # Mock _get_connection to raise an error
    def mock_conn_error(*args, **kwargs):
        raise sqlite3.Error("Mock error")
    
    monkeypatch.setattr(db_manager, "_get_connection", mock_conn_error)
    
    # These should not raise exceptions but log errors and return gracefully
    db_manager.upsert_account("user", "display")
    db_manager.upsert_session("user", "contact")
    db_manager.hide_session("user", "contact")
    assert db_manager.get_all_sessions("user") == []
    with pytest.raises(sqlite3.Error):
        db_manager.save_message("user", "session", "s", "r", "c", datetime.now(), True)
    assert db_manager.get_messages("user", "session") == []
    db_manager.mark_as_read("user", "session")
    db_manager.set_config("k", "v")
    assert db_manager.get_config("k", "default") == "default"


def test_last_message_time_never_goes_backwards(db_manager):
    """Fix #4: save_message should not let last_message_time regress to an older timestamp."""
    account_id = "testuser"
    session_id = "contacta"
    db_manager.upsert_session(account_id, session_id)

    newer = datetime(2025, 6, 1, 12, 0, 0)
    older = datetime(2025, 5, 1, 12, 0, 0)

    # Save newer message first
    db_manager.save_message(account_id, session_id, session_id, account_id, "New msg", newer, False)
    sessions = db_manager.get_all_sessions(account_id)
    assert sessions[0]['last_message_text'] == "New msg"

    # Save older message — last_message_time and text should NOT regress
    db_manager.save_message(account_id, session_id, session_id, account_id, "Old msg", older, False)
    sessions = db_manager.get_all_sessions(account_id)
    assert sessions[0]['last_message_text'] == "New msg"


# ── 新增測試：archive / pin / delete ──────────────────────────

def test_archive_session(db_manager):
    account_id = "testuser"
    session_id = "friend1"
    db_manager.upsert_account(account_id, account_id)
    db_manager.upsert_session(account_id, session_id)

    assert db_manager.is_session_archived(account_id, session_id) is False
    db_manager.archive_session(account_id, session_id)
    assert db_manager.is_session_archived(account_id, session_id) is True

    # 封存的 session 仍然可見
    sessions = db_manager.get_all_sessions(account_id)
    assert len(sessions) == 1
    assert sessions[0]['is_archived'] == 1


def test_delete_session(db_manager):
    account_id = "testuser"
    session_id = "todelete"
    db_manager.upsert_account(account_id, account_id)
    db_manager.upsert_session(account_id, session_id)
    db_manager.save_message(account_id, session_id, session_id, account_id, "msg", datetime.now(), False)

    assert len(db_manager.get_messages(account_id, session_id)) == 1

    db_manager.delete_session(account_id, session_id)

    # session 與 messages 都應該被刪除
    assert len(db_manager.get_all_sessions(account_id)) == 0
    assert len(db_manager.get_messages(account_id, session_id)) == 0


def test_pin_session(db_manager):
    account_id = "testuser"
    db_manager.upsert_account(account_id, account_id)
    db_manager.upsert_session(account_id, "aaa")
    db_manager.upsert_session(account_id, "bbb")

    db_manager.set_pin_session(account_id, "bbb", True, 0)
    sessions = db_manager.get_all_sessions(account_id)
    # 釘選的 bbb 應排在前面
    assert sessions[0]['id'] == "bbb"
    assert sessions[0]['is_pinned'] == 1


def test_update_pin_orders(db_manager):
    account_id = "testuser"
    db_manager.upsert_account(account_id, account_id)
    db_manager.upsert_session(account_id, "aaa")
    db_manager.upsert_session(account_id, "bbb")
    db_manager.set_pin_session(account_id, "aaa", True, 0)
    db_manager.set_pin_session(account_id, "bbb", True, 1)

    # 交換順序
    db_manager.update_pin_orders(account_id, ["bbb", "aaa"])
    sessions = db_manager.get_all_sessions(account_id)
    assert sessions[0]['id'] == "bbb"
    assert sessions[1]['id'] == "aaa"


def test_migration_adds_send_status_to_old_db(tmp_path):
    """A pre-existing DB lacking send_status should gain the column on next init,
    with existing self-sent rows defaulting to 'sent'."""
    db_path = tmp_path / "legacy.db"
    # Build a legacy schema without send_status
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                receiver_id TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_read BOOLEAN DEFAULT 0,
                is_me BOOLEAN NOT NULL,
                UNIQUE(account_id, session_id, sender_id, content, timestamp)
            )
        """)
        conn.execute("""
            INSERT INTO messages (account_id, session_id, sender_id, receiver_id, content, is_me)
            VALUES ('alice', 'bob', 'alice', 'bob', 'old', 1)
        """)
        conn.commit()

    # Re-opening through DatabaseManager triggers the migration
    DatabaseManager(str(db_path))

    with sqlite3.connect(str(db_path)) as conn:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(messages)").fetchall()]
        assert 'send_status' in cols
        # Existing row defaults to 'sent'
        row = conn.execute("SELECT send_status FROM messages WHERE content = 'old'").fetchone()
        assert row[0] == 'sent'


def test_send_status_column_exists_with_default_sent(db_manager):
    """Migration: messages table must have send_status column defaulting to 'sent'."""
    with db_manager._get_connection() as conn:
        cols = {row['name']: row for row in conn.execute("PRAGMA table_info(messages)").fetchall()}
        assert 'send_status' in cols
        assert cols['send_status']['dflt_value'] in ("'sent'", '"sent"')


def test_save_pending_then_update_status(db_manager):
    """Round trip: save_pending_message → update_message_status drives send_status."""
    account_id = "alice"
    session_id = "bob"
    db_manager.upsert_account(account_id, account_id)
    db_manager.upsert_session(account_id, session_id)

    ts = datetime(2026, 4, 24, 12, 0, 0)
    msg_id = db_manager.save_pending_message(account_id, session_id, account_id, session_id, "ping", ts)
    assert isinstance(msg_id, int) and msg_id > 0

    msgs = db_manager.get_messages(account_id, session_id)
    assert len(msgs) == 1
    assert msgs[0]['send_status'] == 'pending'
    assert msgs[0]['is_me'] == 1

    assert db_manager.update_message_status(msg_id, 'sent') is True
    msgs = db_manager.get_messages(account_id, session_id)
    assert msgs[0]['send_status'] == 'sent'

    assert db_manager.update_message_status(msg_id, 'failed') is True
    msgs = db_manager.get_messages(account_id, session_id)
    assert msgs[0]['send_status'] == 'failed'


def test_save_pending_returns_none_on_duplicate(db_manager):
    """UNIQUE constraint: same (account, session, sender, content, timestamp) twice → None."""
    account_id = "alice"
    session_id = "bob"
    db_manager.upsert_account(account_id, account_id)
    db_manager.upsert_session(account_id, session_id)

    ts = datetime(2026, 4, 24, 12, 0, 0)
    first = db_manager.save_pending_message(account_id, session_id, account_id, session_id, "dup", ts)
    second = db_manager.save_pending_message(account_id, session_id, account_id, session_id, "dup", ts)
    assert first is not None
    assert second is None


def test_save_pending_updates_session_summary(db_manager):
    """Pending messages should also surface in the contact list (last_message_text)."""
    account_id = "alice"
    session_id = "bob"
    db_manager.upsert_account(account_id, account_id)
    db_manager.upsert_session(account_id, session_id)

    ts = datetime(2026, 4, 24, 12, 0, 0)
    db_manager.save_pending_message(account_id, session_id, account_id, session_id, "summary check", ts)
    sessions = db_manager.get_all_sessions(account_id)
    assert sessions[0]['last_message_text'] == "summary check"


def test_update_message_status_rejects_unknown_value(db_manager):
    account_id = "alice"
    session_id = "bob"
    db_manager.upsert_account(account_id, account_id)
    db_manager.upsert_session(account_id, session_id)
    msg_id = db_manager.save_pending_message(
        account_id, session_id, account_id, session_id, "x", datetime.now()
    )
    with pytest.raises(ValueError):
        db_manager.update_message_status(msg_id, "delivered")


def test_fail_dangling_pending_marks_only_account_rows(db_manager):
    """殘留 pending 訊息只清理目標帳號，不影響其他帳號或非 pending 狀態。"""
    db_manager.upsert_account("alice", "alice")
    db_manager.upsert_account("bob", "bob")
    db_manager.upsert_session("alice", "carol")
    db_manager.upsert_session("bob", "dave")

    pending_id = db_manager.save_pending_message(
        "alice", "carol", "alice", "carol", "stuck", datetime(2026, 1, 1, 8, 0, 0)
    )
    sent_id = db_manager.save_pending_message(
        "alice", "carol", "alice", "carol", "ok", datetime(2026, 1, 1, 9, 0, 0)
    )
    db_manager.update_message_status(sent_id, 'sent')
    other_pending_id = db_manager.save_pending_message(
        "bob", "dave", "bob", "dave", "stuck-other", datetime(2026, 1, 1, 10, 0, 0)
    )

    reaped = db_manager.fail_dangling_pending("alice")
    assert reaped == 1

    with db_manager._get_connection() as conn:
        rows = {r['id']: r['send_status'] for r in conn.execute("SELECT id, send_status FROM messages").fetchall()}
        assert rows[pending_id] == 'failed'
        assert rows[sent_id] == 'sent'
        assert rows[other_pending_id] == 'pending'


def test_save_message_default_send_status(db_manager):
    """Existing save_message path (incoming + own backups) must default to 'sent'
    so historical messages still render ✓."""
    account_id = "alice"
    session_id = "bob"
    db_manager.upsert_account(account_id, account_id)
    db_manager.upsert_session(account_id, session_id)

    ts = datetime(2026, 4, 24, 12, 0, 0)
    db_manager.save_message(account_id, session_id, session_id, account_id, "incoming", ts, False)
    msgs = db_manager.get_messages(account_id, session_id)
    assert msgs[0]['send_status'] == 'sent'


def test_get_messages_limit(db_manager):
    account_id = "testuser"
    session_id = "friend"
    db_manager.upsert_account(account_id, account_id)
    db_manager.upsert_session(account_id, session_id)
    for i in range(10):
        db_manager.save_message(
            account_id, session_id, session_id, account_id,
            f"msg{i}", datetime(2025, 1, 1, 12, i, 0), False
        )

    # limit=5 should return the 5 newest
    msgs = db_manager.get_messages(account_id, session_id, limit=5)
    assert len(msgs) == 5
    assert msgs[0]['content'] == "msg5"
    assert msgs[-1]['content'] == "msg9"
