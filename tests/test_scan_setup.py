from PySide6.QtCore import Qt

from src.uPtt.ui.screens import ScanSetupScreen


def test_defaults_to_scan_step(qtbot):
    s = ScanSetupScreen()
    qtbot.addWidget(s)
    assert s._steps.currentIndex() == 1  # 掃描設定步（非歡迎）


def test_show_welcome_switches_to_welcome_step(qtbot):
    s = ScanSetupScreen()
    qtbot.addWidget(s)
    s.show_welcome()
    assert s._steps.currentIndex() == 0


def test_welcome_button_advances_to_scan(qtbot):
    s = ScanSetupScreen()
    qtbot.addWidget(s)
    s.show_welcome()
    qtbot.mouseClick(s.welcome_btn, Qt.LeftButton)
    assert s._steps.currentIndex() == 1


def test_reset_returns_to_scan_step(qtbot):
    """重新掃描/reset 一律回到掃描步，不顯示歡迎（回訪流程不受 onboarding 影響）。"""
    s = ScanSetupScreen()
    qtbot.addWidget(s)
    s.show_welcome()
    s.reset()
    assert s._steps.currentIndex() == 1
    # 用 isHidden()（元件自身的顯隱旗標）而非 isVisible()（受祖先是否顯示影響；
    # 測試未 show() 頂層畫面，isVisible 恆 False）。
    assert s.options_widget.isHidden() is False
    assert s.progress_widget.isHidden() is True


def test_external_interface_preserved(qtbot):
    """對外介面不變：選天數 emit scan_days_selected 並顯示進度。"""
    s = ScanSetupScreen()
    qtbot.addWidget(s)
    with qtbot.waitSignal(s.scan_days_selected) as blocker:
        s._start_scan(7)
    assert blocker.args == [7]
    assert s.progress_widget.isHidden() is False
    assert s.options_widget.isHidden() is True


def test_skip_emits_scan_skipped(qtbot):
    s = ScanSetupScreen()
    qtbot.addWidget(s)
    with qtbot.waitSignal(s.scan_skipped):
        qtbot.mouseClick(s.skip_btn, Qt.LeftButton)
