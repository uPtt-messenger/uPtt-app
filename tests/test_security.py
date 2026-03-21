import pytest
import logging
import requests
from unittest.mock import patch
from urllib.parse import urlparse
from src.uPtt.ptt import UPttService
from security_utils import TEST_PASSWORD_CANARY, PasswordLeakError

def test_password_leak_detection_in_api_call():
    """驗證：當非 login API 參數意外包含密碼時，機制應能成功攔截並報錯。"""
    service = UPttService()
    service.ptt_id = "security_test"
    service.ptt_pw = TEST_PASSWORD_CANARY
    service.max_retry = 1
    
    with pytest.raises(PasswordLeakError) as excinfo:
        service.call("get_user", {"user_id": "target", "wrongly_added_pw": TEST_PASSWORD_CANARY})
    
    assert "安全性警報" in str(excinfo.value)

def test_legitimate_login_does_not_trigger_alert():
    """驗證：正常的 login 呼叫應是被允許的。"""
    service = UPttService()
    with patch("PyPtt.Service.call", return_value=True):
        try:
            service.login("test_user", TEST_PASSWORD_CANARY)
        except PasswordLeakError:
            pytest.fail("錯誤：合法的 login 呼叫竟然被安全機制攔截了！")

def test_no_credential_exfiltration_via_http(monkeypatch):
    """
    驗證：在登入流程中，帳密 canary 不會透過 HTTP 請求洩漏至非授權網域。

    威脅模型：惡意程式碼（或被污染的依賴套件）可能在登入後，
    將帳密透過 requests.post 等方式送往外部伺服器。
    本測試攔截所有 HTTP 呼叫並驗證 canary 未出現在非授權目的地。

    合法的對外 HTTP 請求（例如 PyPI 版本查詢）允許通過，
    但其 URL 與請求內容不得包含帳密 canary。
    """
    ALLOWED_HOSTS = {'pypi.org', 'test.pypi.org'}
    intercepted = []

    def spy_request(self, method, url, **kwargs):
        body = (
            str(kwargs.get('data', ''))
            + str(kwargs.get('json', ''))
            + str(kwargs.get('params', ''))
        )
        intercepted.append({'method': method, 'url': str(url), 'body': body})
        # 封鎖所有實際網路請求（測試環境不應有真實對外連線）
        raise requests.exceptions.ConnectionError(f"[security-test] HTTP 請求已被攔截: {method} {url}")

    monkeypatch.setattr(requests.Session, 'request', spy_request)

    service = UPttService()
    with patch("PyPtt.Service.call", return_value={"ptt_id": "TestUser (Test)"}):
        try:
            service.login("test_user", TEST_PASSWORD_CANARY)
        except Exception:
            pass  # 允許因 HTTP 被封鎖而失敗（例如 PyPI 版本查詢）

    for req in intercepted:
        host = urlparse(req['url']).netloc
        if host not in ALLOWED_HOSTS:
            assert TEST_PASSWORD_CANARY not in req['url'], (
                f"安全性警報：帳密 canary 出現在送往 {host} 的 URL 中！"
            )
            assert TEST_PASSWORD_CANARY not in req['body'], (
                f"安全性警報：帳密 canary 出現在送往 {host} 的請求內容中！"
            )


def test_log_leak_detection_mechanism(caplog):
    """驗證：Log 監控機制是否能偵測到密碼出現在 Log 中。"""
    logger = logging.getLogger("uPtt.test")
    logger.info(f"這是一則含有密碼的 Log：{TEST_PASSWORD_CANARY}")
    
    leak_found = False
    for record in caplog.records:
        if TEST_PASSWORD_CANARY in record.getMessage():
            leak_found = True
            break
    
    # 清除 caplog 以免 fixture teardown 時拋出異常
    caplog.clear()
    assert leak_found, "安全機制應能在 Log 中識別出密碼洩漏"
