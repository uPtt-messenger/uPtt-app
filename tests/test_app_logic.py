import os
import sys

import pytest
from unittest.mock import MagicMock, patch, ANY
import PyPtt
from prompt_toolkit.buffer import Buffer

sys.path.append(os.getcwd())

from src.uPttTerm.app import UPttApp
from src.uPttTerm.ptt import UPttService
from src.uPttTerm import contant
from src.uPttTerm.contant import MsgType
from src.uPttTerm.contant import CMD


# --- Custom Mock PyPtt Exceptions to avoid i18n issues ---
class MockWrongIDorPassword(PyPtt.exceptions.WrongIDorPassword):
    def __init__(self):
        self.message = "帳號密碼錯誤"


class MockOnlySecureConnection(PyPtt.exceptions.OnlySecureConnection):
    def __init__(self):
        self.message = "只能使用安全連線"


class MockResetYourContactEmail(PyPtt.exceptions.ResetYourContactEmail):
    def __init__(self):
        self.message = "請先至信箱設定連絡信箱"


class MockLoginError(PyPtt.exceptions.LoginError):
    def __init__(self, message="登入失敗"):  # Allow message to be passed
        self.message = message


class MockNoSuchUser(PyPtt.exceptions.NoSuchUser):
    def __init__(self, user=""):  # Allow user to be passed
        self.message = "查無此人" + (f": {user}" if user else "")


# Fixture to create a UPttApp instance with mocked utils functions
@pytest.fixture
def app_instance():
    with patch('src.uPttTerm.app.utils.login_server') as mock_login_server, \
         patch('src.uPttTerm.app.utils.call_server_api') as mock_call_server_api, \
         patch('prompt_toolkit.buffer.Buffer', autospec=True) as MockBufferClass:

        # Create distinct mock instances for each buffer that UPttApp will create
        mock_id_buffer = MagicMock(spec=Buffer)
        mock_pw_buffer = MagicMock(spec=Buffer)
        mock_target_buffer = MagicMock(spec=Buffer)
        mock_input_buffer = MagicMock(spec=Buffer)

        # Configure the side_effect of MockBufferClass to return these mocks in order
        MockBufferClass.side_effect = [mock_id_buffer, mock_pw_buffer, mock_target_buffer, mock_input_buffer]

        app = UPttApp()

        # Mock the app.app (prompt_toolkit Application) as well
        app.app = MagicMock()
        app.app.layout = MagicMock()
        app.app.layout.focus = MagicMock()
        app.app.invalidate = MagicMock()
        app.app.exit = MagicMock()

        # The app instance's buffers are already the mock objects
        app.id_buffer.reset = MagicMock()
        app.pw_buffer.reset = MagicMock()
        app.target_buffer.reset = MagicMock()
        app.input_buffer.reset = MagicMock()

        # Store mocks in app instance for easy access in tests
        app.mock_login_server = mock_login_server
        app.mock_call_server_api = mock_call_server_api

        yield app


# --- Test login method ---

def test_login_success(app_instance):
    app_instance.id_buffer.text = "test_id"
    app_instance.pw_buffer.text = "test_pw"
    app_instance.mock_login_server.return_value = {'result': 'Login successful.'}

    app_instance.login()

    app_instance.mock_login_server.assert_called_once_with("test_id", "test_pw")
    assert app_instance.state == 'SELECT_TARGET'
    assert app_instance.alert_message is None


def test_login_failure(app_instance):
    app_instance.id_buffer.text = "wrong_id"
    app_instance.pw_buffer.text = "wrong_pw"
    app_instance.mock_login_server.return_value = {'error': '帳號密碼錯誤'}

    app_instance.login()

    assert app_instance.state == 'LOGIN'
    assert app_instance.alert_message == ('fg:red', '帳號密碼錯誤')
    app_instance.app.invalidate.assert_called_once()


# --- Test select_target method ---

def test_select_target_success(app_instance):
    # Setting text triggers _on_target_text_changed which calls call_server_api
    app_instance.target_buffer.text = "target_user"
    app_instance.mock_call_server_api.reset_mock()
    
    app_instance.mock_call_server_api.return_value = {'result': {'ptt_id': 'target_user (Some Name)'}}
    app_instance.state = 'SELECT_TARGET'

    # Mock start_chat as it's called internally
    with patch.object(app_instance, 'start_chat') as mock_start_chat:
        app_instance.select_target()

        app_instance.mock_call_server_api.assert_any_call(
            'get_user', {'user_id': "target_user"}
        )
        assert app_instance.state == 'CHATTING'
        assert app_instance.target == 'target_user'
        assert app_instance.alert_message is None
        mock_start_chat.assert_called_once()


def test_select_target_no_such_user(app_instance):
    # Setting text triggers _on_target_text_changed
    app_instance.target_buffer.text = "non_existent_user"
    app_instance.app.invalidate.reset_mock()
    
    app_instance.mock_call_server_api.return_value = {'error': 'NoSuchUser: non_existent_user'}
    app_instance.state = 'SELECT_TARGET'

    app_instance.select_target()

    assert app_instance.state == 'SELECT_TARGET'
    assert app_instance.alert_message == ('fg:red', '查無此人')
    app_instance.app.invalidate.assert_called()


# --- Test send_message method ---

def test_send_message_empty(app_instance):
    app_instance.input_buffer.text = "   "
    app_instance.send_message()

    # reset() is not called if text is empty after strip()
    app_instance.input_buffer.reset.assert_not_called()
    app_instance.mock_call_server_api.assert_not_called()
    app_instance.app.invalidate.assert_not_called()


def test_send_message_exit_command(app_instance):
    app_instance.input_buffer.text = CMD.EXIT
    app_instance.send_message()

    app_instance.input_buffer.reset.assert_called_once()
    app_instance.app.exit.assert_called_once()
    app_instance.mock_call_server_api.assert_not_called()


def test_send_message_success(app_instance):
    app_name = "uPttTerm"
    ptt_id = "test_id"
    target = "target_user"
    message_text = "Hello, target!"
    app_instance.ptt_id = ptt_id
    app_instance.target = target
    app_instance.input_buffer.text = message_text
    app_instance.mock_call_server_api.return_value = {'result': None}

    # Mock utils.msg_to_mail - correct patching path
    with patch('src.uPttTerm.app.utils.msg_to_mail') as mock_msg_to_mail:
        mock_msg_to_mail.return_value = "formatted_mail_content"
        app_instance.send_message()

        app_instance.input_buffer.reset.assert_called_once()
        mock_msg_to_mail.assert_called_once_with(contant.pkg_name, ptt_id, message_text)
        app_instance.mock_call_server_api.assert_called_once_with(
            'mail',
            {'ptt_id': target, 'title': contant.PTT_MSG_TITLE, 'content': "formatted_mail_content", 'backup': False}
        )
        assert (MsgType.USER, ANY, message_text) in app_instance.messages
        app_instance.app.invalidate.assert_called_once()