from enum import StrEnum

try:
    from . import __name__ as pkg_name
except ImportError:
    from __init__ import __name__ as pkg_name

LOGO = '''
            ███████████   █████     █████      
           ░░███░░░░░███ ░░███     ░░███       
 █████ ████ ░███    ░███ ███████   ███████     
░░███ ░███  ░██████████ ░░░███░   ░░░███░      
 ░███ ░███  ░███░░░░░░    ░███      ░███       
 ░███ ░███  ░███          ░███ ███  ░███ ███   
 ░░████████ █████         ░░█████   ░░█████    
  ░░░░░░░░ ░░░░░           ░░░░░     ░░░░░     
                                               
                                               
                                               
 ███████████                                   
░█░░░███░░░█                                   
░   ░███  ░   ██████  ████████  █████████████  
    ░███     ███░░███░░███░░███░░███░░███░░███ 
    ░███    ░███████  ░███ ░░░  ░███ ░███ ░███ 
    ░███    ░███░░░   ░███      ░███ ░███ ░███ 
    █████   ░░██████  █████     █████░███ █████
   ░░░░░     ░░░░░░  ░░░░░     ░░░░░ ░░░ ░░░░░ '''
# https://patorjk.com/software/taag/
# DOS Rebel

class MsgType(StrEnum):
    SYSTEM = '[系統]'
    USER = '[使用者]'
    TARGET = '[目標]'


DOWNLOAD_URL = "https://github.com/uPtt-messenger/uPttTerm/tree/feat/init"

DIVISION_LINE = "__DIVISION_LINE__"
DIVISION_TYPE = '='  # 用於分隔線的訊息類型

PTT_MSG_TITLE = f"使用 {pkg_name} 傳送的訊息"
PTT_MSG_DIVISION_LINE = DIVISION_TYPE * 20

CMD_EXIT = "/exit"
