import pytest
from PySide6.QtCore import QTimer
from unittest.mock import MagicMock, patch
import PyPtt
from datetime import datetime, timedelta

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
    db = MagicMock()
    db.get_config.return_value = None
    return db

@pytest.fixture
def worker(ptt_service_mock, db_mock):
    return PTTWorker(ptt_service_mock, db_mock)

def test_worker_init_with_last_poll(ptt_service_mock, db_mock):
    last_time = datetime.now().replace(microsecond=0)
    db_mock.get_config.return_value = last_time.isoformat()
    w = PTTWorker(ptt_service_mock, db_mock)
    assert w.last_poll_time == last_time

def test_worker_init_invalid_poll_time(ptt_service_mock, db_mock):
    db_mock.get_config.return_value = "invalid-date"
    w = PTTWorker(ptt_service_mock, db_mock)
    assert w.last_poll_time is None

def test_do_login_success(qtbot, worker, ptt_service_mock, db_mock):
    ptt_service_mock.login.return_value = True
    ptt_service_mock.get_user_info.return_value = {'ptt_id': 'CorrectID', 'nickname': 'Nick'}
    
    with qtbot.waitSignal(worker.login_result) as blocker:
        worker.do_login("testuser", "testpass")
    
    assert blocker.args == [True, "登入成功"]
    ptt_service_mock.login.assert_called_once_with("testuser", "testpass")
    db_mock.upsert_account.assert_called_once()
    assert worker.polling_timer is not None
    assert worker.polling_timer.isActive()

def test_do_login_failure(qtbot, worker, ptt_service_mock):
    ptt_service_mock.login.return_value = False
    
    with qtbot.waitSignal(worker.login_result) as blocker:
        worker.do_login("wronguser", "wrongpass")
    
    assert blocker.args == [False, "登入失敗"]

def test_do_login_exception(qtbot, worker, ptt_service_mock):
    ptt_service_mock.login.side_effect = Exception("Fatal Error")
    
    with qtbot.waitSignal(worker.login_result) as blocker:
        worker.do_login("user", "pass")
    
    assert blocker.args == [False, "Fatal Error"]

def test_poll_new_mails_basic(qtbot, worker, ptt_service_mock, db_mock):
    # Mock newest index in search
    def call_side_effect(api, args=None):
        if api == 'get_newest_index':
            return 1
        if api == 'get_mail':
            return {
                PyPtt.MailField.title: contant.PTT_MSG_TITLE,
                PyPtt.MailField.author: "SenderID (Nick)",
                PyPtt.MailField.date: "Wed Mar 15 10:00:00 2026",
                PyPtt.MailField.content: f"Header\n{contant.PTT_MSG_DIVISION_LINE}\nTest Message Content\n{contant.PTT_MSG_DIVISION_LINE}\nFooter"
            }
        return None

    ptt_service_mock.call.side_effect = call_side_effect
    db_mock.save_message.return_value = True # New message
    
    worker.is_first_polling = False
    
    with qtbot.waitSignal(worker.new_message_received) as blocker:
        worker._poll_new_mails()
    
    assert blocker.args[0]['sender'] == "SenderID"
    assert blocker.args[0]['text'] == "Test Message Content"

def test_poll_new_mails_stop_time(worker, ptt_service_mock):
    last_poll = datetime.now() - timedelta(minutes=5)
    worker.last_poll_time = last_poll
    
    old_time = last_poll - timedelta(minutes=10)
    
    def call_side_effect(api, args=None):
        if api == 'get_newest_index': return 100
        if api == 'get_mail':
            return {
                PyPtt.MailField.date: old_time.strftime('%a %b %d %H:%M:%S %Y'),
                PyPtt.MailField.title: contant.PTT_MSG_TITLE,
                PyPtt.MailField.author: "sender",
                PyPtt.MailField.content: "..."
            }
        return None

    ptt_service_mock.call.side_effect = call_side_effect
    worker._poll_new_mails()
    # Should stop after first mail because it's older than stop_time
    # 1 for get_newest_index, 1 for get_mail index 100
    assert ptt_service_mock.call.call_count == 2

def test_send_message_success(qtbot, worker, ptt_service_mock, db_mock):
    worker.ptt.ptt_id = "SenderID"
    
    with qtbot.waitSignal(worker.send_result) as blocker:
        worker.send_message("ReceiverID", "Hello PTT")
    
    assert blocker.args == [True, ""]
    ptt_service_mock.call.assert_called()
    db_mock.save_message.assert_called_once()

def test_send_message_failure(qtbot, worker, ptt_service_mock):
    ptt_service_mock.call.side_effect = Exception("Send Error")
    
    with qtbot.waitSignal(worker.send_result) as blocker:
        worker.send_message("receiver", "Hello")
    
    assert blocker.args == [False, "Send Error"]

def test_get_user_info_success(qtbot, worker, ptt_service_mock, db_mock):
    ptt_service_mock.get_user_info.return_value = {
        'ptt_id': 'CorrectID',
        'nickname': 'CoolNick'
    }
    
    with qtbot.waitSignal(worker.user_info_result) as blocker:
        worker.get_user_info("correctid")
    
    assert blocker.args == [{'ptt_id': 'CorrectID', 'nickname': 'CoolNick'}]
    db_mock.upsert_session.assert_called_once()

def test_get_user_info_value_error(qtbot, worker, ptt_service_mock):
    ptt_service_mock.get_user_info.side_effect = ValueError("NoSuchUser")
    
    with qtbot.waitSignal(worker.user_info_error) as blocker:
        worker.get_user_info("ghost")
    
    assert blocker.args == ["ghost", "NoSuchUser"]

def test_get_user_info_exception(qtbot, worker, ptt_service_mock):
    ptt_service_mock.get_user_info.side_effect = Exception("Random Error")
    
    with qtbot.waitSignal(worker.user_info_error) as blocker:
        worker.get_user_info("user")
    
    assert "系統錯誤: Random Error" in blocker.args[1]

def test_stop_worker(worker, ptt_service_mock):
    worker.polling_timer = MagicMock(spec=QTimer)
    worker.stop()
    worker.polling_timer.stop.assert_called_once()
    ptt_service_mock.close.assert_called_once()

def test_poll_new_mails_exception(worker, ptt_service_mock, qtbot):
    ptt_service_mock.call.side_effect = Exception("Poll Error")
    with qtbot.waitSignal(worker.status_updated) as blocker:
        worker._poll_new_mails()
    assert "輪詢錯誤: Poll Error" in blocker.args[0]
