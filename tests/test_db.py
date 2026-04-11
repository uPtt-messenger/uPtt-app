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
