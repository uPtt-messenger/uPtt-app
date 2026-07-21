import os
import sys
from typing import Optional

from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from uPtt.ui import styles

# 資源目錄定義 (相容 PyInstaller 與 Nuitka)
if hasattr(sys, '_MEIPASS'):
    # PyInstaller 執行環境
    ASSETS_DIR = os.path.join(sys._MEIPASS, "uPtt", "ui", "assets")
elif 'nuitka' in sys.modules:
    # Nuitka 執行環境 (通常 __file__ 會指向 .app 內部的正確位置)
    # 這裡使用 os.path.dirname(__file__) 通常就能在 Nuitka 編譯後找到 assets
    ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
else:
    # 一般開發環境
    ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")


def render_svg(path: str, width: int, height: int, dpr: float = 1.0,
                theme_tokens: Optional[dict] = None) -> QPixmap:
    """高畫質渲染 SVG 檔案到 QPixmap (支援 High-DPI)。

    SVG 檔案內容以 `{token}` 佔位符寫死語意顏色（見 ui/assets/*.svg），這裡讀檔後用
    theme_tokens（預設目前 active theme，見 styles.theme()）字串替換再交給
    QSvgRenderer，藉此讓圖示跟著主題著色。若 SVG 內沒有任何佔位符（例如測試用的純
    SVG），.format() 為 no-op，行為與純檔案路徑渲染相同。
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            svg_text = f.read()
    except OSError:
        return QPixmap()

    tokens = theme_tokens if theme_tokens is not None else styles.theme()
    try:
        svg_text = svg_text.format(**tokens)
    except (KeyError, IndexError, ValueError):
        # SVG 含未知/格式錯誤的佔位符時保留原始文字，退回未著色渲染而非整個失敗
        pass

    renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
    if not renderer.isValid():
        return QPixmap()

    # 根據 DPR 放大實際像素大小
    pixmap = QPixmap(int(width * dpr), int(height * dpr))
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    # 開啟抗鋸齒與高品質渲染
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()

    # 設定邏輯大小，以便在 Qt 佈局中正確顯示
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


def render_themed_icon(filename: str, size: int = 128,
                        theme_tokens: Optional[dict] = None) -> QIcon:
    """依主題著色渲染 assets 內的 SVG 為 QIcon，取代未著色的 `QIcon(path)` 寫法。

    theme_tokens 省略時使用目前 active theme；系統匣圖示刻意固定傳入 graphite 深色調
    （見 MainWindow.init_tray 呼叫端註解），不隨 App 主題切換。
    """
    path = os.path.join(ASSETS_DIR, filename)
    if not os.path.exists(path):
        return QIcon()
    pixmap = render_svg(path, size, size, 1.0, theme_tokens=theme_tokens)
    return QIcon(pixmap) if not pixmap.isNull() else QIcon()
