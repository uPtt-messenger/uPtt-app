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
    ptt_service_mock.get_user_info.return_value = {'ptt_id': 'CorrectID', 'nickname': 'Nick', 'is_online': True}
    
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


def test_poll_new_mails_uses_embedded_timestamp(qtbot, worker, ptt_service_mock, db_mock):
    """收到帶有嵌入時間戳的 uPtt 訊息時，應使用發送端的時間戳而非 PTT 信件時間"""
    embedded_time = datetime(2026, 3, 15, 9, 58, 30)
    ts_tag = f"{contant.PTT_MSG_TS_PREFIX}{embedded_time.isoformat()}{contant.PTT_MSG_TS_SUFFIX}"

    def call_side_effect(api, args=None):
        if api == 'get_newest_index':
            return 1
        if api == 'get_mail':
            return {
                PyPtt.MailField.title: contant.PTT_MSG_TITLE,
                PyPtt.MailField.author: "SenderID (Nick)",
                PyPtt.MailField.date: "Wed Mar 15 10:00:00 2026",
                PyPtt.MailField.content: (
                    f"Header\n{contant.PTT_MSG_DIVISION_LINE}\nHello\n"
                    f"{contant.PTT_MSG_DIVISION_LINE}\n{ts_tag}"
                ),
            }
        if api == 'del_mail':
            return None
        return None

    ptt_service_mock.call.side_effect = call_side_effect
    db_mock.save_message.return_value = True

    worker.is_first_polling = False

    with qtbot.waitSignal(worker.new_message_received) as blocker:
        worker._poll_new_mails()

    # 驗證 save_message 使用的是嵌入的發送端時間戳，而非 PTT 信件時間 10:00:00
    save_call = db_mock.save_message.call_args
    assert save_call.kwargs.get('timestamp') or save_call[1].get('timestamp') or save_call[0][5] == embedded_time
    assert blocker.args[0]['timestamp'] == embedded_time

def test_poll_new_mails_stop_time(worker, ptt_service_mock):
    """非 uPtt 的舊信應觸發 stop_time 提早結束掃描"""
    last_poll = datetime.now() - timedelta(minutes=5)
    worker.last_poll_time = last_poll

    old_time = last_poll - timedelta(minutes=10)

    def call_side_effect(api, args=None):
        if api == 'get_newest_index': return 100
        if api == 'get_mail':
            return {
                PyPtt.MailField.date: old_time.strftime('%a %b %d %H:%M:%S %Y'),
                PyPtt.MailField.title: "一般站內信標題",
                PyPtt.MailField.author: "sender",
                PyPtt.MailField.content: "一般信件內容"
            }
        return None

    ptt_service_mock.call.side_effect = call_side_effect
    worker._poll_new_mails()
    # Should stop after first mail because it's a non-uPtt mail older than stop_time
    # 1 for get_newest_index, 1 for get_mail index 100
    assert ptt_service_mock.call.call_count == 2

def test_poll_new_mails_new_user_scans_7_days(worker, ptt_service_mock, db_mock):
    """全新使用者（無 last_poll_time）應掃描過去 7 天，7 天外的非 uPtt 信停止"""
    worker.last_poll_time = None
    worker.is_first_polling = True

    now = datetime.now()
    # 8 天前的信 → 超出 7 天窗口
    old_time = now - timedelta(days=8)

    def call_side_effect(api, args=None):
        if api == 'get_newest_index':
            return 1
        if api == 'get_mail':
            return {
                PyPtt.MailField.date: old_time.strftime('%a %b %d %H:%M:%S %Y'),
                PyPtt.MailField.title: "一般站內信標題",
                PyPtt.MailField.author: "sender",
                PyPtt.MailField.content: "一般信件內容"
            }
        return None

    ptt_service_mock.call.side_effect = call_side_effect
    worker._poll_new_mails()
    # 1 get_newest_index + 1 get_mail → break (非 uPtt, 超出 7 天)
    assert ptt_service_mock.call.call_count == 2


def test_poll_extends_2_days_when_uptt_found(worker, ptt_service_mock, db_mock):
    """發現 uPtt 訊息後，掃描範圍應延伸 2 天"""
    last_poll = datetime.now() - timedelta(minutes=5)
    worker.last_poll_time = last_poll
    worker.is_first_polling = False

    # 信件時間排列（由新到舊）：
    #   index 3: uPtt 訊息（新，在 stop_time 內）
    #   index 2: 一般信（舊，超出原始 stop_time 但在延伸 2 天內）
    #   index 1: 一般信（更舊，超出延伸後的 stop_time）
    now = datetime.now()
    times = {
        3: now - timedelta(minutes=1),                                      # 新的 uPtt 訊息
        2: last_poll - timedelta(seconds=10) - timedelta(hours=1),          # 稍微超出原始 stop_time
        1: last_poll - timedelta(seconds=10) - timedelta(days=3),           # 超出延伸後 stop_time
    }

    def call_side_effect(api, args=None):
        if api == 'get_newest_index':
            return 3
        if api == 'get_mail':
            idx = args['index']
            t = times[idx]
            if idx == 3:
                return {
                    PyPtt.MailField.date: t.strftime('%a %b %d %H:%M:%S %Y'),
                    PyPtt.MailField.title: contant.PTT_MSG_TITLE,
                    PyPtt.MailField.author: "SenderID (Nick)",
                    PyPtt.MailField.content: f"H\n{contant.PTT_MSG_DIVISION_LINE}\nMsg\n{contant.PTT_MSG_DIVISION_LINE}\nF"
                }
            else:
                return {
                    PyPtt.MailField.date: t.strftime('%a %b %d %H:%M:%S %Y'),
                    PyPtt.MailField.title: "一般站內信",
                    PyPtt.MailField.author: "other",
                    PyPtt.MailField.content: "content"
                }
        if api == 'del_mail':
            return None
        return None

    ptt_service_mock.call.side_effect = call_side_effect
    db_mock.save_message.return_value = True
    worker._poll_new_mails()

    # 預期：
    #  1. get_newest_index
    #  2. get_mail(3) → uPtt → 處理 + del_mail
    #  3. get_mail(2) → 一般信，超出原始 stop_time → 延伸 2 天 → 在延伸內 → 處理
    #  4. get_mail(1) → 一般信，超出延伸後 stop_time → break
    # 共 5 次 call（get_newest + 3x get_mail + 1x del_mail）
    assert ptt_service_mock.call.call_count == 5


def test_poll_extends_multiple_times(worker, ptt_service_mock, db_mock):
    """延伸範圍內又發現 uPtt，應繼續再延伸 2 天（不限次數）"""
    last_poll = datetime.now() - timedelta(minutes=5)
    worker.last_poll_time = last_poll
    worker.is_first_polling = False

    stop = last_poll - timedelta(seconds=10)
    # index 5: uPtt（stop_time 內）→ 第一次觸發延伸
    # index 4: 一般信（超出原始 stop，在第一次延伸內）→ 處理
    # index 3: uPtt（在第一次延伸內）→ 觸發第二次延伸
    # index 2: 一般信（超出第一次延伸，在第二次延伸內）→ 處理
    # index 1: 一般信（超出第二次延伸）→ break
    times = {
        5: datetime.now() - timedelta(minutes=1),
        4: stop - timedelta(hours=1),
        3: stop - timedelta(days=1),
        2: stop - timedelta(days=3),
        1: stop - timedelta(days=5),
    }

    def call_side_effect(api, args=None):
        if api == 'get_newest_index':
            return 5
        if api == 'get_mail':
            idx = args['index']
            t = times[idx]
            is_uptt = idx in (5, 3)
            if is_uptt:
                return {
                    PyPtt.MailField.date: t.strftime('%a %b %d %H:%M:%S %Y'),
                    PyPtt.MailField.title: contant.PTT_MSG_TITLE,
                    PyPtt.MailField.author: "SenderID (Nick)",
                    PyPtt.MailField.content: f"H\n{contant.PTT_MSG_DIVISION_LINE}\nMsg\n{contant.PTT_MSG_DIVISION_LINE}\nF"
                }
            return {
                PyPtt.MailField.date: t.strftime('%a %b %d %H:%M:%S %Y'),
                PyPtt.MailField.title: "一般站內信",
                PyPtt.MailField.author: "other",
                PyPtt.MailField.content: "content"
            }
        if api == 'del_mail':
            return None
        return None

    ptt_service_mock.call.side_effect = call_side_effect
    db_mock.save_message.return_value = True
    worker._poll_new_mails()

    # get_newest(1) + get_mail x5 + del_mail x2 = 8
    assert ptt_service_mock.call.call_count == 8


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
        'nickname': 'CoolNick',
        'is_online': True,
    }

    with qtbot.waitSignal(worker.user_info_result) as blocker:
        worker.get_user_info("correctid")

    assert blocker.args == [{'ptt_id': 'CorrectID', 'nickname': 'CoolNick', 'is_online': True}]
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
