import os
import sys
import pytest
import string
from unittest.mock import patch, MagicMock
import requests

sys.path.append(os.getcwd())

from src.uPtt.utils import (
    gen_random_string, msg_to_mail,
    get_latest_github_release_version,
    is_update_available, get_app_data_dir,
    VersionCheckWorker,
)
from src.uPtt import contant

def test_get_app_data_dir():
    with patch('sys.platform', 'win32'):
        with patch.dict(os.environ, {"APPDATA": "/tmp/appdata"}):
            with patch('os.path.exists', return_value=True):
                path = get_app_data_dir()
                assert "uPtt" in path
                assert path.startswith("/tmp/appdata")

    with patch('sys.platform', 'darwin'):
        with patch('os.path.expanduser', return_value="/tmp/test/Library/Application Support/uPtt"):
            with patch('os.path.exists', return_value=True):
                path = get_app_data_dir()
                assert "Library/Application Support/uPtt" in path

    with patch('sys.platform', 'linux'):
        with patch('os.path.expanduser', return_value="/tmp/test/.local/share/uPtt"):
            with patch('os.path.exists', return_value=False):
                with patch('os.makedirs') as mock_mkdir:
                    path = get_app_data_dir()
                    assert ".local/share/uPtt" in path
                    mock_mkdir.assert_called_once()

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
    
    expected_mail = f"""{ptt_id} 想要使用 {app_name} 跟你聯繫！

回覆請至以下網址下載 {app_name} 回覆訊息！
{contant.DOWNLOAD_URL}

{contant.PTT_MSG_DIVISION_LINE}
{msg}
{contant.PTT_MSG_DIVISION_LINE}
"""
    
    result = msg_to_mail(app_name, ptt_id, msg)
    assert result == expected_mail

# --- GitHub Release version tests ---

@patch('requests.get')
def test_get_latest_github_release_version_success(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"tag_name": "v1.5.0"}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    version = get_latest_github_release_version()
    assert version == "1.5.0"
    assert "api.github.com" in mock_get.call_args[0][0]

@patch('requests.get')
def test_get_latest_github_release_version_strips_v(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"tag_name": "v2.0.0"}
    mock_get.return_value = mock_response

    assert get_latest_github_release_version() == "2.0.0"

@patch('requests.get')
def test_get_latest_github_release_version_no_prefix(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"tag_name": "3.1.0"}
    mock_get.return_value = mock_response

    assert get_latest_github_release_version() == "3.1.0"

@patch('requests.get')
def test_get_latest_github_release_version_failure(mock_get):
    mock_get.side_effect = requests.exceptions.RequestException("Network error")
    result = get_latest_github_release_version()
    assert "Error fetching data" in result

@patch('requests.get')
def test_get_latest_github_release_version_key_error(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"wrong_key": "nope"}
    mock_get.return_value = mock_response

    result = get_latest_github_release_version()
    assert "Could not find tag_name" in result


# --- is_update_available tests ---

@patch('src.uPtt.utils.get_latest_github_release_version')
@patch('src.uPtt.utils.__version__', "1.0.0")
def test_is_update_available_true(mock_get_gh):
    """有新版本時回傳 True"""
    mock_get_gh.return_value = "1.1.0"
    assert is_update_available() is True
    mock_get_gh.assert_called_once()

@patch('src.uPtt.utils.get_latest_github_release_version')
@patch('src.uPtt.utils.__version__', "1.2.0")
def test_is_update_available_false(mock_get_gh):
    """已是最新版本時回傳 False"""
    mock_get_gh.return_value = "1.1.0"
    assert is_update_available() is False

@patch('src.uPtt.utils.get_latest_github_release_version', return_value="1.1.0")
@patch('src.uPtt.utils.__version__', "1.0.0")
def test_is_update_available_exception(mock_get_gh):
    with patch('packaging.version.parse', side_effect=Exception("Parse error")):
        assert is_update_available() is False


# --- VersionCheckWorker tests ---

class TestVersionCheckWorker:
    @patch('src.uPtt.utils.is_update_available', return_value=True)
    @patch('src.uPtt.utils.get_latest_github_release_version', return_value="2.0.0")
    @patch('src.uPtt.utils.__version__', "1.0.0")
    def test_emits_signal_when_update_available(self, *_mocks):
        """有更新時 emit GitHub release 版本"""
        worker = VersionCheckWorker()
        received = []
        worker.update_available.connect(lambda v: received.append(v))
        worker.check()
        assert received == ["2.0.0"]

    @patch('src.uPtt.utils.is_update_available', return_value=False)
    def test_no_signal_when_up_to_date(self, _mock):
        worker = VersionCheckWorker()
        received = []
        worker.update_available.connect(lambda v: received.append(v))
        worker.check()
        assert received == []

    @patch('src.uPtt.utils.is_update_available', side_effect=Exception("network error"))
    def test_no_crash_on_exception(self, _mock):
        worker = VersionCheckWorker()
        received = []
        worker.update_available.connect(lambda v: received.append(v))
        worker.check()  # should not raise
        assert received == []
