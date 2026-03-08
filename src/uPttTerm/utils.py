import json
import os
import sys

import requests

try:
    from . import contant, __version__, __name__ as pkg_name
    from . import config
except ImportError:
    import contant
    from __init__ import __version__, __name__ as pkg_name
    import config


def gen_random_string(length=10):
    """Generate a random string of fixed length."""
    import random
    import string

    letters = string.ascii_letters + string.digits
    return ''.join(random.choice(letters) for _ in range(length))


# convert msg to PTT mail format

def msg_to_mail(app_name, ptt_id, msg):
    mail = f"""{ptt_id} 想要使用 {app_name} 跟你聯繫！

想要回覆請至以下網址下載回覆訊息！

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

def login_server(username, password, timeout=5):

    try:
        r = requests.get(f"http://127.0.0.1:{config.SERVICE_PORT}/api/login",
        params={
            'username': username,
            'password': password
        }, timeout=timeout)
    except requests.exceptions.ReadTimeout:
        return {
            'error': 'Login request timed out'
        }
    except requests.exceptions.ConnectionError as e:
        return {
            'error': f'Connection error: {e}'
        }

    if r.status_code != 200:
        return {
            'error': f'Server error: {r.status_code}'
        }
    return r.json()


def call_server_api(api:str, args:dict=None, timeout=30):

    try:
        r = requests.get(f"http://127.0.0.1:{config.SERVICE_PORT}/api/call",
        params={
            'api': api,
            'args': json.dumps(args) if args is not None else None
        }, timeout=timeout)
    except requests.exceptions.ReadTimeout:
        return {
            'error': 'Server request timed out'
        }
    except requests.exceptions.ConnectionError as e:
        return {
            'error': f'Connection error: {e}'
        }

    if r.status_code != 200:
        return {
            'error': f'Server error: {r.status_code}'
        }
    return r.json()

def is_server_running():

    try:
        # 縮短逾時至 1 秒，避免在啟動檢查時卡死
        r = requests.get(f"http://127.0.0.1:{config.SERVICE_PORT}/", timeout=1)
    except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
        return False

    return r.status_code == 200



if __name__ == '__main__':
    print(gen_random_string(16))
    print(msg_to_mail("test app name", "test_user", "測試測試訊息"))

    print(is_update_available())
