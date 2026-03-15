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
            
            # 登入成功後，嘗試取得正確的大小寫 ID
            try:
                info = self.get_user_info(ptt_id)
                self.ptt_id = info['ptt_id']
                logger.info(f"使用者登入成功，ID 已修正為: {self.ptt_id}")
            except Exception as e:
                logger.warning(f"登入後取得正確 ID 失敗: {e}，維持原始輸入: {ptt_id}")

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

    def get_user_info(self, ptt_id: str) -> Dict[str, str]:
        """
        取得使用者資訊，回傳正確的大小寫 ID 與暱稱。
        
        Args:
            ptt_id: PTT ID (不分大小寫)
            
        Returns:
            Dict: {
                'ptt_id': '正確大小寫ID',
                'nickname': '暱稱'
            }
            
        Raises:
            ValueError: 如果找不到使用者或資訊不全
            Exception: 其他 API 錯誤
        """
        try:
            user_info = self.call('get_user', {'user_id': ptt_id})
        except Exception as e:
            # 判斷是否為「查無此人」的錯誤
            if "NoSuchUser" in str(e):
                raise ValueError(f"查無此人: {ptt_id}")
            raise e

        if not user_info or 'ptt_id' not in user_info:
            raise ValueError(f"無法取得使用者資訊: {ptt_id}")

        full_id_str = user_info['ptt_id']
        # 格式通常為 "ID (Nickname)"
        nickname = ""
        true_id = ptt_id

        if '(' in full_id_str and ')' in full_id_str:
            start_idx = full_id_str.find('(')
            end_idx = full_id_str.rfind(')')
            true_id = full_id_str[:start_idx].strip()
            nickname = full_id_str[start_idx + 1:end_idx].strip()
        else:
            true_id = full_id_str.strip()

        return {
            'ptt_id': true_id,
            'nickname': nickname
        }

    def close(self):
        """關閉連線"""
        try:
            self.call('logout')
            self.service.close()
        except Exception:
            pass
