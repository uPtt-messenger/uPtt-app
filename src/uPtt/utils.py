import logging
import os
import re
import sys

import requests
from PySide6.QtCore import QObject, Signal, Slot

try:
    from . import contant, __version__
    from . import config
except ImportError:
    import contant
    from __init__ import __version__
    import config

logger = logging.getLogger("uPtt.utils")

SECOND = 1
MINUTE = 60 * SECOND
HOUR = 60 * MINUTE
DAY = 24 * HOUR
WEEK = 7 * DAY




def get_app_data_dir():
    """取得跨平台標準的應用程式資料夾路徑 (macOS, Windows, Linux)。"""
    app_name = "uPtt"
    if sys.platform == "win32":
        path = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), app_name)
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



def get_latest_github_release_version():
    """查詢 GitHub Releases 上的最新正式版本。"""

    logger.info("Checking latest version from GitHub Releases...")
    try:
        url = "https://api.github.com/repos/uPtt-messenger/uPttTerm/releases/latest"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        tag = data["tag_name"]
        # 移除 tag 前綴 "v"（例如 "v0.2.0" → "0.2.0"）
        return tag.lstrip("v")
    except requests.exceptions.RequestException as e:
        return f"Error fetching data: {e}"
    except KeyError:
        return "Error: Could not find tag_name in the response."



def is_update_available():
    """比較目前版本與最新版本，判斷是否有更新可用。"""
    from packaging import version

    current_version = __version__
    latest_version = get_latest_github_release_version()

    try:
        current_ver = version.parse(current_version)
        latest_ver = version.parse(latest_version)
        return latest_ver > current_ver
    except Exception as e:
        logger.debug(f"Error comparing versions: {e}")
        return False



class VersionCheckWorker(QObject):
    """背景版本檢查 Worker，檢查完成後自動停止所屬 thread。"""
    update_available = Signal(str)  # latest_version
    finished = Signal()

    @Slot()
    def check(self):
        try:
            if is_update_available():
                latest_version = get_latest_github_release_version()
                logger.info(f"新版本可用: {latest_version} (目前: {__version__})")
                self.update_available.emit(latest_version)
            else:
                logger.info("目前已是最新版本")
        except Exception:
            logger.debug("版本檢查失敗，靜默忽略", exc_info=True)
        finally:
            self.finished.emit()


if __name__ == '__main__':
    print(gen_random_string(16))
    print(msg_to_mail("test app name", "test_user", "測試測試訊息"))

    print(is_update_available())
