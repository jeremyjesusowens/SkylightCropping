#!/usr/bin/env python3
"""Font comparison mockup for Skylight Cropping.

Shows 5 font pairings in a 1000×900 sheet.

Run:  python design/generate_font_options.py
Out:  design/mockups/logo/fonts.png
"""

from pathlib import Path
import cairosvg

from generate_mockups import rect, line, text, circle, SANS, MONO

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

W, H = 1000, 900
STRIP_H = 160
GAP = 8

PAIRINGS = [
    {
        "label": "1  SYSTEM / LIBERATION",
        "heading": "Liberation Sans, DejaVu Sans, sans-serif",
        "ui":      "Liberation Sans, DejaVu Sans, sans-serif",
        "mono":    "DejaVu Sans Mono, monospace",
    },
    {
        "label": "2  GEOMETRIC / CENTURY GOTHIC",
        "heading": "Futura, Century Gothic, Liberation Sans, sans-serif",
        "ui":      "Futura, Century Gothic, Liberation Sans, sans-serif",
        "mono":    "DejaVu Sans Mono, monospace",
    },
    {
        "label": "3  HUMANIST / GILL SANS",
        "heading": "Gill Sans, Trebuchet MS, Liberation Sans, sans-serif",
        "ui":      "Gill Sans, Trebuchet MS, Liberation Sans, sans-serif",
        "mono":    "Courier New, DejaVu Sans Mono, monospace",
    },
    {
        "label": "4  SLAB / CHARTER + LIBERATION",
        "heading": "Bitstream Charter, DejaVu Serif, serif",
        "ui":      "Liberation Sans, DejaVu Sans, sans-serif",
        "mono":    "DejaVu Sans Mono, monospace",
    },
    {
        "label": "5  ALL MONO",
        "heading": "DejaVu Sans Mono, monospace",
        "ui":      "DejaVu Sans Mono, monospace",
        "mono":    "DejaVu Sans Mono, monospace",
    },
]


def strip_svg(pairing, strip_y):
    """Return SVG elements for one pairing strip, offset by strip_y."""
    b = []
    # Strip background
    b.append(rect(0, strip_y, W, STRIP_H, BAR))

    hf = pairing["heading"]
    uf = pairing["ui"]
    mf = pairing["mono"]
    lbl = pairing["label"]

    # Label top-right
    b.append(text(W - 24, strip_y + 20, lbl, 11, DIM, font=mf,
                  weight="normal", anchor="end", spacing=1))

    # --- left mini-app excerpt ---
    # Wordmark
    b.append(text(30, strip_y + 45, "Skylight Cropping", 22, TXT,
                  font=hf, weight="bold"))
    # Sub-label
    b.append(text(30, strip_y + 72, "QUEUE  4", 12, MUTED, font=uf,
                  weight="normal", spacing=3))
    # Filename
    b.append(text(30, strip_y + 100, "P6131302.jpg", 12, ACCENT, font=mf))
    # Status
    b.append(text(30, strip_y + 122, "● cropped", 12, DONE, font=uf))

    # Separator before right block
    b.append(line(480, strip_y + 16, 480, strip_y + STRIP_H - 16, STROKE, 1))

    # --- right sample block ---
    rx = 500
    b.append(text(rx, strip_y + 30, "The quick brown fox jumps", 14, TXT,
                  font=hf, weight="bold"))
    b.append(text(rx, strip_y + 52, "over the lazy dog. 0123456789", 13, MUTED,
                  font=uf))
    b.append(text(rx, strip_y + 74, "abcdefghijklmnopqrstuvwxyz", 12, DIM,
                  font=uf))
    b.append(text(rx, strip_y + 96, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", 12, DIM,
                  font=uf))
    b.append(text(rx, strip_y + 118, "IMG_4567.CR3  →  1920×1080  ● ok", 12,
                  ACCENT, font=mf))
    b.append(text(rx, strip_y + 140, "Skylight Cropping v2.0", 11, DIM,
                  font=hf, weight="bold", style="italic"))

    return b


def build():
    b = [rect(0, 0, W, H, BG)]

    for i, pairing in enumerate(PAIRINGS):
        y = i * (STRIP_H + GAP)
        b.extend(strip_svg(pairing, y))

    body = "".join(b)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}">{body}</svg>')


if __name__ == "__main__":
    markup = build()
    out_path = OUT / "fonts.png"
    cairosvg.svg2png(bytestring=markup.encode(), write_to=str(out_path),
                     output_width=W * 2, output_height=H * 2)
    print("wrote", out_path)
