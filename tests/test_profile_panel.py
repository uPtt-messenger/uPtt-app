from src.uPtt.ui.profile_panel import ProfilePanel, profile_rows


def test_profile_rows_always_shows_core_fields():
    rows = profile_rows({"ptt_id": "Alice", "nickname": "小明", "is_online": True})
    d = dict(rows)
    assert d["ID"] == "Alice"
    assert d["暱稱"] == "小明"
    assert d["狀態"] == "在線"


def test_profile_rows_offline_and_missing_fallbacks():
    rows = profile_rows({"is_online": False})
    d = dict(rows)
    assert d["狀態"] == "離線"
    assert d["ID"] == "—"       # 缺 ID 以破折號代替
    assert d["暱稱"] == "—"


def test_profile_rows_optional_only_when_present():
    rows = profile_rows({
        "ptt_id": "Alice", "nickname": "小明", "is_online": True,
        "login_count": "123", "money": "", "last_login_date": "07/24/2026",
        "activity": "", "legal_post": "50",
    })
    d = dict(rows)
    assert d["登入次數"] == "123"
    assert d["最後登入"] == "07/24/2026"
    assert d["文章數"] == "50"
    assert "P 幣" not in d      # 空字串不列
    assert "動態" not in d


def test_profile_panel_set_info_populates_grid(qtbot):
    p = ProfilePanel()
    qtbot.addWidget(p)
    p.set_info({"ptt_id": "Alice", "nickname": "小明", "is_online": True, "money": "999"})
    # grid 至少含核心 3 列 + money 列 = 4 列 × 2 欄 = 8 個 widget
    assert p._grid.count() >= 8


def test_profile_panel_loading_then_info(qtbot):
    p = ProfilePanel()
    qtbot.addWidget(p)
    p.set_loading()
    assert p._grid.count() == 1  # 只有「查詢中…」
    p.set_info({"ptt_id": "Bob", "nickname": "", "is_online": False})
    assert p._grid.count() >= 6  # 核心 3 列 × 2 欄
