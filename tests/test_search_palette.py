import pytest
from unittest.mock import MagicMock

from src.uPtt.ui.search_palette import SearchPalette, _preview
from src.uPtt.utils import encode_reply


@pytest.fixture
def db_mock():
    db = MagicMock()
    db.search_messages.return_value = []
    return db


def _make_palette(db, contacts):
    return SearchPalette(db, account_id="alice", contacts_provider=lambda: contacts)


def test_preview_truncates_long_content():
    long = "字" * 100
    out = _preview(long)
    assert out.endswith("…")
    assert len(out) <= 49  # _PREVIEW_MAX(48) + 省略號


def test_preview_strips_reply_wrapper():
    wrapped = encode_reply("bob", "原始被回覆的訊息", "我的回覆內容")
    out = _preview(wrapped)
    # 回覆包裝（[re:@bob|...]）應被剝除，只留實際回覆文字。
    assert "我的回覆內容" in out
    assert "[re:" not in out


def test_compute_results_empty_query_returns_empty(qtbot, db_mock):
    p = _make_palette(db_mock, [])
    qtbot.addWidget(p)
    assert p.compute_results("") == []
    assert p.compute_results("   ") == []
    db_mock.search_messages.assert_not_called()


def test_compute_results_matches_contact_by_id_nick_custom(qtbot, db_mock):
    contacts = [
        {"ptt_id": "bob", "ptt_id_display": "Bob", "nickname": "小明", "custom_name": ""},
        {"ptt_id": "carol", "ptt_id_display": "Carol", "nickname": "", "custom_name": "老王"},
        {"ptt_id": "dave", "ptt_id_display": "Dave", "nickname": "", "custom_name": ""},
    ]
    p = _make_palette(db_mock, contacts)
    qtbot.addWidget(p)

    # 依 ptt_id（大小寫不敏感）
    r = p.compute_results("BOB")
    assert [x["session_id"] for x in r if x["kind"] == "contact"] == ["bob"]
    # 依 nickname
    assert any(x["session_id"] == "bob" for x in p.compute_results("小明"))
    # 依 custom_name
    assert any(x["session_id"] == "carol" for x in p.compute_results("老王"))
    # 無命中
    assert p.compute_results("zzz") == []


def test_compute_results_contacts_before_messages(qtbot, db_mock):
    contacts = [{"ptt_id": "bob", "ptt_id_display": "Bob", "nickname": "hello", "custom_name": ""}]
    db_mock.search_messages.return_value = [
        {"id": 1, "session_id": "carol", "sender_id": "carol", "content": "hello world",
         "timestamp": "2026-01-01T12:00:00", "mail_type": "uptt"},
    ]
    p = _make_palette(db_mock, contacts)
    qtbot.addWidget(p)

    r = p.compute_results("hello")
    kinds = [x["kind"] for x in r]
    assert kinds == ["contact", "message"]  # 聯絡人排在訊息前
    assert r[1]["session_id"] == "carol"
    db_mock.search_messages.assert_called_once_with("alice", "hello", limit=50)


def test_selecting_result_emits_session_and_closes(qtbot, db_mock):
    db_mock.search_messages.return_value = [
        {"id": 1, "session_id": "carol", "sender_id": "carol", "content": "hi there",
         "timestamp": "2026-01-01T12:00:00", "mail_type": "uptt"},
    ]
    p = _make_palette(db_mock, [])
    qtbot.addWidget(p)
    p.input.setText("hi")
    p._run_search()
    assert p.results.count() == 1

    with qtbot.waitSignal(p.session_selected) as blocker:
        p._on_item_chosen(p.results.item(0))
    assert blocker.args == ["carol"]
