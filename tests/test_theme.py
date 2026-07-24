import os
from src.uPtt.ui import theme


def test_render_svg_renders_valid_svg(qapp, tmp_path):
    svg_path = tmp_path / "test.svg"
    svg_path.write_text('<svg width="10" height="10"><rect width="10" height="10" /></svg>')
    pixmap = theme.render_svg(str(svg_path), 10, 10)
    assert not pixmap.isNull()


def test_render_svg_invalid_path_returns_null_pixmap():
    pixmap = theme.render_svg("/no/such/file.svg", 10, 10)
    assert pixmap.isNull()


def test_screens_reexports_same_render_svg():
    from src.uPtt.ui import screens
    assert screens.render_svg is theme.render_svg
    assert screens.ASSETS_DIR == theme.ASSETS_DIR


def test_mute_icon_asset_exists():
    assert os.path.exists(os.path.join(theme.ASSETS_DIR, "icon_mute.svg"))
