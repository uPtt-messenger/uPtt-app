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
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt, QSize, QPointF, QEvent
from PySide6.QtGui import QDropEvent
from PySide6.QtCore import QMimeData
from PySide6.QtWidgets import QListWidgetItem, QApplication

from src.uPtt.ui.widgets import ContactListWidget, ContactItem
from src.uPtt.ui.screens import MainWindow
from src.uPtt.ptt import UPttService


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


@patch('src.uPtt.ui.screens.QMessageBox')
@patch('src.uPtt.ui.screens.VersionCheckWorker')
@patch('src.uPtt.ui.screens.QueryWorker')
@patch('src.uPtt.ui.screens.PTTWorker')
@patch('src.uPtt.ui.screens.QThread')
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
