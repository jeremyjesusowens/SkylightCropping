#!/usr/bin/env python3
"""
smart_crop.py — Smart 16:9 photo cropping and delivery tool.

Subcommands
-----------
  crop   Crop photos to 16:9 using Claude vision to preserve the subject.
  send   Email photos from a directory via SMTP (defaults to Yahoo Mail).

Examples
--------
  python smart_crop.py crop photo.jpg
  python smart_crop.py crop photos/ -o cropped/
  python smart_crop.py crop photos/ --dry-run

  python smart_crop.py send cropped/ --from you@yahoo.com
  python smart_crop.py send cropped/ --from you@yahoo.com --to other@example.com
"""

import argparse
import base64
import getpass
import io
import json
import os
import smtplib
import sys
import time
from dataclasses import dataclass
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Callable, Optional

import anthropic
from PIL import Image, ImageOps

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VERSION = "1.0.0"

TARGET_RATIO = 16 / 9
MAX_FILE_BYTES = 24 * 1024 * 1024  # 24 MB
SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

FOCAL_POINT_PROMPT = (
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
)

DEFAULT_TO = ""  # set your Skylight frame's email address in the app Settings
DEFAULT_SMTP_HOST = "smtp.mail.yahoo.com"
DEFAULT_SMTP_PORT = 587

LogFn = Callable[[str], None]
ProgressFn = Callable[[int, int], None]  # (completed, total)


@dataclass
class CropResult:
    """Structured per-image outcome, surfaced to callers (e.g. the GUI preview).

    Coordinates are in the original, EXIF-corrected image's pixel space.
    """
    path: str
    status: str  # "analyzing" | "cropped" | "dry_run" | "failed"
    width: Optional[int] = None
    height: Optional[int] = None
    focal: Optional[tuple[float, float]] = None        # (x_pct, y_pct) in [0,100]
    box: Optional[tuple[int, int, int, int]] = None    # (left, upper, right, lower)
    output_path: Optional[str] = None
    error: Optional[str] = None
    subject: Optional[str] = None                      # e.g. "alligator", "great blue heron"
    confidence: Optional[int] = None                   # Claude's confidence 0-100
    focal_box: Optional[tuple[float, float, float, float]] = None  # (x1,y1,x2,y2) pct from Claude
    output_size_bytes: Optional[int] = None
    compression_quality: Optional[int] = None          # None = no lossy compression applied
    crop_warning: Optional[str] = None                 # set when crop quality may be poor


ResultFn = Callable[["CropResult"], None]


def _noop_result(result: "CropResult") -> None:
    pass

# Used when no model list can be fetched from the API.
FALLBACK_MODELS = [
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
]


def _noop_progress(completed: int, total: int) -> None:
    pass


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def list_models(api_key: str) -> list[str]:
    """
    Return available Claude model IDs from the Anthropic API, newest first.
    Falls back to a built-in list if the request fails so the UI always has
    something to show.
    """
    try:
        client = anthropic.Anthropic(api_key=api_key)
        ids = [m.id for m in client.models.list(limit=100) if m.id.startswith("claude-")]
        return ids or list(FALLBACK_MODELS)
    except Exception:
        return list(FALLBACK_MODELS)


def collect_images(inputs: list[str], log: LogFn = print) -> list[Path]:
    paths: list[Path] = []
    for inp in inputs:
        p = Path(inp)
        if p.is_dir():
            for ext in SUPPORTED_EXTS:
                paths.extend(p.glob(f"*{ext}"))
                paths.extend(p.glob(f"*{ext.upper()}"))
        elif p.is_file():
            if p.suffix.lower() in SUPPORTED_EXTS:
                paths.append(p)
            else:
                log(f"Warning: unsupported format '{p.suffix}', skipping {p.name}")
        else:
            log(f"Warning: '{inp}' not found, skipping.")
    return sorted(set(paths))


def _print_failure_summary(failures: list[tuple[str, str]], total: int, verb: str) -> None:
    succeeded = total - len(failures)
    print(f"\n{verb}: {succeeded}/{total}")
    if failures:
        print(f"\nFailed ({len(failures)}):")
        for name, reason in failures:
            print(f"  {name}: {reason}")


# ---------------------------------------------------------------------------
# Cropping
# ---------------------------------------------------------------------------

# Claude's internal vision pipeline resamples to this size anyway, and the
# API rejects images over 5 MB. We downsample only the copy sent for analysis;
# the original file is still used for the actual crop so quality is unaffected.
_VISION_MAX_PX = 1568


def encode_image(path: Path) -> tuple[str, str]:
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        if max(img.size) > _VISION_MAX_PX:
            img = img.copy()
            img.thumbnail((_VISION_MAX_PX, _VISION_MAX_PX), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
    data = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
    return data, "image/jpeg"


def get_focal_point(
    client: anthropic.Anthropic, image_path: Path, model: str
) -> tuple[float, float, str, int, tuple[float, float, float, float]]:
    """Ask Claude where the main subject is.

    Returns (x_pct, y_pct, subject_description, confidence, (x1, y1, x2, y2))
    where x/y/bbox values are in [0, 100] and confidence is 0-100.
    """
    data, media_type = encode_image(image_path)
    response = client.messages.create(
        model=model,
        max_tokens=300,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": data,
                        },
                    },
                    {
                        "type": "text",
                        "text": FOCAL_POINT_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    },
                ],
            }
        ],
    )
    text = response.content[0].text.strip()
    start, end = text.find("{"), text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON in response: {text!r}")
    data_parsed = json.loads(text[start:end])
    subject = str(data_parsed.get("subject", "subject"))
    confidence = max(0, min(100, int(data_parsed.get("confidence", 80))))
    x1 = max(0.0, min(100.0, float(data_parsed["x1"])))
    y1 = max(0.0, min(100.0, float(data_parsed["y1"])))
    x2 = max(0.0, min(100.0, float(data_parsed["x2"])))
    y2 = max(0.0, min(100.0, float(data_parsed["y2"])))
    x = (x1 + x2) / 2
    y = (y1 + y2) / 2
    return x, y, subject, confidence, (x1, y1, x2, y2)


def compute_crop_box(
    img_w: int, img_h: int, fx_pct: float, fy_pct: float
) -> tuple[tuple[int, int, int, int], bool]:
    """Return ((left, upper, right, lower), clamped) for the largest 16:9 crop.

    clamped is True when the focal point was close enough to the frame edge that
    the crop had to slide, meaning the subject may not be well-centred in the output.
    """
    fx = fx_pct / 100 * img_w
    fy = fy_pct / 100 * img_h

    if img_w / img_h > TARGET_RATIO:
        crop_w = round(img_h * TARGET_RATIO)
        ideal_left = round(fx - crop_w / 2)
        left = max(0, min(ideal_left, img_w - crop_w))
        return (left, 0, left + crop_w, img_h), left != ideal_left
    else:
        crop_h = round(img_w / TARGET_RATIO)
        ideal_top = round(fy - crop_h / 2)
        top = max(0, min(ideal_top, img_h - crop_h))
        return (0, top, img_w, top + crop_h), top != ideal_top


def _crop_quality_warning(
    confidence: int,
    clamped: bool,
    focal_box: tuple[float, float, float, float],
    img_w: int,
    img_h: int,
) -> Optional[str]:
    """Return a short warning string if the crop may be poor, or None if it looks fine."""
    reasons = []
    if confidence < 60:
        reasons.append("low confidence")
    if clamped:
        reasons.append("subject near frame edge")
    x1, y1, x2, y2 = focal_box
    # Check whether the subject span leaves very little room in the cropping dimension.
    if img_w / img_h > TARGET_RATIO:
        if x2 - x1 > 75:
            reasons.append("subject fills frame width")
    else:
        if y2 - y1 > 75:
            reasons.append("subject fills frame height")
    return "; ".join(reasons) or None


def recrop_image(
    image_path: str,
    output_path: str,
    fx: float,
    fy: float,
    dry_run: bool = False,
    subject: Optional[str] = None,
) -> CropResult:
    """Re-crop with a user-adjusted target point without calling the API."""
    with Image.open(image_path) as img:
        img = ImageOps.exif_transpose(img)
        w, h = img.size
        box, _ = compute_crop_box(w, h, fx, fy)
        if not dry_run:
            cropped = img.crop(box)
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            suffix = Path(image_path).suffix.lower()
            save_kwargs: dict = {}
            if suffix in (".jpg", ".jpeg"):
                save_kwargs = {"quality": 95, "optimize": True}
            cropped.save(out, **save_kwargs)
    return CropResult(
        path=image_path,
        status="dry_run" if dry_run else "cropped",
        width=w, height=h,
        focal=(fx, fy), box=box,
        output_path=output_path,
        subject=subject,
    )


def _encode(img: Image.Image, fmt: str, **kwargs) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt, **kwargs)
    return buf.getvalue()


def _downscale_to_fit(img: Image.Image, fmt: str, save_kwargs: dict, log: LogFn = print) -> bytes:
    current = _encode(img, fmt, **save_kwargs)
    w, h = img.size
    scale = (MAX_FILE_BYTES / len(current)) ** 0.5 * 0.90
    while True:
        new_w, new_h = max(1, round(w * scale)), max(1, round(h * scale))
        data = _encode(img.resize((new_w, new_h), Image.LANCZOS), fmt, **save_kwargs)
        if len(data) <= MAX_FILE_BYTES:
            log(f"  Downscaled to {new_w}x{new_h} to meet 24 MB limit")
            return data
        scale *= 0.85


def _fit_with_quality(
    img: Image.Image, fmt: str, base_kwargs: dict, log: LogFn = print
) -> tuple[bytes, int]:
    data = _encode(img, fmt, quality=95, **base_kwargs)
    if len(data) <= MAX_FILE_BYTES:
        return data, 95

    lo, hi, best_data, best_q = 1, 94, None, 1
    while lo <= hi:
        mid = (lo + hi) // 2
        data = _encode(img, fmt, quality=mid, **base_kwargs)
        if len(data) <= MAX_FILE_BYTES:
            best_q, best_data, lo = mid, data, mid + 1
        else:
            hi = mid - 1

    if best_data is None:
        best_data = _downscale_to_fit(img, fmt, {"quality": 1, **base_kwargs}, log=log)
        best_q = 1

    return best_data, best_q


def save_compressed(
    img: Image.Image, output_path: Path, suffix: str, log: LogFn = print
) -> tuple[int, Optional[int]]:
    """Save img compressed to fit within MAX_FILE_BYTES.

    Returns (size_bytes, quality) where quality is None for lossless formats.
    quality=95 means no lossy reduction was needed; lower values were applied to meet the limit.
    """
    ext = suffix.lower()

    if ext in {".jpg", ".jpeg"}:
        data, quality = _fit_with_quality(img, "JPEG", {"subsampling": 0}, log=log)
        output_path.write_bytes(data)
        log(f"  Compressed to {len(data) / 1024 / 1024:.1f} MB (JPEG, quality {quality})")
        return len(data), quality

    elif ext == ".webp":
        data, quality = _fit_with_quality(img, "WEBP", {}, log=log)
        output_path.write_bytes(data)
        log(f"  Compressed to {len(data) / 1024 / 1024:.1f} MB (WebP, quality {quality})")
        return len(data), quality

    elif ext == ".png":
        data = _encode(img, "PNG", compress_level=9)
        if len(data) > MAX_FILE_BYTES:
            data = _downscale_to_fit(img, "PNG", {"compress_level": 9}, log=log)
        output_path.write_bytes(data)
        log(f"  Compressed to {len(data) / 1024 / 1024:.1f} MB (PNG)")
        return len(data), None

    else:
        img.save(output_path)
        size = output_path.stat().st_size
        label = f"{size / 1024 / 1024:.1f} MB"
        if size > MAX_FILE_BYTES:
            log(f"  Saved at {label} (warning: exceeds 24 MB — this format can't be compressed further)")
        else:
            log(f"  Saved at {label}")
        return size, None


def process_image(
    client: anthropic.Anthropic,
    image_path: Path,
    output_path: Path,
    model: str,
    dry_run: bool,
    log: LogFn = print,
    index: int | None = None,
    total: int | None = None,
) -> CropResult:
    """Crop a single image. Raises on any failure — no silent fallbacks.

    Returns a CropResult describing the focal point and 16:9 box (in the
    original image's pixel space) so callers can preview the crop.
    """
    header = f"[{index}/{total}] {image_path.name}" if index and total else image_path.name
    log(f"\n{header}")

    log("  Analyzing with Claude to find the subject…")
    fx, fy, subject, confidence, focal_box = get_focal_point(client, image_path, model)
    log(f"  Subject: {subject} — target at {fx:.0f}% across, {fy:.0f}% down (confidence: {confidence})")

    with Image.open(image_path) as img:
        img = ImageOps.exif_transpose(img)
        w, h = img.size
        box, clamped = compute_crop_box(w, h, fx, fy)
        crop_w, crop_h = box[2] - box[0], box[3] - box[1]
        warning = _crop_quality_warning(confidence, clamped, focal_box, w, h)
        if warning:
            log(f"  ⚠ Crop quality note: {warning}")

        if dry_run:
            log(f"  Would crop {w}×{h} → {crop_w}×{crop_h} (16:9) — dry run, nothing written")
            return CropResult(path=str(image_path), status="dry_run", width=w, height=h,
                              focal=(fx, fy), box=box, output_path=str(output_path),
                              subject=subject, confidence=confidence, focal_box=focal_box,
                              crop_warning=warning)

        log(f"  Cropping {w}×{h} → {crop_w}×{crop_h} (16:9)")
        cropped = img.crop(box)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    size_bytes, quality = save_compressed(cropped, output_path, image_path.suffix, log=log)
    log(f"  ✓ Saved as {output_path.name}")
    return CropResult(path=str(image_path), status="cropped", width=w, height=h,
                      focal=(fx, fy), box=box, output_path=str(output_path),
                      subject=subject, confidence=confidence, focal_box=focal_box,
                      output_size_bytes=size_bytes, compression_quality=quality,
                      crop_warning=warning)


# ---------------------------------------------------------------------------
# Public API (used by both CLI and GUI)
# ---------------------------------------------------------------------------

def run_crop(
    inputs: list[str],
    output_dir: str | None,
    suffix: str,
    model: str,
    dry_run: bool,
    api_key: str,
    log_fn: LogFn = print,
    progress_fn: ProgressFn = _noop_progress,
    result_fn: ResultFn = _noop_result,
) -> tuple[list[tuple[str, str]], int]:
    """
    Crop images to 16:9. Returns (failures, total) where failures is a list
    of (filename, error_message) tuples for images that could not be cropped.

    result_fn is called with a CropResult as each image is processed: once with
    status="analyzing" when it starts, then with the final outcome ("cropped",
    "dry_run", or "failed"). This lets a UI preview each crop as the batch runs.
    """
    client = anthropic.Anthropic(api_key=api_key)
    images = collect_images(inputs, log=log_fn)
    if not images:
        log_fn("No supported images found.")
        progress_fn(0, 0)
        return [], 0

    total = len(images)
    mode = " — dry run" if dry_run else ""
    log_fn(f"Cropping {total} photo(s) with {model}{mode}")
    progress_fn(0, total)
    failures: list[tuple[str, str]] = []

    for i, img_path in enumerate(images, start=1):
        out_path = (
            Path(output_dir) / (img_path.stem + suffix + img_path.suffix)
            if output_dir
            else img_path.parent / (img_path.stem + suffix + img_path.suffix)
        )
        result_fn(CropResult(path=str(img_path), status="analyzing"))
        try:
            result = process_image(client, img_path, out_path, model, dry_run,
                                   log=log_fn, index=i, total=total)
        except anthropic.AuthenticationError:
            msg = "Invalid API key — verify your key at console.anthropic.com"
            log_fn(f"  ✗ {msg}")
            result_fn(CropResult(path=str(img_path), status="failed", error=msg))
            failures.extend((img.name, msg) for img in images[i - 1:])
            break  # no point continuing with an invalid key
        except Exception as exc:
            log_fn(f"  ✗ Failed: {exc}")
            failures.append((img_path.name, str(exc)))
            result_fn(CropResult(path=str(img_path), status="failed", error=str(exc)))
        else:
            result_fn(result)
        progress_fn(i, total)

    return failures, total


def _send_one(
    img_path: Path,
    from_addr: str,
    to_addr: str,
    smtp_host: str,
    smtp_port: int,
    password: str,
    log_fn: LogFn,
    max_retries: int,
    retry_delay: int,
) -> str | None:
    """
    Send one photo. Returns None on success, or an error string on permanent failure.
    Raises SMTPAuthenticationError immediately so the caller can abort the batch.
    Retries up to max_retries times on transient errors, waiting retry_delay seconds
    between attempts and logging a countdown so the UI stays informative.
    """
    size_mb = img_path.stat().st_size / 1024 / 1024

    for attempt in range(max_retries):
        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(from_addr, password)
                log_fn(f"  Connecting to mail server and sending ({size_mb:.1f} MB)…")
                server.sendmail(from_addr, [to_addr], _build_email(from_addr, to_addr, img_path).as_bytes())
            log_fn("  ✓ Sent")
            return None

        except smtplib.SMTPAuthenticationError:
            raise  # Caller handles this — no point retrying bad credentials

        except (smtplib.SMTPException, ConnectionRefusedError, OSError) as exc:
            if attempt < max_retries - 1:
                log_fn(f"  Hit a problem: {exc}")
                log_fn(f"  Waiting {retry_delay}s before retry {attempt + 2} of {max_retries}…")
                # Log countdown every 15 s so the UI doesn't look frozen
                for remaining in range(retry_delay, 0, -15):
                    time.sleep(min(15, remaining))
                    if remaining > 15:
                        log_fn(f"  Retrying in {remaining - 15}s...")
            else:
                return str(exc)

    return "Max retries exceeded"


def run_send(
    directory: str,
    from_addr: str,
    to_addr: str,
    smtp_host: str,
    smtp_port: int,
    password: str,
    log_fn: LogFn = print,
    max_retries: int = 3,
    retry_delay: int = 90,
    progress_fn: ProgressFn = _noop_progress,
) -> tuple[list[tuple[str, str]], int]:
    """
    Email each photo in directory as an individual attachment.
    Opens a fresh SMTP connection per photo to avoid server-side session
    timeouts on large batches. Retries on transient errors after retry_delay
    seconds, up to max_retries attempts per photo.
    Returns (failures, total) where failures is a list of (filename, error_message).
    """
    images = collect_images([directory], log=log_fn)
    if not images:
        log_fn("No supported images found.")
        progress_fn(0, 0)
        return [], 0

    total = len(images)
    log_fn(
        f"Sending {total} photo(s)\n"
        f"  From: {from_addr}\n"
        f"  To:   {to_addr}\n"
        f"  Via:  {smtp_host}:{smtp_port}  (up to {max_retries} tries each)"
    )
    progress_fn(0, total)
    failures: list[tuple[str, str]] = []

    for i, img_path in enumerate(images, start=1):
        log_fn(f"\n[{i}/{total}] {img_path.name}")
        try:
            error = _send_one(
                img_path, from_addr, to_addr, smtp_host, smtp_port,
                password, log_fn, max_retries, retry_delay,
            )
            if error:
                log_fn(f"  ✗ Gave up after {max_retries} attempt(s): {error}")
                failures.append((img_path.name, error))

        except smtplib.SMTPAuthenticationError:
            log_fn(
                "ERROR: Authentication failed.\n"
                "For Yahoo Mail, use an App Password, not your account password.\n"
                "Generate one at: myaccount.yahoo.com → Security → App passwords"
            )
            failures.extend((img.name, "Authentication failed") for img in images[i - 1:])
            break
        progress_fn(i, total)

    return failures, total


# ---------------------------------------------------------------------------
# Email helper
# ---------------------------------------------------------------------------

def _build_email(from_addr: str, to_addr: str, img_path: Path) -> MIMEMultipart:
    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = img_path.name

    with open(img_path, "rb") as f:
        part = MIMEBase("image", "*")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", "attachment", filename=img_path.name)
    msg.attach(part)
    return msg


# ---------------------------------------------------------------------------
# CLI entry points
# ---------------------------------------------------------------------------

def cmd_crop(args: argparse.Namespace) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("Error: ANTHROPIC_API_KEY environment variable is not set.")
    failures, total = run_crop(
        args.inputs, args.output_dir, args.suffix, args.model, args.dry_run, api_key
    )
    _print_failure_summary(failures, total, "Cropped")


def cmd_send(args: argparse.Namespace) -> None:
    password = args.smtp_password or os.environ.get("SMTP_PASSWORD")
    if not password:
        password = getpass.getpass(f"SMTP password for {args.from_addr}: ")
    failures, total = run_send(
        args.directory, args.from_addr, args.to_addr, args.smtp_host, args.smtp_port, password
    )
    _print_failure_summary(failures, total, "Sent")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # -- crop -----------------------------------------------------------------
    p_crop = sub.add_parser(
        "crop",
        help="Crop photos to 16:9 using Claude vision.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_crop.add_argument("inputs", nargs="+", metavar="IMAGE_OR_DIR",
                        help="Image files or directories to process.")
    p_crop.add_argument("-o", "--output-dir", metavar="DIR",
                        help="Write output files here (default: alongside each source).")
    p_crop.add_argument("--suffix", default="_16x9",
                        help="Suffix before the extension (default: _16x9).")
    p_crop.add_argument("--model", default="claude-opus-4-7",
                        help="Claude model for analysis (default: claude-opus-4-7).")
    p_crop.add_argument("--dry-run", action="store_true",
                        help="Print crop boxes without writing files.")
    p_crop.set_defaults(func=cmd_crop)

    # -- send -----------------------------------------------------------------
    p_send = sub.add_parser(
        "send",
        help="Email photos from a directory via SMTP (defaults to Yahoo Mail).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Sends each photo as an individual email attachment.\n\n"
            "Defaults to Yahoo Mail (smtp.mail.yahoo.com:587).\n"
            "Yahoo requires an App Password — not your Yahoo account password.\n"
            "Generate one at: myaccount.yahoo.com → Security → App passwords\n\n"
            "Set SMTP_PASSWORD in your environment to avoid the password prompt."
        ),
    )
    p_send.add_argument("directory", metavar="DIR",
                        help="Directory of photos to send.")
    p_send.add_argument("--from", dest="from_addr", required=True, metavar="ADDRESS",
                        help="Sender email address.")
    p_send.add_argument("--to", dest="to_addr", default=DEFAULT_TO, metavar="ADDRESS",
                        help=f"Recipient address (default: {DEFAULT_TO}).")
    p_send.add_argument("--smtp-host", default=DEFAULT_SMTP_HOST,
                        help=f"SMTP host (default: {DEFAULT_SMTP_HOST}).")
    p_send.add_argument("--smtp-port", type=int, default=DEFAULT_SMTP_PORT,
                        help=f"SMTP port (default: {DEFAULT_SMTP_PORT}).")
    p_send.add_argument("--smtp-password", default=None, metavar="PASSWORD",
                        help="SMTP password. Prefer SMTP_PASSWORD env var.")
    p_send.set_defaults(func=cmd_send)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
