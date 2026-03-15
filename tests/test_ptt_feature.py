import pytest
from unittest.mock import MagicMock, patch
from src.uPtt.ptt import UPttService

class MockNoSuchUser(Exception):
    pass

def test_get_user_info_success():
    service = UPttService()
    service.ptt_id = "test_user"
    service.ptt_pw = "test_pw"
    
    # Mock the internal call to PyPtt
    mock_response = {
        'ptt_id': 'CodingMan (bug maker)',
        'other_info': '...'
    }
    
    with patch.object(service, 'call', return_value=mock_response):
        info = service.get_user_info("codingman")
        # In current logic, full_id_str is "CodingMan (bug maker)"
        # true_id = full_id_str[:start_idx].strip() -> "CodingMan"
        assert info['ptt_id'] == "CodingMan"
        assert info['nickname'] == "bug maker"

def test_get_user_info_no_nickname():
    service = UPttService()
    service.ptt_id = "test_user"
    service.ptt_pw = "test_pw"
    
    mock_response = {
        'ptt_id': 'JustID',
        'other_info': '...'
    }
    
    with patch.object(service, 'call', return_value=mock_response):
        info = service.get_user_info("justid")
        assert info['ptt_id'] == "JustID"
        assert info['nickname'] == ""

def test_get_user_info_not_found():
    service = UPttService()
    service.ptt_id = "test_user"
    service.ptt_pw = "test_pw"
    
    # Simulate NoSuchUser exception from PyPtt
    with patch.object(service, 'call', side_effect=Exception("NoSuchUser: non_existent")):
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
        
        mock_get_info.return_value = {'ptt_id': 'CorrectID', 'nickname': 'MyNick'}
        
        # Call login with lowercase
        success = service.login("correctid", "password")
        
        assert success is True
        assert service.ptt_id == "CorrectID"
        mock_get_info.assert_called_once_with("correctid")
