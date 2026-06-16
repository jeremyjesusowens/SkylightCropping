#!/usr/bin/env python3
"""
prompt_eval.py — Cheap, low-volume A/B test harness for FOCAL_POINT_PROMPT variants.

Runs each prompt variant against a small, fixed set of test photos — one API
call per (variant, image) pair, no repeats, no statistics — and saves a single
side-by-side comparison image per photo so you can eyeball which variant
crops best. Defaults to claude-haiku-4-5 to keep iteration cheap; once you
pick a winner, re-run it once with --model claude-opus-4-7 (or whatever
model production uses) to confirm it holds up before adopting it.

Usage
-----
  # Edit PROMPT_VARIANTS below to add wording you want to test, then:
  python prompt_eval.py photos/*.jpg
  python prompt_eval.py photos/ --variants baseline,tighter_box
  python prompt_eval.py photos/ --model claude-sonnet-4-6 --out eval_out/

Keep the test set small (5-8 photos covering single subject, group,
landscape, extremities, subject-near-edge) — cost scales as
images x variants, and that's the whole point of this script.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import anthropic
from PIL import Image, ImageDraw, ImageOps

from smart_crop import FOCAL_POINT_PROMPT, collect_images, encode_image

# Add alternate wordings here to test them against the current production
# prompt. Keys become the labels shown on each comparison image.
PROMPT_VARIANTS = {
    "baseline": FOCAL_POINT_PROMPT,
}

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def ask_claude(client: anthropic.Anthropic, image_path: Path, model: str, prompt_text: str) -> dict:
    data, media_type = encode_image(image_path)
    response = client.messages.create(
        model=model,
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}},
                {"type": "text", "text": prompt_text, "cache_control": {"type": "ephemeral"}},
            ],
        }],
    )
    text = response.content[0].text.strip()
    start, end = text.find("{"), text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON in response: {text!r}")
    return json.loads(text[start:end])


def draw_box(img: Image.Image, box_pct: tuple[float, float, float, float], label: str) -> Image.Image:
    w, h = img.size
    x1, y1, x2, y2 = box_pct
    px = (x1 / 100 * w, y1 / 100 * h, x2 / 100 * w, y2 / 100 * h)
    out = img.copy()
    draw = ImageDraw.Draw(out)
    draw.rectangle(px, outline="red", width=max(2, w // 200))
    draw.rectangle((0, 0, w, 22), fill="black")
    draw.text((4, 4), label, fill="white")
    return out


def make_thumb(image_path: Path, max_px: int = 640) -> Image.Image:
    with Image.open(image_path) as img:
        img = ImageOps.exif_transpose(img)
        img = img.copy()
        img.thumbnail((max_px, max_px), Image.LANCZOS)
        return img


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("inputs", nargs="+", help="Test image files or a directory of them.")
    parser.add_argument("--variants", help="Comma-separated subset of PROMPT_VARIANTS keys (default: all).")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Model to test with (default: {DEFAULT_MODEL}, cheapest for iteration).")
    parser.add_argument("--out", default="eval_out", help="Output directory for comparison images (default: eval_out/).")
    parser.add_argument("--yes", action="store_true", help="Skip the call-count confirmation prompt.")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("Error: ANTHROPIC_API_KEY environment variable is not set.")

    variant_names = args.variants.split(",") if args.variants else list(PROMPT_VARIANTS)
    for name in variant_names:
        if name not in PROMPT_VARIANTS:
            sys.exit(f"Unknown variant '{name}'. Available: {', '.join(PROMPT_VARIANTS)}")

    images = collect_images(args.inputs)
    if not images:
        sys.exit("No supported images found.")

    n_calls = len(images) * len(variant_names)
    print(f"{len(images)} image(s) x {len(variant_names)} variant(s) = {n_calls} API call(s) on {args.model}")
    if not args.yes and input("Proceed? [y/N] ").strip().lower() != "y":
        sys.exit("Aborted.")

    client = anthropic.Anthropic(api_key=api_key)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for img_path in images:
        print(f"\n{img_path.name}")
        panels = []
        for name in variant_names:
            thumb = make_thumb(img_path)
            try:
                data = ask_claude(client, img_path, args.model, PROMPT_VARIANTS[name])
                box = (float(data["x1"]), float(data["y1"]), float(data["x2"]), float(data["y2"]))
                label = f"{name}: {data.get('subject', '?')} (conf {data.get('confidence', '?')})"
                print(f"  {label}  box={box}")
                panels.append(draw_box(thumb, box, label))
            except Exception as exc:
                print(f"  {name}: FAILED ({exc})")
                panels.append(draw_box(thumb, (0, 0, 0, 0), f"{name}: ERROR"))

        total_w = sum(p.width for p in panels)
        max_h = max(p.height for p in panels)
        composite = Image.new("RGB", (total_w, max_h), "white")
        x = 0
        for p in panels:
            composite.paste(p, (x, 0))
            x += p.width
        out_path = out_dir / f"{img_path.stem}_compare.jpg"
        composite.save(out_path, quality=90)
        print(f"  -> {out_path}")

    print(f"\nDone. Open {out_dir}/ and compare each *_compare.jpg side by side.")


if __name__ == "__main__":
    main()
