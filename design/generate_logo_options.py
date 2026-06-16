#!/usr/bin/env python3
"""Wordmark / logo treatments for "Skylight Cropping" in the Aurora·Twilight
top bar. Each option is rendered as a strip showing the logo in context next
to the CROP / SEND / SETTINGS nav, so a direction can be chosen before wiring
it into app.py.

Run:  python design/generate_logo_options.py
Out:  design/mockups/logo/options.png   (stacked comparison sheet)
      design/mockups/logo/opt_*.png     (each option on its own)
"""

from pathlib import Path
import cairosvg

from generate_mockups import esc, rect, line, text, circle, MONO

OUT = Path(__file__).parent / "mockups" / "logo"
OUT.mkdir(parents=True, exist_ok=True)

# Aurora · Twilight palette (matches app.py)
BG     = "#0b0c14"
BAR    = "#12131f"
ACCENT = "#A48CFF"
ACC_HV = "#b9a6ff"
TXT    = "#e7e8f0"
MUTED  = "#828aa3"
DIM    = "#5b6178"
DONE   = "#5fd1b0"

BW, BH = 1000, 120           # one strip
SANS = "Liberation Sans, DejaVu Sans, sans-serif"


def nav(b, active="CROP"):
    """Shared CROP/SEND/SETTINGS nav on the right of every strip."""
    x0 = 560
    for i, name in enumerate(("CROP", "SEND", "SETTINGS")):
        on = name == active
        x = x0 + i * 116
        b.append(text(x, BH / 2 + 5, name, 14, TXT if on else MUTED,
                      weight="bold", spacing=2))
        if on:
            b.append(rect(x, BH / 2 + 18, 44, 3, ACCENT, rx=2))


def aperture(b, cx, cy, r, col):
    """Small 6-blade aperture / lens mark."""
    import math
    b.append(circle(cx, cy, r, "none", stroke=col, sw=2))
    for k in range(6):
        a0 = math.radians(60 * k)
        a1 = math.radians(60 * k + 40)
        x1, y1 = cx + r * math.cos(a0), cy + r * math.sin(a0)
        x2, y2 = cx + r * 0.30 * math.cos(a1), cy + r * 0.30 * math.sin(a1)
        b.append(line(x1, y1, x2, y2, col, 1.4, opacity=0.85))


def bracket(b, x, y, w, h, col, sw=2, leg=14):
    """16:9 crop-mark corner brackets around a region."""
    for cx, cy, dx, dy in ((x, y, 1, 1), (x + w, y, -1, 1),
                           (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
        b.append(line(cx, cy, cx + dx * leg, cy, col, sw))
        b.append(line(cx, cy, cx, cy + dy * leg, col, sw))


def strip(builder, tag=None):
    b = [rect(0, 0, BW, BH, BAR)]
    builder(b)
    nav(b)
    if tag:
        b.append(text(BW - 24, 26, tag, 11, DIM, weight="bold",
                      spacing=2, anchor="end"))
    body = "".join(b)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{BW}" height="{BH}" '
            f'viewBox="0 0 {BW} {BH}">{body}</svg>')


# --- the six options --------------------------------------------------------

def opt1(b):
    """Aperture mark + two-tone tracked caps."""
    aperture(b, 44, BH / 2, 17, ACCENT)
    y = BH / 2 + 6
    b.append(text(78, y, "SKYLIGHT", 22, TXT, weight="bold", spacing=4))
    b.append(text(238, y, "CROPPING", 22, ACCENT, weight="bold", spacing=4))


def opt2(b):
    """Crop-mark brackets framing the word — literal nod to cropping."""
    bracket(b, 30, 34, 250, 52, ACCENT, sw=2, leg=13)
    y = BH / 2 + 6
    b.append(text(52, y, "Skylight", 24, TXT, weight="bold"))
    b.append(text(152, y, "Cropping", 24, ACC_HV, weight="normal", style="italic"))


def opt3(b):
    """Stacked lockup with a hairline accent rule."""
    b.append(text(30, 52, "SKYLIGHT", 26, TXT, weight="bold", spacing=6))
    b.append(rect(32, 64, 196, 2, ACCENT, rx=1))
    b.append(text(34, 92, "C R O P P I N G", 12, ACCENT, weight="bold", spacing=8))


def opt4(b):
    """Editorial — divider bar between two weights."""
    y = BH / 2 + 7
    b.append(text(30, y, "Skylight", 26, TXT, weight="bold"))
    b.append(rect(168, 36, 2, 48, ACCENT, rx=1))
    b.append(text(186, y, "CROPPING", 14, MUTED, weight="bold", spacing=5))


def opt5(b):
    """App-icon tile monogram + mixed-case wordmark."""
    b.append(rect(26, BH / 2 - 22, 44, 44, "#1b1d2e", rx=10, stroke="#25283a"))
    # 16:9 frame inside the tile
    b.append(rect(36, BH / 2 - 8, 24, 14, "none", rx=2, stroke=ACCENT, sw=2))
    b.append(circle(52, BH / 2 - 1, 2.5, ACCENT))
    y = BH / 2 + 6
    b.append(text(86, y, "Skylight", 24, TXT, weight="bold"))
    b.append(text(186, y, "Cropping", 24, ACCENT, weight="bold"))


def opt6(b):
    """Gradient wordmark (violet→white) + mono subscript."""
    grad = ('<linearGradient id="lg" x1="0" y1="0" x2="1" y2="0">'
            f'<stop offset="0" stop-color="{ACCENT}"/>'
            f'<stop offset="1" stop-color="{TXT}"/></linearGradient>')
    b.append(f'<defs>{grad}</defs>')
    b.append(text(30, BH / 2 + 2, "Skylight", 30, "url(#lg)", weight="bold"))
    b.append(text(34, BH / 2 + 26, "C R O P P I N G   ·   16:9",
                  11, MUTED, font=MONO, spacing=2))


OPTIONS = [
    ("opt1_aperture",  opt1, "1  APERTURE + TWO-TONE"),
    ("opt2_brackets",  opt2, "2  CROP BRACKETS"),
    ("opt3_stacked",   opt3, "3  STACKED LOCKUP"),
    ("opt4_divider",   opt4, "4  EDITORIAL DIVIDER"),
    ("opt5_tile",      opt5, "5  ICON TILE"),
    ("opt6_gradient",  opt6, "6  GRADIENT WORDMARK"),
]


def render_sheet():
    rows = []
    gap = 12
    sheet_h = len(OPTIONS) * (BH + gap) + gap
    rows.append(rect(0, 0, BW, sheet_h, BG))
    for i, (_, fn, tag) in enumerate(OPTIONS):
        y = gap + i * (BH + gap)
        inner = strip(fn, tag)
        # embed each strip translated down the sheet
        body = inner.split(">", 1)[1].rsplit("</svg>", 1)[0]
        rows.append(f'<g transform="translate(0,{y})">{body}</g>')
    sheet = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{BW}" '
             f'height="{sheet_h}" viewBox="0 0 {BW} {sheet_h}">{"".join(rows)}</svg>')
    cairosvg.svg2png(bytestring=sheet.encode(),
                     write_to=str(OUT / "options.png"),
                     output_width=BW * 2, output_height=sheet_h * 2)
    print("wrote", OUT / "options.png")


if __name__ == "__main__":
    for name, fn, tag in OPTIONS:
        cairosvg.svg2png(bytestring=strip(fn, tag).encode(),
                         write_to=str(OUT / f"{name}.png"),
                         output_width=BW * 2, output_height=BH * 2)
        print("wrote", OUT / f"{name}.png")
    render_sheet()
    print("done")
