# --- uPtt UI 色票 / 字型 token（單一色源）+ 主題切換引擎 ---
#
# 三組主題 Graphite / Bone / Mono，key 完全一致。所有畫面的顏色都應該從
# `active()` 取值，不要在各處硬寫 hex。

import os
import sys
import weakref

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


# 資源目錄定義（相容 PyInstaller 與 Nuitka；ui/ 目錄下與 screens.py 同層，故路徑計算一致）
if hasattr(sys, '_MEIPASS'):
    ASSETS_DIR = os.path.join(sys._MEIPASS, "uPtt", "ui", "assets")
else:
    ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")


def render_svg(path: str, width: int, height: int, dpr: float = 1.0) -> QPixmap:
    """高畫質渲染 SVG 檔案到 QPixmap (支援 High-DPI)"""
    renderer = QSvgRenderer(path)
    if not renderer.isValid():
        return QPixmap()

    pixmap = QPixmap(int(width * dpr), int(height * dpr))
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()

    pixmap.setDevicePixelRatio(dpr)
    return pixmap


# 字型堆疊（等寬 + CJK fallback）。styles.py 全域與 widgets.py 的 MailCard 都引用這一份。
FONT_STACK = (
    '"JetBrains Mono", "Cascadia Code", "SF Mono", "Menlo", "Consolas", '
    '"DejaVu Sans Mono", "PingFang TC", "Microsoft JhengHei", monospace'
)


# Graphite：冷中性近黑底 + 鼠尾草綠強調。key 即語意 token 名。
GRAPHITE = {
    # 底色（冷中性，由深到淺）
    "bg": "#0E1114",           # app 背景 / 聊天區 / 輸入框
    "surface": "#15191E",      # 側邊欄 / 標題列 / 選單 / 卡片
    "surface_hover": "#181D23",  # 清單項 hover 態
    "surface_2": "#1A1F25",    # 選取態 / 次要按鈕 / 對方氣泡

    # 邊框（低不透明白，對齊截圖細框感）
    "border": "rgba(255, 255, 255, 0.09)",
    "border_strong": "rgba(255, 255, 255, 0.14)",

    # 文字（冷白 → 弱 → 極弱）
    "text": "#E6EAEF",
    "text_muted": "#6E7682",
    "text_faint": "#444B55",

    # 強調（鼠尾草綠，取代舊版 sage accent）
    "accent": "#8FBFA0",         # 強調文字 / 邊框 / 焦點
    "accent_hover": "#2F6B47",   # hover / pressed 深綠
    "accent_bg": "#1E2A24",      # 綠調表層：填色按鈕 / 本人氣泡底
    "accent_bg_hover": "#26362E",  # 上者 hover
    "accent_tint_hover": "#C5DDD4",  # 淺色強調 hover（淺底文字用）

    # 危險 / 錯誤語意
    "danger": "#E08070",
    "danger_strong": "#B33A20",

    # 狀態語意（線上/未知/連線中 dot、待送訊息、封存文字）
    # status_offline 不獨立設 key，沿用 text_faint。
    "status_online": "#56D364",
    "status_unknown": "#7D8590",
    "status_connecting": "#D29922",
    "msg_pending": "#5C6773",
    "archived_text": "#6E4040",
}


# Bone：淺色主題（冷灰白）。base token 取自設計畫布 window.THEMES ground-truth；
# 畫布未定義的語意/hover token（原為 None）依 base 推導，另註於行末。
BONE = {
    "bg": "#F3F5F5",           # canvas
    "surface": "#EAECEE",      # canvas
    "surface_hover": "#E1E4E6",  # 推導：surface 略暗（清單 hover）
    "surface_2": "#FFFFFF",    # canvas（elevated 白）

    "border": "rgba(20, 23, 27, 0.14)",         # canvas
    "border_strong": "rgba(20, 23, 27, 0.18)",  # canvas（mailBorder 最強）

    "text": "#14171B",         # canvas
    "text_muted": "#5C6470",   # canvas
    "text_faint": "#9098A4",   # canvas

    "accent": "#2F6B47",       # canvas（deep forest）
    "accent_hover": "#275A3B",   # 推導：accent 加深
    "accent_bg": "#D6E2DA",    # canvas
    "accent_bg_hover": "#C6D7CD",  # 推導：accent_bg 加深
    "accent_tint_hover": "#E1EBE5",  # 推導：淺綠 tint（引用 hover）

    "danger": "#B33A20",       # canvas（failed banner, light mode）
    "danger_strong": "#8C2C16",  # 推導：danger 加深

    "status_online": "#2F6B47",   # canvas：online == accent（畫布無獨立亮綠）
    "status_unknown": "#9098A4",  # 推導：== text_faint 灰
    "status_connecting": "#9A6700",  # beta 分支 warn 權威值（淺底暖金）
    "msg_pending": "#5C6470",  # canvas：送出中 == muted
    "archived_text": "#9E5C4C",  # 推導：淺底暗紅（封存/不存在）
}


# Mono：純灰階淺色主題（白底、黑字、近黑 accent）。base 取自畫布 ground-truth；
# 缺的 token 依 base 推導。★標記處為刻意偏離畫布的判斷，可依喜好改。
MONO = {
    "bg": "#F7F7F7",           # canvas
    "surface": "#EFEFEF",      # canvas
    "surface_hover": "#E7E7E7",  # 推導
    "surface_2": "#FFFFFF",    # canvas

    "border": "rgba(0, 0, 0, 0.16)",         # canvas
    "border_strong": "rgba(0, 0, 0, 0.20)",  # canvas

    "text": "#0A0A0A",         # canvas
    "text_muted": "#6A6A6A",   # canvas
    "text_faint": "#A8A8A8",   # canvas

    "accent": "#0A0A0A",       # canvas（近黑，零彩度）
    "accent_hover": "#2E2E2E",   # 推導
    "accent_bg": "#E4E4E4",    # canvas
    "accent_bg_hover": "#D7D7D7",  # 推導
    "accent_tint_hover": "#DEDEDE",  # 推導

    "danger": "#B33A20",       # canvas（唯一暖色）★純黑白可改灰
    "danger_strong": "#8C2C16",  # 推導

    "status_online": "#0A0A0A",   # canvas：online == accent == 黑
    "status_unknown": "#A8A8A8",  # 推導：灰
    "status_connecting": "#8A8A8A",  # beta 分支 warn 權威值（灰階）
    "msg_pending": "#6A6A6A",  # canvas：送出中 == muted
    "archived_text": "#8A8A8A",  # 推導：灰階
}


# --- 主題切換引擎 ---

THEMES = {"graphite": GRAPHITE, "bone": BONE, "mono": MONO}

_current = "graphite"

# 重套色註冊表：list of (weakref.ref(widget), fn)
_restyles = []


def active():
    """回傳當前主題的 token dict。"""
    return THEMES[_current]


def current_theme():
    """回傳當前主題名稱（供持久化 / UI 反映）。"""
    return _current


def set_theme(name):
    """設定當前主題。name 不在 THEMES 內時 raise ValueError。"""
    global _current
    if name not in THEMES:
        raise ValueError(f"unknown theme: {name!r}")
    _current = name


def register_restyle(widget, fn):
    """登記一個重套色函式：立即套用一次，並以 weakref 追蹤 widget。

    apply_theme() 之後會對所有存活的 widget 重新呼叫 fn(widget)。
    """
    fn(widget)
    _restyles.append((weakref.ref(widget), fn))


def apply_theme(name):
    """切換主題，並對所有已登記且存活的 widget 重新套色。

    已死亡的 weakref、或 fn 呼叫時因 widget 的 C++ 端已刪除而丟出
    RuntimeError 的項目，會從 _restyles 中剪除。
    """
    set_theme(name)

    dead = []
    for entry in _restyles:
        ref, fn = entry
        w = ref()
        if w is None:
            dead.append(entry)
            continue
        try:
            fn(w)
        except RuntimeError:
            dead.append(entry)

    for entry in dead:
        _restyles.remove(entry)


if __name__ == "__main__":
    # self-check：切換主題、還原、三 palette key 對齊、apply_theme 對死 widget 不炸。
    assert active() is GRAPHITE, "預設主題應為 graphite"

    set_theme("bone")
    assert active() is BONE, "set_theme('bone') 後 active() 應為 BONE"
    set_theme("graphite")
    assert active() is GRAPHITE, "set_theme('graphite') 應復原"

    assert set(GRAPHITE.keys()) == set(BONE.keys()) == set(MONO.keys()), (
        "三個 palette 的 key 必須完全一致"
    )

    class _FakeWidget:
        """假 widget：fn 呼叫時模擬 C++ 端已刪除，丟出 RuntimeError。"""

    def _boom(w):
        raise RuntimeError("wrapped C/C++ object has been deleted")

    fake = _FakeWidget()
    register_restyle(fake, lambda w: None)  # 先用 no-op 登記，確保能進 _restyles
    before = len(_restyles)
    # 手動替換成會炸的 fn，模擬 apply_theme 走到它時 widget 已被刪
    _restyles[-1] = (weakref.ref(fake), _boom)
    apply_theme("mono")
    assert len(_restyles) == before - 1, "fn 丟 RuntimeError 的項目應被剪除"

    set_theme("graphite")

    print("theme.py self-check passed.")
