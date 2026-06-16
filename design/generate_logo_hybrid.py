#!/usr/bin/env python3
"""Hybrid logo option: aperture mark + crop brackets + mixed-case italic.

Run:  python design/generate_logo_hybrid.py
Out:  design/mockups/logo/hybrid.png
"""

from pathlib import Path
import cairosvg

from generate_mockups import rect, line, text, circle, SANS

OUT = Path(__file__).parent / "mockups" / "logo"
OUT.mkdir(parents=True, exist_ok=True)

BG     = "#0b0c14"
BAR    = "#12131f"
ACCENT = "#A48CFF"
ACC_HV = "#b9a6ff"
TXT    = "#e7e8f0"
MUTED  = "#828aa3"
DIM    = "#5b6178"
DONE   = "#5fd1b0"
PANEL  = "#161827"
STROKE = "#25283a"

BW, BH = 1000, 120


def aperture(b, cx, cy, r, col):
    import math
    b.append(circle(cx, cy, r, "none", stroke=col, sw=2))
    for k in range(6):
        a0 = math.radians(60 * k)
        a1 = math.radians(60 * k + 40)
        x1, y1 = cx + r * math.cos(a0), cy + r * math.sin(a0)
        x2, y2 = cx + r * 0.30 * math.cos(a1), cy + r * 0.30 * math.sin(a1)
        b.append(line(x1, y1, x2, y2, col, 1.4, opacity=0.85))


def bracket(b, x, y, w, h, col, sw=1.5, leg=13):
    """Corner crop-mark brackets as L-shapes."""
    for cx, cy, dx, dy in ((x, y, 1, 1), (x + w, y, -1, 1),
                           (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
        b.append(line(cx, cy, cx + dx * leg, cy, col, sw))
        b.append(line(cx, cy, cx, cy + dy * leg, col, sw))


def nav(b, active="CROP"):
    x0 = 560
    for i, name in enumerate(("CROP", "SEND", "SETTINGS")):
        on = name == active
        x = x0 + i * 116
        b.append(text(x, BH / 2 + 5, name, 14, TXT if on else MUTED,
                      font=SANS, weight="bold", spacing=2))
        if on:
            b.append(rect(x, BH / 2 + 18, 44, 3, ACCENT, rx=2))


def build():
    b = [rect(0, 0, BW, BH, BAR)]

    # Aperture mark at left
    aperture(b, 44, 60, 17, ACCENT)

    # Bracket zone: x=72, y=28, w=230, h=64 — frames the text
    bracket(b, 72, 28, 230, 64, ACCENT, sw=1.5, leg=13)

    # Mixed-case italic wordmark inside brackets
    # "Skylight" bold white, "Cropping" ACCENT italic — both at y=67
    b.append(text(88, 67, "Skylight", 22, TXT, font=SANS, weight="bold"))
    b.append(text(195, 67, " Cropping", 22, ACCENT, font=SANS,
                  weight="normal", style="italic"))

    nav(b)

    body = "".join(b)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{BW}" height="{BH}" '
           f'viewBox="0 0 {BW} {BH}">{body}</svg>')
    return svg


if __name__ == "__main__":
    markup = build()
    out_path = OUT / "hybrid.png"
    cairosvg.svg2png(bytestring=markup.encode(), write_to=str(out_path),
                     output_width=BW * 2, output_height=BH * 2)
    print("wrote", out_path)
