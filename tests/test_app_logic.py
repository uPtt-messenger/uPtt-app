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


# Fixture to create a UPttApp instance with a mocked PyPtt.Service
@pytest.fixture
def app_instance():
    with patch('src.uPttTerm.app.UPttService') as MockUPttService, \
         patch('prompt_toolkit.buffer.Buffer', autospec=True) as MockBufferClass:

        mock_ptt_service = MagicMock(spec=UPttService)
        MockUPttService.return_value = mock_ptt_service

        # Create distinct mock instances for each buffer that UPttApp will create
        mock_id_buffer = MagicMock(spec=Buffer)
        mock_pw_buffer = MagicMock(spec=Buffer)
        mock_target_buffer = MagicMock(spec=Buffer)
        mock_input_buffer = MagicMock(spec=Buffer)

        # Configure the side_effect of MockBufferClass to return these mocks in order
        MockBufferClass.side_effect = [mock_id_buffer, mock_pw_buffer, mock_target_buffer, mock_input_buffer]

        app = UPttApp()  # Now this will work

        # The app.ptt_service is now our mock_ptt_service
        assert app.ptt_service == mock_ptt_service

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

        yield app  # use yield for fixtures


# --- Test login method ---

def test_login_success(app_instance):
    app_instance.id_buffer.text = "test_id"
    app_instance.pw_buffer.text = "test_pw"
    app_instance.ptt_service.login.return_value = None  # Simulate successful call

    app_instance.login()

    app_instance.ptt_service.login.assert_called_once_with("test_id", "test_pw")
    assert app_instance.state == 'SELECT_TARGET'
    assert app_instance.alert_message is None
    app_instance.app.layout.focus.assert_called_once_with(app_instance.target_buffer)


def test_login_wrong_id_or_password(app_instance):
    app_instance.id_buffer.text = "wrong_id"
    app_instance.pw_buffer.text = "wrong_pw"
    app_instance.ptt_service.login.side_effect = MockWrongIDorPassword()  # Use custom mock exception

    app_instance.login()

    assert app_instance.state == 'LOGIN'
    assert app_instance.alert_message == ('fg:red', '帳號密碼錯誤')
    app_instance.app.invalidate.assert_called_once()


def test_login_only_secure_connection(app_instance):
    app_instance.id_buffer.text = "id"
    app_instance.pw_buffer.text = "pw"
    app_instance.ptt_service.login.side_effect = MockOnlySecureConnection()  # Use custom mock exception

    app_instance.login()

    assert app_instance.state == 'LOGIN'
    assert app_instance.alert_message == ('fg:red', '只能使用安全連線')
    app_instance.app.invalidate.assert_called_once()


def test_login_reset_contact_email(app_instance):
    app_instance.id_buffer.text = "id"
    app_instance.pw_buffer.text = "pw"
    app_instance.ptt_service.login.side_effect = MockResetYourContactEmail()  # Use custom mock exception

    app_instance.login()

    assert app_instance.state == 'LOGIN'
    assert app_instance.alert_message == ('fg:red', '請先至信箱設定連絡信箱')
    app_instance.app.invalidate.assert_called_once()


def test_login_generic_error(app_instance):
    app_instance.id_buffer.text = "id"
    app_instance.pw_buffer.text = "pw"
    generic_error_msg = "Some other login error"
    app_instance.ptt_service.login.side_effect = MockLoginError(generic_error_msg)  # Use custom mock exception

    app_instance.login()

    assert app_instance.state == 'LOGIN'
    assert app_instance.alert_message == ('fg:red', f'登入失敗: {generic_error_msg}')
    app_instance.app.invalidate.assert_called_once()


# --- Test select_target method ---

def test_select_target_success(app_instance):
    app_instance.target_buffer.text = "target_user"
    app_instance.ptt_service.call.return_value = {'ptt_id': 'target_user (Some Name)'}
    app_instance.state = 'SELECT_TARGET'

    # Mock start_chat as it's called internally
    with patch.object(app_instance, 'start_chat') as mock_start_chat:
        app_instance.select_target()

        app_instance.ptt_service.call.assert_called_once_with(
            'get_user', {'user_id': "target_user"}
        )
        assert app_instance.state == 'CHATTING'
        assert app_instance.target == 'target_user'
        assert app_instance.alert_message is None
        mock_start_chat.assert_called_once()
        app_instance.app.layout.focus.assert_called_once_with(app_instance.input_buffer)


def test_select_target_no_such_user(app_instance):
    app_instance.target_buffer.text = "non_existent_user"
    app_instance.ptt_service.call.side_effect = MockNoSuchUser(user="non_existent_user")  # Use custom mock exception
    app_instance.state = 'SELECT_TARGET'

    app_instance.select_target()

    assert app_instance.state == 'SELECT_TARGET'
    assert app_instance.alert_message == ('fg:red', '查無此人')
    app_instance.app.invalidate.assert_called_once()


# --- Test send_message method ---

def test_send_message_empty(app_instance):
    app_instance.input_buffer.text = "   "
    app_instance.send_message()

    # reset() is not called if text is empty after strip()
    app_instance.input_buffer.reset.assert_not_called()
    app_instance.ptt_service.call.assert_not_called()
    app_instance.app.invalidate.assert_not_called()


def test_send_message_exit_command(app_instance):
    app_instance.input_buffer.text = CMD.EXIT
    app_instance.send_message()

    app_instance.input_buffer.reset.assert_called_once()
    app_instance.app.exit.assert_called_once()
    app_instance.ptt_service.call.assert_not_called()


def test_send_message_success(app_instance):
    app_name = "uPttTerm"
    ptt_id = "test_id"
    target = "target_user"
    message_text = "Hello, target!"
    app_instance.ptt_id = ptt_id
    app_instance.target = target
    app_instance.input_buffer.text = message_text
    app_instance.ptt_service.call.return_value = None

    # Mock utils.msg_to_mail - correct patching path
    with patch('src.uPttTerm.app.utils.msg_to_mail') as mock_msg_to_mail:
        mock_msg_to_mail.return_value = "formatted_mail_content"
        app_instance.send_message()

        app_instance.input_buffer.reset.assert_called_once()
        mock_msg_to_mail.assert_called_once_with(contant.pkg_name, ptt_id, message_text)
        app_instance.ptt_service.call.assert_called_once_with(
            'mail',
            {'ptt_id': target, 'title': contant.PTT_MSG_TITLE, 'content': "formatted_mail_content", 'backup': False}
        )
        assert (MsgType.USER, ANY, message_text) in app_instance.messages
        app_instance.app.invalidate.assert_called_once()