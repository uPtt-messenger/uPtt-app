import pytest

from src.uPtt.ui.new_chat_modal import NewChatModal, is_valid_ptt_id


@pytest.mark.parametrize("text,ok", [
    ("bob", True),
    ("Ab12", True),
    ("a" * 12, True),
    ("", False),
    ("  ", False),
    ("1bob", False),         # 不可數字開頭
    ("a", False),            # 太短（<2）
    ("a" * 13, False),       # 太長（>12）
    ("bad-id", False),       # 含非字母數字
    ("has space", False),
])
def test_is_valid_ptt_id(text, ok):
    assert is_valid_ptt_id(text) is ok


def test_validate_states(qtbot):
    m = NewChatModal(account_id="alice")
    qtbot.addWidget(m)

    assert m.validate("") == (False, "")
    ok, msg = m.validate("alice")          # 自己
    assert ok is False and "自己" in msg
    ok, msg = m.validate("1bad")           # 格式錯
    assert ok is False and "格式" in msg
    ok, msg = m.validate("bob")            # 有效
    assert ok is True


def test_submit_emits_only_when_valid(qtbot):
    m = NewChatModal(account_id="alice")
    qtbot.addWidget(m)

    # 無效輸入不 emit
    m.input.setText("1bad")
    got = []
    m.chat_requested.connect(got.append)
    m._submit()
    assert got == []

    # 有效輸入 emit 並帶原始（strip 後）字串
    m.input.setText("  Bob  ")
    with qtbot.waitSignal(m.chat_requested) as blocker:
        m._submit()
    assert blocker.args == ["Bob"]


def test_start_button_enabled_tracks_validity(qtbot):
    m = NewChatModal(account_id="alice")
    qtbot.addWidget(m)

    m.input.setText("bob")
    assert m.start_btn.isEnabled() is True
    m.input.setText("alice")   # 自己
    assert m.start_btn.isEnabled() is False
    m.input.setText("")
    assert m.start_btn.isEnabled() is False
