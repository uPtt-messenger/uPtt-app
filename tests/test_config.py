import pytest

from src.uPtt import config
from src.uPtt.db import DatabaseManager


@pytest.fixture
def db_manager(tmp_path):
    db_file = tmp_path / "test_uptt_config.db"
    return DatabaseManager(str(db_file))


# --- clamp_interval ---

def test_clamp_interval_above_minimum_unchanged():
    assert config.clamp_interval(30, 3) == 30


def test_clamp_interval_below_minimum_clamped():
    assert config.clamp_interval(1, 3) == 3


def test_clamp_interval_equal_to_minimum():
    assert config.clamp_interval(3, 3) == 3


def test_clamp_interval_non_numeric_falls_back_to_minimum():
    assert config.clamp_interval("not-a-number", 5) == 5
    assert config.clamp_interval(None, 5) == 5


def test_clamp_interval_coerces_numeric_strings():
    assert config.clamp_interval("42", 3) == 42


# --- get_setting_interval ---

def test_get_setting_interval_no_setting_returns_default(db_manager):
    """DB 無設定時應 fallback 到 default，並仍套用 minimum 夾值。"""
    value = config.get_setting_interval(
        db_manager, config.SETTING_MAIL_INTERVAL, config.CHECK_PTT_MAIL_INTERVAL, config.MAIL_INTERVAL_MIN)
    assert value == max(config.CHECK_PTT_MAIL_INTERVAL, config.MAIL_INTERVAL_MIN)


def test_get_setting_interval_reads_saved_value(db_manager):
    db_manager.set_config(config.SETTING_MAIL_INTERVAL, 15)
    value = config.get_setting_interval(
        db_manager, config.SETTING_MAIL_INTERVAL, config.CHECK_PTT_MAIL_INTERVAL, config.MAIL_INTERVAL_MIN)
    assert value == 15


def test_get_setting_interval_clamps_saved_value_below_minimum(db_manager):
    db_manager.set_config(config.SETTING_ONLINE_INTERVAL, 1)
    value = config.get_setting_interval(
        db_manager, config.SETTING_ONLINE_INTERVAL, config.CHECK_ONLINE_STATUS_INTERVAL, config.ONLINE_INTERVAL_MIN)
    assert value == config.ONLINE_INTERVAL_MIN


# --- 設定持久化 round-trip（每個 SETTING_* key）---

def test_setting_theme_round_trip(db_manager):
    db_manager.set_config(config.SETTING_THEME, "mono")
    assert db_manager.get_config(config.SETTING_THEME) == "mono"


def test_setting_notify_enabled_round_trip(db_manager):
    db_manager.set_config(config.SETTING_NOTIFY_ENABLED, False)
    assert db_manager.get_config(config.SETTING_NOTIFY_ENABLED, True) is False

    db_manager.set_config(config.SETTING_NOTIFY_ENABLED, True)
    assert db_manager.get_config(config.SETTING_NOTIFY_ENABLED, False) is True


def test_setting_interval_keys_round_trip(db_manager):
    for key in (
        config.SETTING_MAIL_INTERVAL,
        config.SETTING_WATERBALL_INTERVAL,
        config.SETTING_ONLINE_INTERVAL,
    ):
        db_manager.set_config(key, 77)
        assert db_manager.get_config(key) == 77
