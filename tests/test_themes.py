"""Phase 1 主題骨幹的最小自我檢查。純 assert，不用 fixture/框架。"""
from uPtt.ui import styles
from uPtt.ui.widgets import ContactItem


def test_themes_keys():
    assert set(styles.THEMES) == {'graphite', 'bone', 'mono'}


def test_build_style_has_no_leftover_placeholders_or_old_dark_hex():
    for name in styles.THEMES:
        styles.set_theme(name)
        s = styles.build_style()
        assert '%(' not in s  # 沒有殘留未替換的 template 佔位符
        if name != 'graphite':
            # bone/mono 不應殘留 graphite 的舊寫死暗色色碼
            assert '#0D1117' not in s
            assert '#21262D' not in s


def test_theme_getter_and_fallback():
    styles.set_theme('bone')
    assert styles.theme()['id'] == 'bone'

    styles.set_theme('does-not-exist')
    assert styles.theme()['id'] == styles.DEFAULT_THEME == 'graphite'


def test_set_theme_affects_actual_widget(qtbot):
    """驗證 styles module 已統一為單一實例：set_theme() 之後，實際建立出來的
    widget 必須讀到相同的 active theme，不能有另一份互不相通的 module 狀態。"""
    original = styles.theme().get('id')
    try:
        styles.set_theme('bone')
        t = styles.THEMES['bone']

        item = ContactItem("TestUser", unread_count=1)
        qtbot.addWidget(item)

        assert t['accentSoft'] in item.avatar_label.styleSheet()
    finally:
        styles.set_theme(original)


def test_warn_token_distinct_from_online_and_danger():
    """warn（重連中）必須與 online（已連線）、danger 分得開，否則使用者無法靠顏色辨識狀態。"""
    for t in styles.THEMES.values():
        assert t['warn'] != t['online']
        assert t['warn'] != t['danger']


def test_warn_token_distinct_from_all_status_colors():
    """warn 除了要與 online/danger 分開，也不能與 muted（次要文字）、faint（更弱化的文字）
    同色——否則連線重連中的警示狀態點會被誤讀成一般弱化文字。mono 主題刻意零彩度，
    只能靠明度區隔，最容易撞色，需要獨立驗證五者互不相同。"""
    for t in styles.THEMES.values():
        assert len({t['warn'], t['muted'], t['faint'], t['online'], t['danger']}) == 5
