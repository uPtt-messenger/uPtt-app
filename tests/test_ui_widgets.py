import pytest
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QLabel, QListWidgetItem
from uPtt.ui.widgets import (
    ChatBubble, ContactItem, ContactListWidget, MailCard, WaterballBubble,
    EmptyChatPlaceholder, EmptySidebarPlaceholder, SyncSpinner,
)
from uPtt.ui import styles
from uPtt.ui.styles import get_bubble_style

def test_get_bubble_style():
    # 氣泡顏色現在來自 active theme 的 own/other token，不再是寫死色碼
    styles.set_theme('graphite')
    t = styles.theme()

    style_me = get_bubble_style(True)
    assert f"background-color: {t['own']};" in style_me

    style_other = get_bubble_style(False)
    assert f"background-color: {t['other']};" in style_other

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


def test_contact_item_unread_badge_flush_right_after_list_resize(qtbot):
    """right_container（時間＋未讀徽章）要貼齊聯絡人清單的右緣，即使 view 在
    item 已存在的情況下改變寬度（模擬視窗 resize／側欄動態調寬後的情境）。

    QAbstractItemView 對 setItemWidget() 掛上去的 widget，其幾何同步
    (updateEditorGeometries) 預設延後到下一輪事件迴圈/繪製才真正套用；resize
    當下若不主動同步一次，列內的 ContactItem 仍依照舊寬度排列子元件——未讀
    徽章因此浮在列中間、右側留一大片空白，直到下一次重繪才自我修正
    （見 ContactListWidget.resizeEvent）。"""
    lw = ContactListWidget()
    qtbot.addWidget(lw)
    lw.resize(640, 400)  # 先給一個寬版面，讓 item 的初始佈局吃到「舊」寬度

    item = QListWidgetItem()
    item.setSizeHint(QSize(0, 70))
    widget = ContactItem("Bob", unread_count=3)
    lw.addItem(item)
    lw.setItemWidget(item, widget)
    lw.grab()  # 強制觸發一次 editor-geometry 同步，讓 item 在寬版面下先落定

    lw.resize(189, 400)  # 縮寬（模擬側欄自動變窄／視窗縮小），刻意不 show()/grab()

    right_container = widget.unread_label.parentWidget()
    gap = widget.width() - right_container.geometry().right()
    assert gap <= 12, (
        f"未讀徽章右緣與列右緣間距 {gap}px，應貼齊右緣（含版面留白，容許 <=12px）"
    )


THEME_NAMES = ['graphite', 'bone', 'mono']


def _other_theme_tokens(name, key):
    return [styles.THEMES[n][key] for n in THEME_NAMES if n != name]


def test_chat_bubble_uses_active_theme_tokens(qtbot):
    # Phase 2: widgets.py 不得寫死色碼，時間戳顏色需隨 active theme 切換
    try:
        for name in THEME_NAMES:
            styles.set_theme(name)
            t = styles.theme()
            bubble = ChatBubble("hi", "10:00", is_me=False)
            qtbot.addWidget(bubble)

            style = bubble.time_label.styleSheet()
            assert t['faint'] in style
            for other_value in _other_theme_tokens(name, 'faint'):
                assert other_value not in style
    finally:
        styles.set_theme('graphite')


def test_mail_card_uses_active_theme_tokens(qtbot):
    try:
        for name in THEME_NAMES:
            styles.set_theme(name)
            t = styles.theme()
            card = MailCard("subj", "body", "10:00")
            qtbot.addWidget(card)

            card_style = card.card.styleSheet()
            assert t['mailBorder'] in card_style
            for other_value in _other_theme_tokens(name, 'mailBorder'):
                assert other_value not in card_style

            subject_label = next(l for l in card.findChildren(QLabel) if l.text() == "subj")
            subject_style = subject_label.styleSheet()
            assert t['accent'] in subject_style
            for other_value in _other_theme_tokens(name, 'accent'):
                assert other_value not in subject_style
    finally:
        styles.set_theme('graphite')


def test_contact_item_uses_active_theme_tokens(qtbot):
    try:
        for name in THEME_NAMES:
            styles.set_theme(name)
            t = styles.theme()
            item = ContactItem("TestUser", unread_count=3)
            qtbot.addWidget(item)

            avatar_style = item.avatar_label.styleSheet()
            assert t['accentSoft'] in avatar_style
            for other_value in _other_theme_tokens(name, 'accentSoft'):
                assert other_value not in avatar_style

            badge_style = item.unread_label.styleSheet()
            assert t['accent'] in badge_style
            for other_value in _other_theme_tokens(name, 'accent'):
                assert other_value not in badge_style
    finally:
        styles.set_theme('graphite')


def test_empty_chat_placeholder_shows_expected_copy(qtbot):
    placeholder = EmptyChatPlaceholder()
    qtbot.addWidget(placeholder)
    assert "選一個對話" in placeholder.title_label.text()
    assert placeholder.subtitle_label.textFormat() == Qt.PlainText


def test_empty_sidebar_placeholder_shows_expected_copy(qtbot):
    placeholder = EmptySidebarPlaceholder()
    qtbot.addWidget(placeholder)
    assert "還沒有對話" in placeholder.title_label.text()
    assert placeholder.subtitle_label.textFormat() == Qt.PlainText


def test_empty_state_widgets_all_themes_no_exception(qtbot):
    """空狀態元件與 spinner 在三套主題下建構/換色都不得丟例外，且顏色跟著當前主題。"""
    try:
        for name in THEME_NAMES:
            styles.set_theme(name)
            t = styles.theme()

            chat_placeholder = EmptyChatPlaceholder()
            qtbot.addWidget(chat_placeholder)
            assert t['accent'] in chat_placeholder.logo_label.styleSheet()

            sidebar_placeholder = EmptySidebarPlaceholder()
            qtbot.addWidget(sidebar_placeholder)
            assert t['border'] in sidebar_placeholder.icon_label.styleSheet()

            spinner = SyncSpinner()
            qtbot.addWidget(spinner)
            spinner.start()
            spinner._tick()
            spinner.grab()  # 強制觸發一次 paintEvent，確認畫弧線不丟例外
            spinner.stop()
    finally:
        styles.set_theme('graphite')
