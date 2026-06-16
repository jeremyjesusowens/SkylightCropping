#!/usr/bin/env python3
"""Generate a high-quality release screenshot mockup for Skylight Cropping.

Renders a 1280×820 logical-pixel canvas at 2× (2560×1640) to
design/mockups/release_screenshot.png

Run:  python design/generate_release_mockup.py
"""

from pathlib import Path
import cairosvg

W, H = 1280, 820
OUT = Path(__file__).parent / "mockups"
OUT.mkdir(parents=True, exist_ok=True)

SANS = "Liberation Sans, DejaVu Sans, sans-serif"
MONO = "DejaVu Sans Mono, Courier New, monospace"

# --- Aurora/Twilight palette ---
BG     = "#0b0c14"
BAR    = "#12131f"
PANEL  = "#161827"
PANEL2 = "#11121c"
STROKE = "#25283a"
ACCENT = "#A48CFF"
TXT    = "#e7e8f0"
MUTED  = "#828aa3"
DIM    = "#5b6178"
DONE   = "#5fd1b0"
ERRC   = "#ff6b6b"
THUMB  = "#1b1d2e"
SEL    = "#1d2030"


# --- tiny SVG helpers (same API as generate_mockups.py) --------------------

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def rect(x, y, w, h, fill, rx=0, opacity=None, stroke=None, sw=1):
    o = f' fill-opacity="{opacity}"' if opacity is not None else ""
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"{o}{s}/>'


def line(x1, y1, x2, y2, stroke, sw=1, opacity=None, dash=None):
    o = f' stroke-opacity="{opacity}"' if opacity is not None else ""
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{sw}"{o}{d}/>'


def text(x, y, s, size, fill, font=SANS, weight="normal", anchor="start",
         spacing=None, opacity=None, style="normal"):
    sp = f' letter-spacing="{spacing}"' if spacing is not None else ""
    o  = f' fill-opacity="{opacity}"' if opacity is not None else ""
    return (f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" '
            f'font-weight="{weight}" font-style="{style}" fill="{fill}" '
            f'text-anchor="{anchor}"{sp}{o}>{esc(s)}</text>')


def circle(cx, cy, r, fill, opacity=None, stroke=None, sw=1):
    o = f' fill-opacity="{opacity}"' if opacity is not None else ""
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"{o}{s}/>'


def svg(body, w=W, h=H, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">{defs}{body}</svg>')


def render(name, markup):
    path = OUT / f"{name}.png"
    cairosvg.svg2png(bytestring=markup.encode(), write_to=str(path),
                     output_width=W * 2, output_height=H * 2)
    print("wrote", path)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def halo_text(x, y, s, size, fill, font=MONO, weight="normal", anchor="start",
              halo="#000000", halo_w=2):
    """Text with a dark halo for legibility over photos."""
    shadow = (f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" '
              f'font-weight="{weight}" fill="{halo}" text-anchor="{anchor}" '
              f'stroke="{halo}" stroke-width="{halo_w}" '
              f'stroke-linejoin="round" paint-order="stroke">{esc(s)}</text>')
    label  = (f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" '
              f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{esc(s)}</text>')
    return shadow + label


def crop_bracket(x, y, w, h, arm=14, col=ACCENT, sw=2):
    """Draw four L-shaped corner brackets around a bounding box."""
    lines = []
    # top-left
    lines.append(line(x, y + arm, x, y, col, sw))
    lines.append(line(x, y, x + arm, y, col, sw))
    # top-right
    lines.append(line(x + w - arm, y, x + w, y, col, sw))
    lines.append(line(x + w, y, x + w, y + arm, col, sw))
    # bottom-left
    lines.append(line(x, y + h - arm, x, y + h, col, sw))
    lines.append(line(x, y + h, x + arm, y + h, col, sw))
    # bottom-right
    lines.append(line(x + w - arm, y + h, x + w, y + h, col, sw))
    lines.append(line(x + w, y + h - arm, x + w, y + h, col, sw))
    return "".join(lines)


# ---------------------------------------------------------------------------
# MAIN MOCKUP
# ---------------------------------------------------------------------------

def release_mockup():
    defs = (
        '<defs>'
        # Sky gradient: dark blue-grey at top, misty grey-blue at bottom
        '<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0"   stop-color="#1b2a3c"/>'
        '<stop offset="0.5" stop-color="#2c4a60"/>'
        '<stop offset="1"   stop-color="#4a6a7e"/>'
        '</linearGradient>'
        # Mist/ground haze
        '<linearGradient id="mist" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0"   stop-color="#3a5a6a" stop-opacity="0"/>'
        '<stop offset="1"   stop-color="#8aabb8" stop-opacity="0.35"/>'
        '</linearGradient>'
        # Dim overlay for outside-crop areas
        '<linearGradient id="dimOverlay" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#000000" stop-opacity="0.55"/>'
        '<stop offset="1" stop-color="#000000" stop-opacity="0.55"/>'
        '</linearGradient>'
        # Footer log bg gradient
        '<linearGradient id="footerGrad" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0"   stop-color="#12131f"/>'
        '<stop offset="1"   stop-color="#0e0f19"/>'
        '</linearGradient>'
        # Queue item fade at bottom
        '<linearGradient id="queueFade" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0.6" stop-color="#161827" stop-opacity="0"/>'
        '<stop offset="1"   stop-color="#161827" stop-opacity="1"/>'
        '</linearGradient>'
        # Accent glow for "analyzing" badge
        '<filter id="glowAccent" x="-50%" y="-50%" width="200%" height="200%">'
        '<feGaussianBlur in="SourceGraphic" stdDeviation="3" result="blur"/>'
        '<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter>'
        # Crop button subtle gradient
        '<linearGradient id="btnGrad" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0"   stop-color="#b89fff"/>'
        '<stop offset="1"   stop-color="#8a6edf"/>'
        '</linearGradient>'
        # Clip path for preview canvas
        '<clipPath id="previewClip">'
        '<rect x="16" y="72" width="844" height="516" rx="6"/>'
        '</clipPath>'
        # Clip for right panel
        '<clipPath id="queueClip">'
        '<rect x="876" y="72" width="388" height="516" rx="8"/>'
        '</clipPath>'
        '</defs>'
    )

    b = []

    # -----------------------------------------------------------------------
    # BACKGROUND
    # -----------------------------------------------------------------------
    b.append(rect(0, 0, W, H, BG))

    # -----------------------------------------------------------------------
    # TOP BAR  (y=0..60)
    # -----------------------------------------------------------------------
    b.append(rect(0, 0, W, 60, BAR))
    # Subtle bottom border
    b.append(line(0, 60, W, 60, STROKE, 1))

    # Logo with crop-bracket corner marks around "Skylight Cropping"
    # Text sits at roughly x=32..195, y=20..44 — bracket tightly around it
    logo_x, logo_y, logo_w, logo_h = 28, 18, 172, 28
    b.append(crop_bracket(logo_x, logo_y, logo_w, logo_h, arm=10, col=ACCENT, sw=2))
    b.append(text(logo_x + 14, logo_y + 20, "Skylight", 20, "#ffffff", weight="bold"))
    b.append(text(logo_x + 98, logo_y + 20, "Cropping", 20, ACCENT, style="italic"))

    # Nav items
    nav_items = [("CROP", True, 680), ("SEND", False, 760), ("SETTINGS", False, 830)]
    for label, active, nx in nav_items:
        col = "#ffffff" if active else MUTED
        wt  = "bold" if active else "normal"
        b.append(text(nx, 36, label, 13, col, weight=wt, spacing=1))
        if active:
            # underline accent bar
            b.append(rect(nx, 55, len(label) * 8 + 2, 3, ACCENT, rx=1))

    # -----------------------------------------------------------------------
    # PREVIEW CANVAS  (x=16..860, y=72..588)
    # -----------------------------------------------------------------------
    PX, PY, PW, PH = 16, 72, 844, 516

    # Outer container
    b.append(rect(PX, PY, PW, PH, "#0a0b12", rx=6))

    # --- Photo simulation (clipped) ---
    b.append('<g clip-path="url(#previewClip)">')

    # Sky background gradient
    b.append(rect(PX, PY, PW, PH, "url(#sky)"))

    # Mist layer at bottom
    b.append(rect(PX, PY + PH * 0.6, PW, PH * 0.4, "url(#mist)"))

    # Water/ground horizon line area
    b.append(rect(PX, PY + int(PH * 0.72), PW, int(PH * 0.28), "#3a5c6a", opacity=0.4))

    # Tree line silhouette (irregular dark band)
    tree_y = PY + int(PH * 0.62)
    # Main treeline base
    b.append(rect(PX, tree_y, PW, int(PH * 0.10), "#0d1a20", opacity=0.85))

    # Individual tree shapes (rough triangles/irregular shapes via paths)
    trees = [
        # (x_offset_from_PX, bottom_y, top_y, width)
        (20,  tree_y + 50, tree_y - 30, 28),
        (55,  tree_y + 50, tree_y - 48, 22),
        (80,  tree_y + 50, tree_y - 20, 32),
        (120, tree_y + 50, tree_y - 52, 18),
        (145, tree_y + 50, tree_y - 35, 26),
        (175, tree_y + 50, tree_y - 60, 20),
        (210, tree_y + 50, tree_y - 42, 24),
        (250, tree_y + 50, tree_y - 28, 30),
        (290, tree_y + 50, tree_y - 55, 18),
        (315, tree_y + 50, tree_y - 38, 22),
        (350, tree_y + 50, tree_y - 44, 20),
        (390, tree_y + 50, tree_y - 32, 28),
        (430, tree_y + 50, tree_y - 50, 16),
        (460, tree_y + 50, tree_y - 25, 24),
        (500, tree_y + 50, tree_y - 48, 20),
        (540, tree_y + 50, tree_y - 36, 26),
        (580, tree_y + 50, tree_y - 58, 18),
        (620, tree_y + 50, tree_y - 40, 22),
        (660, tree_y + 50, tree_y - 30, 28),
        (700, tree_y + 50, tree_y - 52, 20),
        (740, tree_y + 50, tree_y - 44, 24),
        (780, tree_y + 50, tree_y - 36, 20),
        (810, tree_y + 50, tree_y - 26, 26),
    ]
    for dx, by, ty, tw in trees:
        tx = PX + dx
        hw = tw // 2
        b.append(f'<path d="M {tx-hw} {by} L {tx} {ty} L {tx+hw} {by} Z" '
                 f'fill="#0d1a20" opacity="0.9"/>')

    # Subtle water reflections
    for i in range(6):
        wy = PY + int(PH * 0.76) + i * 8
        b.append(line(PX + 100 + i * 40, wy, PX + 200 + i * 50, wy,
                      "#5a8090", 1, opacity=0.25))

    # --- Bird (great blue heron) near 60% across, 55% down ---
    BRD_X = PX + int(PW * 0.60)
    BRD_Y = PY + int(PH * 0.54)

    # Legs (thin lines going down to water)
    b.append(line(BRD_X - 4,  BRD_Y + 12, BRD_X - 6,  BRD_Y + 52, "#3a3a44", 2))
    b.append(line(BRD_X + 4,  BRD_Y + 12, BRD_X + 7,  BRD_Y + 52, "#3a3a44", 2))
    # Feet
    b.append(line(BRD_X - 6,  BRD_Y + 52, BRD_X - 16, BRD_Y + 56, "#3a3a44", 1.5))
    b.append(line(BRD_X - 6,  BRD_Y + 52, BRD_X - 4,  BRD_Y + 58, "#3a3a44", 1.5))
    b.append(line(BRD_X + 7,  BRD_Y + 52, BRD_X + 17, BRD_Y + 56, "#3a3a44", 1.5))
    b.append(line(BRD_X + 7,  BRD_Y + 52, BRD_X + 9,  BRD_Y + 58, "#3a3a44", 1.5))

    # Body (elongated ellipse, slightly tilted)
    b.append(f'<ellipse cx="{BRD_X}" cy="{BRD_Y}" rx="28" ry="14" '
             f'fill="#2a2a34" transform="rotate(-8 {BRD_X} {BRD_Y})"/>')

    # Wing fold suggestion
    b.append(f'<ellipse cx="{BRD_X - 4}" cy="{BRD_Y + 2}" rx="22" ry="10" '
             f'fill="#35353f" transform="rotate(-6 {BRD_X-4} {BRD_Y+2})"/>')

    # Neck (S-curve via path)
    nx0, ny0 = BRD_X + 6, BRD_Y - 10
    nx1, ny1 = BRD_X + 14, BRD_Y - 26
    nx2, ny2 = BRD_X + 10, BRD_Y - 42
    nx3, ny3 = BRD_X + 16, BRD_Y - 54
    b.append(f'<path d="M {nx0} {ny0} C {nx0+8} {ny0-8} {nx1+6} {ny1-6} '
             f'{nx2} {ny2} C {nx2-4} {ny2-6} {nx3-4} {ny3+4} {nx3} {ny3}" '
             f'fill="none" stroke="#2a2a34" stroke-width="7" stroke-linecap="round"/>')

    # Head (small circle)
    b.append(circle(BRD_X + 16, BRD_Y - 58, 7, "#2a2a34"))

    # Beak (long thin line)
    b.append(line(BRD_X + 20, BRD_Y - 58, BRD_X + 40, BRD_Y - 54, "#3a3a44", 2.5))

    # Eye (tiny highlight)
    b.append(circle(BRD_X + 19, BRD_Y - 60, 2, "#5a5a6a"))
    b.append(circle(BRD_X + 19, BRD_Y - 60, 0.8, "#aaaabb"))

    # Crown plumes (thin lines)
    b.append(line(BRD_X + 14, BRD_Y - 63, BRD_X + 8,  BRD_Y - 72, "#3a3a44", 1.5))
    b.append(line(BRD_X + 16, BRD_Y - 64, BRD_X + 18, BRD_Y - 74, "#3a3a44", 1.5))

    # Tail feathers
    b.append(f'<path d="M {BRD_X-22} {BRD_Y+4} C {BRD_X-36} {BRD_Y+10} '
             f'{BRD_X-44} {BRD_Y+8} {BRD_X-50} {BRD_Y+12}" '
             f'fill="none" stroke="#2a2a34" stroke-width="5" stroke-linecap="round"/>')

    # --- Rule of thirds grid (faint stippled white lines) ---
    for i in (1, 2):
        b.append(line(PX + PW * i // 3, PY, PX + PW * i // 3, PY + PH,
                      "#ffffff", 1, opacity=0.18, dash="4 6"))
        b.append(line(PX, PY + PH * i // 3, PX + PW, PY + PH * i // 3,
                      "#ffffff", 1, opacity=0.18, dash="4 6"))

    # --- 16:9 crop box inside the canvas ---
    # Crop box: left=280, top=160 (canvas-relative), right=840, bottom=520
    CL, CT, CR, CB = 280, 160, 840, 520
    # But clip to canvas bounds (PX..PX+PW, PY..PY+PH)
    CROP_X = PX + CL
    CROP_Y = PY + CT
    CROP_W = CR - CL
    CROP_H = CB - CT

    # Dim regions outside the crop box
    # Top strip
    b.append(rect(PX, PY, PW, CT, "#000000", opacity=0.52))
    # Bottom strip
    b.append(rect(PX, PY + CB, PW, PH - CB, "#000000", opacity=0.52))
    # Left strip (between top/bottom strips)
    b.append(rect(PX, PY + CT, CL, CROP_H, "#000000", opacity=0.52))
    # Right strip
    b.append(rect(PX + CR, PY + CT, PW - CR, CROP_H, "#000000", opacity=0.52))

    # Crop box outline
    b.append(rect(CROP_X, CROP_Y, CROP_W, CROP_H, "none",
                  stroke=ACCENT, sw=2))

    # Corner handles
    HANDLE = 7
    for hx in (CROP_X, CROP_X + CROP_W):
        for hy in (CROP_Y, CROP_Y + CROP_H):
            b.append(rect(hx - HANDLE // 2, hy - HANDLE // 2, HANDLE, HANDLE, ACCENT))

    # --- Target crosshair at bird position ---
    TGT_X = BRD_X
    TGT_Y = BRD_Y - 20   # roughly centre-mass of bird

    # Black underlay lines for contrast
    b.append(line(TGT_X - 22, TGT_Y, TGT_X + 22, TGT_Y, "#000000", 3))
    b.append(line(TGT_X, TGT_Y - 22, TGT_X, TGT_Y + 22, "#000000", 3))
    # Crosshair lines
    b.append(line(TGT_X - 20, TGT_Y, TGT_X - 8,  TGT_Y, ACCENT, 1.5))
    b.append(line(TGT_X + 8,  TGT_Y, TGT_X + 20, TGT_Y, ACCENT, 1.5))
    b.append(line(TGT_X, TGT_Y - 20, TGT_X, TGT_Y - 8,  ACCENT, 1.5))
    b.append(line(TGT_X, TGT_Y + 8,  TGT_X, TGT_Y + 20, ACCENT, 1.5))
    # Circle
    b.append(circle(TGT_X, TGT_Y, 6, "none", stroke=ACCENT, sw=1.5))

    # Label near crosshair
    b.append(halo_text(TGT_X + 14, TGT_Y - 10,
                       "great blue heron  ·  61%, 54%",
                       10, ACCENT, halo_w=3))

    # Bottom-left filename
    b.append(halo_text(PX + 10, PY + PH - 10, "IMG_0847.jpg", 11, "#ffffff", halo_w=3))

    # Bottom-right dimensions
    b.append(halo_text(PX + PW - 10, PY + PH - 10,
                       "5184 × 3888  →  16:9",
                       10, "#c0c8d8", anchor="end", halo_w=3))

    b.append('</g>')  # end preview clip

    # Inset border around preview canvas
    b.append(rect(PX, PY, PW, PH, "none", rx=6, stroke=STROKE, sw=1))

    # Top-centre faint hint text (outside clip so it draws on top)
    b.append(text(PX + PW // 2, PY + 18, "click to move target",
                  9, DIM, anchor="middle"))

    # -----------------------------------------------------------------------
    # RIGHT PANEL — QUEUE  (x=876..1264, y=72..588)
    # -----------------------------------------------------------------------
    QX, QY, QW, QH = 876, 72, 388, 516
    b.append(rect(QX, QY, QW, QH, PANEL, rx=8, stroke=STROKE, sw=1))

    # Header
    b.append(text(QX + 16, QY + 30, "QUEUE", 11, MUTED,
                  weight="bold", spacing=2))
    b.append(text(QX + QW - 16, QY + 30, "7", 13, ACCENT,
                  weight="bold", anchor="end"))

    # Separator
    b.append(line(QX + 16, QY + 40, QX + QW - 16, QY + 40, STROKE, 1))

    # Add Files / Add Folder / Clear buttons
    BTN_Y = QY + 56
    btn_defs = [
        ("Add Files",   QX + 16,  84),
        ("Add Folder",  QX + 112, 90),
        ("Clear",       QX + 214, 56),
    ]
    for btn_label, bx, bw in btn_defs:
        b.append(rect(bx, BTN_Y, bw, 26, "none", rx=5, stroke=STROKE, sw=1))
        b.append(text(bx + bw // 2, BTN_Y + 17, btn_label,
                      11, MUTED, anchor="middle"))

    # Queue items
    ITEM_H = 56
    items = [
        ("IMG_0843.jpg", DONE,   "● cropped",   False),
        ("IMG_0844.jpg", DONE,   "● cropped",   False),
        ("IMG_0847.jpg", ACCENT, "● analyzing", True),
        ("IMG_0851.jpg", DIM,    "● queued",    False),
        ("IMG_0852.jpg", DIM,    "● queued",    False),
    ]
    IY = QY + 96
    for i, (fname, status_col, status_txt, selected) in enumerate(items):
        iy = IY + i * ITEM_H
        # Selected background
        if selected:
            b.append(rect(QX + 1, iy, QW - 2, ITEM_H, SEL, rx=4))
            # Subtle left accent bar
            b.append(rect(QX + 1, iy + 6, 3, ITEM_H - 12, ACCENT, rx=1))

        # Thumbnail placeholder
        b.append(rect(QX + 16, iy + 10, 52, 36, THUMB, rx=4))
        b.append(rect(QX + 16, iy + 10, 52, 36, "none", rx=4, stroke=STROKE, sw=1))
        # Tiny "photo" hint lines in thumbnail
        for ti in range(3):
            b.append(line(QX + 22, iy + 20 + ti * 8,
                          QX + 62, iy + 20 + ti * 8,
                          "#2a2d42", 1))

        # Filename
        fname_col = TXT if selected else "#b0b8cc"
        b.append(text(QX + 78, iy + 24, fname, 12, fname_col, font=MONO))

        # Status
        if selected:
            # Glow effect for analyzing state
            b.append(f'<text x="{QX + 78}" y="{iy + 40}" '
                     f'font-family="{MONO}" font-size="10" fill="{status_col}" '
                     f'filter="url(#glowAccent)">{esc(status_txt)}</text>')
        else:
            b.append(text(QX + 78, iy + 40, status_txt, 10, status_col, font=MONO))

    # Queue fade gradient at bottom
    b.append(rect(QX + 1, QY + 96 + 4 * ITEM_H + 20, QW - 2, QH - 96 - 4 * ITEM_H - 20,
                  "url(#queueFade)", rx=8))

    # -----------------------------------------------------------------------
    # CONTROLS PANEL  (x=16, y=600..660)
    # -----------------------------------------------------------------------
    CPY = 600
    b.append(rect(16, CPY, 844, 62, PANEL, rx=8, stroke=STROKE, sw=1))

    # Row 1 — Output
    b.append(text(28, CPY + 20, "Output", 11, MUTED, weight="bold"))
    # Path text field
    b.append(rect(80, CPY + 8, 620, 24, PANEL2, rx=4, stroke=STROKE, sw=1))
    b.append(text(88, CPY + 24,
                  r"C:\Users\username\Pictures\skylight cropped",
                  11, TXT, font=MONO))
    # Browse button
    b.append(rect(712, CPY + 8, 60, 24, "none", rx=4, stroke=STROKE, sw=1))
    b.append(text(742, CPY + 24, "Browse", 11, MUTED, anchor="middle"))

    # Row 1 — Suffix
    b.append(text(784, CPY + 20, "Suffix", 11, MUTED, weight="bold"))
    b.append(rect(824, CPY + 8, 58, 24, PANEL2, rx=4, stroke=STROKE, sw=1))
    b.append(text(830, CPY + 24, "_16x9", 11, TXT, font=MONO))

    # Row 2 — Dry run + Model
    b.append(text(28, CPY + 50, "Dry run", 11, MUTED, weight="bold"))
    # Toggle (off)
    b.append(rect(80, CPY + 38, 32, 16, "#2a2d42", rx=8, stroke=STROKE, sw=1))
    b.append(circle(88, CPY + 46, 6, DIM))

    b.append(text(130, CPY + 50, "Model", 11, MUTED, weight="bold"))
    # Dropdown
    b.append(rect(174, CPY + 38, 178, 22, PANEL2, rx=4, stroke=STROKE, sw=1))
    b.append(text(180, CPY + 53, "claude-sonnet-4-6", 11, TXT, font=MONO))
    b.append(text(344, CPY + 53, "▾", 11, MUTED, anchor="end"))

    # -----------------------------------------------------------------------
    # BIG CROP BUTTON  (x=16, y=668, w=844, h=48)
    # -----------------------------------------------------------------------
    b.append(rect(16, 668, 844, 48, "url(#btnGrad)", rx=8))
    # Subtle top highlight
    b.append(rect(16, 668, 844, 1, "#ffffff", opacity=0.12))
    b.append(text(W // 2 - 188, 698,  # rough centre of 16..860
                  "Crop Photos", 16, "#ffffff", weight="bold", anchor="middle"))
    # Slight left icon suggestion
    b.append(text(233, 698, "✂", 15, "#ffffff", opacity=0.7))

    # -----------------------------------------------------------------------
    # FOOTER  (full width, y=720..820, h=100)
    # -----------------------------------------------------------------------
    FY = 720
    b.append(rect(0, FY, W, H - FY, "url(#footerGrad)"))
    b.append(line(0, FY, W, FY, STROKE, 1))

    # Status line
    b.append(text(16, FY + 20, "Done — 2/7 cropped", 12, TXT, weight="bold"))
    b.append(text(W - 16, FY + 20, "2 / 7", 12, ACCENT, weight="bold", anchor="end"))

    # Progress bar (28% filled)
    b.append(rect(16, FY + 28, W - 32, 5, "#1e2033", rx=2))
    b.append(rect(16, FY + 28, int((W - 32) * 0.28), 5, ACCENT, rx=2))

    # Activity log label
    b.append(text(16, FY + 52, "ACTIVITY LOG", 10, MUTED, weight="bold", spacing=2))

    # Log text area
    LOG_Y = FY + 64
    b.append(rect(16, LOG_Y, W - 32, H - LOG_Y - 8, PANEL2, rx=4, stroke=STROKE, sw=1))

    log_lines = [
        ("[2] IMG_0844.jpg", TXT, False),
        ("  Subject: great blue heron — target at 58% across, 52% down", MUTED, False),
        ("  Cropping 5184×3888 → 9216×5184 (16:9)", MUTED, False),
        ("  ✓ Saved as IMG_0844_16x9.jpg", DONE, False),
        ("[3] IMG_0847.jpg", TXT, False),
        ("  Analyzing with Claude to find the subject…", ACCENT, True),
    ]
    ly = LOG_Y + 16
    for line_text, col, is_active in log_lines:
        if is_active:
            b.append(f'<text x="26" y="{ly}" font-family="{MONO}" font-size="11" '
                     f'fill="{col}" filter="url(#glowAccent)">{esc(line_text)}</text>')
        else:
            b.append(text(26, ly, line_text, 11, col, font=MONO))
        ly += 15

    return svg("".join(b), defs=defs)


if __name__ == "__main__":
    render("release_screenshot", release_mockup())
    print("done")
