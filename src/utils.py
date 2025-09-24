import contant


def gen_random_string(length=10):
    """Generate a random string of fixed length."""
    import random
    import string

    letters = string.ascii_letters + string.digits
    return ''.join(random.choice(letters) for _ in range(length))


# convert msg to PTT mail format

def msg_to_mail(app_name, ptt_id, msg):
    mail = f"""{ptt_id} 想要使用 {app_name} 跟你聯繫！
想要回覆請至 xxxx 下載回覆訊息！
{contant.PTT_MSG_DIVISION_LINE}
{msg}
{contant.PTT_MSG_DIVISION_LINE}
"""
    return mail


if __name__ == '__main__':
    print(gen_random_string(16))
    print(msg_to_mail("test app name", "測試測試訊息"))
