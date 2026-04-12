import logging
import os
import sys
from unittest.mock import patch, MagicMock
from src.uPtt.app import setup_logging, main

def test_setup_logging_basic():
    # Clear existing handlers to test fresh setup
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    setup_logging(debug_mode=False)
    
    assert root_logger.level == logging.INFO
    # Should have at least one handler (console)
    assert len(root_logger.handlers) >= 1

def test_setup_logging_debug():
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    if os.path.exists("uptt_debug.log"):
        os.remove("uptt_debug.log")
        
    try:
        setup_logging(debug_mode=True)
        assert root_logger.level == logging.DEBUG
        assert os.path.exists("uptt_debug.log")
    finally:
        if os.path.exists("uptt_debug.log"):
            os.remove("uptt_debug.log")

@patch('src.uPtt.app.QApplication')
@patch('src.uPtt.app.QFontDatabase')
@patch('src.uPtt.app.MainWindow')
@patch('src.uPtt.app.DatabaseManager')
@patch('src.uPtt.app.UPttService')
@patch('src.uPtt.app.QLocalServer')
@patch('src.uPtt.app.QLocalSocket')
@patch('src.uPtt.utils.get_app_data_dir', return_value="/tmp/test_uptt")
@patch('sys.exit')
def test_main_debug_mode(mock_exit, mock_dir, mock_socket, mock_server, mock_ptt, mock_db, mock_main_win, mock_fontdb, mock_qapp):
    # Simulate debug mode
    with patch('sys.argv', ['run_app.py', '--debug']):
        main()
        
    mock_qapp.assert_called_once()
    mock_main_win.assert_called_once()
    mock_db.assert_called_once()
    # 主 session + 副 session 各一次
    assert mock_ptt.call_count == 2
    # Debug mode skips QLocalServer logic
    mock_server.assert_not_called()

@patch('src.uPtt.app.QApplication')
@patch('src.uPtt.app.QFontDatabase')
@patch('src.uPtt.app.MainWindow')
@patch('src.uPtt.app.DatabaseManager')
@patch('src.uPtt.app.UPttService')
@patch('src.uPtt.app.QLocalServer')
@patch('src.uPtt.app.QLocalSocket')
@patch('src.uPtt.utils.get_app_data_dir', return_value="/tmp/test_uptt")
@patch('sys.exit')
def test_main_single_instance_first(mock_exit, mock_dir, mock_socket, mock_server, mock_ptt, mock_db, mock_main_win, mock_fontdb, mock_qapp):
    # Simulate normal mode, first instance
    mock_socket_instance = mock_socket.return_value
    mock_socket_instance.waitForConnected.return_value = False # No other instance
    
    mock_server_instance = mock_server.return_value
    mock_server_instance.listen.return_value = True
    
    with patch('sys.argv', ['run_app.py']):
        main()
        
    mock_server_instance.listen.assert_called_once()
    mock_main_win.assert_called_once()

@patch('src.uPtt.app.QApplication')
@patch('src.uPtt.app.QFontDatabase')
@patch('src.uPtt.app.MainWindow')
@patch('src.uPtt.app.QLocalSocket')
@patch('sys.exit')
def test_main_single_instance_exists(mock_exit, mock_socket, mock_main_win, mock_fontdb, mock_qapp):
    # Simulate normal mode, already running
    mock_socket_instance = mock_socket.return_value
    mock_socket_instance.waitForConnected.return_value = True # Another instance detected
    
    with patch('sys.argv', ['run_app.py']):
        main()
        
    # Should not initialize main window or DB if another instance is running
    mock_main_win.assert_not_called()
