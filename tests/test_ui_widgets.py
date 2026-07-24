import pytest
from PySide6.QtCore import Qt
from src.uPtt.ui.widgets import ChatBubble, ContactItem
from src.uPtt.ui.styles import get_bubble_style
from src.uPtt.ui.theme import GRAPHITE

def test_get_bubble_style():
    # 自己的訊息泡泡：實心 accent 綠底 + 深色文字，靠右，需與對方泡泡視覺可區分。
    style_me = get_bubble_style(True)
    assert f"background-color: {GRAPHITE['accent']};" in style_me
    assert f"color: {GRAPHITE['bg']};" in style_me

    style_other = get_bubble_style(False)
    assert f"background-color: {GRAPHITE['surface_2']};" in style_other
    assert style_me != style_other

def test_chat_bubble_me(qtbot):
    bubble = ChatBubble("Hello Me", "10:00", is_me=True)
    qtbot.addWidget(bubble)
    
    assert bubble.message_label.text() == "Hello Me"
    assert bubble.time_label.text() == "10:00"
    assert bubble.is_me is True

def test_chat_bubble_other(qtbot):
    bubble = ChatBubble("Hello You", "11:00", is_me=False)
    qtbot.addWidget(bubble)
    
    assert bubble.message_label.text() == "Hello You"
    assert bubble.time_label.text() == "11:00"
    assert bubble.is_me is False

def test_contact_item_init(qtbot):
    item = ContactItem("TestUser", "MyNick", unread_count=5)
    qtbot.addWidget(item)
    
    assert item.ptt_id == "testuser"
    assert item.id_label.text() == "TestUser"
    assert "(MyNick)" in item.nickname_label.text()
    assert item.unread_label.text() == "5"

def test_contact_item_update_info(qtbot):
    item = ContactItem("testuser")
    qtbot.addWidget(item)
    
    item.update_info("TestUserCorrect", "NewNick")
    assert item.id_label.text() == "TestUserCorrect"
    assert "(NewNick)" in item.nickname_label.text()
    
    item.set_nickname("AnotherNick")
    assert "(AnotherNick)" in item.nickname_label.text()
    
    item.set_unread(10)
    assert item.unread_label.text() == "10"

    item.set_unread(0)
    assert item.unread_label.text() == ""


def test_contact_item_custom_name_overrides_nickname_label(qtbot):
    item = ContactItem("TestUser", "PTTNick", custom_name="MyAlias")
    qtbot.addWidget(item)
    assert "(MyAlias)" in item.nickname_label.text()
    assert "PTTNick" not in item.nickname_label.text()


def test_contact_item_set_custom_name_updates_label(qtbot):
    item = ContactItem("TestUser", "PTTNick")
    qtbot.addWidget(item)
    assert "(PTTNick)" in item.nickname_label.text()

    item.set_custom_name("MyAlias")
    assert "(MyAlias)" in item.nickname_label.text()

    item.set_custom_name("")
    assert "(PTTNick)" in item.nickname_label.text()


def test_contact_item_update_info_keeps_custom_name_priority(qtbot):
    item = ContactItem("TestUser", "OldNick", custom_name="MyAlias")
    qtbot.addWidget(item)
    item.update_info("TestUserCorrect", "NewNick")
    # PTT 暱稱查詢刷新不應蓋掉本機自訂名稱的顯示優先權
    assert "(MyAlias)" in item.nickname_label.text()


def test_contact_item_get_data_includes_custom_name(qtbot):
    item = ContactItem("TestUser", "Nick", custom_name="Alias")
    qtbot.addWidget(item)
    data = item.get_data()
    assert data['custom_name'] == "Alias"


def test_chat_bubble_stores_message_id(qtbot):
    bubble = ChatBubble("Hello", "10:00", is_me=True, message_id=42)
    qtbot.addWidget(bubble)
    assert bubble.message_id == 42

def test_chat_bubble_delete_action_emits_message_id(qtbot):
    bubble = ChatBubble("Hello", "10:00", is_me=True, message_id=42)
    qtbot.addWidget(bubble)
    menu = bubble._build_context_menu()
    delete_action = next(a for a in menu.actions() if a.text().startswith("刪除"))
    with qtbot.waitSignal(bubble.delete_requested, timeout=1000) as blocker:
        delete_action.trigger()
    assert blocker.args == [42]

def test_chat_bubble_no_delete_action_without_message_id(qtbot):
    bubble = ChatBubble("Hello", "10:00", is_me=True)
    qtbot.addWidget(bubble)
    menu = bubble._build_context_menu()
    assert not any(a.text().startswith("刪除") for a in menu.actions())
