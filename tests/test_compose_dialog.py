import pytest

from src.uPtt.ui.compose_dialog import ComposeDialog


def test_validate_states(qtbot):
    d = ComposeDialog(account_id="alice")
    qtbot.addWidget(d)

    assert d.validate("", "hi") == (False, "")
    ok, msg = d.validate("alice", "hi")        # 寄給自己
    assert ok is False and "自己" in msg
    ok, msg = d.validate("1bad", "hi")         # 格式錯
    assert ok is False and "格式" in msg
    ok, msg = d.validate("bob", "   ")         # 內文空白
    assert ok is False and "內文" in msg
    ok, _ = d.validate("bob", "hello")         # 有效
    assert ok is True


def test_submit_emits_only_when_valid(qtbot):
    d = ComposeDialog(account_id="alice")
    qtbot.addWidget(d)

    d.recipient.setText("1bad")
    d.body.setPlainText("hi")
    got = []
    d.send_requested.connect(lambda *a: got.append(a))
    d._submit()
    assert got == []

    d.recipient.setText("  Bob  ")
    d.subject.setText(" 標題 ")
    d.body.setPlainText("內文內容")
    with qtbot.waitSignal(d.send_requested) as blocker:
        d._submit()
    assert blocker.args == ["Bob", "標題", "內文內容"]


def test_set_result_success_closes(qtbot):
    d = ComposeDialog(account_id="alice")
    qtbot.addWidget(d)
    d.show()
    d.set_result(True, "")
    assert d.isVisible() is False


def test_set_result_failure_shows_message(qtbot):
    d = ComposeDialog(account_id="alice")
    qtbot.addWidget(d)
    d.recipient.setText("bob")
    d.body.setPlainText("hi")
    d._submit()                         # 進 busy、status = 寄送中…
    d.set_result(False, "發送失敗，請稍後再試")
    assert "發送失敗" in d.status.text()
    assert d.send_btn.isEnabled() is True   # 失敗後可重試
