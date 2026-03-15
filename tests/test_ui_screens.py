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

@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_main_window_init(mock_qthread, mock_worker, qtbot, ptt_service_mock):
    # Mock assets to avoid FileNotFoundError
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock)
        qtbot.addWidget(window)
        
        assert window.windowTitle() == "uPtt"
        assert window.central_stack.count() == 2
        # First screen should be login
        assert window.central_stack.currentIndex() == 0

@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_on_login_result_success(mock_qthread, mock_worker, qtbot, ptt_service_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock)
        qtbot.addWidget(window)
        
        # Simulate successful login signal from worker
        ptt_service_mock.ptt_id = "CorrectID"
        window.on_login_result(True, "Login Success")
        
        # Should switch to chat screen (index 1)
        assert window.central_stack.currentIndex() == 1
        assert "CorrectID" in window.user_id_label.text()

@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
def test_on_login_result_failure(mock_qthread, mock_worker, qtbot, ptt_service_mock):
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock)
        qtbot.addWidget(window)
        
        # Simulate failed login
        window.on_login_result(False, "Invalid Password")
        
        # Should stay on login screen
        assert window.central_stack.currentIndex() == 0
        assert window.login_screen.error_label.text() == "Invalid Password"
