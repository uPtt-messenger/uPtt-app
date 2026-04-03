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
        # last_poll_time 在 do_login 成功後才載入（需要帳號 ID 作為 key）
        self.last_poll_time: Optional[datetime] = None
            
        self.is_first_polling = True
        self._was_connected = True  # 追蹤上次連線狀態，用於判斷是否需發射訊號
        self._last_newest_index: Optional[int] = None  # 上次輪詢時的信箱最新索引
        self._online_check_timer: Optional[QTimer] = None
        self._waterball_timer: Optional[QTimer] = None
        self._last_waterball_batch: Optional[str] = None  # 上一批水球的指紋，用於整批去重

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

                # 登入成功後，載入該帳號的 last_poll_time
                poll_key = f'LAST_POLL_TIME_{self.ptt.ptt_id.lower()}'
                last_poll_str = self.db.get_config(poll_key)
                try:
                    self.last_poll_time = datetime.fromisoformat(last_poll_str) if last_poll_str else None
                except (ValueError, TypeError):
                    self.last_poll_time = None

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

        # 啟動水球輪詢
        if self._waterball_timer is None:
            self._waterball_timer = QTimer()
            self._waterball_timer.timeout.connect(self._poll_waterballs)
            wb_interval = getattr(config, 'CHECK_WATERBALL_INTERVAL', 5) * 1000
            self._waterball_timer.start(wb_interval)
            logger.info(f"開始輪詢水球，間隔: {wb_interval / 1000}s")

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
        輪詢新信件的內部邏輯（時間驅動掃描策略）
        - 全新使用者：掃描過去 7 天，發現 uPtt 訊息則延伸至 9 天
        - 已有紀錄：掃描到上次輪詢時間，發現 uPtt 訊息則多掃 2 天
        - uPtt 訊息無論多舊都會處理並刪除
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
                    self.db.set_config(f'LAST_POLL_TIME_{self.ptt.ptt_id.lower()}', current_poll_start.isoformat())
                    return
                elif total_newest < self._last_newest_index:
                    # 索引變小代表有信被刪除（例如 uPtt 訊息處理後刪信），也不需掃描
                    logger.debug(f"信箱索引減少 ({self._last_newest_index} → {total_newest})，跳過掃描")
                    self._last_newest_index = total_newest
                    self.last_poll_time = current_poll_start
                    self.db.set_config(f'LAST_POLL_TIME_{self.ptt.ptt_id.lower()}', current_poll_start.isoformat())
                    return

            # 3. 建立停止時間（時間驅動掃描策略）
            #    - 全新使用者（無 last_poll_time）：至少掃描過去一週
            #    - 已有掃描紀錄：掃描到上次掃描時間（含 10 秒緩衝）
            #    - 若掃描途中發現 uPtt 訊息，自動延伸掃描範圍 2 天（不限次數）
            if self.last_poll_time:
                stop_time = self.last_poll_time - timedelta(seconds=10)
            else:
                stop_time = current_poll_start - timedelta(days=7)

            found_uptt = False

            self.is_first_polling = False

            start_idx = total_newest
            end_idx = 1

            logger.debug(f"輪詢掃描中: 總數={total_newest}, 新增={total_newest - (self._last_newest_index or 0)}, 截止時間={stop_time}")

            mails_to_emit = []
            deleted_count = 0

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

                # 先解析標題，判斷是否為 uPtt 訊息
                raw_title = mail.get(PyPtt.MailField.title)
                title = str(raw_title) if raw_title is not None else ""
                is_uptt_msg = contant.PTT_MSG_TITLE in title

                if is_uptt_msg:
                    found_uptt = True

                # --- 核心優化：提早結束判定 (僅對非 uPtt 訊息生效) ---
                # uPtt 訊息無論多舊都必須處理並刪除，不受時間截止點限制
                if mail_time < stop_time and not is_uptt_msg:
                    if found_uptt:
                        # 發現過 uPtt 訊息，多掃兩天以確保不遺漏離線訊息
                        stop_time = stop_time - timedelta(days=2)
                        found_uptt = False  # 重置，若延伸範圍內又有 uPtt 則繼續延伸
                        if mail_time < stop_time:
                            logger.debug(f"已進入舊信區域 (索引 {mail_idx}, 時間 {mail_time}), 延伸掃描後仍超出截止時間 {stop_time}, 停止。")
                            break
                    else:
                        logger.debug(f"已進入舊信區域 (索引 {mail_idx}, 時間 {mail_time}), 停止本次掃描。")
                        break

                raw_author = mail.get(PyPtt.MailField.author)
                if not raw_author:
                    continue
                full_author = raw_author.strip()
                sender_id = full_author.split(' ')[0]
                is_backup = (self.ptt.ptt_id and sender_id.lower() == self.ptt.ptt_id.lower())

                if not is_uptt_msg:
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
                        # 優先使用發送端嵌入的時間戳，確保兩端排序一致
                        embedded_ts = utils.parse_embedded_timestamp(content, end)
                        msg_time = embedded_ts if embedded_ts else mail_time
                        current_user = self.ptt.ptt_id
                        self.db.upsert_session(account_id=current_user, display_id=sender_id)
                        is_new = self.db.save_message(
                            account_id=current_user,
                            session_id=sender_id,
                            sender_id=sender_id,
                            receiver_id=current_user,
                            content=text,
                            timestamp=msg_time,
                            is_me=False,
                            mail_type='uptt'
                        )

                        if is_new:
                            mails_to_emit.append({
                                'sender': sender_id,
                                'text': text,
                                'time': msg_time.strftime("%H:%M"),
                                'full_author': full_author,
                                'timestamp': msg_time,
                                'mail_type': 'uptt',
                                'subject': ''
                            })

                # uPtt 訊息處理完即刪除（含 backup 副本）
                self.ptt.call('del_mail', {'index': mail_idx})
                deleted_count += 1
                continue

            # 5. 更新本次輪詢成功結束的時間與索引並存入資料庫
            # 扣除已刪除的 uPtt 信件數，避免下次輪詢誤判「索引減少＝無新信」
            self._last_newest_index = total_newest - deleted_count
            self.last_poll_time = current_poll_start
            self.db.set_config(f'LAST_POLL_TIME_{self.ptt.ptt_id.lower()}', current_poll_start.isoformat())

            # 6. 發射訊號
            for mail_data in reversed(mails_to_emit):
                self.new_message_received.emit(mail_data)
                self.last_mail_time = mail_data['timestamp']

        except PyPtt.ConnectionClosed:
            logger.warning("輪詢時偵測到連線中斷，將延遲重連...")
            if self._was_connected:
                self._was_connected = False
                self.connection_lost.emit()
                self.status_updated.emit("連線中斷，正在嘗試重新連線...")
            # 使用 QTimer.singleShot 延遲重連，避免阻塞 worker thread 事件迴圈
            QTimer.singleShot(5000, self._deferred_reconnect)
        except Exception as e:
            logger.exception(f"輪詢信件發生錯誤: {e}")
            # 檢查是否為連線相關錯誤
            if not self.ptt.is_connected and self._was_connected:
                self._was_connected = False
                self.connection_lost.emit()
            self.status_updated.emit(f"輪詢錯誤: {e}")

    def _deferred_reconnect(self):
        """延遲重連（由 QTimer.singleShot 觸發），避免阻塞事件迴圈。"""
        if self.ptt.reconnect():
            self._was_connected = True
            self.connection_restored.emit()
            self.status_updated.emit("已重新連線")
            logger.info("延遲重連成功，下次輪詢將恢復正常")
        else:
            logger.error("延遲重連失敗，將在下次輪詢時重試")

    @Slot(str, str, object)
    def send_message(self, receiver_id, text, timestamp=None):
        """發送站內信"""
        try:
            # PTT ID 通常不分大小寫，但發送時建議使用原始輸入或去空白
            receiver_id = receiver_id.strip()
            # 使用 UI 傳入的時間戳，確保 UI 顯示與 DB 儲存的排序一致
            send_time = timestamp if isinstance(timestamp, datetime) else datetime.now()
            # 封裝成 uPtt 格式的站內信（嵌入發送端時間戳）
            ptt_msg = utils.msg_to_mail(contant.pkg_name, self.ptt.ptt_id or "uPttUser", text, timestamp=send_time)

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
            # 2. 儲存訊息（使用與信件中嵌入的相同時間戳）
            self.db.save_message(
                account_id=current_user,
                session_id=receiver_id,
                sender_id=current_user,
                receiver_id=receiver_id,
                content=text,
                timestamp=send_time,
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

    def _poll_waterballs(self):
        """輪詢水球訊息"""
        try:
            waterballs = self.ptt.call('get_waterball', {'post_action': PyPtt.WaterballPostAction.CLEAR})

            if not waterballs:
                return

            current_user = self.ptt.ptt_id
            if not current_user:
                return

            # 整批去重：若這批水球跟上次完全一樣，代表 CLEAR 沒生效，直接跳過
            batch_fingerprint = str([
                (wb.get(PyPtt.WaterballField.target, ''),
                 wb.get(PyPtt.WaterballField.content, ''),
                 wb.get(PyPtt.WaterballField.date, ''),
                 wb.get(PyPtt.WaterballField.type))
                for wb in waterballs
            ])
            if batch_fingerprint == self._last_waterball_batch:
                return
            self._last_waterball_batch = batch_fingerprint

            for wb in waterballs:
                wb_type = wb.get(PyPtt.WaterballField.type)
                target = wb.get(PyPtt.WaterballField.target, '').strip()
                content = wb.get(PyPtt.WaterballField.content, '').strip()
                date_str = wb.get(PyPtt.WaterballField.date, '')

                if not target or not content:
                    continue

                # 跳過自己對自己的水球
                if target.lower() == current_user.lower():
                    continue

                # 解析時間戳記
                wb_time = self._parse_waterball_date(date_str)

                is_me = (wb_type == PyPtt.WaterballType.SEND)
                if is_me:
                    sender_id = current_user
                    receiver_id = target
                else:
                    sender_id = target
                    receiver_id = current_user

                # 儲存至資料庫
                self.db.upsert_session(account_id=current_user, display_id=target)
                is_new = self.db.save_message(
                    account_id=current_user,
                    session_id=target,
                    sender_id=sender_id,
                    receiver_id=receiver_id,
                    content=content,
                    timestamp=wb_time,
                    is_me=is_me,
                    mail_type='waterball'
                )

                # 發射訊號通知 UI（收到的與自己發出的都通知）
                if is_new:
                    self.new_message_received.emit({
                        'sender': target,
                        'text': content,
                        'time': wb_time.strftime("%H:%M"),
                        'full_author': target,
                        'timestamp': wb_time,
                        'mail_type': 'waterball',
                        'subject': '',
                        'is_me': is_me,
                    })

        except PyPtt.ConnectionClosed:
            logger.warning("水球輪詢時連線中斷")
        except Exception as e:
            logger.debug(f"水球輪詢錯誤: {e}")

    @staticmethod
    def _parse_waterball_date(date_val) -> datetime:
        """解析水球時間。PyPtt 新版回傳 datetime，舊版回傳 str。"""
        if isinstance(date_val, datetime):
            return date_val
        # 相容舊版 PyPtt 回傳字串的情況
        now = datetime.now()
        formats = [
            ('%m/%d/%Y %H:%M:%S', False),  # "03/15/2026 10:30:00"
            ('%m/%d %H:%M:%S', True),       # "03/15 10:30:00" (需補年份)
            ('%m/%d %H:%M', True),          # "03/15 10:30" (需補年份)
        ]
        for fmt, needs_year in formats:
            try:
                wb_time = datetime.strptime(str(date_val).strip(), fmt)
                if needs_year:
                    wb_time = wb_time.replace(year=now.year)
                    if wb_time > now:
                        wb_time = wb_time.replace(year=now.year - 1)
                return wb_time
            except (ValueError, TypeError):
                continue
        # 確定性 fallback
        h = abs(hash(str(date_val))) % 86400
        return now.replace(hour=h // 3600, minute=(h % 3600) // 60, second=h % 60, microsecond=0)

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
            if self._waterball_timer:
                self._waterball_timer.stop()
            if self._online_check_timer:
                self._online_check_timer.stop()

            # 關閉 PTT 連線
            if self.ptt:
                self.ptt.close()
            logger.info("Worker 已成功停止")
        except Exception as e:
            logger.error(f"停止 Worker 時發生錯誤: {e}")
