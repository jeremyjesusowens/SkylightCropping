#!/usr/bin/env python3
"""Color/mood variants of the 'Darkroom Pro' direction for Skylight Cropping.

Same image-first layout (big 16:9 preview with rule-of-thirds + focal marker,
queue panel, transport bar, film-strip) rendered in several palettes so a
colour direction can be chosen before implementation.

Run:  python design/generate_darkroom_variants.py
Out:  design/mockups/darkroom/*.png
"""

from pathlib import Path
import cairosvg

# Reuse the SVG helpers from the main generator (no rendering happens on import).
from generate_mockups import esc, rect, line, text, circle, svg, W, H, MONO

OUT = Path(__file__).parent / "mockups" / "darkroom"
OUT.mkdir(parents=True, exist_ok=True)


# --- the themeable mockup ---------------------------------------------------

def darkroom(t):
    ACC = t["accent"]
    TXT = t.get("text", "#f2f2f2")
    MUT = t["muted"]
    defs = (f'<defs>'
            f'<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{t["sky0"]}"/>'
            f'<stop offset="0.55" stop-color="{t["sky1"]}"/>'
            f'<stop offset="1" stop-color="{t["sky2"]}"/></linearGradient>'
            f'<linearGradient id="panel" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{t["panel0"]}"/>'
            f'<stop offset="1" stop-color="{t["panel1"]}"/></linearGradient></defs>')
    b = []
    b.append(rect(0, 0, W, H, t["bg"]))
    # top bar
    b.append(rect(0, 0, W, 56, t["bar"]))
    b.append(text(32, 36, "S K Y L I G H T", 18, TXT, weight="bold", spacing=2))
    b.append(text(210, 36, t["tag"], 12, ACC, weight="bold", spacing=4))
    for i, (lab, on) in enumerate([("CROP", True), ("SEND", False), ("SETTINGS", False)]):
        x = 470 + i * 110
        b.append(text(x, 36, lab, 13, TXT if on else MUT, weight="bold", spacing=2))
        if on:
            b.append(rect(x, 44, 44, 3, ACC))
    b.append(text(W - 32, 36, "—  ▢  ✕", 13, MUT, anchor="end"))
    # palette name chip (so the variant is identifiable)
    b.append(text(W - 32, 78, t["name"], 12, MUT, weight="bold", spacing=3, anchor="end"))

    # preview canvas
    px, py, pw, ph = 32, 84, 600, 470
    b.append(rect(px - 6, py - 6, pw + 12, ph + 12, "#000000"))
    b.append(rect(px, py, pw, ph, "url(#sky)"))
    # subject silhouette near the right third
    sx = px + pw * 0.62
    sub = t["subject"]
    b.append(circle(sx, py + ph * 0.42, 26, sub))
    b.append(f'<path d="M {sx-34} {py+ph} Q {sx} {py+ph*0.5} {sx+34} {py+ph} Z" fill="{sub}"/>')
    b.append(circle(px + pw * 0.2, py + ph * 0.22, 30, t["orb"], opacity=0.8))
    # rule of thirds
    for i in (1, 2):
        b.append(line(px + pw * i / 3, py, px + pw * i / 3, py + ph, "#ffffff", 1, opacity=0.25))
        b.append(line(px, py + ph * i / 3, px + pw, py + ph * i / 3, "#ffffff", 1, opacity=0.25))
    # crop rectangle (16:9)
    ch = pw * 9 / 16
    cy = py + (ph - ch) / 2
    b.append(rect(px, cy, pw, ch, "none", stroke=ACC, sw=2))
    b.append(rect(px, py, pw, cy - py, t["bg"], opacity=0.55))
    b.append(rect(px, cy + ch, pw, py + ph - (cy + ch), t["bg"], opacity=0.55))
    for hx in (px, px + pw):
        for hy in (cy, cy + ch):
            b.append(rect(hx - 5, hy - 5, 10, 10, ACC))
    # focal marker
    fx, fy = sx, py + ph * 0.42
    b.append(circle(fx, fy, 13, "none", stroke=ACC, sw=2))
    b.append(line(fx - 20, fy, fx + 20, fy, ACC, 1, opacity=0.8))
    b.append(line(fx, fy - 20, fx, fy + 20, ACC, 1, opacity=0.8))
    b.append(text(fx + 20, fy - 18, "focal  62% , 48%", 12, ACC, font=MONO))
    b.append(text(px + 8, py + ph - 12, "beach_sunrise.jpg", 13, "#ffffff", font=MONO, opacity=0.85))
    b.append(text(px + pw - 8, py + ph - 12, "4032 × 3024  →  16:9", 12, "#ffffff",
                  font=MONO, anchor="end", opacity=0.7))

    # right panel — queue
    qx = 656
    b.append(rect(qx, 84, W - qx - 32, 470, "url(#panel)", rx=6, stroke=t["stroke"]))
    b.append(text(qx + 18, 116, "QUEUE", 12, MUT, weight="bold", spacing=3))
    b.append(text(W - 50, 116, "12", 12, ACC, weight="bold", anchor="end"))
    q = [("beach_sunrise.jpg", t["done"], "done"),
         ("kids_porch.png", t["done"], "done"),
         ("garden_wide.jpg", ACC, "now"),
         ("dog_run.jpg", MUT, "queued"),
         ("harbor_dusk.webp", MUT, "queued"),
         ("trail_morning.jpg", MUT, "queued")]
    yy = 138
    for name, col, st in q:
        active = st == "now"
        if active:
            b.append(rect(qx + 8, yy, W - qx - 48, 48, "#ffffff", rx=6, opacity=0.05))
        b.append(rect(qx + 18, yy + 8, 56, 32, t["thumb"], rx=3))
        b.append(rect(qx + 18, yy + 8, 56, 32, "none", rx=3, stroke=t["stroke"]))
        b.append(text(qx + 84, yy + 24, name, 13, TXT if active else MUT, font=MONO))
        b.append(circle(qx + 84, yy + 38, 3, col))
        b.append(text(qx + 96, yy + 42, st, 11, col))
        yy += 56

    # bottom transport bar
    by = 580
    b.append(rect(32, by, W - 64, 130, "url(#panel)", rx=6, stroke=t["stroke"]))
    b.append(text(56, by + 34, "RENDERING", 12, MUT, weight="bold", spacing=3))
    b.append(text(W - 56, by + 34, "07 / 20", 22, ACC, weight="bold", anchor="end"))
    b.append(rect(56, by + 48, W - 112, 8, t["track"], rx=4))
    b.append(rect(56, by + 48, (W - 112) * 0.35, 8, ACC, rx=4))
    chips = [("OUTPUT  same folder", 56), ("SUFFIX  _16x9", 296),
             ("MODEL  claude-opus-4-7", 470)]
    for s, x in chips:
        b.append(text(x, by + 92, s, 12, MUT, font=MONO))
    b.append(rect(W - 250, by + 74, 194, 38, ACC, rx=4))
    b.append(text(W - 153, by + 99, "EXPORT  16:9", 14, t["accent_ink"], weight="bold",
                  anchor="middle", spacing=1))
    # film strip
    fy2 = 736
    b.append(text(32, fy2, "RECENT", 11, MUT, weight="bold", spacing=3))
    for i in range(9):
        x = 32 + i * 104
        b.append(rect(x, fy2 + 14, 92, 116, t["panel1"], rx=3, stroke=t["stroke"]))
        b.append(rect(x + 8, fy2 + 22, 76, 60, t["thumb"], rx=2))
        b.append(text(x + 8, fy2 + 104, f"IMG_{2200+i}", 10, MUT, font=MONO))
        b.append(circle(x + 80, fy2 + 26, 4, t["done"] if i < 5 else MUT))
    return svg("".join(b), defs=defs)


# --- palettes ---------------------------------------------------------------

THEMES = {
    "a_amber_golden": dict(
        name="AMBER · GOLDEN HOUR", tag="DARKROOM",
        bg="#0e0f13", bar="#15171c", accent="#E8B04B", accent_ink="#1a1205",
        panel0="#1c1f26", panel1="#15171c", stroke="#262a33", track="#23262e",
        muted="#8a909c", thumb="#2b3340", done="#3aa657",
        sky0="#2b4a78", sky1="#c98a5e", sky2="#e8c39a", subject="#23303f",
        orb="#fbe9c9"),
    "b_ice_cyan": dict(
        name="ICE · GRAPHITE + CYAN", tag="STUDIO",
        bg="#0c0e11", bar="#14171b", accent="#48D6E6", accent_ink="#04181c",
        panel0="#181b21", panel1="#121419", stroke="#232a33", track="#1c2128",
        muted="#7e8693", thumb="#1d2530", done="#46c98a",
        sky0="#16243f", sky1="#37618c", sky2="#bcd3e6", subject="#152130",
        orb="#dff0f6"),
    "c_crimson_cinema": dict(
        name="CRIMSON · CINEMA", tag="CINEMA",
        bg="#0c0a0b", bar="#161012", accent="#F0484E", accent_ink="#1c0506",
        panel0="#1d1517", panel1="#140f10", stroke="#2c2023", track="#241a1c",
        muted="#988a8d", thumb="#2a1c1f", done="#3aa657",
        sky0="#2a1b3a", sky1="#7a2f3a", sky2="#e3a574", subject="#2a1418",
        orb="#f7dac0"),
    "d_safelight_analog": dict(
        name="SAFELIGHT · ANALOG", tag="ANALOG",
        bg="#120c0a", bar="#1a1210", accent="#FF6B45", accent_ink="#1c0703",
        panel0="#221813", panel1="#180f0c", stroke="#33231c", track="#291c16",
        muted="#a48d80", thumb="#2c1d15", done="#cf9a3a",
        sky0="#3a2230", sky1="#8a4a3a", sky2="#e6b88c", subject="#2a160f",
        orb="#ffd9b0"),
    "e_aurora_violet": dict(
        name="AURORA · TWILIGHT", tag="TWILIGHT",
        bg="#0b0c14", bar="#12131f", accent="#A48CFF", accent_ink="#0e0822",
        panel0="#181a28", panel1="#11121c", stroke="#25283a", track="#1c1e2c",
        muted="#828aa3", thumb="#1b1d2e", done="#5fd1b0",
        sky0="#1a1d3a", sky1="#5a4a8c", sky2="#cfa6d8", subject="#191a2e",
        orb="#ede0f7"),
}


if __name__ == "__main__":
    for key, theme in THEMES.items():
        path = OUT / f"{key}.png"
        cairosvg.svg2png(bytestring=darkroom(theme).encode(), write_to=str(path),
                         output_width=W * 2, output_height=H * 2)
        print("wrote", path)
    print("done")
