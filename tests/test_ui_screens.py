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
    # 每次 save_pending_message 回傳遞增的 row id，模擬 SQLite 的 lastrowid
    counter = {"n": 0}
    def _save_pending(*args, **kwargs):
        counter["n"] += 1
        return counter["n"]
    db.save_pending_message.side_effect = _save_pending
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
            assert isinstance(args[3], int) and args[3] > 0  # msg_id from save_pending_message
        db_mock.save_pending_message.assert_called_once()

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
def test_send_result_matches_correct_message_by_id(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    """on_send_result must locate the pending bubble by msg_id, even when results
    arrive out of order or the user switches chats first (Issue #13)."""
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)

        window.add_or_select_contact("ContactA")
        window.message_edit.setText("MsgA")
        with patch.object(window, 'send_requested'):
            window.handle_send()
        msg_id_a = window.chat_histories['contacta'][-1]['msg_id']

        window.add_or_select_contact("ContactB")
        window.message_edit.setText("MsgB")
        with patch.object(window, 'send_requested'):
            window.handle_send()
        msg_id_b = window.chat_histories['contactb'][-1]['msg_id']

        # B's result arrives first (out of order vs send order)
        window.on_send_result(msg_id_b, True, "")
        assert window.chat_histories['contactb'][-1]['send_status'] == 'sent'
        assert window.chat_histories['contacta'][-1]['send_status'] == 'pending'

        window.on_send_result(msg_id_a, True, "")
        assert window.chat_histories['contacta'][-1]['send_status'] == 'sent'


@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_send_result_two_pending_same_contact(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    """Two rapid sends to same contact — each result should match its own bubble by msg_id."""
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)

        window.add_or_select_contact("Target")
        window.message_edit.setText("First")
        with patch.object(window, 'send_requested'):
            window.handle_send()
        first_id = window.chat_histories['target'][0]['msg_id']

        window.message_edit.setText("Second")
        with patch.object(window, 'send_requested'):
            window.handle_send()
        second_id = window.chat_histories['target'][1]['msg_id']

        msgs = window.chat_histories['target']
        assert msgs[0]['send_status'] == 'pending'
        assert msgs[1]['send_status'] == 'pending'

        window.on_send_result(first_id, True, "")
        assert msgs[0]['send_status'] == 'sent'
        assert msgs[1]['send_status'] == 'pending'

        window.on_send_result(second_id, True, "")
        assert msgs[1]['send_status'] == 'sent'


@patch('src.uPtt.ui.screens.QMessageBox')
@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_send_result_updates_status_when_user_switched_chat(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, mock_msgbox, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    """Issue #13: status update must persist on the original chat even if the user
    switched away before the result arrived."""
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)

        window.add_or_select_contact("ContactA")
        window.message_edit.setText("hi")
        with patch.object(window, 'send_requested'):
            window.handle_send()
        msg_id = window.chat_histories['contacta'][-1]['msg_id']

        # User switches away to B before send completes
        window.add_or_select_contact("ContactB")
        assert window.current_chat_id == 'contactb'

        # Send fails
        window.on_send_result(msg_id, False, "boom")

        # The pending bubble in A must now be 'failed', not lost
        assert window.chat_histories['contacta'][-1]['send_status'] == 'failed'
        mock_msgbox.warning.assert_called_once()


@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_history_loaded_from_db_carries_send_status(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    """Self-sent rows loaded from DB must carry their send_status so old messages
    show ✓/✗/⏳ instead of nothing (Issue #13 follow-up)."""
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)

        sent_ts = datetime(2026, 4, 24, 10, 0, 0)
        failed_ts = datetime(2026, 4, 24, 10, 1, 0)
        recv_ts = datetime(2026, 4, 24, 10, 2, 0)
        db_mock.get_messages.return_value = [
            {'id': 11, 'content': 'old sent', 'timestamp': sent_ts, 'is_me': 1, 'mail_type': 'uptt', 'subject': '', 'send_status': 'sent'},
            {'id': 12, 'content': 'old failed', 'timestamp': failed_ts, 'is_me': 1, 'mail_type': 'uptt', 'subject': '', 'send_status': 'failed'},
            {'id': 13, 'content': 'reply from peer', 'timestamp': recv_ts, 'is_me': 0, 'mail_type': 'uptt', 'subject': '', 'send_status': 'sent'},
        ]
        window.add_or_select_contact("Peer")

        history = window.chat_histories['peer']
        # Self-sent messages: status survives the round trip
        assert history[0]['send_status'] == 'sent'
        assert history[0]['msg_id'] == 11
        assert history[1]['send_status'] == 'failed'
        assert history[1]['msg_id'] == 12
        # Received messages: no send_status key (only is_me messages render it)
        assert 'send_status' not in history[2]


@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_history_default_send_status_when_db_missing_column(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    """Pre-migration rows have NULL send_status — UI should default to 'sent' so
    historical messages still show the ✓ marker."""
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)

        ts = datetime(2026, 1, 1, 9, 0, 0)
        db_mock.get_messages.return_value = [
            {'id': 5, 'content': 'pre-migration msg', 'timestamp': ts, 'is_me': 1, 'mail_type': 'uptt', 'subject': '', 'send_status': None},
        ]
        window.add_or_select_contact("Old")
        assert window.chat_histories['old'][0]['send_status'] == 'sent'


@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_handle_send_suppresses_duplicate(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    """save_pending_message returning None (UNIQUE conflict) must NOT enqueue or
    leave a stuck-pending bubble in the UI."""
    with patch('os.path.exists', return_value=True):
        db_mock.save_pending_message.side_effect = None
        db_mock.save_pending_message.return_value = None  # simulate UNIQUE conflict
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.add_or_select_contact("dup")
        window.message_edit.setText("same content")

        with patch.object(window, 'send_requested') as mock_signal:
            window.handle_send()
            mock_signal.emit.assert_not_called()
        window.worker.enqueue_send.assert_not_called()
        # No stuck-pending bubble appended
        assert window.chat_histories.get('dup', []) == []


@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_login_reaps_dangling_pending(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    """on_login_result must call db.fail_dangling_pending so a crash mid-send
    can't leave permanent ⏳ bubbles after restart."""
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        db_mock.fail_dangling_pending.return_value = 3
        window.on_login_result(True, "ok")
        db_mock.fail_dangling_pending.assert_called_once_with("MyID")


@patch('src.uPtt.ui.screens.QMessageBox')
@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_logout_reaps_dangling_pending(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, mock_msg, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    """Logout terminates the worker; any in-flight send leaves a pending row.
    handle_logout must sweep them so the next login (same or different account)
    starts clean."""
    with patch('os.path.exists', return_value=True):
        mock_msg.question.return_value = mock_msg.Yes
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        db_mock.fail_dangling_pending.return_value = 2

        window.handle_logout()

        db_mock.fail_dangling_pending.assert_called_once_with("MyID")


@patch('src.uPtt.ui.screens.QMessageBox')
@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_logout_reaps_pending_even_if_stop_threads_raises(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, mock_msg, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    """The reap is in a finally block, so a raising _stop_all_threads must NOT
    skip cleanup. Locks in the contract that justifies the nested try/finally."""
    with patch('os.path.exists', return_value=True):
        mock_msg.question.return_value = mock_msg.Yes
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window._stop_all_threads = MagicMock(side_effect=RuntimeError("boom"))

        window.handle_logout()

        db_mock.fail_dangling_pending.assert_called_once_with("MyID")


@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_on_new_message_self_echo_marks_sent(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    """When PTT echoes our own outbound mail back via the polling path, the
    rendered bubble must still show ✓ — not blank — so the marker is consistent
    with the handle_send path."""
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.add_or_select_contact("Peer")

        window.on_new_message({
            'sender': 'Peer',
            'text': 'echoed back',
            'time': '12:00',
            'full_author': 'Peer (Nick)',
            'timestamp': datetime(2026, 4, 24, 12, 0, 0),
            'mail_type': 'uptt',
            'is_me': True,
        })

        history = window.chat_histories['peer']
        assert len(history) == 1
        assert history[0]['is_me'] is True
        assert history[0]['send_status'] == 'sent'


@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_handle_send_dup_preserves_reply_context(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, db_mock):
    """If a send is suppressed due to UNIQUE conflict while a reply is staged,
    the reply preview must remain so the user doesn't silently lose context."""
    with patch('os.path.exists', return_value=True):
        db_mock.save_pending_message.side_effect = None
        db_mock.save_pending_message.return_value = None
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.add_or_select_contact("Peer")
        window.set_reply_to("original message being quoted", False)
        assert window.reply_to is not None
        assert not window.reply_bar.isHidden()

        window.message_edit.setText("my reply")
        with patch.object(window, 'send_requested') as mock_signal:
            window.handle_send()
            mock_signal.emit.assert_not_called()

        # Reply state restored after duplicate-send was suppressed
        assert window.reply_to is not None
        assert not window.reply_bar.isHidden()
        assert window.message_edit.text() == "my reply"


@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_send_status_survives_chat_switch_round_trip(mock_qthread, mock_worker, mock_query_worker, mock_ver_worker, qtbot, ptt_service_mock, ptt_query_service_mock, tmp_path):
    """Issue #13 end-to-end: real DatabaseManager. Send → switch chat → simulate
    worker result → switch back → bubble's send_status reflects the result."""
    from src.uPtt.db import DatabaseManager

    db = DatabaseManager(str(tmp_path / "e2e.db"))
    db.upsert_account("MyID", "MyID")
    db.upsert_session("MyID", "ContactA")
    db.upsert_session("MyID", "ContactB")

    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db)
        qtbot.addWidget(window)

        # Send to A
        window.add_or_select_contact("ContactA")
        window.message_edit.setText("hello A")
        with patch.object(window, 'send_requested'):
            window.handle_send()
        msg_id = window.chat_histories['contacta'][-1]['msg_id']
        assert msg_id > 0

        # User switches to B before result arrives
        window.add_or_select_contact("ContactB")

        # Worker eventually reports failure — DB row updated, then signal fires.
        # QMessageBox.warning is modal and would hang the test, so stub it.
        db.update_message_status(msg_id, 'failed')
        with patch('src.uPtt.ui.screens.QMessageBox'):
            window.on_send_result(msg_id, False, "boom")

        # Switch back to A — chat_histories[A] is REBUILT from DB
        window.add_or_select_contact("ContactA")
        history = window.chat_histories['contacta']
        # The previously-pending message must now show as 'failed', not vanish
        my_msgs = [m for m in history if m.get('is_me')]
        assert len(my_msgs) == 1
        assert my_msgs[0]['send_status'] == 'failed'
        assert my_msgs[0]['msg_id'] == msg_id


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
