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

def test_worker_init_last_poll_is_none(ptt_service_mock, db_mock):
    """last_poll_time 在 __init__ 時應為 None，需等 do_login 成功後才載入。"""
    w = PTTWorker(ptt_service_mock, db_mock)
    assert w.last_poll_time is None

def test_worker_login_loads_last_poll(qtbot, ptt_service_mock, db_mock):
    """do_login 成功後應載入該帳號的 LAST_POLL_TIME。"""
    last_time = datetime.now().replace(microsecond=0)
    ptt_service_mock.ptt_id = "TestUser"
    ptt_service_mock.login.return_value = True
    ptt_service_mock.get_user_info.return_value = {'ptt_id': 'TestUser', 'nickname': 'Nick', 'is_online': True}
    db_mock.get_config.return_value = last_time.isoformat()
    w = PTTWorker(ptt_service_mock, db_mock)
    with qtbot.waitSignal(w.login_result):
        w.do_login("testuser", "testpass")
    db_mock.get_config.assert_called_with('LAST_POLL_TIME_testuser')
    assert w.last_poll_time == last_time

def test_worker_login_invalid_poll_time(qtbot, ptt_service_mock, db_mock):
    """do_login 成功後若 LAST_POLL_TIME 格式不合法，應設為 None。"""
    ptt_service_mock.ptt_id = "TestUser"
    ptt_service_mock.login.return_value = True
    ptt_service_mock.get_user_info.return_value = {'ptt_id': 'TestUser', 'nickname': 'Nick', 'is_online': True}
    db_mock.get_config.return_value = "invalid-date"
    w = PTTWorker(ptt_service_mock, db_mock)
    with qtbot.waitSignal(w.login_result):
        w.do_login("testuser", "testpass")
    assert w.last_poll_time is None

def test_do_login_success(qtbot, worker, ptt_service_mock, db_mock):
    """回訪使用者登入成功後應自動啟動輪詢"""
    ptt_service_mock.login.return_value = True
    ptt_service_mock.get_user_info.return_value = {'ptt_id': 'CorrectID', 'nickname': 'Nick', 'is_online': True}
    # 模擬回訪使用者（有之前的輪詢時間）
    db_mock.get_config.return_value = datetime.now().isoformat()

    with qtbot.waitSignal(worker.login_result) as blocker:
        worker.do_login("testuser", "testpass")

    assert blocker.args == [True, "登入成功"]
    ptt_service_mock.login.assert_called_once_with("testuser", "testpass")
    db_mock.upsert_account.assert_called_once()
    assert worker.polling_timer is not None
    assert worker.polling_timer.isActive()


def test_do_login_first_time_no_polling(qtbot, ptt_service_mock, db_mock):
    """首次登入（無 last_poll_time）應發射 first_time_detected 且不啟動輪詢"""
    ptt_service_mock.login.return_value = True
    ptt_service_mock.get_user_info.return_value = {'ptt_id': 'NewUser', 'nickname': 'Nick', 'is_online': True}
    db_mock.get_config.return_value = None

    w = PTTWorker(ptt_service_mock, db_mock)

    first_time_received = []
    w.first_time_detected.connect(lambda: first_time_received.append(True))

    with qtbot.waitSignal(w.login_result) as blocker:
        w.do_login("newuser", "newpass")

    assert blocker.args == [True, "登入成功"]
    assert len(first_time_received) == 1
    assert w.polling_timer is None


def test_do_initial_scan_emits_progress(qtbot, ptt_service_mock, db_mock):
    """do_initial_scan 應發射 scan_progress 與 scan_complete"""
    ptt_service_mock.ptt_id = "TestUser"

    def call_side_effect(api, args=None):
        if api == 'get_newest_index':
            return 2
        if api == 'get_mail':
            return {
                PyPtt.MailField.title: "一般站內信",
                PyPtt.MailField.author: "sender (Nick)",
                PyPtt.MailField.date: datetime.now().strftime('%a %b %d %H:%M:%S %Y'),
                PyPtt.MailField.content: "test content"
            }
        return None

    ptt_service_mock.call.side_effect = call_side_effect
    db_mock.save_message.return_value = True

    w = PTTWorker(ptt_service_mock, db_mock)
    w.is_first_polling = True

    progress_updates = []
    w.scan_progress.connect(lambda cur, total, title: progress_updates.append((cur, total, title)))

    with qtbot.waitSignal(w.scan_complete):
        w.do_initial_scan(7)

    assert len(progress_updates) == 2
    assert progress_updates[0][1] == 2  # total = 2
    assert progress_updates[1][0] == 2  # scanned = 2
    assert w.polling_timer is not None  # polling started after scan


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
    actual_ts = save_call.kwargs.get('timestamp')
    assert actual_ts == embedded_time
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
        worker.enqueue_send("ReceiverID", "Hello PTT")
        worker.send_message("ReceiverID", "Hello PTT")

    assert blocker.args == [True, ""]
    ptt_service_mock.call.assert_called()
    db_mock.save_message.assert_called_once()

def test_send_message_failure(qtbot, worker, ptt_service_mock):
    ptt_service_mock.call.side_effect = Exception("Send Error")

    with qtbot.waitSignal(worker.send_result) as blocker:
        worker.enqueue_send("receiver", "Hello")
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

    result = blocker.args[0]
    assert result['ptt_id'] == 'CorrectID'
    assert result['nickname'] == 'CoolNick'
    assert result['is_online'] is True
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


def test_poll_save_failure_skips_deletion(worker, ptt_service_mock, db_mock):
    """save_message 拋出例外時，不應刪除 PTT 上的 uPtt 信件（防止資料遺失）"""
    import sqlite3

    call_log = []

    def call_side_effect(api, args=None):
        call_log.append(api)
        if api == 'get_newest_index':
            return 1
        if api == 'get_mail':
            return {
                PyPtt.MailField.title: contant.PTT_MSG_TITLE,
                PyPtt.MailField.author: "SenderID (Nick)",
                PyPtt.MailField.date: "Wed Mar 15 10:00:00 2026",
                PyPtt.MailField.content: (
                    f"Header\n{contant.PTT_MSG_DIVISION_LINE}\n"
                    f"Test Message\n{contant.PTT_MSG_DIVISION_LINE}\nFooter"
                ),
            }
        return None

    ptt_service_mock.call.side_effect = call_side_effect
    db_mock.save_message.side_effect = sqlite3.OperationalError("database is locked")

    worker.is_first_polling = False
    worker._poll_new_mails()

    # del_mail 不應被呼叫，因為 save_message 失敗了
    assert 'del_mail' not in call_log


def test_poll_index_decrease_still_scans(worker, ptt_service_mock, db_mock):
    """信箱索引減少（外部刪信）時，仍應繼續掃描以免遺漏新信件"""
    worker.is_first_polling = False
    worker._last_newest_index = 10  # 上次記錄的索引
    worker.last_poll_time = datetime.now() - timedelta(minutes=1)

    def call_side_effect(api, args=None):
        if api == 'get_newest_index':
            return 8  # 比上次少（外部刪了信）
        if api == 'get_mail':
            return {
                PyPtt.MailField.title: contant.PTT_MSG_TITLE,
                PyPtt.MailField.author: "SenderID (Nick)",
                PyPtt.MailField.date: datetime.now().strftime('%a %b %d %H:%M:%S %Y'),
                PyPtt.MailField.content: (
                    f"Header\n{contant.PTT_MSG_DIVISION_LINE}\n"
                    f"New Message\n{contant.PTT_MSG_DIVISION_LINE}\nFooter"
                ),
            }
        if api == 'del_mail':
            return None
        return None

    ptt_service_mock.call.side_effect = call_side_effect
    db_mock.save_message.return_value = True

    worker._poll_new_mails()

    # 應該有呼叫 get_mail（代表有進行掃描，而非跳過）
    api_calls = [c[0][0] for c in ptt_service_mock.call.call_args_list]
    assert 'get_mail' in api_calls


def test_poll_content_none_skips_gracefully(worker, ptt_service_mock, db_mock):
    """信件 content 為 None 時應跳過而非崩潰"""
    def call_side_effect(api, args=None):
        if api == 'get_newest_index':
            return 1
        if api == 'get_mail':
            return {
                PyPtt.MailField.title: contant.PTT_MSG_TITLE,
                PyPtt.MailField.author: "SenderID (Nick)",
                PyPtt.MailField.date: datetime.now().strftime('%a %b %d %H:%M:%S %Y'),
                # content 欄位缺失
            }
        return None

    ptt_service_mock.call.side_effect = call_side_effect
    worker.is_first_polling = False

    # 不應拋出 KeyError
    worker._poll_new_mails()

    # save_message 不應被呼叫（因為 content 為 None，直接跳過）
    db_mock.save_message.assert_not_called()


def test_initial_scan_save_failure_skips_deletion(ptt_service_mock, db_mock):
    """do_initial_scan 中 save_message 失敗時不應刪除 PTT 信件"""
    import sqlite3

    ptt_service_mock.ptt_id = "TestUser"
    call_log = []

    def call_side_effect(api, args=None):
        call_log.append(api)
        if api == 'get_newest_index':
            return 1
        if api == 'get_mail':
            return {
                PyPtt.MailField.title: contant.PTT_MSG_TITLE,
                PyPtt.MailField.author: "SenderID (Nick)",
                PyPtt.MailField.date: datetime.now().strftime('%a %b %d %H:%M:%S %Y'),
                PyPtt.MailField.content: (
                    f"Header\n{contant.PTT_MSG_DIVISION_LINE}\n"
                    f"Test Message\n{contant.PTT_MSG_DIVISION_LINE}\nFooter"
                ),
            }
        return None

    ptt_service_mock.call.side_effect = call_side_effect
    db_mock.save_message.side_effect = sqlite3.OperationalError("disk I/O error")

    w = PTTWorker(ptt_service_mock, db_mock)
    w.do_initial_scan(7)

    assert 'del_mail' not in call_log


def test_author_without_space_before_nickname(qtbot, worker, ptt_service_mock, db_mock):
    """author 欄位暱稱前無空格時，sender_id 應正確提取 PTT ID"""
    def call_side_effect(api, args=None):
        if api == 'get_newest_index':
            return 1
        if api == 'get_mail':
            return {
                PyPtt.MailField.title: "一般站內信",
                PyPtt.MailField.author: "SenderID(暱稱)",  # 無空格
                PyPtt.MailField.date: datetime.now().strftime('%a %b %d %H:%M:%S %Y'),
                PyPtt.MailField.content: "test content"
            }
        return None

    ptt_service_mock.call.side_effect = call_side_effect
    db_mock.save_message.return_value = True
    worker.is_first_polling = False

    with qtbot.waitSignal(worker.new_message_received) as blocker:
        worker._poll_new_mails()

    # sender 應為 "SenderID" 而非 "SenderID(暱稱)"
    assert blocker.args[0]['sender'] == "SenderID"
