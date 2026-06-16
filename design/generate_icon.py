#!/usr/bin/env python3
"""Generate the app icon (aperture mark on dark tile) as PNG and ICO.

Run:  python design/generate_icon.py
Out:  assets/icon.png   – master 512×512 (also used by macOS iconphoto)
      assets/icon.ico   – multi-size Windows icon
"""

import io
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).parent.parent / "assets"
OUT.mkdir(parents=True, exist_ok=True)

BG     = (11, 12, 20, 255)       # #0b0c14
ACCENT = (164, 140, 255, 255)    # #A48CFF
ACCENT_DIM = (164, 140, 255, 160)

MASTER = 512   # render at 4× for supersampling
SS     = 4     # supersample factor
RENDER = MASTER * SS


def _draw_aperture(draw: ImageDraw.ImageDraw, cx, cy, r, sw, blade_w):
    """Draw the 6-blade aperture mark at (cx, cy) with ring radius r."""
    # Outer ring
    draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                 outline=ACCENT, width=sw)

    # 6 blades
    for k in range(6):
        a0 = math.radians(60 * k)
        a1 = math.radians(60 * k + 40)
        x1 = cx + r * math.cos(a0)
        y1 = cy + r * math.sin(a0)
        x2 = cx + r * 0.30 * math.cos(a1)
        y2 = cy + r * 0.30 * math.sin(a1)
        draw.line([(x1, y1), (x2, y2)], fill=ACCENT, width=blade_w)

    # Center dot
    dot_r = r * 0.09
    draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r],
                 fill=ACCENT)


def create_icon(size: int) -> Image.Image:
    ss = size * SS
    img = Image.new("RGBA", (ss, ss), BG)
    draw = ImageDraw.Draw(img)

    cx = cy = ss / 2
    r  = ss * 0.34
    sw  = max(2, int(ss * 0.025))
    bw  = max(2, int(ss * 0.019))

    # Soft glow behind the ring
    glow = Image.new("RGBA", (ss, ss), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gr = int(r * 1.12)
    gd.ellipse([cx - gr, cy - gr, cx + gr, cy + gr],
               outline=(164, 140, 255, 60), width=int(ss * 0.06))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=int(ss * 0.04)))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    _draw_aperture(draw, cx, cy, r, sw, bw)

    # Downsample for antialiasing
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    master = create_icon(MASTER)
    master_path = OUT / "icon.png"
    master.save(master_path, "PNG")
    print(f"wrote {master_path}")

    # ICO — Windows multi-size
    ico_sizes = [256, 128, 64, 48, 32, 16]
    frames = [create_icon(s) for s in ico_sizes]
    ico_path = OUT / "icon.ico"
    frames[0].save(
        ico_path, format="ICO",
        sizes=[(s, s) for s in ico_sizes],
        append_images=frames[1:],
    )
    print(f"wrote {ico_path}")
    print("done")
