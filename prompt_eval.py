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

    # Centering on the raw bounding box midpoint can crowd a subject that is
    # facing or moving in a clear direction. This asks Claude to bias the box
    # toward the subject's back so the final crop leaves room ahead of it.
    "lead_room": (
        "This photo will be cropped to a 16:9 aspect ratio for a digital picture frame. "
        "Your job is to identify the best center point for that crop.\n\n"
        "Step 1 — Identify the PRIMARY SUBJECT: the single animal, person, or object "
        "the viewer's eye is drawn to first. If the image is a pure landscape with no "
        "clear subject, use the most visually interesting area.\n\n"
        "Step 2 — Draw an imaginary tight bounding box around that subject's PRIMARY BODY MASS only. "
        "Deliberately EXCLUDE extremities that extend far from the body: "
        "do NOT include beaks, bills, tails, wingtips, outstretched legs, feet, antlers, "
        "fins, or any thin appendage that projects away from the torso. "
        "Only the core torso (and head when it is close to the torso).\n\n"
        "Step 2.5 — If the subject is clearly facing or moving in one direction, shift the "
        "box 10-15% of its width AWAY from that direction (toward the subject's back), so the "
        "crop leaves breathing room in front of it instead of crowding the frame edge it's "
        "heading toward.\n\n"
        "Step 3 — Rate your confidence (0-100) that the bounding box will produce a "
        "well-composed 16:9 crop. Give a LOW score if: the subject is very close to the "
        "frame edge, the subject fills nearly the entire image leaving no crop flexibility, "
        "there is no clear primary subject, or the subject's most compelling feature "
        "(e.g. a bird's full wingspan in flight) cannot be captured without extremities.\n\n"
        "Step 4 — Return ONLY a JSON object with no explanation:\n"
        '{"subject": "<brief description e.g. alligator, great blue heron>", '
        '"x1": <left edge of box, 0-100>, "y1": <top edge of box, 0-100>, '
        '"x2": <right edge of box, 0-100>, "y2": <bottom edge of box, 0-100>, '
        '"confidence": <0-100>}\n\n'
        "All coordinate values are percentages of image dimensions."
    ),

    # Trims the baseline's repetition to test whether a shorter (cheaper,
    # faster) prompt holds the same quality.
    "concise": (
        "Find the best 16:9 crop center for this digital-frame photo.\n\n"
        "1. Identify the primary subject (the thing the eye is drawn to first; for a "
        "landscape with no clear subject, use the most visually interesting area).\n"
        "2. Draw a tight box around its core body mass only — exclude beaks, tails, "
        "outstretched limbs, wingtips, or anything projecting away from the torso.\n"
        "3. Confidence 0-100: score low if the subject is near an edge, fills the frame, "
        "is unclear, or its key feature (e.g. a full wingspan) needs an excluded extremity.\n\n"
        "Return ONLY this JSON, no explanation:\n"
        '{"subject": "<brief description>", "x1": <0-100>, "y1": <0-100>, '
        '"x2": <0-100>, "y2": <0-100>, "confidence": <0-100>}'
    ),

    # The baseline forces a single subject, which is ambiguous for group
    # photos — a common case for a family picture frame.
    "multi_subject": (
        "This photo will be cropped to a 16:9 aspect ratio for a digital picture frame. "
        "Your job is to identify the best center point for that crop.\n\n"
        "Step 1 — Identify the PRIMARY SUBJECT(S): the animal(s), person(s), or object "
        "the viewer's eye is drawn to first. If there are several people or animals "
        "clearly grouped together (e.g. a family, a couple, a small herd), treat them as "
        "ONE subject and box the whole group. If the image is a pure landscape with no "
        "clear subject, use the most visually interesting area.\n\n"
        "Step 2 — Draw an imaginary tight bounding box around the subject's (or group's) "
        "PRIMARY BODY MASS only. Deliberately EXCLUDE extremities that extend far from the "
        "body: do NOT include beaks, bills, tails, wingtips, outstretched legs, feet, "
        "antlers, fins, or any thin appendage that projects away from the torso. Only the "
        "core torso (and head when close to the torso) of each member of the group.\n\n"
        "Step 3 — Rate your confidence (0-100) that the bounding box will produce a "
        "well-composed 16:9 crop. Give a LOW score if: the subject is very close to the "
        "frame edge, the subject(s) fill nearly the entire image leaving no crop "
        "flexibility, there is no clear primary subject, group members are too spread out "
        "to box tightly together, or the subject's most compelling feature (e.g. a bird's "
        "full wingspan in flight) cannot be captured without extremities.\n\n"
        "Step 4 — Return ONLY a JSON object with no explanation:\n"
        '{"subject": "<brief description e.g. \'family of four\', great blue heron>", '
        '"x1": <left edge of box, 0-100>, "y1": <top edge of box, 0-100>, '
        '"x2": <right edge of box, 0-100>, "y2": <bottom edge of box, 0-100>, '
        '"confidence": <0-100>}\n\n'
        "All coordinate values are percentages of image dimensions."
    ),
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
