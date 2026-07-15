import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel
from src.uPtt.ui.widgets import ChatBubble, ContactItem, MailCard, WaterballBubble
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

HTML_PAYLOAD = '<img src="http://evil/x.png">'


def test_chat_bubble_html_not_rendered_as_richtext(qtbot):
    # M-3: 不受信任的站內信內容不得以 rich text 算繪（否則 <img> 會自動抓遠端）
    bubble = ChatBubble(HTML_PAYLOAD, "10:00", is_me=False)
    qtbot.addWidget(bubble)

    assert bubble.message_label.textFormat() == Qt.TextFormat.PlainText
    # <img> 被當純文字保留，而非解析成圖片標籤
    assert "<img" in bubble.message_label.text()


def test_mail_card_html_not_rendered_as_richtext(qtbot):
    # 主旨與內文皆為不受信任內容，兩者都須為 PlainText
    card = MailCard("<a href='http://evil'>subj</a>", HTML_PAYLOAD, "10:00")
    qtbot.addWidget(card)

    labels = card.findChildren(QLabel)
    content_label = next(l for l in labels if "<img" in l.text())
    subject_label = next(l for l in labels if "<a href" in l.text())
    assert content_label.textFormat() == Qt.TextFormat.PlainText
    assert subject_label.textFormat() == Qt.TextFormat.PlainText


def test_waterball_bubble_html_not_rendered_as_richtext(qtbot):
    wb = WaterballBubble(HTML_PAYLOAD, "10:00", is_me=False)
    qtbot.addWidget(wb)

    assert wb.message_label.textFormat() == Qt.TextFormat.PlainText
    assert "<img" in wb.message_label.text()


def test_contact_item_id_and_nickname_html_not_rendered_as_richtext(qtbot):
    # M-3: 對方 ID/暱稱同屬不受信任的 PTT 內容，暱稱欄位不限 HTML 字元
    payload_id = '<img src=x onerror=alert(1)>'
    payload_nick = '<a href=evil>nick</a>'
    item = ContactItem(payload_id, payload_nick)
    qtbot.addWidget(item)

    assert item.id_label.textFormat() == Qt.TextFormat.PlainText
    assert item.nickname_label.textFormat() == Qt.TextFormat.PlainText
    assert item.id_label.text() == payload_id
    assert payload_nick in item.nickname_label.text()


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
