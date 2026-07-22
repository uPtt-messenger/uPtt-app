# --- uPtt UI 色票 / 字型 token（單一色源）---
#
# 目前只有 Graphite 一組深色主題（sage green 強調）。所有畫面的顏色都應該
# 從這裡取值，不要在各處硬寫 hex。
#
# ponytail: 刻意只做「一組 token + 字型字串」，不做主題切換引擎、不做 class
# 抽象、不做 registry。未來要加 Bone / Mono 就多一個同 key 的 dict，再挑一個
# 切換點決定用哪個——切換那步等真的要做再做，先不預留。


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

    # 危險 / 錯誤語意
    "danger": "#E08070",
    "danger_strong": "#B33A20",
}
