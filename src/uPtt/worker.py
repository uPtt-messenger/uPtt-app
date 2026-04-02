import logging
from datetime import datetime, timedelta
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
    user_info_result = Signal(dict)  # {'ptt_id': str, 'nickname': str, 'is_online': bool}
    user_info_error = Signal(str, str)  # (ID, 錯誤訊息)
    online_status_updated = Signal(str, bool)  # (ptt_id 小寫, is_online)
    status_updated = Signal(str)
    connection_lost = Signal()       # 連線中斷
    connection_restored = Signal()   # 連線恢復

    def __init__(self, ptt_service: UPttService, db):
        super().__init__()
        self.ptt = ptt_service
        self.db = db
        self.polling_timer: Optional[QTimer] = None
        self.last_mail_time: Optional[datetime] = None
        # 從資料庫載入上次輪詢的時間，實現持久化
        last_poll_str = self.db.get_config('LAST_POLL_TIME')
        try:
            self.last_poll_time = datetime.fromisoformat(last_poll_str) if last_poll_str else None
        except (ValueError, TypeError):
            self.last_poll_time = None
            
        self.is_first_polling = True
        self._was_connected = True  # 追蹤上次連線狀態，用於判斷是否需發射訊號
        self._last_newest_index: Optional[int] = None  # 上次輪詢時的信箱最新索引
        self._online_check_timer: Optional[QTimer] = None

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

        # 啟動在線狀態定期檢查
        if self._online_check_timer is None:
            self._online_check_timer = QTimer()
            self._online_check_timer.timeout.connect(self._check_all_online_status)
            online_interval = getattr(config, 'CHECK_ONLINE_STATUS_INTERVAL', 60) * 1000
            self._online_check_timer.start(online_interval)
            logger.info(f"開始輪詢在線狀態，間隔: {online_interval / 1000}s")
            # 首次立即檢查一次
            self._check_all_online_status()

    def _poll_new_mails(self):
        """
        輪詢新信件的內部邏輯 (超級優化版：帶有時間截止點)
        除了第一次掃描，後續僅檢查 10-15 秒內的信件，看到舊信即停止。
        """
        try:
            # 記錄本次輪詢開始的時間
            current_poll_start = datetime.now()

            # 1. 取得信箱總數
            total_newest = self.ptt.call('get_newest_index', {'index_type': PyPtt.NewIndex.MAIL})

            # 如果之前是斷線狀態，現在成功了，代表已恢復
            if not self._was_connected:
                self._was_connected = True
                self.connection_restored.emit()
                self.status_updated.emit("已重新連線")
                logger.info("連線已恢復")
            
            if not total_newest or total_newest == 0:
                self.last_poll_time = current_poll_start
                return

            # 2. 快速跳過：如果信箱最新索引沒有變化，表示沒有新信，不需掃描
            if not self.is_first_polling and self._last_newest_index is not None:
                if total_newest == self._last_newest_index:
                    logger.debug(f"信箱無變化 (總數={total_newest})，跳過掃描")
                    self.last_poll_time = current_poll_start
                    self.db.set_config('LAST_POLL_TIME', current_poll_start.isoformat())
                    return
                elif total_newest < self._last_newest_index:
                    # 索引變小代表有信被刪除（例如 uPtt 訊息處理後刪信），也不需掃描
                    logger.debug(f"信箱索引減少 ({self._last_newest_index} → {total_newest})，跳過掃描")
                    self._last_newest_index = total_newest
                    self.last_poll_time = current_poll_start
                    self.db.set_config('LAST_POLL_TIME', current_poll_start.isoformat())
                    return

            # 3. 定義掃描上限 (防呆用：初次啟動可掃描較多封數以補齊離線訊息)
            scan_limit = 200 if self.is_first_polling else 50

            # 4. 建立停止時間 (不論是否為初次啟動，只要有紀錄就啟用截止點)
            stop_time = None
            if self.last_poll_time:
                # 緩衝 10 秒以應對 PTT 伺服器時間誤差
                stop_time = self.last_poll_time - timedelta(seconds=10)

            self.is_first_polling = False

            start_idx = total_newest
            end_idx = max(1, total_newest - scan_limit + 1)

            logger.debug(f"輪詢掃描中: 總數={total_newest}, 新增={total_newest - (self._last_newest_index or 0)}, 截止時間={stop_time}")

            mails_to_emit = []
            
            # 4. 倒序掃描
            for mail_idx in range(start_idx, end_idx - 1, -1):
                mail = self.ptt.call('get_mail', {'index': mail_idx})
                
                if not mail:
                    continue

                # 取得信件日期
                msg_date_str = mail.get(PyPtt.MailField.date)
                try:
                    mail_time = datetime.strptime(msg_date_str, '%a %b %d %H:%M:%S %Y')
                except (ValueError, TypeError):
                    mail_time = datetime.now()

                # --- 核心優化：提早結束判定 ---
                if stop_time and mail_time < stop_time:
                    logger.debug(f"已進入舊信區域 (索引 {mail_idx}, 時間 {mail_time}), 停止本次掃描。")
                    break

                # 本地端過濾標題
                raw_title = mail.get(PyPtt.MailField.title)
                title = str(raw_title) if raw_title is not None else ""
                
                raw_author = mail.get(PyPtt.MailField.author)
                if not raw_author:
                    continue
                full_author = raw_author.strip()
                sender_id = full_author.split(' ')[0]
                is_backup = (self.ptt.ptt_id and sender_id.lower() == self.ptt.ptt_id.lower())

                if contant.PTT_MSG_TITLE not in title:
                    # 一般站內信：儲存為 mail_type='mail' 並顯示
                    if not is_backup:
                        content = mail[PyPtt.MailField.content]
                        current_user = self.ptt.ptt_id
                        self.db.upsert_session(account_id=current_user, display_id=sender_id)
                        is_new = self.db.save_message(
                            account_id=current_user,
                            session_id=sender_id,
                            sender_id=sender_id,
                            receiver_id=current_user,
                            content=content,
                            timestamp=mail_time,
                            is_me=False,
                            mail_type='mail',
                            subject=title
                        )
                        if is_new:
                            mails_to_emit.append({
                                'sender': sender_id,
                                'text': content,
                                'time': mail_time.strftime("%H:%M"),
                                'full_author': full_author,
                                'timestamp': mail_time,
                                'mail_type': 'mail',
                                'subject': title
                            })
                    continue

                # 處理 uPtt 訊息
                if not is_backup:
                    content = mail[PyPtt.MailField.content]
                    div_pos = content.find(contant.PTT_MSG_DIVISION_LINE)
                    end = content.rfind(contant.PTT_MSG_DIVISION_LINE)

                    if div_pos >= 0 and end > div_pos:
                        start = div_pos + len(contant.PTT_MSG_DIVISION_LINE)
                        text = content[start:end].strip()
                        current_user = self.ptt.ptt_id
                        self.db.upsert_session(account_id=current_user, display_id=sender_id)
                        is_new = self.db.save_message(
                            account_id=current_user,
                            session_id=sender_id,
                            sender_id=sender_id,
                            receiver_id=current_user,
                            content=text,
                            timestamp=mail_time,
                            is_me=False,
                            mail_type='uptt'
                        )

                        if is_new:
                            mails_to_emit.append({
                                'sender': sender_id,
                                'text': text,
                                'time': mail_time.strftime("%H:%M"),
                                'full_author': full_author,
                                'timestamp': mail_time,
                                'mail_type': 'uptt',
                                'subject': ''
                            })

                # uPtt 訊息處理完即刪除（含 backup 副本）
                self.ptt.call('del_mail', {'index': mail_idx})
                continue

            # 5. 更新本次輪詢成功結束的時間與索引並存入資料庫
            self._last_newest_index = total_newest
            self.last_poll_time = current_poll_start
            self.db.set_config('LAST_POLL_TIME', current_poll_start.isoformat())

            # 6. 發射訊號
            for mail_data in reversed(mails_to_emit):
                self.new_message_received.emit(mail_data)
                self.last_mail_time = mail_data['timestamp']

        except PyPtt.ConnectionClosed:
            logger.warning("輪詢時偵測到連線中斷，嘗試自動重連...")
            if self._was_connected:
                self._was_connected = False
                self.connection_lost.emit()
                self.status_updated.emit("連線中斷，正在嘗試重新連線...")
            # ptt.call 內部重連失敗才會拋出此例外，再嘗試一次頂層重連
            if self.ptt.reconnect():
                self._was_connected = True
                self.connection_restored.emit()
                self.status_updated.emit("已重新連線")
                logger.info("頂層重連成功，下次輪詢將恢復正常")
            else:
                logger.error("頂層重連失敗，將在下次輪詢時重試")
        except Exception as e:
            logger.exception(f"輪詢信件發生錯誤: {e}")
            # 檢查是否為連線相關錯誤
            if not self.ptt.is_connected and self._was_connected:
                self._was_connected = False
                self.connection_lost.emit()
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
        """主動獲取使用者資訊 (包含暱稱、正確大小寫與在線狀態)"""
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
                'nickname': info['nickname'],
                'is_online': info['is_online'],
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

    def _check_all_online_status(self):
        """定期檢查所有聯絡人的在線狀態"""
        if not self.ptt.ptt_id:
            return
        try:
            sessions = self.db.get_all_sessions(self.ptt.ptt_id)
            for s in sessions:
                contact_id = s['id']
                # 跳過自己
                if contact_id == self.ptt.ptt_id.lower():
                    continue
                try:
                    info = self.ptt.get_user_info(contact_id)
                    self.online_status_updated.emit(contact_id, info['is_online'])
                except Exception as e:
                    logger.debug(f"檢查 {contact_id} 在線狀態失敗: {e}")
        except Exception as e:
            logger.warning(f"在線狀態輪詢失敗: {e}")

    @Slot()
    def stop(self):
        """停止所有背景任務並登出"""
        try:
            logger.info("正在停止 Worker...")
            if self.polling_timer:
                self.polling_timer.stop()
            if self._online_check_timer:
                self._online_check_timer.stop()

            # 關閉 PTT 連線
            if self.ptt:
                self.ptt.close()
            logger.info("Worker 已成功停止")
        except Exception as e:
            logger.error(f"停止 Worker 時發生錯誤: {e}")
