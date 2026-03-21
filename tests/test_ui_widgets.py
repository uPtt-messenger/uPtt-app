import pytest
from PySide6.QtCore import Qt
from src.uPtt.ui.widgets import ChatBubble, ContactItem
from src.uPtt.ui.styles import get_bubble_style

def test_get_bubble_style():
    style_me = get_bubble_style(True)
    assert "background-color: #1C3A2E;" in style_me

    style_other = get_bubble_style(False)
    assert "background-color: #21262D;" in style_other

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
