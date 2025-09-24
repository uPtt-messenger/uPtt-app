import config
import utils

SYSTEM_MSG = "[系統]"
USER_MSG = "[使用者]"
TARGET_MSG = "[目標]"

DIVISION_LINE = utils.gen_random_string(32)
DIVISION_TYPE = '='  # 用於分隔線的訊息類型

PTT_MSG_TITLE = f"來自 {config.APP_NAME} 的訊息"
PTT_MSG_DIVISION_LINE = DIVISION_TYPE * 20
