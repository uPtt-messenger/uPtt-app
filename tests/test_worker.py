import pytest
from PySide6.QtCore import QTimer
from unittest.mock import MagicMock, patch
import PyPtt
from datetime import datetime

from src.uPtt.worker import PTTWorker
from src.uPtt.ptt import UPttService
from src.uPtt import contant

@pytest.fixture
def ptt_service_mock():
    service = MagicMock(spec=UPttService)
    service.ptt_id = "TestUser"
    return service

@pytest.fixture
def db_mock():
    return MagicMock()

@pytest.fixture
def worker(ptt_service_mock, db_mock):
    return PTTWorker(ptt_service_mock, db_mock)

def test_do_login_success(qtbot, worker, ptt_service_mock):
    ptt_service_mock.login.return_value = True
    
    with qtbot.waitSignal(worker.login_result) as blocker:
        worker.do_login("testuser", "testpass")
    
    assert blocker.args == [True, "登入成功"]
    ptt_service_mock.login.assert_called_once_with("testuser", "testpass")
    assert worker.polling_timer is not None
    assert worker.polling_timer.isActive()

def test_do_login_failure(qtbot, worker, ptt_service_mock):
    ptt_service_mock.login.return_value = False
    
    with qtbot.waitSignal(worker.login_result) as blocker:
        worker.do_login("wronguser", "wrongpass")
    
    assert blocker.args == [False, "登入失敗"]

def test_send_message_success(qtbot, worker, ptt_service_mock):
    worker.ptt.ptt_id = "SenderID"
    
    with qtbot.waitSignal(worker.send_result) as blocker:
        worker.send_message("ReceiverID", "Hello PTT")
    
    assert blocker.args == [True, ""]
    ptt_service_mock.call.assert_called_once()
    args, kwargs = ptt_service_mock.call.call_args
    assert args[0] == 'mail'
    assert args[1]['ptt_id'] == "ReceiverID"
    assert "Hello PTT" in args[1]['content']

def test_get_user_info_success(qtbot, worker, ptt_service_mock):
    ptt_service_mock.get_user_info.return_value = {
        'ptt_id': 'CorrectID',
        'nickname': 'CoolNick'
    }
    
    with qtbot.waitSignal(worker.user_info_result) as blocker:
        worker.get_user_info("correctid")
    
    assert blocker.args == [{'ptt_id': 'CorrectID', 'nickname': 'CoolNick'}]

def test_poll_new_mails_parsing(qtbot, worker, ptt_service_mock, db_mock):
    # Mock newest index in search
    def call_side_effect(api, args=None):
        if api == 'get_newest_index':
            # Check if search_list is used
            if args and 'search_list' in args:
                return 1 # Only 1 mail in search results
            return 100
        if api == 'get_mail':
            if args and args.get('index') == 1: # 1st mail in search
                return {
                    PyPtt.MailField.title: contant.PTT_MSG_TITLE,
                    PyPtt.MailField.author: "SenderID (Nick)",
                    PyPtt.MailField.date: "Wed Mar 15 10:00:00 2026",
                    PyPtt.MailField.content: f"Header\n{contant.PTT_MSG_DIVISION_LINE}\nTest Message Content\n{contant.PTT_MSG_DIVISION_LINE}\nFooter"
                }
            return None
        if api == 'del_mail':
            return None
        return None

    ptt_service_mock.call.side_effect = call_side_effect
    db_mock.save_message.return_value = True # New message
    
    worker.is_first_polling = False # To limit loop
    
    with qtbot.waitSignal(worker.new_message_received) as blocker:
        worker._poll_new_mails()
    
    assert blocker.args[0]['sender'] == "SenderID"
    assert blocker.args[0]['text'] == "Test Message Content"
    assert blocker.args[0]['time'] == "10:00"
    # newest implementation uses reversed(mails_to_emit) and emits, 
    # so we should check if del_mail was called with search_list
    ptt_service_mock.call.assert_any_call('del_mail', {'index': 1, 'search_list': [(PyPtt.SearchType.KEYWORD, contant.PTT_MSG_TITLE)]})

def test_stop_worker(worker, ptt_service_mock):
    worker.polling_timer = MagicMock(spec=QTimer)
    worker.stop()
    worker.polling_timer.stop.assert_called_once()
    ptt_service_mock.close.assert_called_once()
