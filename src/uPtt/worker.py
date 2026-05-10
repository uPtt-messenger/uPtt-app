import logging
import queue
import re
from datetime import datetime, timedelta
from typing import Optional

import PyPtt
from PySide6.QtCore import QObject, Signal, Slot, QTimer

from . import config, contant, utils
from .ptt import UPttService

logger = logging.getLogger("uPtt.worker")

# 後續輪詢時每次最多掃描的信件數量
MAX_POLL_SCAN = 50


class PTTWorker(QObject):
    """
    PTT 背景工作者，負責所有非同步的 PTT I/O 操作。
    """
    # 訊號定義
    login_result = Signal(bool, str)  # (成功與否, 訊息)
    new_message_received = Signal(dict)  # {'sender': str, 'text': str, 'time': str, 'full_author': str}
    send_result = Signal(int, bool, str)  # (DB row id, 成功與否, 錯誤訊息)；msg_id=-1 代表無對應 DB row
    status_updated = Signal(str)
    connection_lost = Signal()       # 連線中斷
    connection_restored = Signal()   # 連線恢復
    first_time_detected = Signal()          # 首次登入（無 last_poll_time）
    scan_progress = Signal(int, int, str)   # (已掃描數, 總數, 信件標題)
    scan_complete = Signal()                # 首次掃描完成
    disconnected = Signal(str)  # 非預期斷線（如信箱已滿導致 PyPtt 自動登出）

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
        self._waterball_timer: Optional[QTimer] = None
        self._last_waterball_batch: Optional[str] = None  # 上一批水球的指紋，用於整批去重
        self._send_queue: queue.Queue = queue.Queue()  # Thread-safe 發送佇列

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

                is_first_time = self.last_poll_time is None
                if is_first_time:
                    self.first_time_detected.emit()
                self.login_result.emit(True, "登入成功")
                if not is_first_time:
                    self.start_polling()
            else:
                self.login_result.emit(False, "登入失敗")
        except PyPtt.WrongIDorPassword:
            self.login_result.emit(False, "帳號或密碼錯誤")
        except PyPtt.LoginTooOften:
            self.login_result.emit(False, "登入太頻繁，請稍後再試")
        except Exception as e:
            logger.error(f"登入失敗: {e}")
            self.login_result.emit(False, "連線失敗，請檢查網路連線")

    def start_polling(self):
        """開始背景輪詢新信件"""
        if self.polling_timer is None:
            self.polling_timer = QTimer(self)
            self.polling_timer.timeout.connect(self._poll_new_mails)
            # 根據 config 設定間隔 (秒轉毫秒)
            interval = getattr(config, 'CHECK_PTT_MAIL_INTERVAL', 10) * 1000
            self.polling_timer.start(interval)
            logger.info(f"開始輪詢新信件，間隔: {interval / 1000}s")

        # 啟動水球輪詢
        if self._waterball_timer is None:
            self._waterball_timer = QTimer(self)
            self._waterball_timer.timeout.connect(self._poll_waterballs)
            wb_interval = getattr(config, 'CHECK_WATERBALL_INTERVAL', 5) * 1000
            self._waterball_timer.start(wb_interval)
            logger.info(f"開始輪詢水球，間隔: {wb_interval / 1000}s")

    @Slot()
    def stop_polling(self):
        """暫停所有輪詢計時器（不登出）"""
        if self.polling_timer:
            self.polling_timer.stop()
            self.polling_timer = None
        if self._waterball_timer:
            self._waterball_timer.stop()
            self._waterball_timer = None
        logger.info("已暫停所有輪詢")

    @Slot()
    def do_skip_scan(self):
        """跳過首次掃描，直接設定 last_poll_time 並開始輪詢"""
        now = datetime.now()
        self.last_poll_time = now
        self.is_first_polling = False
        self.db.set_config(f'LAST_POLL_TIME_{self.ptt.ptt_id.lower()}', now.isoformat())
        logger.info("使用者跳過首次掃描，直接開始輪詢")
        self.scan_complete.emit()
        self.start_polling()

    def _process_single_mail(self, mail, mail_idx: int):
        """處理單一信件，回傳 (emit_dict_or_None, is_uptt, should_delete)。

        將 do_initial_scan 與 _poll_new_mails 共用的信件處理邏輯抽出，
        避免兩處重複維護。
        """
        current_user = self.ptt.ptt_id

        raw_author = mail.get(PyPtt.MailField.author)
        if not raw_author:
            return None, False, False
        full_author = raw_author.strip()
        match = re.match(r'[A-Za-z0-9]+', full_author)
        sender_id = match.group() if match else full_author.split()[0]
        is_backup = (current_user and sender_id.lower() == current_user.lower())

        msg_date_str = mail.get(PyPtt.MailField.date)
        try:
            mail_time = datetime.strptime(msg_date_str, '%a %b %d %H:%M:%S %Y')
        except (ValueError, TypeError):
            mail_time = datetime.now()

        raw_title = mail.get(PyPtt.MailField.title)
        title = str(raw_title) if raw_title is not None else ""
        is_uptt_msg = (title == contant.PTT_MSG_TITLE)

        if not is_uptt_msg:
            # 一般站內信
            if is_backup:
                return None, False, False
            content = mail.get(PyPtt.MailField.content)
            if content is None:
                return None, False, False
            content = utils.strip_ansi(content)
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
            emit_dict = None
            if is_new:
                emit_dict = {
                    'sender': sender_id,
                    'text': content,
                    'time': mail_time.strftime("%H:%M"),
                    'full_author': full_author,
                    'timestamp': mail_time,
                    'mail_type': 'mail',
                    'subject': title
                }
            return emit_dict, False, False

        # ── uPtt 訊息 ──
        content = mail.get(PyPtt.MailField.content)
        if content is None:
            logger.warning(f"uPtt mail at index {mail_idx} has no content, skipping")
            return None, True, is_backup  # 備份副本仍需刪除

        div_pos = content.find(contant.PTT_MSG_DIVISION_LINE)
        end = content.rfind(contant.PTT_MSG_DIVISION_LINE)

        if div_pos < 0 or end <= div_pos:
            logger.error(
                f"uPtt mail at index {mail_idx} has malformed content "
                f"(div_pos={div_pos}, end={end}); skipping deletion."
            )
            return None, True, is_backup  # 備份副本仍需刪除

        start = div_pos + len(contant.PTT_MSG_DIVISION_LINE)
        text = content[start:end].strip()
        text = utils.unwrap_ptt_lines(text)
        embedded_ts = utils.parse_embedded_timestamp(content, end)
        msg_time = embedded_ts if embedded_ts else mail_time

        # 備份副本（自己發的）也需要存入本地 DB，避免多裝置訊息遺失
        if is_backup:
            self.db.upsert_session(account_id=current_user, display_id=sender_id, set_visible=False)
            # backup 沒有明確的 receiver，但 session_id 就是自己
            # 不 emit 訊號（UI 已在發送時顯示過），但仍需存到 DB
            try:
                self.db.save_message(
                    account_id=current_user,
                    session_id=sender_id,
                    sender_id=current_user,
                    receiver_id=sender_id,
                    content=text,
                    timestamp=msg_time,
                    is_me=True,
                    mail_type='uptt'
                )
            except Exception as e:
                logger.error(f"儲存 uPtt backup 訊息失敗 (index={mail_idx}): {e}")
            return None, True, True  # 仍需刪除

        # 對方發來的 uPtt 訊息
        self.db.upsert_session(account_id=current_user, display_id=sender_id)
        try:
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
        except Exception as e:
            logger.error(
                f"儲存 uPtt 訊息失敗 (index={mail_idx})，"
                f"跳過刪除以防資料遺失: {e}"
            )
            return None, True, False

        emit_dict = None
        if is_new:
            emit_dict = {
                'sender': sender_id,
                'text': text,
                'time': msg_time.strftime("%H:%M"),
                'full_author': full_author,
                'timestamp': msg_time,
                'mail_type': 'uptt',
                'subject': ''
            }
        return emit_dict, True, True

    @Slot(int)
    def do_initial_scan(self, scan_days):
        """首次登入信箱掃描，帶進度回報"""
        try:
            current_poll_start = datetime.now()
            total_newest = self.ptt.call('get_newest_index', {'index_type': PyPtt.NewIndex.MAIL})

            if not total_newest or total_newest == 0:
                self.last_poll_time = current_poll_start
                self.db.set_config(f'LAST_POLL_TIME_{self.ptt.ptt_id.lower()}', current_poll_start.isoformat())
                self.scan_complete.emit()
                self.start_polling()
                return

            scan_all = (scan_days == 0)
            stop_time = None if scan_all else current_poll_start - timedelta(days=scan_days)
            found_uptt = False
            self.is_first_polling = False

            scanned_count = 0
            mails_to_emit = []
            deleted_count = 0

            logger.info(f"首次掃描: 總數={total_newest}, 掃描範圍={'全部' if scan_all else f'{scan_days}天'}")

            for mail_idx in range(total_newest, 0, -1):
                self._drain_send_queue()
                mail = self.ptt.call('get_mail', {'index': mail_idx})

                if not mail:
                    continue

                scanned_count += 1

                # 取得信件日期以判斷停止時間
                msg_date_str = mail.get(PyPtt.MailField.date)
                try:
                    mail_time = datetime.strptime(msg_date_str, '%a %b %d %H:%M:%S %Y')
                except (ValueError, TypeError):
                    mail_time = datetime.now()

                raw_title = mail.get(PyPtt.MailField.title)
                title = str(raw_title) if raw_title is not None else ""
                is_uptt_msg = (title == contant.PTT_MSG_TITLE)

                if is_uptt_msg:
                    found_uptt = True

                self.scan_progress.emit(scanned_count, total_newest, title)

                if stop_time and mail_time < stop_time and not is_uptt_msg:
                    if found_uptt:
                        stop_time = stop_time - timedelta(days=2)
                        found_uptt = False
                        if mail_time < stop_time:
                            break
                    else:
                        break

                # 使用共用方法處理信件
                emit_dict, is_uptt, should_delete = self._process_single_mail(mail, mail_idx)
                if emit_dict:
                    mails_to_emit.append(emit_dict)
                if should_delete:
                    self.ptt.call('del_mail', {'index': mail_idx})
                    deleted_count += 1

            # 更新狀態
            self._last_newest_index = total_newest - deleted_count
            self.last_poll_time = current_poll_start
            self.db.set_config(f'LAST_POLL_TIME_{self.ptt.ptt_id.lower()}', current_poll_start.isoformat())

            for mail_data in reversed(mails_to_emit):
                self.new_message_received.emit(mail_data)
                self.last_mail_time = mail_data['timestamp']

            logger.info(f"首次掃描完成: 掃描 {scanned_count} 封, 新訊息 {len(mails_to_emit)} 封")
            self.scan_complete.emit()
            self.start_polling()

        except Exception as e:
            logger.exception(f"首次掃描發生錯誤: {e}")
            self.status_updated.emit(f"掃描錯誤: {e}")
            self.scan_complete.emit()
            self.start_polling()

    def _poll_new_mails(self):
        """
        輪詢新信件的內部邏輯（時間驅動掃描策略）
        - 已有紀錄：掃描到上次輪詢時間，發現 uPtt 訊息則多掃 2 天
        - 非 uPtt 訊息最多掃描 MAX_POLL_SCAN 封，避免長時間斷線後阻塞
        - uPtt 訊息無論多舊都會處理並刪除
        """
        # 優先處理待發送訊息
        self._drain_send_queue()
        try:
            current_poll_start = datetime.now()

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

            # 快速跳過：信箱最新索引沒有變化
            if not self.is_first_polling and self._last_newest_index is not None:
                if total_newest == self._last_newest_index:
                    logger.debug(f"信箱無變化 (總數={total_newest})，跳過掃描")
                    self.last_poll_time = current_poll_start
                    self.db.set_config(f'LAST_POLL_TIME_{self.ptt.ptt_id.lower()}', current_poll_start.isoformat())
                    return
                elif total_newest < self._last_newest_index:
                    logger.debug(f"信箱索引減少 ({self._last_newest_index} → {total_newest})，仍繼續掃描")

            if self.last_poll_time:
                stop_time = self.last_poll_time - timedelta(seconds=10)
            else:
                stop_time = current_poll_start - timedelta(days=7)

            found_uptt = False
            self.is_first_polling = False

            logger.debug(f"輪詢掃描中: 總數={total_newest}, 新增={total_newest - (self._last_newest_index or 0)}, 截止時間={stop_time}")

            mails_to_emit = []
            deleted_count = 0
            scan_count = 0

            for mail_idx in range(total_newest, 0, -1):
                self._drain_send_queue()
                mail = self.ptt.call('get_mail', {'index': mail_idx})

                if not mail:
                    continue

                msg_date_str = mail.get(PyPtt.MailField.date)
                try:
                    mail_time = datetime.strptime(msg_date_str, '%a %b %d %H:%M:%S %Y')
                except (ValueError, TypeError):
                    mail_time = datetime.now()

                raw_title = mail.get(PyPtt.MailField.title)
                title = str(raw_title) if raw_title is not None else ""
                is_uptt_msg = (title == contant.PTT_MSG_TITLE)

                if is_uptt_msg:
                    found_uptt = True
                else:
                    scan_count += 1  # uPtt 訊息不計入掃描數量

                # 提早結束判定 (僅對非 uPtt 訊息生效)
                if mail_time < stop_time and not is_uptt_msg:
                    if found_uptt:
                        stop_time = stop_time - timedelta(days=2)
                        found_uptt = False
                        if mail_time < stop_time:
                            logger.debug(f"已進入舊信區域 (索引 {mail_idx}, 時間 {mail_time}), 停止。")
                            break
                    else:
                        logger.debug(f"已進入舊信區域 (索引 {mail_idx}, 時間 {mail_time}), 停止本次掃描。")
                        break

                # 掃描數量上限 (uPtt 訊息不計入，必須全部處理並刪除)
                if scan_count >= MAX_POLL_SCAN and not is_uptt_msg:
                    logger.debug(f"已達掃描上限 ({MAX_POLL_SCAN})，停止本次輪詢")
                    break

                # 使用共用方法處理信件
                emit_dict, is_uptt, should_delete = self._process_single_mail(mail, mail_idx)
                if emit_dict:
                    mails_to_emit.append(emit_dict)
                if should_delete:
                    self.ptt.call('del_mail', {'index': mail_idx})
                    deleted_count += 1

            self._last_newest_index = total_newest - deleted_count
            self.last_poll_time = current_poll_start
            self.db.set_config(f'LAST_POLL_TIME_{self.ptt.ptt_id.lower()}', current_poll_start.isoformat())

            for mail_data in reversed(mails_to_emit):
                self.new_message_received.emit(mail_data)
                self.last_mail_time = mail_data['timestamp']

        except PyPtt.ConnectionClosed:
            logger.warning("輪詢時偵測到連線中斷，將延遲重連...")
            if self._was_connected:
                self._was_connected = False
                self.connection_lost.emit()
                self.status_updated.emit("連線中斷，正在嘗試重新連線...")
            QTimer.singleShot(5000, self._deferred_reconnect)
        except PyPtt.MailboxFull:
            # PyPtt 的 del_mail() 偵測到信箱已滿時，會先呼叫 api.logout() 再拋出此例外。
            # 此時 PTT 連線已中斷，必須停止輪詢並通知 UI 返回登入畫面。
            logger.error("信箱已滿，PyPtt 已自動登出。停止輪詢。")
            if self.polling_timer:
                self.polling_timer.stop()
            self.disconnected.emit(
                "郵件信箱已滿，PTT 已自動登出。\n請至 PTT 清理信箱後重新登入。"
            )
        except Exception as e:
            logger.exception(f"輪詢信件發生錯誤: {e}")
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

    # ── 發送訊息：優先佇列機制 ──────────────────────────────

    def enqueue_send(self, receiver_id: str, text: str, timestamp=None, msg_id: int = -1):
        """Thread-safe: 從任何執行緒將發送請求加入優先佇列。

        UI 直接呼叫此方法（不經 Qt 事件佇列），確保請求在阻塞操作
        之間被 _drain_send_queue() 即時撈出處理。msg_id 為 UI 預先寫入 DB
        的 pending 訊息 row id，發送結果透過此 id 對應回 DB 與 UI bubble。
        """
        self._send_queue.put((receiver_id, text, timestamp, msg_id))

    def _drain_send_queue(self) -> bool:
        """處理所有待發送訊息。在每個阻塞操作之間協作式呼叫。

        Returns:
            True 若有實際發送過訊息。
        """
        sent = False
        while not self._send_queue.empty():
            try:
                receiver_id, text, timestamp, msg_id = self._send_queue.get_nowait()
            except queue.Empty:
                break
            logger.info(f"[發送插隊] 偵測到待發送訊息，暫停當前任務，優先發送給 {receiver_id}")
            self._do_send(receiver_id, text, timestamp, msg_id)
            sent = True
        return sent

    @Slot(str, str, object, int)
    def send_message(self, receiver_id, text, timestamp=None, msg_id: int = -1):
        """由 signal 觸發的後備路徑：worker 閒置時直接處理佇列。

        訊息已由 enqueue_send 放入佇列，此處僅負責喚醒 drain，不再入列。
        """
        self._drain_send_queue()

    def _do_send(self, receiver_id, text, timestamp, msg_id: int = -1):
        """實際執行站內信發送。pending row 由 UI 預先寫入 DB；此處只負責
        呼叫 PyPtt 並依結果更新 send_status。"""
        try:
            receiver_id = receiver_id.strip()
            send_time = timestamp if isinstance(timestamp, datetime) else datetime.now()
            ptt_msg = utils.msg_to_mail(contant.pkg_name, self.ptt.ptt_id or "uPttUser", text, timestamp=send_time)

            logger.info(f"正在發送站內信給 {receiver_id}...")
            self.ptt.call('mail', {
                'ptt_id': receiver_id,
                'title': contant.PTT_MSG_TITLE,
                'content': ptt_msg,
                'sign_file': '0',
                'backup': False
            })

            if msg_id > 0:
                self.db.update_message_status(msg_id, 'sent')

            logger.info(f"訊息已成功發送至 {receiver_id}")
            self.send_result.emit(msg_id, True, "")
        except Exception as e:
            logger.exception(f"發送訊息過程中發生例外狀況: {e}")
            if msg_id > 0:
                self.db.update_message_status(msg_id, 'failed')
            self.send_result.emit(msg_id, False, "發送失敗，請稍後再試")

    def _poll_waterballs(self):
        """輪詢水球訊息"""
        # 優先處理待發送訊息
        self._drain_send_queue()
        try:
            waterballs = self.ptt.call('get_waterball', {'post_action': PyPtt.WaterballPostAction.CLEAR})

            if not waterballs:
                return

            current_user = self.ptt.ptt_id
            if not current_user:
                return

            # 整批去重：若這批水球跟上次完全一樣，代表 CLEAR 沒生效，直接跳過
            # 排序以避免 PTT 回傳順序不同導致誤判為不同批次
            batch_fingerprint = str(sorted([
                (wb.get(PyPtt.WaterballField.target, ''),
                 wb.get(PyPtt.WaterballField.content, ''),
                 wb.get(PyPtt.WaterballField.date, ''),
                 wb.get(PyPtt.WaterballField.type))
                for wb in waterballs
            ]))
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

    @Slot()
    def stop(self):
        """停止所有背景任務並登出"""
        try:
            logger.info("正在停止 Worker...")
            if self.polling_timer:
                self.polling_timer.stop()
            if self._waterball_timer:
                self._waterball_timer.stop()

            # 關閉 PTT 連線
            if self.ptt:
                self.ptt.close()
            logger.info("Worker 已成功停止")
        except Exception as e:
            logger.error(f"停止 Worker 時發生錯誤: {e}")


class QueryWorker(QObject):
    """
    使用者狀態查詢背景工作者。
    獨立的 PyPtt session 專職處理 get_user_info、在線輪詢與活躍對話輪詢,
    不與訊息收發 session 共用 UI 狀態,避免查詢卡住送信。
    """
    user_info_result = Signal(dict)
    user_info_error = Signal(str, str)
    online_status_updated = Signal(str, bool)
    session_archived = Signal(str)
    query_session_degraded = Signal()   # 副 session 無法提供使用者狀態(登入失敗或斷線)
    query_session_restored = Signal()   # 副 session 恢復正常

    def __init__(self, ptt_service: UPttService, db):
        super().__init__()
        self.ptt = ptt_service
        self.db = db
        self._online_check_timer: Optional[QTimer] = None
        self._online_check_queue: list[str] = []
        self._active_chat_online_timer: Optional[QTimer] = None
        self._active_chat_id: Optional[str] = None
        self._degraded: bool = False  # 副 session 目前是否處於降級狀態
        self._pending_user_info: list[str] = []  # 副 session 登入前暫存的查詢請求

    def _mark_degraded(self, reason: str):
        """進入降級狀態,通知 UI。重複進入不會重複 emit。"""
        if not self._degraded:
            self._degraded = True
            logger.warning(f"[Query] 進入降級狀態: {reason}")
            self.query_session_degraded.emit()

    def _mark_restored(self):
        """從降級狀態恢復,通知 UI。"""
        if self._degraded:
            self._degraded = False
            logger.info("[Query] 副 session 已恢復正常")
            self.query_session_restored.emit()

    @Slot(str, str)
    def do_login(self, ptt_id: str, ptt_pw: str):
        """以 kick_other_session=False 登入,與主 session 共存。"""
        try:
            self.ptt.login(ptt_id, ptt_pw, force=False)
            logger.info(f"[Query] 副 session 登入成功: {self.ptt.ptt_id}")
            self._mark_restored()
            self._start_online_polling()
            # 重放登入前暫存的查詢請求（以 QTimer 逐筆處理，避免阻塞事件迴圈）
            self._replay_queue = self._pending_user_info[:]
            self._pending_user_info.clear()
            if self._replay_queue:
                QTimer.singleShot(500, self._replay_next_pending)
        except Exception as e:
            logger.warning(f"[Query] 副 session 登入失敗,使用者狀態功能將無法使用: {e}")
            self._mark_degraded(f"登入失敗: {e}")

    def _replay_next_pending(self):
        """逐筆重放登入前暫存的 user_info 查詢，每筆間隔 2 秒避免阻塞。"""
        if not hasattr(self, '_replay_queue') or not self._replay_queue:
            return
        queued_id = self._replay_queue.pop(0)
        self.get_user_info(queued_id)
        if self._replay_queue:
            QTimer.singleShot(2000, self._replay_next_pending)

    def _start_online_polling(self):
        """啟動在線狀態定期檢查(登入成功後呼叫)。"""
        if self._online_check_timer is None:
            self._online_check_timer = QTimer(self)
            self._online_check_timer.timeout.connect(self._check_all_online_status)
            interval = getattr(config, 'CHECK_ONLINE_STATUS_INTERVAL', 60) * 1000
            self._online_check_timer.start(interval)
            logger.info(f"[Query] 開始輪詢在線狀態,間隔: {interval / 1000}s")
            self._check_all_online_status()

    def _emit_user_info(self, info: dict):
        """將 get_user_info 回傳的 dict 發射為 user_info_result 訊號。"""
        self.user_info_result.emit({
            'ptt_id': info['ptt_id'],
            'nickname': info['nickname'],
            'is_online': info['is_online'],
            'activity': info.get('activity', ''),
            'login_count': info.get('login_count', ''),
            'last_login_date': info.get('last_login_date', ''),
            'legal_post': info.get('legal_post', ''),
            'illegal_post': info.get('illegal_post', ''),
            'money': info.get('money', ''),
        })

    def _handle_no_such_user(self, ptt_id: str):
        """處理查無此人的情況：封存會話並通知 UI。"""
        if self.ptt.ptt_id:
            self.db.archive_session(self.ptt.ptt_id, ptt_id)
            self.session_archived.emit(ptt_id.lower())
            logger.info(f"使用者 {ptt_id} 不存在,會話已封存")

    @Slot(str)
    def get_user_info(self, ptt_id):
        """主動獲取使用者資訊 (包含暱稱、正確大小寫與在線狀態)。"""
        if not self.ptt.ptt_id:
            logger.info(f"[Query] 副 session 尚未登入,暫存查詢: {ptt_id}")
            self._pending_user_info.append(ptt_id)
            return
        try:
            logger.info(f"--- 開始查詢使用者資訊: {ptt_id} ---")
            info = self.ptt.get_user_info(ptt_id)
            self._mark_restored()

            self.db.upsert_session(
                account_id=self.ptt.ptt_id,
                display_id=info['ptt_id'],
                nickname=info['nickname']
            )

            self._emit_user_info(info)
            logger.info(f"成功獲取使用者資訊: {info}")
        except ValueError as e:
            self._mark_restored()
            error_msg = str(e)
            logger.warning(f"查詢使用者 {ptt_id} 失敗: {error_msg}")
            if "查無此人" in error_msg:
                self._handle_no_such_user(ptt_id)
            else:
                self.user_info_error.emit(ptt_id, error_msg)
        except PyPtt.ConnectionClosed:
            self._mark_degraded("連線中斷")
            logger.warning(f"[Query] 查詢 {ptt_id} 時連線中斷")
            self.user_info_error.emit(ptt_id, "副 session 連線中斷")
        except Exception as e:
            self._mark_degraded(f"查詢例外: {e}")
            logger.error(f"獲取使用者 {ptt_id} 資訊過程中發生非預期錯誤: {e}", exc_info=True)
            self.user_info_error.emit(ptt_id, f"系統錯誤: {str(e)}")
        finally:
            logger.info(f"--- 查詢結束: {ptt_id} ---")

    @Slot(str)
    def check_online_priority(self, ptt_id: str):
        """立即查詢指定聯絡人的在線狀態(打開對話視窗時優先更新)。"""
        if not self.ptt.ptt_id:
            return
        ptt_id_lower = ptt_id.lower()
        if ptt_id_lower == self.ptt.ptt_id.lower():
            return
        try:
            logger.info(f"[優先在線查詢] 查詢 {ptt_id_lower}")
            info = self.ptt.get_user_info(ptt_id_lower)
            self._mark_restored()
            status = "在線" if info['is_online'] else "離線"
            logger.info(f"[優先在線查詢] {ptt_id_lower} → {status}")
            self.online_status_updated.emit(ptt_id_lower, info['is_online'])
            self._emit_user_info(info)
        except ValueError as e:
            self._mark_restored()
            if "查無此人" in str(e):
                self._handle_no_such_user(ptt_id_lower)
            else:
                logger.info(f"[優先在線查詢] {ptt_id} 查詢失敗: {e}")
        except PyPtt.ConnectionClosed:
            self._mark_degraded("連線中斷")
            logger.warning(f"[優先在線查詢] {ptt_id} 連線中斷")
        except Exception as e:
            self._mark_degraded(f"查詢例外: {e}")
            logger.info(f"[優先在線查詢] {ptt_id} 查詢失敗: {e}")

    def _check_all_online_status(self):
        """定期檢查所有聯絡人的在線狀態(非阻塞式:每次只查一人,讓出事件迴圈)。"""
        if not self.ptt.ptt_id:
            return
        if self._online_check_queue:
            logger.info(f"[在線檢查] 上一輪尚未完成(剩餘 {len(self._online_check_queue)} 人),跳過本輪")
            return
        try:
            sessions = self.db.get_all_sessions(self.ptt.ptt_id)
            my_id = self.ptt.ptt_id.lower()
            self._online_check_queue = [
                s['id'] for s in sessions if s['id'] != my_id and not s.get('is_archived')
            ]
            if self._online_check_queue:
                per_user_delay = getattr(config, 'ONLINE_CHECK_PER_USER_DELAY', 5) * 1000
                logger.info(f"[在線檢查] 開始新一輪,共 {len(self._online_check_queue)} 位聯絡人")
                QTimer.singleShot(per_user_delay, self._check_next_online_status)
        except Exception as e:
            logger.warning(f"在線狀態輪詢失敗: {e}")

    def _check_next_online_status(self):
        """從佇列中取出一個聯絡人查詢在線狀態,查完後讓出事件迴圈再查下一個。"""
        if not self._online_check_queue or not self.ptt.ptt_id:
            self._online_check_queue.clear()
            return
        contact_id = self._online_check_queue.pop(0)
        remaining = len(self._online_check_queue)
        try:
            logger.info(f"[在線檢查] 查詢 {contact_id}(剩餘 {remaining} 人)")
            info = self.ptt.get_user_info(contact_id)
            self._mark_restored()
            status = "在線" if info['is_online'] else "離線"
            logger.info(f"[在線檢查] {contact_id} → {status}")
            self.online_status_updated.emit(contact_id, info['is_online'])
        except ValueError as e:
            self._mark_restored()
            if "查無此人" in str(e):
                self._handle_no_such_user(contact_id)
            else:
                logger.info(f"[在線檢查] {contact_id} 查詢失敗: {e}")
        except PyPtt.ConnectionClosed:
            self._mark_degraded("連線中斷")
            logger.warning(f"[在線檢查] {contact_id} 連線中斷,清空本輪佇列")
            self._online_check_queue.clear()
            return
        except Exception as e:
            self._mark_degraded(f"查詢例外: {e}")
            logger.info(f"[在線檢查] {contact_id} 查詢失敗: {e}")
        try:
            if self._online_check_queue:
                per_user_delay = getattr(config, 'ONLINE_CHECK_PER_USER_DELAY', 5) * 1000
                QTimer.singleShot(per_user_delay, self._check_next_online_status)
            else:
                logger.info("[在線檢查] 本輪全部完成")
        except Exception as e:
            logger.warning(f"在線狀態檢查鏈排程失敗,清空佇列: {e}")
            self._online_check_queue.clear()

    @Slot(str)
    def set_active_chat(self, ptt_id: str):
        """設定目前開啟的對話視窗,啟動該使用者的高頻在線狀態輪詢。

        傳入空字串表示關閉對話視窗。
        """
        new_id = ptt_id.lower() if ptt_id else None

        if new_id == self._active_chat_id:
            return

        self._active_chat_id = new_id

        if self._active_chat_online_timer:
            self._active_chat_online_timer.stop()
            self._active_chat_online_timer = None

        if not new_id or not self.ptt.ptt_id:
            return

        if new_id == self.ptt.ptt_id.lower():
            return

        self._poll_active_chat_online()
        self._active_chat_online_timer = QTimer(self)
        self._active_chat_online_timer.timeout.connect(self._poll_active_chat_online)
        interval = getattr(config, 'CHECK_ACTIVE_CHAT_ONLINE_INTERVAL', 10) * 1000
        self._active_chat_online_timer.start(interval)
        logger.info(f"開始高頻在線輪詢: {new_id},間隔: {interval / 1000}s")

    def _poll_active_chat_online(self):
        """查詢目前開啟對話的使用者在線狀態。"""
        chat_id = self._active_chat_id
        if not chat_id or not self.ptt.ptt_id:
            return
        try:
            info = self.ptt.get_user_info(chat_id)
            self._mark_restored()
            self.online_status_updated.emit(chat_id, info['is_online'])
        except ValueError as e:
            self._mark_restored()
            if "查無此人" in str(e):
                if self._active_chat_online_timer:
                    self._active_chat_online_timer.stop()
                    self._active_chat_online_timer = None
                self._active_chat_id = None
                self._handle_no_such_user(chat_id)
            else:
                logger.debug(f"[活躍對話在線檢查] {chat_id} 查詢失敗: {e}")
        except PyPtt.ConnectionClosed:
            self._mark_degraded("連線中斷")
            logger.warning(f"[活躍對話在線檢查] {chat_id} 連線中斷")
        except Exception as e:
            self._mark_degraded(f"查詢例外: {e}")
            logger.debug(f"[活躍對話在線檢查] {chat_id} 查詢失敗: {e}")

    @Slot()
    def stop(self):
        """停止 query worker:關閉所有 timer 並登出副 session。"""
        try:
            logger.info("正在停止 QueryWorker...")
            if self._online_check_timer:
                self._online_check_timer.stop()
                self._online_check_timer = None
            if self._active_chat_online_timer:
                self._active_chat_online_timer.stop()
                self._active_chat_online_timer = None
            self._active_chat_id = None
            self._online_check_queue.clear()

            if self.ptt:
                self.ptt.close()
            logger.info("QueryWorker 已成功停止")
        except Exception as e:
            logger.error(f"停止 QueryWorker 時發生錯誤: {e}")
