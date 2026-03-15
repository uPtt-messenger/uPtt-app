import logging
import time
import PyPtt
from typing import Any, Dict, Optional

logger = logging.getLogger("uPtt.ptt")

class UPttService:
    """PTT 核心服務類別，負責底層 PyPtt 操作"""
    
    def __init__(self):
        self.service: PyPtt.Service = PyPtt.Service(
            {'log_level': PyPtt.log.SILENT}
        )
        self.ptt_id: Optional[str] = None
        self.ptt_pw: Optional[str] = None
        self.max_retry = 3
        self.retry_delay = 2  # 秒

    def login(self, ptt_id: str, ptt_pw: str, force: bool = True) -> bool:
        """
        執行登入操作。
        
        Args:
            ptt_id: PTT 帳號
            ptt_pw: PTT 密碼
            force: 是否踢掉其他連線
            
        Returns:
            bool: 登入成功與否
        """
        try:
            self.service.call('login', {'ptt_id': ptt_id, 'ptt_pw': ptt_pw, 'kick_other_session': force})
            self.ptt_id = ptt_id
            self.ptt_pw = ptt_pw
            logger.info(f"使用者 {ptt_id} 登入成功")
            return True
        except Exception as e:
            logger.error(f"登入失敗: {e}")
            raise e

    def call(self, api: str, args: Optional[Dict[str, Any]] = None) -> Any:
        """
        安全呼叫 PyPtt API，具備斷線自動重連機制。
        """
        if api != 'logout' and (self.ptt_pw is None or self.ptt_id is None):
            raise PyPtt.RequireLogin("在呼叫 API 之前必須先登入 PTT。")

        if api == 'logout':
            self.ptt_id = None
            self.ptt_pw = None
            try:
                self.service.call('logout')
            except Exception:
                pass
            return True

        for i in range(self.max_retry):
            try:
                return self.service.call(api, args)
            except (PyPtt.ConnectionClosed, Exception) as e:
                logger.warning(f"API 呼叫失敗 (嘗試 {i+1}/{self.max_retry}): {e}")
                if i < self.max_retry - 1:
                    time.sleep(self.retry_delay)
                    try:
                        self.service.call(
                            'login',
                            {'ptt_id': self.ptt_id, 'ptt_pw': self.ptt_pw, 'kick_other_session': True}
                        )
                    except Exception:
                        pass
                else:
                    raise e
        return None

    def close(self):
        """關閉連線"""
        try:
            self.call('logout')
            self.service.close()
        except Exception:
            pass
