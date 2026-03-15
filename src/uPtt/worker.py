import logging
from datetime import datetime
from typing import Optional

import PyPtt
from PySide6.QtCore import QObject, Signal, Slot, QTimer

from . import config, contant, utils
from .ptt import UPttService

logger = logging.getLogger("uPtt.worker")


class PTTWorker(QObject):
    """
    PTT 背景工作者，負責所有非同步的 PTT I/O 操作。
    """
    # 訊號定義
    login_result = Signal(bool, str)  # (成功與否, 訊息)
    new_message_received = Signal(dict)  # {'sender': str, 'text': str, 'time': str, 'full_author': str}
    send_result = Signal(bool, str)  # (成功與否, 錯誤訊息)
    user_info_result = Signal(dict)  # {'ptt_id': str, 'nickname': str}
    user_info_error = Signal(str, str)  # (ID, 錯誤訊息)
    status_updated = Signal(str)

    def __init__(self, ptt_service: UPttService, db):
        super().__init__()
        self.ptt = ptt_service
        self.db = db
        self.polling_timer: Optional[QTimer] = None
        self.last_mail_time: Optional[datetime] = None
        self.is_first_polling = True

    @Slot(str, str)
    def do_login(self, username, password):
        """執行登入"""
        try:
            success = self.ptt.login(username, password)
            if success:
                # 取得登入者的資訊並存入資料庫
                try:
                    user_info = self.ptt.get_user_info(username)
                    self.db.upsert_account(
                        ptt_id=user_info['ptt_id'], 
                        display_id=user_info['ptt_id'],
                        nickname=user_info['nickname']
                    )
                except Exception as e:
                    logger.warning(f"登入後更新帳號資訊失敗: {e}")

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
            logger.info(f"開始輪詢新信件，間隔: {interval / 1000}s")

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
                # 只處理符合特定標題的訊息信 (uPtt 專用)
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
                        # --- 存入資料庫 (加入 account_id 隔離) ---
                        current_user = self.ptt.ptt_id
                        # 1. 確保會話存在
                        self.db.upsert_session(account_id=current_user, display_id=mail_data['sender_id'])
                        # 2. 儲存訊息
                        self.db.save_message(
                            account_id=current_user,
                            session_id=mail_data['sender_id'],
                            sender_id=mail_data['sender_id'],
                            receiver_id=current_user,
                            content=text,
                            timestamp=mail_data['time'],
                            is_me=False
                        )

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
            # 封裝成 uPtt 格式的站內信
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

            # --- 發送成功後存入資料庫 (加入 account_id 隔離) ---
            current_user = self.ptt.ptt_id
            # 1. 確保會話存在
            self.db.upsert_session(account_id=current_user, display_id=receiver_id)
            # 2. 儲存訊息
            self.db.save_message(
                account_id=current_user,
                session_id=receiver_id,
                sender_id=current_user,
                receiver_id=receiver_id,
                content=text,
                timestamp=datetime.now(),
                is_me=True
            )

            logger.info(f"訊息已成功發送至 {receiver_id}")
            self.send_result.emit(True, "")
        except Exception as e:
            logger.exception(f"發送訊息過程中發生例外狀況: {e}")
            self.send_result.emit(False, str(e))

    @Slot(str)
    def get_user_info(self, ptt_id):
        """主動獲取使用者資訊 (包含暱稱與正確大小寫)"""
        try:
            logger.info(f"--- 開始查詢使用者資訊: {ptt_id} ---")
            info = self.ptt.get_user_info(ptt_id)
            
            # --- 更新資料庫中的暱稱與顯示 ID (加入 account_id 隔離) ---
            self.db.upsert_session(
                account_id=self.ptt.ptt_id, 
                display_id=info['ptt_id'], 
                nickname=info['nickname']
            )

            self.user_info_result.emit({
                'ptt_id': info['ptt_id'],
                'nickname': info['nickname']
            })
            logger.info(f"成功獲取使用者資訊: {info}")
            
        except ValueError as e:
            error_msg = str(e)
            logger.warning(f"查詢使用者 {ptt_id} 失敗: {error_msg}")
            self.user_info_error.emit(ptt_id, error_msg)
        except Exception as e:
            logger.error(f"獲取使用者 {ptt_id} 資訊過程中發生非預期錯誤: {e}", exc_info=True)
            self.user_info_error.emit(ptt_id, f"系統錯誤: {str(e)}")
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
