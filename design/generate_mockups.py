#!/usr/bin/env python3
"""Generate UI redesign mockups for Skylight Cropping as PNGs.

Each mockup is hand-authored SVG rendered to PNG via cairosvg. They depict a
redesign of the app's main "Crop" screen so the styles can be compared.

Run:  python design/generate_mockups.py
Out:  design/mockups/*.png
"""

from pathlib import Path
import cairosvg

W, H = 1000, 900
OUT = Path(__file__).parent / "mockups"
OUT.mkdir(parents=True, exist_ok=True)

SANS = "Liberation Sans, DejaVu Sans, sans-serif"
SERIF = "Bitstream Charter, DejaVu Serif, serif"
MONO = "DejaVu Sans Mono, monospace"


# --- tiny SVG helpers -------------------------------------------------------

def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


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
    o = f' fill-opacity="{opacity}"' if opacity is not None else ""
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


# ===========================================================================
# 1. METRO / ZUNE
# ===========================================================================

def metro():
    b = []
    b.append(rect(0, 0, W, H, "#080808"))
    # tiny app chrome
    b.append(text(40, 46, "SKYLIGHT CROPPING", 13, "#5a5a5a", weight="bold",
                  spacing=3))
    b.append(text(W - 40, 46, "— □ ✕", 14, "#444", anchor="end"))
    # panorama pivot header (bleeds off the right edge)
    b.append(text(34, 138, "crop", 84, "#ffffff", weight="normal"))
    b.append(text(250, 138, "send", 84, "#3a3a3a"))
    b.append(text(470, 138, "settings", 84, "#3a3a3a"))
    b.append(text(820, 138, "abou", 84, "#1f1f1f"))  # bleed cue
    # giant count
    b.append(text(36, 250, "12", 110, "#E3008C", weight="bold"))
    b.append(text(190, 222, "PHOTOS", 18, "#9a9a9a", weight="bold", spacing=4))
    b.append(text(190, 250, "READY TO CROP", 18, "#5a5a5a", weight="bold", spacing=4))
    # live tiles
    tiles = [
        (36, 300, 150, 150, "#E3008C", "plus", "ADD\nFILES"),
        (200, 300, 150, 150, "#00ABA9", "folder", "ADD\nFOLDER"),
        (364, 300, 72, 72, "#2D89EF", "", "CLEAR"),
    ]
    for x, y, w, h, col, glyph, lab in tiles:
        b.append(rect(x, y, w, h, col))
        if glyph == "plus":
            b.append(line(x + 32, y + 26, x + 32, y + 62, "#ffffff", 5))
            b.append(line(x + 14, y + 44, x + 50, y + 44, "#ffffff", 5))
        elif glyph == "folder":
            b.append(f'<path d="M {x+16} {y+30} h 18 l 5 7 h 21 v 25 h -44 Z" '
                     f'fill="none" stroke="#ffffff" stroke-width="4" stroke-linejoin="round"/>')
        lines = lab.split("\n")
        ly = y + h - 16 - (len(lines) - 1) * 20
        for ln in lines:
            b.append(text(x + 16, ly, ln, 16, "#ffffff", weight="bold", spacing=1))
            ly += 20
    # file list (flat, edge-to-edge, no boxes)
    fx, fy = 460, 296
    b.append(text(fx, fy, "QUEUE", 13, "#7a7a7a", weight="bold", spacing=4))
    files = ["beach_sunrise.jpg", "kids_porch.png", "garden_wide.jpg",
             "dog_run.jpg", "harbor_dusk.webp"]
    yy = fy + 34
    for f in files:
        b.append(text(fx, yy, f, 22, "#dddddd"))
        b.append(text(W - 40, yy, "queued", 13, "#5a5a5a", anchor="end",
                      weight="bold", spacing=2))
        b.append(line(fx, yy + 14, W - 40, yy + 14, "#1c1c1c", 1))
        yy += 44
    # options as flat key/value rows
    ox, oy = 36, 506
    b.append(text(ox, oy, "OPTIONS", 13, "#7a7a7a", weight="bold", spacing=4))
    opts = [("OUTPUT FOLDER", "same as source"),
            ("FILENAME SUFFIX", "_16x9"),
            ("MODEL", "claude-opus-4-7"),
            ("DRY RUN", "off")]
    yy = oy + 38
    for k, v in opts:
        b.append(text(ox, yy, k, 14, "#7a7a7a", weight="bold", spacing=2))
        b.append(text(400, yy, v, 22, "#eaeaea"))
        b.append(line(ox, yy + 16, 400 - 40, yy + 16, "#161616"))
        yy += 50
    # big action tile
    b.append(rect(36, 724, 364, 96, "#E3008C"))
    b.append(text(60, 770, "crop photos", 34, "#ffffff"))
    b.append(text(60, 800, "SEND 12 IMAGES TO CLAUDE VISION", 12, "#ffd0ec",
                  weight="bold", spacing=2))
    # progress strip
    b.append(text(440, 744, "CROPPING", 13, "#7a7a7a", weight="bold", spacing=4))
    b.append(text(W - 40, 744, "7 / 20", 22, "#ffffff", anchor="end", weight="bold"))
    b.append(rect(440, 760, W - 480, 6, "#1c1c1c"))
    b.append(rect(440, 760, (W - 480) * 0.35, 6, "#E3008C"))
    b.append(text(440, 800, "beach_sunrise.jpg  •  focal 62%, 48%  •  cropped",
                  14, "#6a6a6a", font=MONO))
    return svg("".join(b))


# ===========================================================================
# 2. FLUENT 2 / WINDOWS 11 MICA
# ===========================================================================

def fluent():
    ACC = "#005FB8"
    defs = ('<defs><linearGradient id="mica" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#f6f3f9"/>'
            '<stop offset="1" stop-color="#eef2f7"/></linearGradient></defs>')
    b = []
    b.append(rect(0, 0, W, H, "url(#mica)", rx=10))
    # title bar
    b.append(text(72, 40, "Skylight Cropping", 14, "#1b1b1b", weight="bold"))
    b.append(circle(40, 35, 7, ACC))
    b.append(text(W - 38, 40, "—  ▢  ✕", 13, "#5a5a5a", anchor="end"))
    # nav rail (acrylic)
    b.append(rect(16, 60, 210, H - 76, "#ffffff", rx=10, opacity=0.55))
    b.append(rect(16, 60, 210, H - 76, "none", rx=10, stroke="#e3e3e3"))

    def nav_icon(kind, x, y, col):
        if kind == "crop":
            return (line(x, y - 7, x, y + 9, col, 2) + line(x - 8, y + 1, x + 8, y + 1, col, 2)
                    + line(x - 1, y - 8, x + 9, y - 8, col, 2) + line(x + 9, y - 9, x + 9, y + 8, col, 2))
        if kind == "send":
            return f'<path d="M {x-9} {y-8} L {x+9} {y} L {x-9} {y+8} L {x-4} {y} Z" fill="{col}"/>'
        # settings: sliders
        out = ""
        for i, yy in enumerate((y - 6, y, y + 6)):
            out += line(x - 9, yy, x + 9, yy, col, 2)
            out += circle(x - 4 + i * 5, yy, 2.6, "#ffffff", stroke=col, sw=1.6)
        return out

    items = [("crop", "Crop", True), ("send", "Send", False),
             ("settings", "Settings", False)]
    yy = 96
    for kind, lab, active in items:
        if active:
            b.append(rect(24, yy - 18, 194, 40, "#ffffff", rx=7, opacity=0.9))
            b.append(rect(28, yy - 9, 3, 22, ACC, rx=2))
        b.append(nav_icon(kind, 56, yy + 2, ACC if active else "#444"))
        b.append(text(80, yy + 7, lab, 15, "#101010" if active else "#3a3a3a",
                      weight="bold" if active else "normal"))
        yy += 50
    # version footer in rail
    b.append(text(40, H - 36, "v1.0  •  Mica", 11, "#9a9a9a"))

    # main column
    mx = 250

    def card(x, y, w, h, title=None):
        out = rect(x + 2, y + 3, w, h, "#000000", rx=10, opacity=0.05)  # soft shadow
        out += rect(x, y, w, h, "#ffffff", rx=10, stroke="#ececec")
        if title:
            out += text(x + 20, y + 30, title, 15, "#1b1b1b", weight="bold")
        return out

    b.append(text(mx, 96, "Crop", 30, "#141414", weight="bold"))
    b.append(text(mx, 122, "Smart 16:9 cropping powered by Claude vision",
                  13, "#6b6b6b"))

    # Photos card
    b.append(card(mx, 140, W - mx - 24, 250, "Photos to crop"))
    b.append(text(W - 44, 170, "12 selected", 13, "#8a8a8a", anchor="end"))
    bx = mx + 20
    b.append(rect(bx, 192, 120, 34, ACC, rx=6))
    b.append(text(bx + 60, 214, "Add files", 14, "#ffffff", weight="bold", anchor="middle"))
    b.append(rect(bx + 132, 192, 128, 34, "#ffffff", rx=6, stroke="#d6d6d6"))
    b.append(text(bx + 132 + 64, 214, "Add folder", 14, "#1b1b1b", anchor="middle"))
    b.append(rect(bx + 272, 192, 84, 34, "#ffffff", rx=6, stroke="#e6e6e6"))
    b.append(text(bx + 272 + 42, 214, "Clear", 14, "#6b6b6b", anchor="middle"))
    # file rows
    rows = ["beach_sunrise.jpg", "kids_porch.png", "garden_wide.jpg", "dog_run.jpg"]
    ry = 248
    for i, f in enumerate(rows):
        if i % 2 == 0:
            b.append(rect(mx + 16, ry - 16, W - mx - 56, 30, "#f7f9fb", rx=6))
        b.append(circle(mx + 32, ry, 4, "#3aa657"))
        b.append(text(mx + 48, ry + 5, f, 13, "#2b2b2b", font=MONO))
        b.append(text(W - 44, ry + 5, "ready", 12, "#8a8a8a", anchor="end"))
        ry += 34

    # Options card
    oy = 408
    b.append(card(mx, oy, W - mx - 24, 210, "Options"))
    fields = [("Output folder", "Same folder as source", True),
              ("Filename suffix", "_16x9", False),
              ("Model", "claude-opus-4-7        ▾", False)]
    fy = oy + 56
    for lab, val, full in fields:
        b.append(text(mx + 20, fy + 6, lab, 13, "#3b3b3b"))
        fw = W - mx - 24 - 220
        b.append(rect(mx + 180, fy - 14, fw, 32, "#ffffff", rx=6, stroke="#dcdcdc"))
        b.append(text(mx + 196, fy + 6, val, 13, "#2b2b2b", font=MONO))
        fy += 46
    # toggle (dry run)
    b.append(text(mx + 20, fy + 6, "Dry run — preview only", 13, "#3b3b3b"))
    b.append(rect(mx + 180, fy - 9, 40, 22, "#cfd4da", rx=11))
    b.append(circle(mx + 191, fy + 2, 8, "#ffffff"))

    # CTA
    b.append(rect(mx, 636, W - mx - 24, 50, ACC, rx=8))
    b.append(text((mx + W - 24) / 2, 667, "Crop Photos", 16, "#ffffff",
                  weight="bold", anchor="middle"))

    # status InfoBar
    sy = 706
    b.append(rect(mx, sy, W - mx - 24, 150, "#ffffff", rx=10, stroke="#ececec"))
    b.append(rect(mx, sy, 4, 150, ACC, rx=2))
    b.append(text(mx + 20, sy + 30, "Cropping…", 14, "#1b1b1b", weight="bold"))
    b.append(text(W - 44, sy + 30, "7 of 20", 14, ACC, weight="bold", anchor="end"))
    b.append(rect(mx + 20, sy + 44, W - mx - 64, 6, "#e9edf1", rx=3))
    b.append(rect(mx + 20, sy + 44, (W - mx - 64) * 0.35, 6, ACC, rx=3))
    b.append(text(mx + 20, sy + 78, "Activity log", 12, "#6b6b6b", weight="bold"))
    log = ["✓ beach_sunrise.jpg  →  focal 62%, 48%  cropped",
           "✓ kids_porch.png  →  focal 40%, 55%  cropped",
           "→ garden_wide.jpg  analysing…"]
    ly = sy + 100
    for l in log:
        b.append(text(mx + 20, ly, l, 12, "#5a5a5a", font=MONO))
        ly += 19
    return svg("".join(b), defs=defs)


# ===========================================================================
# 3. DARKROOM PRO / CINEMATIC
# ===========================================================================

def darkroom():
    GOLD = "#E8B04B"
    defs = ('<defs>'
            '<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#2b4a78"/>'
            '<stop offset="0.55" stop-color="#c98a5e"/>'
            '<stop offset="1" stop-color="#e8c39a"/></linearGradient>'
            '<linearGradient id="panel" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#1c1f26"/>'
            '<stop offset="1" stop-color="#15171c"/></linearGradient></defs>')
    b = []
    b.append(rect(0, 0, W, H, "#0e0f13"))
    # top bar
    b.append(rect(0, 0, W, 56, "#15171c"))
    b.append(text(32, 36, "S K Y L I G H T", 18, "#f2f2f2", weight="bold", spacing=2))
    b.append(text(210, 36, "DARKROOM", 12, GOLD, weight="bold", spacing=4))
    for i, (t, on) in enumerate([("CROP", True), ("SEND", False), ("SETTINGS", False)]):
        x = 470 + i * 110
        b.append(text(x, 36, t, 13, "#f2f2f2" if on else "#6a6f7a", weight="bold", spacing=2))
        if on:
            b.append(rect(x, 44, 44, 3, GOLD))
    b.append(text(W - 32, 36, "—  ▢  ✕", 13, "#6a6f7a", anchor="end"))

    # preview canvas
    px, py, pw, ph = 32, 84, 600, 470
    b.append(rect(px - 6, py - 6, pw + 12, ph + 12, "#000000"))
    # the photo
    b.append(rect(px, py, pw, ph, "url(#sky)"))
    # a "subject" — figure silhouette near right third
    sx = px + pw * 0.62
    b.append(circle(sx, py + ph * 0.42, 26, "#23303f"))
    b.append(f'<path d="M {sx-34} {py+ph} Q {sx} {py+ph*0.5} {sx+34} {py+ph} Z" fill="#23303f"/>')
    b.append(circle(px + pw * 0.2, py + ph * 0.22, 30, "#fbe9c9", opacity=0.8))  # sun
    # rule of thirds
    for i in (1, 2):
        b.append(line(px + pw * i / 3, py, px + pw * i / 3, py + ph, "#ffffff", 1, opacity=0.25))
        b.append(line(px, py + ph * i / 3, px + pw, py + ph * i / 3, "#ffffff", 1, opacity=0.25))
    # crop rectangle (16:9 inside)
    ch = pw * 9 / 16
    cy = py + (ph - ch) / 2
    b.append(rect(px, cy, pw, ch, "none", stroke=GOLD, sw=2))
    # darken outside crop
    b.append(rect(px, py, pw, cy - py, "#0e0f13", opacity=0.55))
    b.append(rect(px, cy + ch, pw, py + ph - (cy + ch), "#0e0f13", opacity=0.55))
    # corner handles
    for hx in (px, px + pw):
        for hy in (cy, cy + ch):
            b.append(rect(hx - 5, hy - 5, 10, 10, GOLD))
    # focal marker
    fx, fy = sx, py + ph * 0.42
    b.append(circle(fx, fy, 13, "none", stroke=GOLD, sw=2))
    b.append(line(fx - 20, fy, fx + 20, fy, GOLD, 1, opacity=0.8))
    b.append(line(fx, fy - 20, fx, fy + 20, GOLD, 1, opacity=0.8))
    b.append(text(fx + 20, fy - 18, "focal  62% , 48%", 12, GOLD, font=MONO))
    b.append(text(px + 8, py + ph - 12, "beach_sunrise.jpg", 13, "#ffffff", font=MONO, opacity=0.85))
    b.append(text(px + pw - 8, py + ph - 12, "4032 × 3024  →  16:9", 12, "#ffffff",
                  font=MONO, anchor="end", opacity=0.7))

    # right panel — queue
    qx = 656
    b.append(rect(qx, 84, W - qx - 32, 470, "url(#panel)", rx=6, stroke="#262a33"))
    b.append(text(qx + 18, 116, "QUEUE", 12, "#8a909c", weight="bold", spacing=3))
    b.append(text(W - 50, 116, "12", 12, GOLD, weight="bold", anchor="end"))
    q = [("beach_sunrise.jpg", "#3aa657", "done"),
         ("kids_porch.png", "#3aa657", "done"),
         ("garden_wide.jpg", GOLD, "now"),
         ("dog_run.jpg", "#5a606b", "queued"),
         ("harbor_dusk.webp", "#5a606b", "queued"),
         ("trail_morning.jpg", "#5a606b", "queued")]
    yy = 138
    for name, col, st in q:
        active = st == "now"
        if active:
            b.append(rect(qx + 8, yy, W - qx - 48, 48, "#ffffff", rx=6, opacity=0.05))
        b.append(rect(qx + 18, yy + 8, 56, 32, "#2b3340", rx=3))  # thumb
        b.append(rect(qx + 18, yy + 8, 56, 32, "none", rx=3, stroke="#3a4250"))
        b.append(text(qx + 84, yy + 24, name, 13, "#e6e6e6" if active else "#aab0bc", font=MONO))
        b.append(circle(qx + 84, yy + 38, 3, col))
        b.append(text(qx + 96, yy + 42, st, 11, col))
        yy += 56

    # bottom transport bar
    by = 580
    b.append(rect(32, by, W - 64, 130, "url(#panel)", rx=6, stroke="#262a33"))
    b.append(text(56, by + 34, "RENDERING", 12, "#8a909c", weight="bold", spacing=3))
    b.append(text(W - 56, by + 34, "07 / 20", 22, GOLD, weight="bold", anchor="end"))
    b.append(rect(56, by + 48, W - 112, 8, "#23262e", rx=4))
    b.append(rect(56, by + 48, (W - 112) * 0.35, 8, GOLD, rx=4))
    # transport / settings chips
    chips = [("OUTPUT  same folder", 56), ("SUFFIX  _16x9", 296),
             ("MODEL  claude-opus-4-7", 470)]
    for t, x in chips:
        b.append(text(x, by + 92, t, 12, "#9aa0ac", font=MONO))
    # export button
    b.append(rect(W - 250, by + 74, 194, 38, GOLD, rx=4))
    b.append(text(W - 153, by + 99, "EXPORT  16:9", 14, "#1a1205", weight="bold",
                  anchor="middle", spacing=1))
    # film strip
    fy2 = 736
    b.append(text(32, fy2, "RECENT", 11, "#6a6f7a", weight="bold", spacing=3))
    for i in range(9):
        x = 32 + i * 104
        b.append(rect(x, fy2 + 14, 92, 116, "#1a1d24", rx=3, stroke="#262a33"))
        b.append(rect(x + 8, fy2 + 22, 76, 60, "#2b3340", rx=2))
        b.append(text(x + 8, fy2 + 104, f"IMG_{2200+i}", 10, "#6a6f7a", font=MONO))
        b.append(circle(x + 80, fy2 + 26, 4, "#3aa657" if i < 5 else "#5a606b"))
    return svg("".join(b), defs=defs)


# ===========================================================================
# 4. EDITORIAL / SWISS LIGHT
# ===========================================================================

def editorial():
    INK = "#1c1a17"
    ACC = "#B5563A"
    PAPER = "#f7f4ee"
    b = []
    b.append(rect(0, 0, W, H, PAPER))
    # masthead
    b.append(text(56, 56, "AI-ASSISTED 16:9 CROPPING", 12, ACC, weight="bold",
                  spacing=5))
    b.append(text(W - 56, 56, "NO. 01 — CROP", 12, "#9a948a", weight="bold",
                  spacing=3, anchor="end"))
    b.append(line(56, 72, W - 56, 72, INK, 1))
    b.append(text(52, 168, "Skylight", 96, INK, font=SERIF))
    b.append(text(560, 168, "Crop", 96, "#cfc7b8", font=SERIF, style="italic"))
    b.append(line(56, 198, W - 56, 198, INK, 1))
    b.append(text(56, 224, "Claude vision finds the subject and keeps it in frame — "
                  "no dumb centre-crops.", 16, "#4a463f", font=SERIF, style="italic"))

    # left rail — contents
    lx = 56
    b.append(text(lx, 286, "CONTENTS", 11, "#9a948a", weight="bold", spacing=4))
    nav = [("01", "Crop", True), ("02", "Send", False), ("03", "Settings", False)]
    yy = 326
    for num, lab, active in nav:
        b.append(text(lx, yy, num, 14, ACC if active else "#b8b1a4", font=SERIF))
        b.append(text(lx + 38, yy, lab, 24, INK if active else "#a8a194", font=SERIF,
                      weight="bold" if active else "normal"))
        if active:
            b.append(line(lx, yy + 12, lx + 150, yy + 12, ACC, 2))
        yy += 50
    # selection stat
    b.append(line(lx, 486, lx + 230, 486, "#ddd6c8", 1))
    b.append(text(lx, 548, "12", 72, INK, font=SERIF))
    b.append(text(lx + 4, 576, "PHOTOS SELECTED", 12, "#9a948a", weight="bold", spacing=3))
    b.append(text(lx, 632, "Add files", 16, INK, font=SERIF, style="italic"))
    b.append(text(lx + 96, 632, "+", 18, ACC, weight="bold"))
    b.append(text(lx, 664, "Add folder", 16, INK, font=SERIF, style="italic"))
    b.append(text(lx, 696, "Clear", 16, "#a8a194", font=SERIF, style="italic"))

    # right column — queue + options as a typographic table
    rx = 330
    rw = W - 56 - rx
    b.append(text(rx, 286, "THE QUEUE", 11, "#9a948a", weight="bold", spacing=4))
    files = [("beach_sunrise.jpg", "ready"), ("kids_porch.png", "ready"),
             ("garden_wide.jpg", "ready"), ("dog_run.jpg", "ready")]
    yy = 320
    for f, st in files:
        b.append(text(rx, yy, f, 19, INK, font=SERIF))
        b.append(text(W - 56, yy, st, 13, "#9a948a", anchor="end", font=SERIF, style="italic"))
        b.append(line(rx, yy + 14, W - 56, yy + 14, "#e4ddd0", 1))
        yy += 40

    # options table
    b.append(text(rx, 510, "SPECIFICATIONS", 11, "#9a948a", weight="bold", spacing=4))
    specs = [("Output folder", "Same folder as source"),
             ("Filename suffix", "_16x9"),
             ("Model", "claude-opus-4-7"),
             ("Dry run", "Off")]
    yy = 544
    for k, v in specs:
        b.append(text(rx, yy, k, 15, "#6b665d", font=SERIF, style="italic"))
        b.append(text(W - 56, yy, v, 16, INK, anchor="end", font=SERIF))
        b.append(line(rx, yy + 12, W - 56, yy + 12, "#e4ddd0", 1))
        yy += 40

    # CTA
    b.append(rect(rx, 720, rw, 54, "none", stroke=INK, sw=1.5))
    b.append(text(rx + 24, 754, "Crop Photos", 22, INK, font=SERIF))
    b.append(text(W - 80, 754, "→", 26, ACC, weight="bold", anchor="end"))

    # footer status
    b.append(line(56, 824, W - 56, 824, INK, 1))
    b.append(text(56, 856, "CROPPING", 12, ACC, weight="bold", spacing=3))
    b.append(text(150, 856, "beach_sunrise.jpg — focal 62%, 48%", 14, "#6b665d",
                  font=SERIF, style="italic"))
    b.append(text(W - 56, 856, "7 of 20", 16, INK, font=SERIF, anchor="end"))
    return svg("".join(b))


if __name__ == "__main__":
    render("1_metro_zune", metro())
    render("2_fluent_mica", fluent())
    render("3_darkroom_pro", darkroom())
    render("4_editorial_swiss", editorial())
    print("done")
