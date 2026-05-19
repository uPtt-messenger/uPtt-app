import pytest
from PySide6.QtCore import QTimer
from unittest.mock import MagicMock, patch
import PyPtt
from datetime import datetime, timedelta

from src.uPtt.worker import PTTWorker, QueryWorker
from src.uPtt.ptt import UPttService
from src.uPtt import contant

@pytest.fixture(autouse=True)
def patch_pyptt_i18n():
    """全域 Patch PyPtt.i18n 屬性，避免 Exception 實例化時因缺少語系字串而失敗。"""
    attributes = {
        'mail_box_full': '郵件已滿',
        'connection_closed': '連線中斷',
        'wrong_id_pw': '帳號或密碼錯誤',
        'login_too_often': '登入太頻繁',
        'require_login': '請先登入',
    }
    with patch.multiple(PyPtt.i18n, create=True, **attributes):
        yield

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

@pytest.fixture
def query_worker(ptt_service_mock, db_mock):
    return QueryWorker(ptt_service_mock, db_mock)

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
    
    # 登入失敗時應回傳固定的使用者友善訊息，而非原始 exception 內容
    assert blocker.args == [False, "連線失敗，請檢查網路連線"]

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
        worker.enqueue_send("ReceiverID", "Hello PTT", None, 42)
        worker.send_message("ReceiverID", "Hello PTT", None, 42)

    assert blocker.args == [42, True, ""]
    ptt_service_mock.call.assert_called()
    # Pending row 由 UI 端寫入，worker 只更新狀態
    db_mock.save_message.assert_not_called()
    db_mock.update_message_status.assert_called_once_with(42, 'sent')

def test_send_message_failure(qtbot, worker, ptt_service_mock, db_mock):
    ptt_service_mock.call.side_effect = Exception("Send Error")

    with qtbot.waitSignal(worker.send_result) as blocker:
        worker.enqueue_send("receiver", "Hello", None, 7)
        worker.send_message("receiver", "Hello", None, 7)

    assert blocker.args == [7, False, "發送失敗，請稍後再試"]
    db_mock.update_message_status.assert_called_once_with(7, 'failed')


def test_send_message_updates_db_before_emitting_signal(qtbot, worker, ptt_service_mock, db_mock):
    """on_send_result may reload from DB; status update must happen first."""
    worker.ptt.ptt_id = "SenderID"
    call_order = []
    db_mock.update_message_status.side_effect = lambda *a, **k: call_order.append('db')

    def emit_recorder(*args):
        call_order.append('emit')

    worker.send_result.connect(emit_recorder)
    worker.enqueue_send("ReceiverID", "Hello", None, 99)
    worker.send_message("ReceiverID", "Hello", None, 99)
    qtbot.wait(50)

    assert call_order == ['db', 'emit']


def test_send_message_no_msg_id_skips_status_update(qtbot, worker, ptt_service_mock, db_mock):
    """msg_id <= 0 時（UI pending 寫入失敗），仍應發出，但不更新 DB 狀態。"""
    worker.ptt.ptt_id = "SenderID"

    with qtbot.waitSignal(worker.send_result) as blocker:
        worker.enqueue_send("ReceiverID", "Hello", None, -1)
        worker.send_message("ReceiverID", "Hello", None, -1)

    assert blocker.args == [-1, True, ""]
    db_mock.update_message_status.assert_not_called()

def test_get_user_info_success(qtbot, query_worker, ptt_service_mock, db_mock):
    ptt_service_mock.get_user_info.return_value = {
        'ptt_id': 'CorrectID',
        'nickname': 'CoolNick',
        'is_online': True,
    }

    with qtbot.waitSignal(query_worker.user_info_result) as blocker:
        query_worker.get_user_info("correctid")

    result = blocker.args[0]
    assert result['ptt_id'] == 'CorrectID'
    assert result['nickname'] == 'CoolNick'
    assert result['is_online'] is True
    db_mock.upsert_session.assert_called_once()

def test_get_user_info_value_error(qtbot, query_worker, ptt_service_mock):
    ptt_service_mock.get_user_info.side_effect = ValueError("NoSuchUser")

    with qtbot.waitSignal(query_worker.user_info_error) as blocker:
        query_worker.get_user_info("ghost")

    assert blocker.args == ["ghost", "NoSuchUser"]

def test_get_user_info_exception(qtbot, query_worker, ptt_service_mock):
    ptt_service_mock.get_user_info.side_effect = Exception("Random Error")

    with qtbot.waitSignal(query_worker.user_info_error) as blocker:
        query_worker.get_user_info("user")

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
    """信件 content 為 None 時應跳過而非崩潰，non-backup 不刪除（保守策略）"""
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
                # content 欄位缺失
            }
        return None

    ptt_service_mock.call.side_effect = call_side_effect
    worker.is_first_polling = False

    worker._poll_new_mails()

    db_mock.save_message.assert_not_called()
    assert 'del_mail' not in call_log


def test_poll_malformed_uptt_content_falls_back_to_mail(qtbot, worker, ptt_service_mock, db_mock):
    """對方在 PTT 回覆 uPtt 信件並刪去格式時，應 fallback 為一般站內信顯示，不刪除信件"""
    call_log = []
    plain_content = "你好，這是回覆"
    reply_title = f"Re: {contant.PTT_MSG_TITLE}"

    def call_side_effect(api, args=None):
        call_log.append(api)
        if api == 'get_newest_index':
            return 1
        if api == 'get_mail':
            return {
                PyPtt.MailField.title: reply_title,
                PyPtt.MailField.author: "SenderID (Nick)",
                PyPtt.MailField.date: datetime.now().strftime('%a %b %d %H:%M:%S %Y'),
                PyPtt.MailField.content: plain_content,
            }
        return None

    ptt_service_mock.call.side_effect = call_side_effect
    db_mock.save_message.return_value = True
    worker.is_first_polling = False

    with qtbot.waitSignal(worker.new_message_received) as blocker:
        worker._poll_new_mails()

    assert 'del_mail' not in call_log
    saved_kwargs = db_mock.save_message.call_args.kwargs
    assert saved_kwargs['mail_type'] == 'mail'
    assert saved_kwargs['subject'] == reply_title
    assert blocker.args[0]['mail_type'] == 'mail'
    assert blocker.args[0]['sender'] == 'SenderID'


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


def test_waterball_fingerprint_order_independent(worker):
    """Fix #6: Waterball batch fingerprint should be order-independent to avoid false mismatches."""
    wb_a = {
        PyPtt.WaterballField.target: 'UserA',
        PyPtt.WaterballField.content: 'Hello',
        PyPtt.WaterballField.date: '01/01',
        PyPtt.WaterballField.type: PyPtt.WaterballType.SEND,
    }
    wb_b = {
        PyPtt.WaterballField.target: 'UserB',
        PyPtt.WaterballField.content: 'World',
        PyPtt.WaterballField.date: '01/02',
        PyPtt.WaterballField.type: PyPtt.WaterballType.CATCH,
    }

    # Build fingerprint in order [A, B]
    batch_ab = sorted([
        (wb.get(PyPtt.WaterballField.target, ''),
         wb.get(PyPtt.WaterballField.content, ''),
         wb.get(PyPtt.WaterballField.date, ''),
         wb.get(PyPtt.WaterballField.type))
        for wb in [wb_a, wb_b]
    ])

    # Build fingerprint in order [B, A]
    batch_ba = sorted([
        (wb.get(PyPtt.WaterballField.target, ''),
         wb.get(PyPtt.WaterballField.content, ''),
         wb.get(PyPtt.WaterballField.date, ''),
         wb.get(PyPtt.WaterballField.type))
        for wb in [wb_b, wb_a]
    ])

    assert str(batch_ab) == str(batch_ba)


# ── QueryWorker 專屬測試 ──────────────────────────────────────────

def test_query_worker_init(query_worker):
    """QueryWorker 初始狀態:未降級,無 timer,無佇列。"""
    assert query_worker._degraded is False
    assert query_worker._online_check_timer is None
    assert query_worker._active_chat_online_timer is None
    assert query_worker._active_chat_id is None
    assert query_worker._online_check_queue == []


def test_query_worker_do_login_success_starts_polling(qtbot, query_worker, ptt_service_mock):
    """副 session 登入成功應啟動在線輪詢 timer,並清除降級狀態。"""
    ptt_service_mock.login.return_value = True
    # 預先把 query_worker 設為降級,驗證登入成功會恢復
    query_worker._degraded = True

    with qtbot.waitSignal(query_worker.query_session_restored):
        query_worker.do_login("testuser", "testpass")

    ptt_service_mock.login.assert_called_once_with("testuser", "testpass", force=False)
    assert query_worker._online_check_timer is not None
    assert query_worker._online_check_timer.isActive()
    assert query_worker._degraded is False


def test_query_worker_do_login_failure_marks_degraded(qtbot, query_worker, ptt_service_mock):
    """副 session 登入失敗應發射 query_session_degraded。"""
    ptt_service_mock.login.side_effect = Exception("LoginTooOften")

    with qtbot.waitSignal(query_worker.query_session_degraded):
        query_worker.do_login("testuser", "testpass")

    assert query_worker._degraded is True
    assert query_worker._online_check_timer is None


def test_query_worker_connection_closed_marks_degraded(qtbot, query_worker, ptt_service_mock):
    """查詢時遇到 ConnectionClosed 應進入降級狀態。"""
    # bypass __init__ — i18n strings aren't loaded until PyPtt.Service() runs
    ptt_service_mock.get_user_info.side_effect = PyPtt.ConnectionClosed.__new__(PyPtt.ConnectionClosed)

    with qtbot.waitSignal(query_worker.query_session_degraded):
        query_worker.get_user_info("target")

    assert query_worker._degraded is True


def test_query_worker_successful_call_restores(qtbot, query_worker, ptt_service_mock):
    """降級後成功查詢應發射 query_session_restored。"""
    query_worker._degraded = True
    ptt_service_mock.get_user_info.return_value = {
        'ptt_id': 'Target',
        'nickname': 'Nick',
        'is_online': True,
    }

    with qtbot.waitSignal(query_worker.query_session_restored):
        query_worker.get_user_info("target")

    assert query_worker._degraded is False


def test_query_worker_skips_when_not_logged_in(query_worker, ptt_service_mock):
    """副 session 未登入(ptt_id=None)時,查詢應靜默跳過,不呼叫 PyPtt。"""
    ptt_service_mock.ptt_id = None

    query_worker.get_user_info("someone")

    ptt_service_mock.get_user_info.assert_not_called()


def test_query_worker_stop_closes_session(query_worker, ptt_service_mock):
    """停止時應關閉 timer 並登出副 session。"""
    query_worker._online_check_timer = MagicMock(spec=QTimer)
    query_worker._active_chat_online_timer = MagicMock(spec=QTimer)

    query_worker.stop()

    query_worker._online_check_timer  # 確認引用還在 (stop 之前)
    ptt_service_mock.close.assert_called_once()


def test_ptt_service_kick_on_reconnect_flag():
    """UPttService 預設允許重連 kick;副 session 應能關閉此行為。"""
    from src.uPtt.ptt import UPttService
    with patch('src.uPtt.ptt.PyPtt.Service') as mock_svc:
        main = UPttService()
        assert main.kick_on_reconnect is True

        query = UPttService(kick_on_reconnect=False)
        assert query.kick_on_reconnect is False


# ── 新增測試 ──────────────────────────────────────────────────

def test_do_skip_scan(qtbot, worker, ptt_service_mock, db_mock):
    """do_skip_scan 應設定 last_poll_time、發射 scan_complete、啟動輪詢。"""
    ptt_service_mock.ptt_id = "TestUser"

    with qtbot.waitSignal(worker.scan_complete):
        worker.do_skip_scan()

    assert worker.last_poll_time is not None
    assert worker.is_first_polling is False
    db_mock.set_config.assert_called()
    assert worker.polling_timer is not None


def test_connection_lost_signal(qtbot, worker, ptt_service_mock, db_mock):
    """輪詢時遇到 ConnectionClosed 應發射 connection_lost。"""
    ptt_service_mock.ptt_id = "TestUser"
    worker._was_connected = True
    worker.last_poll_time = datetime.now()
    ptt_service_mock.call.side_effect = PyPtt.ConnectionClosed()

    with qtbot.waitSignal(worker.connection_lost):
        worker._poll_new_mails()


def test_query_worker_queues_requests_before_login(query_worker, ptt_service_mock):
    """副 session 登入前的 user_info 請求應被暫存。"""
    ptt_service_mock.ptt_id = None

    query_worker.get_user_info("friend1")
    query_worker.get_user_info("friend2")

    ptt_service_mock.get_user_info.assert_not_called()
    assert len(query_worker._pending_user_info) == 2
    assert "friend1" in query_worker._pending_user_info


def test_query_worker_replays_after_login(qtbot, query_worker, ptt_service_mock, db_mock):
    """副 session 登入後應將暫存請求排入 replay 佇列。"""
    ptt_service_mock.ptt_id = None
    query_worker._pending_user_info = ["friend1", "friend2"]

    ptt_service_mock.login.return_value = True
    ptt_service_mock.ptt_id = "TestUser"
    ptt_service_mock.get_user_info.return_value = {
        'ptt_id': 'Friend1',
        'nickname': 'nick',
        'is_online': True,
    }

    query_worker.do_login("TestUser", "pass")

    # 暫存佇列應已清空，轉移至 replay 佇列（由 QTimer 逐筆處理）
    assert len(query_worker._pending_user_info) == 0
    # replay_queue 可能已開始處理（第一筆在 500ms 後），但至少不為空或已完成
    # 直接驗證 _replay_next_pending 方法可正確執行
    query_worker._replay_queue = ["friend3"]
    query_worker._replay_next_pending()
    ptt_service_mock.get_user_info.assert_called()


def test_do_login_wrong_password(qtbot, worker, ptt_service_mock):
    """帳號密碼錯誤應回傳固定訊息。"""
    ptt_service_mock.login.side_effect = PyPtt.WrongIDorPassword()

    with qtbot.waitSignal(worker.login_result) as blocker:
        worker.do_login("user", "wrong")

    assert blocker.args == [False, "帳號或密碼錯誤"]


def test_do_login_too_often(qtbot, worker, ptt_service_mock):
    """登入太頻繁應回傳固定訊息。"""
    ptt_service_mock.login.side_effect = PyPtt.LoginTooOften()

    with qtbot.waitSignal(worker.login_result) as blocker:
        worker.do_login("user", "pass")

    assert blocker.args == [False, "登入太頻繁，請稍後再試"]


# --- Issue #11: 使用者信箱已滿 (MailboxFull) 處理 ---
#
# 背景：
# PyPtt 的 del_mail() 在刪信後檢查 is_mailbox_full，若為 True 會：
#   1. 呼叫 api.logout() — 立即中斷 PTT 連線、清除內部 _is_login
#   2. raise MailboxFull() — 拋出例外（message="郵件已滿"）
#
# 在生產環境中，PyPtt.Service() 建立時會呼叫 i18n.init()，
# 此時 i18n.mail_box_full = "郵件已滿" 存在，MailboxFull 可正常實例化。
# 但測試環境中我們使用 MagicMock 取代 UPttService，未建立真正的 PyPtt.Service，
# 因此 i18n.mail_box_full 不存在，需要 patch 才能建立 MailboxFull 例外物件。


def _make_mailbox_full():
    """建立 PyPtt.MailboxFull 例外。"""
    return PyPtt.MailboxFull()


def _make_uptt_mail_call_side_effect(mail_idx_to_fail_on=None):
    """
    建立模擬 ptt.call 的 side_effect：
    - get_newest_index：回傳 1
    - get_mail：回傳一封合法的 uPtt 訊息
    - del_mail：若 index 符合 mail_idx_to_fail_on，拋出 MailboxFull
    """
    mailbox_full_exc = _make_mailbox_full()

    def call_side_effect(api, args=None):
        if api == 'get_newest_index':
            return 1
        if api == 'get_mail':
            return {
                PyPtt.MailField.title: contant.PTT_MSG_TITLE,
                PyPtt.MailField.author: "SenderUser (Nick)",
                PyPtt.MailField.date: "Wed Apr  1 10:00:00 2026",
                PyPtt.MailField.content: (
                    f"Header\n{contant.PTT_MSG_DIVISION_LINE}\n"
                    f"Hello\n{contant.PTT_MSG_DIVISION_LINE}\nFooter"
                ),
            }
        if api == 'del_mail':
            idx = (args or {}).get('index')
            if mail_idx_to_fail_on is not None and idx == mail_idx_to_fail_on:
                raise mailbox_full_exc
        return None
    return call_side_effect


def test_poll_mailbox_full_emits_disconnected(worker, ptt_service_mock, qtbot):
    """
    當 del_mail 因自身信箱已滿拋出 MailboxFull 時，
    worker 應發射 disconnected 訊號（而非通用的 status_updated），
    讓 UI 可以正確處理並返回登入畫面。
    """
    worker.is_first_polling = False
    ptt_service_mock.call.side_effect = _make_uptt_mail_call_side_effect(mail_idx_to_fail_on=1)

    with qtbot.waitSignal(worker.disconnected) as blocker:
        worker._poll_new_mails()

    assert "信箱已滿" in blocker.args[0]


def test_poll_mailbox_full_stops_polling_timer(worker, ptt_service_mock, qtbot):
    """
    MailboxFull 發生時，worker 應停止 polling timer，
    防止後續輪詢持續拋出 RequireLogin 錯誤。
    """
    worker.is_first_polling = False
    worker.polling_timer = MagicMock(spec=QTimer)

    ptt_service_mock.call.side_effect = _make_uptt_mail_call_side_effect(mail_idx_to_fail_on=1)

    with qtbot.waitSignal(worker.disconnected):
        worker._poll_new_mails()

    worker.polling_timer.stop.assert_called_once()


def test_poll_mailbox_full_no_new_message_signal(worker, ptt_service_mock, db_mock, qtbot):
    """
    當 MailboxFull 在 del_mail 中斷輪詢迴圈時（訊息處理完畢後才拋出），
    new_message_received 訊號不應被發射，
    因為例外在 emit 區塊之前就中止了迴圈。

    此測試記錄現有行為：緩衝在 mails_to_emit 中的訊息會因此遺失。
    """
    worker.is_first_polling = False
    ptt_service_mock.call.side_effect = _make_uptt_mail_call_side_effect(mail_idx_to_fail_on=1)

    signals_received = []
    worker.new_message_received.connect(lambda d: signals_received.append(d))

    worker._poll_new_mails()

    # MailboxFull 在 emit 區塊前中止，不應發射任何訊號
    assert signals_received == []


def test_poll_mailbox_full_does_not_emit_status_updated(worker, ptt_service_mock, qtbot):
    """
    MailboxFull 應走 disconnected 路徑，不應發射通用的 status_updated 訊號。
    """
    worker.is_first_polling = False
    ptt_service_mock.call.side_effect = _make_uptt_mail_call_side_effect(mail_idx_to_fail_on=1)

    status_signals = []
    worker.status_updated.connect(lambda s: status_signals.append(s))

    worker._poll_new_mails()

    assert status_signals == []


def test_poll_generic_exception_still_emits_status_updated(worker, ptt_service_mock, qtbot):
    """
    非 MailboxFull 的例外（如網路逾時、伺服器錯誤等）
    仍應走通用的 status_updated 路徑，確保修復未影響既有行為。
    """
    ptt_service_mock.call.side_effect = Exception("random network error")

    with qtbot.waitSignal(worker.status_updated) as blocker:
        worker._poll_new_mails()

    assert "輪詢錯誤" in blocker.args[0]
    assert "random network error" in blocker.args[0]


# --- Issue #11: UPttService 層級測試 ---
# 以下測試直接驗證 ptt.py 的 UPttService.call() 行為，
# 確認 MailboxFull 的傳播路徑與狀態不一致問題。


def test_mailbox_full_bypasses_retry_mechanism():
    """
    驗證 UPttService.call() 的重連機制不處理 MailboxFull。

    ptt.py 的 call() 只對 ConnectionClosed 做自動重連（最多 3 次）。
    MailboxFull 不是 ConnectionClosed 的子類別，
    因此應直接傳播到上層，不觸發任何重試。
    """
    service = UPttService()
    service.ptt_id = "TestUser"
    service.ptt_pw = "TestPass"

    mailbox_full_exc = _make_mailbox_full()

    # Mock PyPtt.Service.call 讓 del_mail 拋出 MailboxFull
    service.service = MagicMock()
    service.service.call.side_effect = mailbox_full_exc

    with pytest.raises(PyPtt.MailboxFull):
        service.call('del_mail', {'index': 1})

    # 驗證只呼叫了一次（沒有重試）
    assert service.service.call.call_count == 1

    # 驗證狀態不一致：UPttService 仍然以為已登入
    assert service.ptt_id == "TestUser"
    assert service.ptt_pw == "TestPass"


def test_mailbox_full_state_inconsistency():
    """
    驗證信箱滿時的狀態不一致問題（Issue #11 的根因）。

    流程：
    1. del_mail 拋出 MailboxFull → UPttService.ptt_id/ptt_pw 仍有值
    2. 但 PyPtt 內部已 logout（_is_login=False、連線已關）
    3. 下一次 API 呼叫 → PyPtt 內部拋出 RequireLogin
    4. RequireLogin 也非 ConnectionClosed → 不重連 → 持續失敗

    這證明 MailboxFull 會造成程式進入無法自動恢復的錯誤狀態。
    """
    service = UPttService()
    service.ptt_id = "TestUser"
    service.ptt_pw = "TestPass"

    mailbox_full_exc = _make_mailbox_full()

    # Mock PyPtt.Service.call
    service.service = MagicMock()

    # 第一次呼叫：del_mail → MailboxFull（模擬 PyPtt 內部已 logout）
    service.service.call.side_effect = mailbox_full_exc
    with pytest.raises(PyPtt.MailboxFull):
        service.call('del_mail', {'index': 1})

    # 狀態不一致：UPttService 以為還在線
    assert service.ptt_id is not None
    assert service.ptt_pw is not None

    # 第二次呼叫：模擬 PyPtt 內部 _is_login=False 後的行為
    service.service.call.side_effect = PyPtt.RequireLogin("require login")
    with pytest.raises(PyPtt.RequireLogin):
        service.call('get_newest_index', {'index_type': PyPtt.NewIndex.MAIL})

    # RequireLogin 也不觸發重連（非 ConnectionClosed），只呼叫一次
    # call_count = 2（del_mail 一次 + get_newest_index 一次）
    assert service.service.call.call_count == 2
