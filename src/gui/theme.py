"""
UI design tokens — colours, fonts, and layout constants.
All GUI components import from here so visual changes are made in one place.
"""

PALETTE = dict(
    bg_dark      = "#0F0F13",
    bg_mid       = "#16161D",
    bg_panel     = "#1C1C26",
    bg_hover     = "#252535",
    border       = "#2A2A3D",
    accent       = "#7B61FF",
    accent_light = "#A594FF",
    accent_dim   = "#3D2F9E",
    success      = "#34D399",
    danger       = "#F87171",
    fg_primary   = "#E8E8F0",
    fg_secondary = "#8888AA",
    fg_dim       = "#505068",
    canvas_bg    = "#2B2B3C",
    shadow       = "#09090F",
)

FONT_MONO  = ("Courier", 9)
FONT_UI    = ("Helvetica", 10)
FONT_LABEL = ("Helvetica", 8)

# PDF font list — order must match PDF_FONTS
PDF_FONTS       = ["helv",      "tiro",            "cour",        "zadb",           "symb"   ]
PDF_FONT_LABELS = ["Helvetica", "Times New Roman", "Courier New", "Zapf Dingbats",  "Symbol" ]

# Tk font families that visually match the PDF fonts
TK_FONT_MAP = {
    "Helvetica":       "Helvetica",
    "Times New Roman": "Times New Roman",
    "Courier New":     "Courier New",
    "Zapf Dingbats":   "Helvetica",
    "Symbol":          "Helvetica",
}

# Rendering
RENDER_DPI  = 1.5
MIN_SCALE   = 0.3
MAX_SCALE   = 5.0
SCALE_STEP  = 0.15

# Text box grip handle dimensions
GRIP_W      = 20
GRIP_H      = 20
MIN_BOX_PX  = 60   # minimum box width/height in canvas pixels

# Undo history cap
MAX_UNDO_STEPS = 20

# Thumbnail panel
THUMB_SCALE   = 0.18
THUMB_PAD     = 8
THUMB_PANEL_W = 148