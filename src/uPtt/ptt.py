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
        self._connected = False

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
            self._connected = True

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

    def reconnect(self) -> bool:
        """
        重新建立連線並登入。
        遵循 PyPtt 官方範例：建立全新 Service 實例再重新登入。

        Returns:
            bool: 重連成功與否
        """
        if self.ptt_id is None or self.ptt_pw is None:
            return False

        max_retry = 5
        for retry_time in range(max_retry):
            try:
                self.service = PyPtt.Service({'log_level': PyPtt.log.SILENT})
                self.service.call('login', {
                    'ptt_id': self.ptt_id,
                    'ptt_pw': self.ptt_pw,
                    'kick_other_session': True if retry_time > 0 else False,
                })
                self._connected = True
                logger.info(f"重連成功 (第 {retry_time + 1} 次嘗試)")
                return True
            except PyPtt.LoginTooOften:
                logger.warning(f"登入太頻繁，等待 60 秒後再試 ({retry_time + 1}/{max_retry})")
                time.sleep(60)
            except PyPtt.LoginError:
                logger.warning(f"登入失敗，等待 3 秒後再試 ({retry_time + 1}/{max_retry})")
                time.sleep(3)
            except PyPtt.WrongIDorPassword:
                logger.error("帳號密碼錯誤，放棄重連")
                return False
            except Exception as e:
                logger.error(f"重連失敗 ({retry_time + 1}/{max_retry}): {e}")
                time.sleep(self.retry_delay)

        logger.error(f"重連已達最大嘗試次數 ({max_retry})，放棄重連")
        return False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def call(self, api: str, args: Optional[Dict[str, Any]] = None) -> Any:
        """
        安全呼叫 PyPtt API，具備斷線自動重連機制。
        """
        if api != 'logout' and (self.ptt_pw is None or self.ptt_id is None):
            raise PyPtt.RequireLogin("在呼叫 API 之前必須先登入 PTT。")

        if api == 'logout':
            self._connected = False
            self.ptt_id = None
            self.ptt_pw = None
            try:
                self.service.call('logout')
            except Exception as e:
                logger.error(f"登出時發生錯誤: {e}")
            return True

        for i in range(self.max_retry):
            try:
                result = self.service.call(api, args)
                self._connected = True
                return result
            except PyPtt.ConnectionClosed:
                self._connected = False
                logger.warning(f"連線中斷，嘗試重連 ({i+1}/{self.max_retry})")
                if not self.reconnect():
                    raise PyPtt.ConnectionClosed()
                # reconnect 成功，下次迴圈重試原始 API 呼叫
        return None

    def get_user_info(self, ptt_id: str) -> Dict[str, str]:
        """
        取得使用者資訊，回傳正確的大小寫 ID、暱稱與在線狀態。

        Args:
            ptt_id: PTT ID (不分大小寫)

        Returns:
            Dict: {
                'ptt_id': '正確大小寫ID',
                'nickname': '暱稱',
                'is_online': bool
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

        # 判斷在線狀態：《目前動態》為 "不在站上" 代表離線
        activity = user_info.get('activity', '')
        is_online = bool(activity and activity != '不在站上')

        return {
            'ptt_id': true_id,
            'nickname': nickname,
            'is_online': is_online,
        }

    def close(self):
        """關閉連線"""
        self._connected = False
        try:
            self.call('logout')
            self.service.close()
        except Exception as e:
            logger.error(f"關閉連線時發生錯誤: {e}")
