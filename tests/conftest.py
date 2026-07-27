import pytest
import logging
import PyPtt
import sys
import os

# 將 tests 加入 sys.path 以便於測試檔案之間互相匯入
sys.path.append(os.path.dirname(__file__))

from security_utils import TEST_PASSWORD_CANARY, PasswordLeakError
from unittest.mock import patch
from typing import Any, Dict, Optional

@pytest.fixture(autouse=True)
def security_monitor(caplog):
    """
    全域安全性監控 Fixture。
    """
    caplog.set_level(logging.DEBUG)
    
    # 紀錄原始的 call 方法
    original_call = PyPtt.Service.call
    
    def wrapped_call(self, api: str, args: Optional[Dict[str, Any]] = None) -> Any:
        # 如果不是 login 呼叫，但參數中出現了金雀鳥密碼，立即拋出錯誤
        if api != 'login' and args:
            args_str = str(args)
            if TEST_PASSWORD_CANARY in args_str:
                error_msg = f"安全性警報：在呼叫 API '{api}' 時，參數中偵測到敏感密碼！"
                raise PasswordLeakError(error_msg)
        
        return original_call(self, api, args)

    # 套用 Patch 到 PyPtt 核心呼叫
    with patch("PyPtt.Service.call", side_effect=wrapped_call, autospec=True):
        yield
        
        # 測試執行完畢後檢查 Log
        for record in caplog.records:
            log_msg = record.getMessage()
            if TEST_PASSWORD_CANARY in log_msg:
                raise PasswordLeakError(f"安全性警報：在日誌中偵測到敏感密碼！")
