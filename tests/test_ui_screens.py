import pytest
from datetime import datetime
from PySide6.QtCore import Qt
from unittest.mock import MagicMock, patch, ANY
import os

# Set offscreen platform for CI/CLI environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from src.uPtt.ui.screens import LoginWindow, MainWindow
from src.uPtt.ptt import UPttService
from src.uPtt.worker import PTTWorker
from src.uPtt.ui.widgets import ContactItem

@pytest.fixture
def ptt_service_mock():
    service = MagicMock(spec=UPttService)
    service.ptt_id = "MyID"
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
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_main_window_init(mock_qthread, mock_worker, mock_ver_worker, qtbot, ptt_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, db_mock)
        qtbot.addWidget(window)
        assert window.windowTitle() == "uPtt"
        assert window.central_stack.currentIndex() == 0

@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_on_login_result_success(mock_qthread, mock_worker, mock_ver_worker, qtbot, ptt_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, db_mock)
        qtbot.addWidget(window)
        window.on_login_result(True, "Login Success")
        assert window.central_stack.currentIndex() == 1

@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_on_login_result_failure(mock_qthread, mock_worker, mock_ver_worker, qtbot, ptt_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, db_mock)
        qtbot.addWidget(window)
        window.on_login_result(False, "Failed")
        assert window.central_stack.currentIndex() == 0

@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_main_window_close_chat(mock_qthread, mock_worker, mock_ver_worker, qtbot, ptt_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, db_mock)
        qtbot.addWidget(window)
        window.add_or_select_contact("TestUser")
        window.close_current_chat()
        assert window.contact_list.count() == 0

@patch('src.uPtt.ui.screens.QMessageBox')
@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_main_window_block_user(mock_qthread, mock_worker, mock_ver_worker, mock_msg, qtbot, ptt_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, db_mock)
        qtbot.addWidget(window)
        window.add_or_select_contact("BadUser")
        window.handle_contact_action("BadUser", "BLOCK")
        assert "baduser" in window.blocked_users

@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_on_new_message_blocked(mock_qthread, mock_worker, mock_ver_worker, qtbot, ptt_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, db_mock)
        qtbot.addWidget(window)
        window.blocked_users.add("baduser")
        msg_data = {'sender': 'BadUser', 'text': 'Hi', 'time': '10:00', 'full_author': 'BadUser'}
        window.on_new_message(msg_data)
        assert "baduser" not in window.chat_histories

@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_on_user_info_result(mock_qthread, mock_worker, mock_ver_worker, qtbot, ptt_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, db_mock)
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
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_load_sessions_from_db(mock_qthread, mock_worker, mock_ver_worker, qtbot, ptt_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        db_mock.get_all_sessions.return_value = [{'id': 'u1', 'display_id': 'U1', 'nickname': 'N1', 'unread_count': 0}]
        window = MainWindow(ptt_service_mock, db_mock)
        qtbot.addWidget(window)
        window.load_sessions_from_db()
        assert window.contact_list.count() == 1

@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_handle_send(mock_qthread, mock_worker, mock_ver_worker, qtbot, ptt_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, db_mock)
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
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_handle_logout(mock_qthread, mock_worker, mock_ver_worker, mock_msg, qtbot, ptt_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        mock_msg.question.return_value = mock_msg.Yes
        window = MainWindow(ptt_service_mock, db_mock)
        qtbot.addWidget(window)
        window.handle_logout()
        assert window.central_stack.currentIndex() == 0

@patch('PySide6.QtCore.QMetaObject.invokeMethod')
@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_fully_quit(mock_qthread, mock_worker, mock_ver_worker, mock_invoke, qtbot, ptt_service_mock, db_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, db_mock)
        qtbot.addWidget(window)
        window.fully_quit()
        # Should call invokeMethod for worker.stop
        mock_invoke.assert_called()

def test_render_svg_exists():
    from src.uPtt.ui.screens import render_svg
    with open("test_pixmap.svg", "w") as f:
        f.write('<svg width="10" height="10"><rect width="10" height="10" /></svg>')
    try:
        pixmap = render_svg("test_pixmap.svg", 10, 10)
        assert not pixmap.isNull()
    finally:
        if os.path.exists("test_pixmap.svg"): os.remove("test_pixmap.svg")
