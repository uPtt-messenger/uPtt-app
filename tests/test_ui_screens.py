import pytest
from datetime import datetime
from PySide6.QtCore import Qt
from unittest.mock import MagicMock, patch, ANY
import os

# Set offscreen platform for CI/CLI environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from src.uPtt.ui.screens import LoginWindow, MainWindow
from src.uPtt.ptt import UPttService
from src.uPtt.worker import PTTWorker, QueryWorker
from src.uPtt.ui.widgets import ContactItem

@pytest.fixture
def ptt_service_mock():
    service = MagicMock(spec=UPttService)
    service.ptt_id = "MyID"
    service.ptt_pw = "mypass"
    return service

@pytest.fixture
def ptt_query_service_mock():
    service = MagicMock(spec=UPttService)
    service.ptt_id = "MyID"
    service.ptt_pw = "mypass"
    return service

@pytest.fixture
def db_mock():
    db = MagicMock()
    db.get_all_sessions.return_value = []
    db.get_messages.return_value = []
    return db

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
    
    window.username_input.setText("")
    window.password_input.setText("testpass")
    
    with patch.object(window, 'login_requested') as mock_signal:
        qtbot.mouseClick(window.login_btn, Qt.LeftButton)
        mock_signal.emit.assert_not_called()
    
    assert window.error_label.text() == "請輸入完整帳號密碼"

def test_login_window_version_label(qtbot):
    from uPtt import __version__
    window = LoginWindow()
    qtbot.addWidget(window)
    assert window.version_label.text() == f"v{__version__}"

@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_main_window_init(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        assert window.windowTitle() == "uPtt"
        assert window.central_stack.currentIndex() == 0

@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_on_login_result_success(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.on_login_result(True, "Login Success")
        assert window.central_stack.currentIndex() == 1

@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_on_login_result_failure(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.on_login_result(False, "Failed")
        assert window.central_stack.currentIndex() == 0

@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_first_time_login_shows_scan_screen(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window._is_first_time_login = True
        window.on_login_result(True, "Login Success")
        assert window.central_stack.currentIndex() == 2


@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_scan_complete_transitions_to_chat(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.central_stack.setCurrentIndex(2)
        window._on_scan_complete()
        assert window.central_stack.currentIndex() == 1


@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_main_window_close_chat(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.add_or_select_contact("TestUser")
        window.close_current_chat()
        assert window.contact_list.count() == 0

@patch('src.uPtt.ui.screens.QMessageBox')
@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_main_window_block_user(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, mock_msg, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.add_or_select_contact("BadUser")
        window.handle_contact_action("BadUser", "BLOCK")
        assert "baduser" in window.blocked_users

@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_on_new_message_blocked(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.blocked_users.add("baduser")
        msg_data = {'sender': 'BadUser', 'text': 'Hi', 'time': '10:00', 'full_author': 'BadUser'}
        window.on_new_message(msg_data)
        assert "baduser" not in window.chat_histories

@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_on_user_info_result(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.add_or_select_contact("testuser")

        # Manually trigger on_user_info_result
        data = {'ptt_id': 'TestUser', 'nickname': 'CoolNick'}
        window.on_user_info_result(data)

        # Verify UI update
        item = window.contact_list.item(0)
        widget = window.contact_list.itemWidget(item)
        assert widget.id_label.text() == "TestUser"
        assert "(CoolNick)" in widget.nickname_label.text()

@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_load_sessions_from_db(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        db_mock.get_all_sessions.return_value = [{'id': 'u1', 'display_id': 'U1', 'nickname': 'N1', 'unread_count': 0}]
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.load_sessions_from_db()
        assert window.contact_list.count() == 1

@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_handle_send(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.add_or_select_contact("target")
        window.message_edit.setText("Hello")
        with patch.object(window, 'send_requested') as mock_signal:
            window.handle_send()
            mock_signal.emit.assert_called_once()
            args = mock_signal.emit.call_args[0]
            assert args[0] == "target"
            assert args[1] == "Hello"
            assert isinstance(args[2], datetime)

@patch('src.uPtt.ui.screens.QMessageBox')
@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_handle_logout(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, mock_msg, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        mock_msg.question.return_value = mock_msg.Yes
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.handle_logout()
        assert window.central_stack.currentIndex() == 0

@patch('PySide6.QtCore.QMetaObject.invokeMethod')
@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_fully_quit(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, mock_invoke, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.fully_quit()
        # Should call invokeMethod for worker.stop
        mock_invoke.assert_called()

@patch('PySide6.QtCore.QMetaObject.invokeMethod')
@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_fully_quit_is_reentrant_safe(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, mock_invoke, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    # Regression: closeEvent can re-fire during QApplication.quit tear-down,
    # so fully_quit must short-circuit on re-entry (see PRs #15 / #17).
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window._stop_all_threads = MagicMock()
        window.fully_quit()
        window.fully_quit()
        assert window._stop_all_threads.call_count == 1

def test_render_svg_exists():
    from src.uPtt.ui.screens import render_svg
    with open("test_pixmap.svg", "w") as f:
        f.write('<svg width="10" height="10"><rect width="10" height="10" /></svg>')
    try:
        pixmap = render_svg("test_pixmap.svg", 10, 10)
        assert not pixmap.isNull()
    finally:
        if os.path.exists("test_pixmap.svg"): os.remove("test_pixmap.svg")


@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_send_result_matches_correct_message_fifo(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    """Fix #2: on_send_result should match send results in FIFO order across different targets."""
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)

        # Send message to contact A
        window.add_or_select_contact("ContactA")
        window.message_edit.setText("MsgA")
        with patch.object(window, 'send_requested'):
            window.handle_send()

        # Send message to contact B
        window.add_or_select_contact("ContactB")
        window.message_edit.setText("MsgB")
        with patch.object(window, 'send_requested'):
            window.handle_send()

        # First result should match contactA's pending message
        window.on_send_result(True, "")
        msg_a = [m for m in window.chat_histories.get('contacta', []) if m.get('is_me')]
        assert len(msg_a) == 1
        assert msg_a[0]['send_status'] == 'sent'

        # Second result should match contactB's pending message
        window.on_send_result(True, "")
        msg_b = [m for m in window.chat_histories.get('contactb', []) if m.get('is_me')]
        assert len(msg_b) == 1
        assert msg_b[0]['send_status'] == 'sent'


@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_send_result_fifo_same_contact(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    """Fix #2: Two rapid sends to same contact — results should match in FIFO order."""
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)

        window.add_or_select_contact("Target")
        window.message_edit.setText("First")
        with patch.object(window, 'send_requested'):
            window.handle_send()

        window.message_edit.setText("Second")
        with patch.object(window, 'send_requested'):
            window.handle_send()

        msgs = window.chat_histories['target']
        assert len(msgs) == 2
        assert msgs[0]['send_status'] == 'pending'
        assert msgs[1]['send_status'] == 'pending'

        # First result should mark the FIRST pending message
        window.on_send_result(True, "")
        assert msgs[0]['send_status'] == 'sent'
        assert msgs[1]['send_status'] == 'pending'

        # Second result should mark the SECOND pending message
        window.on_send_result(True, "")
        assert msgs[1]['send_status'] == 'sent'


@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_duplicate_message_does_not_inflate_unread(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    """Fix #1: Duplicate messages should not increment unread count."""
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)

        now = datetime.now()
        window.add_or_select_contact("SenderA")
        window.current_chat_id = None  # simulate not viewing this chat

        msg_data = {
            'sender': 'SenderA', 'text': 'Hello',
            'time': now.strftime("%H:%M"), 'full_author': 'SenderA',
            'timestamp': now, 'mail_type': 'uptt',
        }
        window.on_new_message(msg_data)
        assert window.unread_counts.get('sendera', 0) == 1

        # Send the exact same message again (duplicate)
        window.on_new_message(msg_data)
        assert window.unread_counts.get('sendera', 0) == 1  # should NOT be 2


@patch('src.uPtt.ui.screens.QMessageBox')
@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_draft_cleared_on_delete(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, mock_msg, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    """Fix #5: session_drafts should be cleared when a session is deleted."""
    with patch('os.path.exists', return_value=True):
        mock_msg.question.return_value = mock_msg.Yes
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)

        window.add_or_select_contact("DraftUser")
        window.session_drafts['draftuser'] = "unsent text"

        window.handle_contact_action("DraftUser", "DELETE")
        assert 'draftuser' not in window.session_drafts


@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_draft_cleared_on_close(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    """Fix #5: session_drafts should be cleared when a session is closed."""
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)

        window.add_or_select_contact("CloseUser")
        window.session_drafts['closeuser'] = "draft text"

        window.handle_contact_action("CloseUser", "CLOSE")
        assert 'closeuser' not in window.session_drafts
