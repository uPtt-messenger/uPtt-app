import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any

from PySide6.QtCore import QObject, Signal, Slot, QTimer
import PyPtt
from uPttTerm.ptt import UPttService
from uPttTerm import config, contant, utils

logger = logging.getLogger("uPttTerm.worker")

class PTTWorker(QObject):
    """
    PTT 背景工作者，負責所有非同步的 PTT I/O 操作。
    """
    # 訊號定義
    login_result = Signal(bool, str)  # (成功與否, 訊息)
    new_message_received = Signal(dict)  # {'sender': str, 'text': str, 'time': str, 'full_author': str}
    send_result = Signal(bool, str)  # (成功與否, 錯誤訊息)
    user_info_result = Signal(dict)  # {'ptt_id': str, 'nickname': str}
    status_updated = Signal(str)

    def __init__(self, ptt_service: UPttService):
        super().__init__()
        self.ptt = ptt_service
        self.polling_timer: Optional[QTimer] = None
        self.last_mail_time: Optional[datetime] = None
        self.is_first_polling = True

    @Slot(str, str)
    def do_login(self, username, password):
        """執行登入"""
        try:
            success = self.ptt.login(username, password)
            if success:
                self.login_result.emit(True, "登入成功")
                # 登入成功後自動開始輪詢
                self.start_polling()
            else:
                self.login_result.emit(False, "登入失敗")
        except Exception as e:
            self.login_result.emit(False, str(e))

    def start_polling(self):
        """開始背景輪詢新信件"""
        if self.polling_timer is None:
            self.polling_timer = QTimer()
            self.polling_timer.timeout.connect(self._poll_new_mails)
            # 根據 config 設定間隔 (秒轉毫秒)
            interval = getattr(config, 'CHECK_PTT_MAIL_INTERVAL', 10) * 1000
            self.polling_timer.start(interval)
            logger.info(f"開始輪詢新信件，間隔: {interval/1000}s")

    def _poll_new_mails(self):
        """輪詢新信件的內部邏輯"""
        try:
            newest_idx = self.ptt.call('get_newest_index', {'index_type': PyPtt.NewIndex.MAIL})
            if not newest_idx:
                return

            # 初次啟動檢查較多封數
            lookback = 50 if self.is_first_polling else 10
            self.is_first_polling = False
            
            mails_to_process = []
            for mail_idx in range(max(1, newest_idx - lookback), newest_idx + 1):
                mail = self.ptt.call('get_mail', {'index': mail_idx})
                # 只處理符合特定標題的訊息信 (uPttTerm 專用)
                if not mail or mail.get(PyPtt.MailField.title) != contant.PTT_MSG_TITLE:
                    continue
                
                full_author = mail[PyPtt.MailField.author].strip()
                sender_id = full_author.split(' ')[0]
                
                # --- 新增過濾邏輯：忽略自己寄出的備份信 ---
                if self.ptt.ptt_id and sender_id.lower() == self.ptt.ptt_id.lower():
                    # 如果是自己的備份信，直接刪除但不處理
                    self.ptt.call('del_mail', {'index': mail_idx})
                    continue
                
                try:
                    msg_time = datetime.strptime(mail[PyPtt.MailField.date], '%a %b %d %H:%M:%S %Y')
                except ValueError:
                    continue
                content = mail[PyPtt.MailField.content]
                
                mails_to_process.append({
                    'index': mail_idx,
                    'sender_id': sender_id,
                    'full_author': full_author,
                    'content': content,
                    'time': msg_time
                })

            # 依序處理訊息並發射訊號
            for mail_data in mails_to_process:
                content = mail_data['content']
                try:
                    # 擷取分隔線中間的內容
                    start = content.find(contant.PTT_MSG_DIVISION_LINE) + len(contant.PTT_MSG_DIVISION_LINE)
                    end = content.rfind(contant.PTT_MSG_DIVISION_LINE)
                    if start < end:
                        text = content[start:end].strip()
                        self.new_message_received.emit({
                            'sender': mail_data['sender_id'],
                            'text': text,
                            'time': mail_data['time'].strftime("%H:%M"),
                            'full_author': mail_data['full_author'],
                            'timestamp': mail_data['time']
                        })
                    self.last_mail_time = mail_data['time']
                except Exception as e:
                    logger.error(f"解析信件失敗: {e}")

            # 處理完後刪除信件 (避免 PTT 空間爆滿)
            for mail_data in sorted(mails_to_process, key=lambda x: x['index'], reverse=True):
                self.ptt.call('del_mail', {'index': mail_data['index']})

        except Exception as e:
            logger.error(f"輪詢發生錯誤: {e}")
            self.status_updated.emit(f"輪詢錯誤: {e}")

    @Slot(str, str)
    def send_message(self, receiver_id, text):
        """發送站內信"""
        try:
            # PTT ID 通常不分大小寫，但發送時建議使用原始輸入或去空白
            receiver_id = receiver_id.strip()
            # 封裝成 uPttTerm 格式的站內信
            ptt_msg = utils.msg_to_mail(contant.pkg_name, self.ptt.ptt_id or "uPttUser", text)
            
            logger.info(f"正在發送站內信給 {receiver_id}...")
            # 呼叫 PyPtt mail API
            # 注意：PyPtt 的 mail API 成功時可能回傳 None 或特殊物件，我們以不噴錯為準
            self.ptt.call('mail', {
                'ptt_id': receiver_id,
                'title': contant.PTT_MSG_TITLE,
                'content': ptt_msg,
                'sign_file': '0',
                'backup': False
            })
            
            logger.info(f"訊息已成功發送至 {receiver_id}")
            self.send_result.emit(True, "")
        except Exception as e:
            logger.exception(f"發送訊息過程中發生例外狀況: {e}")
            self.send_result.emit(False, str(e))

    @Slot(str)
    def get_user_info(self, ptt_id):
        """主動獲取使用者資訊 (包含暱稱)"""
        try:
            logger.info(f"--- 開始查詢使用者資訊: {ptt_id} ---")
            user_info = self.ptt.call('get_user', {'user_id': ptt_id})
            
            if user_info:
                # 取得帶有暱稱的完整 ID 字串，例如 "TaiwanAILabs (台灣人工智慧實驗室)"
                full_id_str = user_info.get('ptt_id', ptt_id)
                
                nickname = ""
                # 解析格式: ID (暱稱)
                if '(' in full_id_str and ')' in full_id_str:
                    start = full_id_str.find('(') + 1
                    end = full_id_str.rfind(')')
                    nickname = full_id_str[start:end].strip()
                
                logger.info(f"成功解析使用者資訊: {ptt_id} -> 暱稱='{nickname}'")
                
                self.user_info_result.emit({
                    'ptt_id': ptt_id.lower(),
                    'nickname': nickname
                })
            else:
                logger.warning(f"查詢失敗: PTT 未回傳 {ptt_id} 的任何資訊")
        except Exception as e:
            logger.error(f"獲取使用者 {ptt_id} 資訊過程中發生例外狀況: {e}", exc_info=True)
        finally:
            logger.info(f"--- 查詢結束: {ptt_id} ---")

    @Slot()
    def stop(self):
        """停止所有背景任務並登出"""
        try:
            logger.info("正在停止 Worker...")
            if self.polling_timer:
                self.polling_timer.stop()
            
            # 關閉 PTT 連線
            if self.ptt:
                self.ptt.close()
            logger.info("Worker 已成功停止")
        except Exception as e:
            logger.error(f"停止 Worker 時發生錯誤: {e}")
