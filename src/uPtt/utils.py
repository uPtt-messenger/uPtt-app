import os
import re
import sys

import requests

try:
    from . import contant, __version__, __name__ as pkg_name
    from . import config
except ImportError:
    import contant
    from __init__ import __version__, __name__ as pkg_name
    import config

SECOND = 1
MINUTE = 60 * SECOND
HOUR = 60 * MINUTE
DAY = 24 * HOUR
WEEK = 7 * DAY




def get_app_data_dir():
    """取得跨平台標準的應用程式資料夾路徑 (macOS, Windows, Linux)。"""
    app_name = "uPtt"
    if sys.platform == "win32":
        path = os.path.join(os.environ.get("APPDATA"), app_name)
    elif sys.platform == "darwin":
        path = os.path.expanduser(f"~/Library/Application Support/{app_name}")
    else:
        path = os.path.expanduser(f"~/.local/share/{app_name}")
    
    # 確保資料夾存在
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    return path


def gen_random_string(length=10):
    """Generate a random string of fixed length."""
    import random
    import string

    letters = string.ascii_letters + string.digits
    return ''.join(random.choice(letters) for _ in range(length))


# convert msg to PTT mail format

_REPLY_RE = re.compile(r'^\[re:@([^\|\]]+)\|([^\]]*)\]\n(.*)', re.DOTALL)
_REPLY_PREVIEW_MAX = 80


def encode_reply(sender_id: str, preview: str, actual_msg: str) -> str:
    """將回覆資訊編碼進訊息內容中。"""
    preview_flat = preview.replace('\n', ' ').replace('|', ' ').replace(']', ' ')[:_REPLY_PREVIEW_MAX]
    return f'[re:@{sender_id}|{preview_flat}]\n{actual_msg}'


def decode_reply(content: str):
    """解析訊息中的回覆資訊。回傳 (reply_info_dict 或 None, actual_text)。"""
    m = _REPLY_RE.match(content)
    if m:
        return {'sender': m.group(1), 'preview': m.group(2)}, m.group(3)
    return None, content


def msg_to_mail(app_name, ptt_id, msg):
    mail = f"""{ptt_id} 想要使用 {app_name} 跟你聯繫！

回覆請至以下網址下載 {app_name} 回覆訊息！
{contant.DOWNLOAD_URL}

{contant.PTT_MSG_DIVISION_LINE}
{msg}
{contant.PTT_MSG_DIVISION_LINE}
"""
    return mail


def get_latest_pypi_version(is_test: bool=False):
    """查詢 PyPI 上指定套件的最新版本。"""

    print(f"Checking latest version from {'Test' if is_test else 'PyPI'}...")
    try:
        url = f"https://{'test.' if is_test else ''}pypi.org/pypi/{pkg_name}/json"

        response = requests.get(url)
        response.raise_for_status()  # 如果請求失敗則拋出異常
        data = response.json()
        latest_version = data["info"]["version"]
        return latest_version
    except requests.exceptions.RequestException as e:
        return f"Error fetching data: {e}"
    except KeyError:
        return "Error: Could not find version info in the response."

def is_running_from_pypi_install():
    script_path = os.path.abspath(__file__)
    for path in sys.path:
        if "site-packages" in path or "dist-packages" in path:
            if script_path.startswith(path):
                return True
    return False


def is_update_available():
    """比較目前版本與最新版本，判斷是否有更新可用。"""
    from packaging import version

    current_version = __version__
    # current_version = '0.1.0.dev20250925150919'
    latest_version = get_latest_pypi_version(
        'dev' in current_version or not is_running_from_pypi_install()
    )

    try:
        current_ver = version.parse(current_version)
        latest_ver = version.parse(latest_version)
        return latest_ver > current_ver
    except Exception as e:
        print(f"Error comparing versions: {e}")
        return False



if __name__ == '__main__':
    print(gen_random_string(16))
    print(msg_to_mail("test app name", "test_user", "測試測試訊息"))

    print(is_update_available())
