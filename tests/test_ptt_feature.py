import pytest
import time
from unittest.mock import MagicMock, patch
from src.uPtt.ptt import UPttService
import PyPtt
from security_utils import TEST_PASSWORD_CANARY

class MockNoSuchUser(Exception):
    pass

def test_get_user_info_success():
    service = UPttService()
    service.ptt_id = "test_user"
    service.ptt_pw = "test_pw"

    # Mock the internal call to PyPtt
    mock_response = {
        'ptt_id': 'CodingMan (bug maker)',
        'activity': '閱讀文章',
        'other_info': '...'
    }

    with patch.object(service, 'call', return_value=mock_response):
        info = service.get_user_info("codingman")
        # In current logic, full_id_str is "CodingMan (bug maker)"
        # true_id = full_id_str[:start_idx].strip() -> "CodingMan"
        assert info['ptt_id'] == "CodingMan"
        assert info['nickname'] == "bug maker"
        assert info['is_online'] is True

def test_get_user_info_no_nickname():
    service = UPttService()
    service.ptt_id = "test_user"
    service.ptt_pw = "test_pw"

    mock_response = {
        'ptt_id': 'JustID',
        'activity': '不在站上',
        'other_info': '...'
    }

    with patch.object(service, 'call', return_value=mock_response):
        info = service.get_user_info("justid")
        assert info['ptt_id'] == "JustID"
        assert info['nickname'] == ""
        assert info['is_online'] is False

def test_get_user_info_not_found():
    service = UPttService()
    service.ptt_id = "test_user"
    service.ptt_pw = "test_pw"
    
    # Simulate NoSuchUser exception from PyPtt
    with patch.object(service, 'call', side_effect=PyPtt.NoSuchUser("non_existent")):
        with pytest.raises(ValueError, match="查無此人"):
            service.get_user_info("non_existent")

def test_get_user_info_missing_data():
    service = UPttService()
    service.ptt_id = "test_user"
    service.ptt_pw = "test_pw"
    
    with patch.object(service, 'call', return_value={}):
        with pytest.raises(ValueError, match="無法取得使用者資訊"):
            service.get_user_info("some_user")

def test_login_id_correction():
    service = UPttService()
    
    # Mock login and get_user_info
    with patch.object(service.service, 'call') as mock_ptt_call, \
         patch.object(service, 'get_user_info') as mock_get_info:
        
        mock_get_info.return_value = {'ptt_id': 'CorrectID', 'nickname': 'MyNick', 'is_online': True}
        
        # Call login with lowercase
        success = service.login("correctid", "password")
        
        assert success is True
        assert service.ptt_id == "CorrectID"
        mock_get_info.assert_called_once_with("correctid")

def test_login_failure():
    service = UPttService()
    with patch.object(service.service, 'call', side_effect=Exception("Login failed")):
        with pytest.raises(Exception, match="Login failed"):
            service.login("user", "pass")

def test_login_failure_redacts_password_from_log(caplog):
    """威脅模型：PyPtt 例外的 str() 意外帶出呼叫參數（含明文密碼），
    login() 的 catch-all log 不得讓密碼明文落地，但 raise e 的重拋行為不變。"""
    boom = Exception(f"boom {{'ptt_pw': '{TEST_PASSWORD_CANARY}'}}")
    service = UPttService()
    with patch.object(service.service, 'call', side_effect=boom):
        with pytest.raises(Exception, match="boom"):
            service.login("user", TEST_PASSWORD_CANARY)

    assert TEST_PASSWORD_CANARY not in caplog.text

    assert TEST_PASSWORD_CANARY not in caplog.text

def test_login_get_info_failure():
    service = UPttService()
    with patch.object(service.service, 'call'), \
         patch.object(service, 'get_user_info', side_effect=Exception("API error")):
        # Should still return True
        success = service.login("user", "pass")
        assert success is True
        assert service.ptt_id == "user"

def test_call_require_login():
    service = UPttService()
    with pytest.raises(PyPtt.RequireLogin):
        service.call("some_api")

def test_call_logout():
    service = UPttService()
    service.ptt_id = "user"
    service.ptt_pw = "pass"
    with patch.object(service.service, 'call') as mock_call:
        res = service.call("logout")
        assert res is True
        assert service.ptt_id is None
        assert service.ptt_pw is None
        mock_call.assert_called_with("logout")

def test_call_retry_success():
    service = UPttService()
    service.ptt_id = "user"
    service.ptt_pw = "pass"
    service.retry_delay = 0.1

    with patch.object(service, 'reconnect', return_value=True) as mock_reconnect:
        # First call raises ConnectionClosed, reconnect succeeds, second call succeeds
        with patch.object(service.service, 'call') as mock_call:
            mock_call.side_effect = [PyPtt.ConnectionClosed(), "Success"]

            res = service.call("get_user", {"user_id": "test"})
            assert res == "Success"
            mock_reconnect.assert_called_once()

def test_call_retry_failure():
    service = UPttService()
    service.ptt_id = "user"
    service.ptt_pw = "pass"
    service.retry_delay = 0.1
    service.max_retry = 2

    with patch.object(service, 'reconnect', return_value=False) as mock_reconnect:
        with patch.object(service.service, 'call') as mock_call:
            mock_call.side_effect = PyPtt.ConnectionClosed()

            with pytest.raises(PyPtt.ConnectionClosed):
                service.call("get_user", {"user_id": "test"})

            mock_reconnect.assert_called_once()

def test_close():
    service = UPttService()
    with patch.object(service, 'call') as mock_call, \
         patch.object(service.service, 'close') as mock_close:
        service.close()
        mock_call.assert_called_with("logout")
        mock_close.assert_called_once()


# ── Issue #2: reconnect 退避策略與鎖範圍 ──────────────────────────
# UPttService() 先於 monkeypatch 建立，其 __init__ 會初始化 PyPtt i18n，
# 使得 PyPtt.LoginTooOften()/LoginError() 可正常實例化。


def _login_raiser(exc_factory, calls=None):
    """回傳一個 fake PyPtt.Service factory：其 .call('login', ...) 拋出指定例外。"""
    def factory(*args, **kwargs):
        svc = MagicMock()

        def call(api, args=None):
            if api == 'login':
                if calls is not None:
                    calls.append(args)
                raise exc_factory()
        svc.call.side_effect = call
        return svc
    return factory


def test_reconnect_login_too_often_backs_off_60s_max_5(monkeypatch):
    """LoginTooOften 時應等待 60 秒並最多重試 5 次（mock sleep，不真等）。"""
    service = UPttService()
    service.ptt_id = "user"
    service.ptt_pw = "pass"
    service.service = MagicMock()
    UPttService._last_reconnect_ts = 0.0

    sleeps = []
    monkeypatch.setattr("src.uPtt.ptt.time.sleep", lambda s: sleeps.append(s))
    login_calls = []
    monkeypatch.setattr("src.uPtt.ptt.PyPtt.Service",
                        _login_raiser(PyPtt.LoginTooOften, login_calls))

    result = service.reconnect()

    assert result is False
    assert len(login_calls) == 5     # 最多 5 次
    assert 60 in sleeps              # LoginTooOften 等待 60 秒
    assert 3 not in sleeps


def test_reconnect_login_error_waits_3s(monkeypatch):
    """一般 LoginError 失敗時應等待 3 秒後重試。"""
    service = UPttService()
    service.ptt_id = "user"
    service.ptt_pw = "pass"
    service.service = MagicMock()
    UPttService._last_reconnect_ts = 0.0

    sleeps = []
    monkeypatch.setattr("src.uPtt.ptt.time.sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr("src.uPtt.ptt.PyPtt.Service", _login_raiser(PyPtt.LoginError))

    result = service.reconnect()

    assert result is False
    assert sleeps.count(3) == 5      # 每次一般失敗等待 3 秒
    assert 60 not in sleeps


def test_reconnect_login_happens_within_lock(monkeypatch):
    """實際 login 呼叫必須在持有 _reconnect_lock 期間發生（序列化雙 session）。"""
    service = UPttService()
    service.ptt_id = "user"
    service.ptt_pw = "pass"
    service.service = MagicMock()
    UPttService._last_reconnect_ts = 0.0
    monkeypatch.setattr("src.uPtt.ptt.time.sleep", lambda s: None)

    lock_state_at_login = []

    def factory(*args, **kwargs):
        svc = MagicMock()

        def call(api, args=None):
            if api == 'login':
                lock_state_at_login.append(UPttService._reconnect_lock.locked())
        svc.call.side_effect = call
        return svc

    monkeypatch.setattr("src.uPtt.ptt.PyPtt.Service", factory)

    result = service.reconnect()

    assert result is True
    assert lock_state_at_login == [True]


def test_reconnect_backoff_releases_lock(monkeypatch):
    """backoff sleep 期間必須釋放 _reconnect_lock，讓另一 session 能取得鎖並登入。

    基線（整個重試迴圈含 sleep 都在鎖內）→ sleep 時鎖仍被持有 → FAIL；
    修後（backoff sleep 移出鎖）→ sleep 時鎖已釋放 → PASS。
    """
    service = UPttService()
    service.ptt_id = "user"
    service.ptt_pw = "pass"
    service.service = MagicMock()
    UPttService._last_reconnect_ts = 0.0

    lock_held_during_backoff = []

    def fake_sleep(s):
        if s == 3:  # LoginError 的 3s backoff
            lock_held_during_backoff.append(UPttService._reconnect_lock.locked())
    monkeypatch.setattr("src.uPtt.ptt.time.sleep", fake_sleep)

    # 第一次 login 失敗（LoginError → 3s backoff），第二次成功
    attempts = {'n': 0}

    def factory(*args, **kwargs):
        svc = MagicMock()

        def call(api, args=None):
            if api == 'login':
                attempts['n'] += 1
                if attempts['n'] == 1:
                    raise PyPtt.LoginError()
        svc.call.side_effect = call
        return svc

    monkeypatch.setattr("src.uPtt.ptt.PyPtt.Service", factory)

    result = service.reconnect()

    assert result is True
    # backoff sleep 期間鎖必須已釋放，否則另一 session 被卡住最長 300s
    assert lock_held_during_backoff == [False]


def test_reconnect_wrong_credentials_gives_up_immediately(monkeypatch):
    """reconnect() 遇 WrongIDorPassword → 不 sleep、單次嘗試即 return False。"""
    service = UPttService()
    service.ptt_id = "user"
    service.ptt_pw = "pass"
    service.service = MagicMock()
    UPttService._last_reconnect_ts = 0.0

    sleeps = []
    monkeypatch.setattr("src.uPtt.ptt.time.sleep", lambda s: sleeps.append(s))
    login_calls = []
    monkeypatch.setattr("src.uPtt.ptt.PyPtt.Service",
                        _login_raiser(PyPtt.WrongIDorPassword, login_calls))

    result = service.reconnect()

    assert result is False
    assert len(login_calls) == 1   # 立即放棄，只嘗試一次
    assert sleeps == []            # 完全不 sleep


def test_reconnect_generic_failure_redacts_password_from_log(monkeypatch, caplog):
    """威脅模型：同 test_login_failure_redacts_password_from_log，但走 reconnect()
    的 generic Exception 分支（ptt.py 的重連失敗 log）。"""
    service = UPttService()
    service.ptt_id = "user"
    service.ptt_pw = TEST_PASSWORD_CANARY
    service.service = MagicMock()
    UPttService._last_reconnect_ts = 0.0

    monkeypatch.setattr("src.uPtt.ptt.time.sleep", lambda s: None)
    boom = Exception(f"boom {{'ptt_pw': '{TEST_PASSWORD_CANARY}'}}")
    monkeypatch.setattr("src.uPtt.ptt.PyPtt.Service", _login_raiser(lambda: boom))

    result = service.reconnect()

    assert result is False
    assert TEST_PASSWORD_CANARY not in caplog.text
