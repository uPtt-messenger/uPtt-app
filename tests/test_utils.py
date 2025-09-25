import pytest
import string
from src.uPttTerm.utils import gen_random_string, msg_to_mail
from src.uPttTerm import contant

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
