import pytest
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock
from PySide6.QtCore import Qt

from src.uPtt import config
from src.uPtt.db import DatabaseManager
from src.uPtt.ptt import UPttService
from src.uPtt.worker import PTTWorker
from src.uPtt.ui.settings import SettingsWindow, ToggleSwitch, ThemeCard

# settings.py 內部一律用不帶 "src." 前綴的絕對匯入（`from uPtt.ui import theme`，與
# screens.py/worker.py 既有慣例一致）。pytest.ini 的 `pythonpath = . src` 讓
# `uPtt.*` 與 `src.uPtt.*` 各自成為獨立的 sys.modules 項目、各自持有一份
# theme._current；要觀察 SettingsWindow 對全域主題狀態的改動，必須用它實際
# 匯入的同一份模組，否則會讀到另一份從未被改動過的 theme 模組。
from uPtt.ui import theme


@pytest.fixture(autouse=True)
def reset_theme():
    """settings.py 的 ThemeCard 點擊會改動全域主題狀態，測試前後都要還原，
    避免污染同一 pytest session 內其他測試檔的主題假設（預設 graphite）。"""
    theme.set_theme("graphite")
    yield
    theme.set_theme("graphite")


@pytest.fixture
def db_mock():
    db = MagicMock()
    db.get_config.return_value = None
    return db


@pytest.fixture
def db_manager(tmp_path):
    db_file = tmp_path / "test_settings.db"
    return DatabaseManager(str(db_file))


# --- ToggleSwitch ---

def test_toggle_switch_default_unchecked(qtbot):
    toggle = ToggleSwitch()
    qtbot.addWidget(toggle)
    assert toggle.isChecked() is False


def test_toggle_switch_checked_state_toggles(qtbot):
    toggle = ToggleSwitch()
    qtbot.addWidget(toggle)
    toggle.setChecked(True)
    assert toggle.isChecked() is True


# --- ThemeCard ---

def test_theme_card_click_emits_theme_id(qtbot):
    card = ThemeCard("bone", theme.THEMES["bone"])
    qtbot.addWidget(card)
    with qtbot.waitSignal(card.clicked) as blocker:
        qtbot.mouseClick(card, Qt.LeftButton)
    assert blocker.args == ["bone"]


def test_theme_card_set_selected_updates_flag(qtbot):
    card = ThemeCard("mono", theme.THEMES["mono"])
    qtbot.addWidget(card)
    assert card._selected is False
    card.set_selected(True)
    assert card._selected is True


# --- SettingsWindow: 建構不炸 ---

def test_settings_window_builds_without_crash(qtbot, db_mock):
    win = SettingsWindow(db_mock)
    qtbot.addWidget(win)
    assert win.windowTitle() == "設定"
    assert set(win._theme_cards.keys()) == set(theme.THEMES.keys())


def test_settings_window_initial_theme_selection_reflects_db(qtbot, db_mock):
    db_mock.get_config.side_effect = lambda key, default=None: (
        "bone" if key == config.SETTING_THEME else default
    )
    win = SettingsWindow(db_mock)
    qtbot.addWidget(win)
    assert win._selected_theme == "bone"
    assert win._theme_cards["bone"]._selected is True
    assert win._theme_cards["graphite"]._selected is False


# --- 主題卡點擊：套用主題 + 落 DB ---

def test_click_theme_card_applies_and_persists_theme(qtbot, db_mock):
    win = SettingsWindow(db_mock)
    qtbot.addWidget(win)

    qtbot.mouseClick(win._theme_cards["mono"], Qt.LeftButton)

    assert theme.current_theme() == "mono"
    db_mock.set_config.assert_any_call(config.SETTING_THEME, "mono")
    assert win._theme_cards["mono"]._selected is True
    assert win._theme_cards["graphite"]._selected is False


# --- 桌面通知開關：落 DB ---

def test_notify_toggle_writes_db(qtbot, db_mock):
    """db_mock.get_config 預設回傳 None → 初始 bool(None)=False，與 ToggleSwitch
    的預設未勾選狀態相同（不觸發 toggled）；因此先切到 True 才會是第一次真正的變更。"""
    win = SettingsWindow(db_mock)
    qtbot.addWidget(win)

    win.notify_toggle.setChecked(True)
    db_mock.set_config.assert_any_call(config.SETTING_NOTIFY_ENABLED, True)

    win.notify_toggle.setChecked(False)
    db_mock.set_config.assert_any_call(config.SETTING_NOTIFY_ENABLED, False)


# --- 輪詢間隔 spinbox：落 DB ---

def test_mail_interval_spin_writes_db(qtbot, db_mock):
    win = SettingsWindow(db_mock)
    qtbot.addWidget(win)

    win.mail_spin.setValue(42)
    db_mock.set_config.assert_any_call(config.SETTING_MAIL_INTERVAL, 42)


def test_waterball_interval_spin_writes_db(qtbot, db_mock):
    win = SettingsWindow(db_mock)
    qtbot.addWidget(win)

    win.waterball_spin.setValue(15)
    db_mock.set_config.assert_any_call(config.SETTING_WATERBALL_INTERVAL, 15)


def test_online_interval_spin_writes_db(qtbot, db_mock):
    win = SettingsWindow(db_mock)
    qtbot.addWidget(win)

    win.online_spin.setValue(60)
    db_mock.set_config.assert_any_call(config.SETTING_ONLINE_INTERVAL, 60)


def test_mail_interval_spin_clamps_below_minimum(qtbot, db_mock):
    """QSpinBox 本身的 range 下限已避免 UI 選到低於 min 的值，但 setValue()
    仍會被 Qt 夾到 range 內；額外驗證寫入 DB 的值不會低於 MAIL_INTERVAL_MIN。"""
    win = SettingsWindow(db_mock)
    qtbot.addWidget(win)

    win.mail_spin.setValue(0)  # QSpinBox.setRange(min, 3600) 會自動夾到 min
    assert win.mail_spin.value() == config.MAIL_INTERVAL_MIN
    db_mock.set_config.assert_any_call(config.SETTING_MAIL_INTERVAL, config.MAIL_INTERVAL_MIN)


# --- 整合：spinbox 變更即時套用到真正的 PTTWorker（跨執行緒 invoke）---

def test_mail_interval_change_applies_to_running_worker(qtbot, db_manager):
    ptt_service_mock = MagicMock(spec=UPttService)
    ptt_service_mock.ptt_id = "TestUser"
    worker = PTTWorker(ptt_service_mock, db_manager)
    worker.start_polling()

    win = SettingsWindow(db_manager, worker=worker)
    qtbot.addWidget(win)

    win.mail_spin.setValue(33)

    qtbot.waitUntil(lambda: worker.polling_timer.interval() == 33000, timeout=2000)
    assert db_manager.get_config(config.SETTING_MAIL_INTERVAL) == 33
