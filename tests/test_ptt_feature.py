import pytest
import time
from unittest.mock import MagicMock, patch
from src.uPtt.ptt import UPttService
import PyPtt

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
