import os
import sys

import string

sys.path.append(os.getcwd())

from unittest.mock import patch, MagicMock
import requests
import sys

from src.uPtt.utils import gen_random_string, msg_to_mail, get_latest_pypi_version, is_running_from_pypi_install, is_update_available, is_server_running
from src.uPtt import contant

def test_gen_random_string_length():
    length = 15
    result = gen_random_string(length)
    assert isinstance(result, str)
    assert len(result) == length

def test_gen_random_string_characters():
    result = gen_random_string(20)
    allowed_chars = string.ascii_letters + string.digits
    for char in result:
        assert char in allowed_chars

def test_msg_to_mail():
    app_name = "TestApp"
    ptt_id = "testuser"
    msg = "Hello, this is a test message."
    
    expected_mail = f"""{ptt_id} 想要使用 {app_name} 跟你聯繫！\n\n想要回覆請至以下網址下載回覆訊息！\n\n{contant.DOWNLOAD_URL}\n\n{contant.PTT_MSG_DIVISION_LINE}\n{msg}\n{contant.PTT_MSG_DIVISION_LINE}\n"""
    
    result = msg_to_mail(app_name, ptt_id, msg)
    assert result == expected_mail

@patch('requests.get')
def test_get_latest_pypi_version_success(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"info": {"version": "1.2.3"}}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    
    version = get_latest_pypi_version(is_test=False)
    assert version == "1.2.3"
    assert "pypi.org" in mock_get.call_args[0][0]

@patch('requests.get')
def test_get_latest_pypi_version_failure(mock_get):
    mock_get.side_effect = requests.exceptions.RequestException("Network error")
    
    version = get_latest_pypi_version()
    assert "Error fetching data" in version

def test_is_running_from_pypi_install_true():
    with patch('os.path.abspath', return_value="/usr/local/lib/python3.12/site-packages/uPtt/utils.py"):
        with patch('sys.path', ["/usr/local/lib/python3.12/site-packages"]):
            assert is_running_from_pypi_install() is True

def test_is_running_from_pypi_install_false():
    with patch('os.path.abspath', return_value="/home/user/git/uPtt/src/uPtt/utils.py"):
        with patch('sys.path', ["/home/user/git/uPtt/src"]):
            assert is_running_from_pypi_install() is False

@patch('src.uPtt.utils.get_latest_pypi_version')
@patch('src.uPtt.utils.__version__', "1.0.0")
def test_is_update_available_true(mock_get_latest):
    mock_get_latest.return_value = "1.1.0"
    assert is_update_available() is True

@patch('src.uPtt.utils.get_latest_pypi_version')
@patch('src.uPtt.utils.__version__', "1.2.0")
def test_is_update_available_false(mock_get_latest):
    mock_get_latest.return_value = "1.1.0"
    assert is_update_available() is False

@patch('requests.get')
def test_is_server_running_true(mock_get):
    mock_get.return_value.status_code = 200
    assert is_server_running() is True

@patch('requests.get')
def test_is_server_running_false(mock_get):
    mock_get.side_effect = requests.exceptions.ConnectionError()
    assert is_server_running() is False
