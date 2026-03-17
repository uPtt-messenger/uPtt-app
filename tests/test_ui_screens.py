import pytest
from PySide6.QtCore import Qt
from unittest.mock import MagicMock, patch
import os

# Set offscreen platform for CI/CLI environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from src.uPtt.ui.screens import LoginWindow, MainWindow
from src.uPtt.ptt import UPttService
from src.uPtt.worker import PTTWorker

@pytest.fixture
def ptt_service_mock():
    return MagicMock(spec=UPttService)

@pytest.fixture
def db_mock():
    return MagicMock()

def test_login_window_emit_signal(qtbot):
    window = LoginWindow()
    qtbot.addWidget(window)
    
    window.username_input.setText("testuser")
    window.password_input.setText("testpass")
    
    with qtbot.waitSignal(window.login_requested) as blocker:
        qtbot.mouseClick(window.login_btn, Qt.LeftButton)
    
    assert blocker.args == ["testuser", "testpass"]
    assert window.login_btn.isEnabled() is False
    assert window.login_btn.text() == "正在連線..."

def test_login_window_empty_input(qtbot):
    window = LoginWindow()
    qtbot.addWidget(window)
    
    # Try login with empty username
    window.username_input.setText("")
    window.password_input.setText("testpass")
    
    with patch.object(window, 'login_requested') as mock_signal:
        qtbot.mouseClick(window.login_btn, Qt.LeftButton)
        mock_signal.emit.assert_not_called()
    
    assert window.error_label.text() == "請輸入完整帳號密碼"
    # Use isHidden() or check text because isVisible() can be False in offscreen mode
    assert window.error_label.text() != ""

def test_login_window_version_label(qtbot):
    from uPtt import __version__
    window = LoginWindow()
    qtbot.addWidget(window)
    assert window.version_label.text() == f"v{__version__}"

@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_main_window_init(mock_qthread, mock_worker, qtbot, ptt_service_mock, db_mock):
    # Mock assets to avoid FileNotFoundError
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, db_mock)
        qtbot.addWidget(window)
        
        assert window.windowTitle() == "uPtt"
        assert window.central_stack.count() == 2
        # First screen should be login
        assert window.central_stack.currentIndex() == 0

@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_on_login_result_success(mock_qthread, mock_worker, qtbot, ptt_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, db_mock)
        qtbot.addWidget(window)
        
        # Simulate successful login signal from worker
        ptt_service_mock.ptt_id = "CorrectID"
        window.on_login_result(True, "Login Success")
        
        # Should switch to chat screen (index 1)
        assert window.central_stack.currentIndex() == 1
        assert "CorrectID" in window.user_id_label.text()

@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_on_login_result_failure(mock_qthread, mock_worker, qtbot, ptt_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, db_mock)
        qtbot.addWidget(window)
        
        # Simulate failed login
        window.on_login_result(False, "Invalid Password")
        
        # Should stay on login screen
        assert window.central_stack.currentIndex() == 0
        assert window.login_screen.error_label.text() == "Invalid Password"

@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_main_window_close_chat(mock_qthread, mock_worker, qtbot, ptt_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        ptt_service_mock.ptt_id = "MyID"
        window = MainWindow(ptt_service_mock, db_mock)
        qtbot.addWidget(window)
        
        # Add a contact
        window.add_or_select_contact("TestUser")
        assert window.contact_list.count() == 1
        assert window.current_chat_id == "testuser"
        
        # Close the chat
        window.close_current_chat()
        
        # Should be removed from list and current_chat_id reset
        assert window.contact_list.count() == 0
        assert window.current_chat_id is None

@patch('src.uPtt.ui.screens.QMessageBox')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_main_window_block_user(mock_qthread, mock_worker, mock_qmessagebox, qtbot, ptt_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        ptt_service_mock.ptt_id = "MyID"
        window = MainWindow(ptt_service_mock, db_mock)
        qtbot.addWidget(window)
        
        window.add_or_select_contact("BadUser")
        assert "baduser" not in window.blocked_users
        
        # Block the user (MOCK QMessageBox to auto-accept if any)
        window.handle_contact_action("BadUser", "BLOCK")
        
        assert "baduser" in window.blocked_users
        assert window.contact_list.count() == 0
        mock_qmessagebox.information.assert_called_once()

@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_on_new_message_blocked(mock_qthread, mock_worker, qtbot, ptt_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, db_mock)
        qtbot.addWidget(window)

        window.blocked_users.add("baduser")

        # Simulate new message from blocked user
        msg_data = {
            'sender': 'BadUser',
            'text': 'Hello',
            'time': '12:00',
            'full_author': 'BadUser (BadGuy)'
        }
        window.on_new_message(msg_data)

        # Should NOT be added to history or list
        assert "baduser" not in window.chat_histories
        assert window.contact_list.count() == 0

@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_on_new_message_new_contact_no_duplicate(mock_qthread, mock_worker, qtbot, ptt_service_mock, db_mock):
    """新聯絡人第一次傳訊息時，訊息不應重複出現在 chat_histories"""
    from datetime import datetime
    with patch('os.path.exists', return_value=True):
        ptt_service_mock.ptt_id = "MyID"

        # 模擬 DB 已有這則訊息（worker 先存入 DB 後才發射 signal）
        msg_time = datetime(2026, 3, 17, 7, 59, 0)
        db_mock.get_messages.return_value = [{
            'content': '安安，Mac 封測中',
            'timestamp': msg_time,
            'is_me': 0,
            'sender_id': 'codingman',
            'receiver_id': 'myid',
        }]
        db_mock.get_all_sessions.return_value = []

        window = MainWindow(ptt_service_mock, db_mock)
        qtbot.addWidget(window)

        # 確認 codingman 不在 chat_histories（全新聯絡人）
        assert 'codingman' not in window.chat_histories

        msg_data = {
            'sender': 'CodingMan',
            'text': '安安，Mac 封測中',
            'time': '07:59',
            'full_author': 'CodingMan (bug maker)',
            'timestamp': msg_time,
        }
        window.on_new_message(msg_data)

        # 修復後：chat_histories 只應有 1 筆（由 on_contact_selected 從 DB 載入）
        assert 'codingman' in window.chat_histories
        assert len(window.chat_histories['codingman']) == 1
