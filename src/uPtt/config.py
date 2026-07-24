
# 在記憶體中最多儲存的訊息數量
MAX_MESSAGES = 256

# 每 5 秒檢查一次批踢踢信箱
CHECK_PTT_MAIL_INTERVAL = 5

# 每 10 秒檢查一次水球
CHECK_WATERBALL_INTERVAL = 10

# 每 120 秒檢查一次聯絡人在線狀態
CHECK_ONLINE_STATUS_INTERVAL = 120

# 當前開啟的對話視窗，每 10 秒檢查該使用者在線狀態
CHECK_ACTIVE_CHAT_ONLINE_INTERVAL = 10

# 在線狀態批次查詢時，每位使用者間隔 5 秒
ONLINE_CHECK_PER_USER_DELAY = 5

SERVICE_PORT = 53081

# --- 使用者可調設定（存於 DB settings 表的 key，全域非分帳號）---
SETTING_NOTIFY_ENABLED = 'setting_notify_enabled'
SETTING_MAIL_INTERVAL = 'setting_mail_interval'
SETTING_WATERBALL_INTERVAL = 'setting_waterball_interval'
SETTING_ONLINE_INTERVAL = 'setting_online_interval'
SETTING_THEME = 'setting_theme'  # 值為 uPtt.ui.theme.THEMES 的 key（預設 'graphite'）

# 輪詢間隔下限（秒），避免過度頻繁請求導致 PTT 限流
MAIL_INTERVAL_MIN = 3
WATERBALL_INTERVAL_MIN = 3
ONLINE_INTERVAL_MIN = 30


def clamp_interval(value, minimum):
    """將輪詢間隔（秒）夾到下限；非數值則回傳下限。"""
    try:
        value = int(value)
    except (TypeError, ValueError):
        return minimum
    return max(value, minimum)


def get_setting_interval(db, key, default, minimum):
    """讀取 DB 設定的輪詢間隔（秒）；查無設定時 fallback 到 default，並夾到下限。"""
    value = db.get_config(key, default)
    if value is None:
        value = default
    return clamp_interval(value, minimum)