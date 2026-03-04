"""
UI design tokens — colours, fonts, and layout constants.
Overhauled: refined slate/sage palette, softer geometry, generous spacing.
All GUI components import from here so visual changes are made in one place.
"""

# ── Colour palette ────────────────────────────────────────────────────────────
# Cool-charcoal backgrounds, sage-green accent, off-white text.
PALETTE = dict(
    # Backgrounds — three tonal layers
    bg_dark      = "#1A1D20",   # deepest — window background
    bg_mid       = "#1E2226",   # topbar / status bar
    bg_panel     = "#22262B",   # sidebars, panels
    bg_hover     = "#2A2F35",   # hover state, input fields
    bg_card      = "#2E333A",   # raised card within a panel

    # Borders — very subtle; prefer tonal depth over hard lines
    border       = "#32383F",
    border_light = "#3D444D",

    # Accent — muted sage green (calm, professional, non-fatiguing)
    accent       = "#5C8A6E",   # primary action
    accent_light = "#7BB594",   # hover / highlight
    accent_dim   = "#2D4A3A",   # selected state background
    accent_subtle= "#1E3029",   # faint tint (active tool bg)

    # Semantic colours
    success      = "#6DB88A",
    danger       = "#C0635A",
    warning      = "#C49A42",

    # Text hierarchy
    fg_primary   = "#DDE1E6",   # body text
    fg_secondary = "#8C949E",   # labels, captions
    fg_dim       = "#545C66",   # placeholders, disabled
    fg_inverse   = "#1A1D20",   # text on accent buttons

    # Canvas
    canvas_bg    = "#2B2F35",
    page_shadow  = "#111315",

    # Misc
    shadow       = "#13161A",
    overlay      = "#00000066",
)

# ── Typography ────────────────────────────────────────────────────────────────
# Standardised on a single sans-serif family throughout.
# Tk doesn't load web fonts; we fall back to the best available system font.
_SANS = "Helvetica Neue"   # macOS; falls back gracefully on Win/Linux

FONT_TITLE  = (_SANS, 13, "bold")
FONT_UI     = (_SANS, 10)
FONT_UI_MED = (_SANS, 10, "bold")
FONT_LABEL  = (_SANS, 9)
FONT_SMALL  = (_SANS, 8)
FONT_MONO   = ("Menlo", 9)         # monospace for coords / zoom

# ── PDF fonts ─────────────────────────────────────────────────────────────────
PDF_FONTS       = ["helv",      "tiro",            "cour",        "zadb",          "symb"  ]
PDF_FONT_LABELS = ["Helvetica", "Times New Roman", "Courier New", "Zapf Dingbats", "Symbol"]

TK_FONT_MAP = {
    "Helvetica":       "Helvetica",
    "Times New Roman": "Times New Roman",
    "Courier New":     "Courier New",
    "Zapf Dingbats":   "Helvetica",
    "Symbol":          "Helvetica",
}

# ── Rendering ─────────────────────────────────────────────────────────────────
RENDER_DPI  = 1.5
MIN_SCALE   = 0.3
MAX_SCALE   = 5.0
SCALE_STEP  = 0.15

# ── Text box grip ─────────────────────────────────────────────────────────────
GRIP_W      = 20
GRIP_H      = 20
MIN_BOX_PX  = 60

# ── History ───────────────────────────────────────────────────────────────────
MAX_UNDO_STEPS = 20

# ── Layout ────────────────────────────────────────────────────────────────────
# Left icon toolbar
ICON_BAR_W      = 52        # px width of the thin vertical tool strip

# Right panel
RIGHT_PANEL_W   = 220       # px width of the right Properties+Pages panel
TAB_BAR_H       = 36        # px height of the tab strip

# Thumbnail panel (now lives inside the right panel)
THUMB_SCALE     = 0.18
THUMB_PAD       = 10
THUMB_PANEL_W   = RIGHT_PANEL_W   # thumbnails fill the right panel

# Spacing
PAD_S  = 6     # tight spacing between related items
PAD_M  = 10    # standard padding
PAD_L  = 16    # section/group spacing
PAD_XL = 24    # outer margins

# Button geometry
BTN_RADIUS = 5  # simulated via relief; tk doesn't support CSS border-radius