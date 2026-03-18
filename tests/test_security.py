import pytest
import logging
from unittest.mock import patch
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
