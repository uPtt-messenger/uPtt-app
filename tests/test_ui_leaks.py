"""ContactItem widget 洩漏回歸測試。

用 shiboken6.isValid() 驗證舊 widget 在下列兩個路徑後真的被銷毀：
1. ContactListWidget.dropEvent() 重排時取代舊 item。
2. MainWindow 登出流程清空 contact_list。

deleteLater() 是非同步的，需靠 app.sendPostedEvents(None, QEvent.DeferredDelete)
把排入佇列的刪除事件同步跑掉，才能立即斷言 isValid()==False（純呼叫
QApplication.processEvents() 不足以觸發 DeferredDelete，實測驗證過）。
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shiboken6
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt, QSize, QPointF, QEvent
from PySide6.QtGui import QDropEvent
from PySide6.QtCore import QMimeData
from PySide6.QtWidgets import QListWidgetItem, QApplication

from uPtt.ui.widgets import ContactListWidget, ContactItem
from uPtt.ui.screens import MainWindow
from uPtt.ptt import UPttService


def _flush_deferred_deletes():
    """同步處理所有 deleteLater() 佇列中的刪除事件。"""
    QApplication.instance().sendPostedEvents(None, QEvent.DeferredDelete)


@pytest.fixture
def ptt_service_mock():
    service = MagicMock(spec=UPttService)
    service.ptt_id = "MyID"
    service.ptt_pw = "mypass"
    return service


@pytest.fixture
def ptt_query_service_mock():
    service = MagicMock(spec=UPttService)
    service.ptt_id = "MyID"
    service.ptt_pw = "mypass"
    return service


@pytest.fixture
def db_mock():
    db = MagicMock()
    db.get_all_sessions.return_value = []
    db.get_messages.return_value = []
    return db


def test_drop_event_deletes_replaced_widgets(qtbot):
    """dropEvent 重排後，被取代的舊 ContactItem widget 必須已銷毀（不再是 orphan）。"""
    lw = ContactListWidget()
    qtbot.addWidget(lw)
    lw.resize(300, 300)
    lw.show()

    old_widgets = []
    for i in range(3):
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 70))
        widget = ContactItem(ptt_id=f"user{i}", nickname="", unread_count=0, is_pinned=False)
        lw.addItem(item)
        lw.setItemWidget(item, widget)
        old_widgets.append(widget)

    lw.setCurrentItem(lw.item(0))  # source = user0

    # 拖到最後一個項目的位置，觸發重排
    target_rect = lw.visualItemRect(lw.item(2))
    pos = QPointF(target_rect.center())
    event = QDropEvent(pos, Qt.MoveAction, QMimeData(), Qt.LeftButton, Qt.NoModifier, QEvent.Drop)

    lw.dropEvent(event)
    _flush_deferred_deletes()

    for w in old_widgets:
        assert not shiboken6.isValid(w), f"{w.ptt_id} 應已在 dropEvent 重排後被銷毀"

    # 重排後的資料仍完整（user0 移到 user1/user2 之後）
    assert lw.count() == 3
    assert [lw.itemWidget(lw.item(i)).ptt_id for i in range(3)] == ["user1", "user2", "user0"]


@patch('uPtt.ui.main_window.QMessageBox')
@patch('uPtt.ui.main_window.VersionCheckWorker')
@patch('uPtt.ui.main_window.QueryWorker')
@patch('uPtt.ui.main_window.PTTWorker')
@patch('uPtt.ui.main_window.QThread')
def test_logout_deletes_contact_list_widgets(mock_qthread, mock_worker, mock_query_worker,
                                              mock_ver_worker, mock_msgbox, qtbot,
                                              ptt_service_mock, ptt_query_service_mock, db_mock):
    """登出流程清空 contact_list 後，所有 ContactItem widget 必須已銷毀。"""
    db_mock.get_all_sessions.return_value = [
        {'id': f'user{i}', 'display_id': f'User{i}', 'nickname': '', 'unread_count': 0,
         'is_pinned': 0, 'last_message_time': '', 'is_archived': 0}
        for i in range(3)
    ]
    mock_msgbox.question.return_value = mock_msgbox.Yes

    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        # worker/thread 都是 MagicMock，QMetaObject.invokeMethod 對它們必然拋型別錯誤且
        # 被 _do_logout 的 except 吞掉；與本測試要驗證的 contact_list widget 清理無關，
        # 直接短路掉（沿用 test_fully_quit_is_reentrant_safe 同款作法）。
        window._stop_all_threads = MagicMock()
        window.load_sessions_from_db()

        assert window.contact_list.count() == 3
        old_widgets = [window.contact_list.itemWidget(window.contact_list.item(i)) for i in range(3)]

        window.handle_logout()
        _flush_deferred_deletes()

        assert window.contact_list.count() == 0
        for w in old_widgets:
            assert not shiboken6.isValid(w), "登出後 ContactItem widget 應已被銷毀"


@patch('uPtt.ui.main_window.VersionCheckWorker')
@patch('uPtt.ui.main_window.QueryWorker')
@patch('uPtt.ui.main_window.PTTWorker')
@patch('uPtt.ui.main_window.QThread')
def test_apply_theme_twice_leaves_no_ghost_message_widgets(mock_qthread, mock_worker, mock_query_worker,
                                                             mock_ver_worker, qtbot, ptt_service_mock,
                                                             ptt_query_service_mock, db_mock):
    """apply_theme() 對已經渲染出對話內容的視窗連續呼叫兩次時，refresh_chat_display()
    若只用 deleteLater()（非同步）清除舊 bubble，在同一個事件迴圈迭代內立刻重建
    就會讓舊 widget 疊在新 widget 上（畫面殘影、文字重複）。
    用「訊息區子 widget 數量」驗證第二次套用主題後沒有殘留幽靈 widget。"""
    db_mock.get_messages.return_value = [
        {'id': 1, 'content': 'hello there', 'timestamp': datetime(2026, 7, 20, 9, 0, 0),
         'is_me': 0, 'mail_type': 'uptt', 'subject': '', 'send_status': None},
        {'id': 2, 'content': 'hi back', 'timestamp': datetime(2026, 7, 20, 9, 1, 0),
         'is_me': 1, 'mail_type': 'uptt', 'subject': '', 'send_status': 'sent'},
    ]
    with patch('os.path.exists', return_value=True):
        window = MainWindow(ptt_service_mock, ptt_query_service_mock, db_mock)
        qtbot.addWidget(window)
        window.on_login_result(True, "Login Success")
        window.add_or_select_contact("Alice")

        count_after_first_render = len(window.messages_widget.children())
        assert count_after_first_render > 0

        # 刻意不呼叫 processEvents()：重現「使用中切換主題」時，deleteLater()
        # 尚未有機會被事件迴圈處理就馬上重繪的情境。
        window.apply_theme('bone')
        count_after_second_apply = len(window.messages_widget.children())

        assert count_after_second_apply == count_after_first_render, (
            f"apply_theme() 連續呼叫兩次後，訊息區子 widget 數量從 "
            f"{count_after_first_render} 增為 {count_after_second_apply}，"
            f"代表舊 bubble 未即時脫離、殘留成疊圖幽靈 widget"
        )
