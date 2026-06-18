#!/usr/bin/env python3
"""
rate_photos.py — Cheap, fast AI photo rating and feedback.

Deliberately separate from smart_crop.py's cropping pipeline. This is about
getting a fun rating + one-line feedback on lots of photos as cheaply as
possible, not pixel-precise subject detection — so it leans hard on
cost-saving choices:

  * Haiku by default — the cheapest current Claude model.
  * Smaller image payload than the cropper sends (rating doesn't need fine
    detail), which directly shrinks vision input tokens.
  * Tiny max_tokens — the response is a single small JSON object.
  * A persistent on-disk cache keyed by (path, size, mtime, model) so a photo
    is never re-rated (and never re-billed) unless it actually changed or the
    user explicitly asks for a re-rate.
"""

import base64
import io
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import anthropic
from PIL import Image, ImageOps

from smart_crop import collect_images

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Kept well below the cropper's 1568px — a rating/feedback judgment doesn't
# need fine detail, and fewer pixels means fewer (billed) vision tokens.
_RATE_VISION_MAX_PX = 896

# Cheapest-first so the default selection is the cost-effective one.
RATE_MODELS = [
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
    "claude-opus-4-7",
]
DEFAULT_RATE_MODEL = RATE_MODELS[0]

RATE_PROMPT = (
    "You are a fun, encouraging photography critic rating a personal photo for a "
    "digital picture frame slideshow. Judge composition, lighting, emotional impact, "
    "subject/moment, and technical quality.\n\n"
    "Return ONLY a JSON object, no explanation. Include both a short version for a "
    "compact list view and a longer breakdown for a detail view someone can open by "
    "clicking the photo:\n"
    '{"score": <integer 0-100, overall appeal>, '
    '"headline": "<punchy 2-4 word verdict, e.g. \'Pure Magic\' or \'Solid Snapshot\'>", '
    '"feedback": "<one specific, encouraging sentence, max 20 words, for the list view>", '
    '"tags": [<1-3 short lowercase strengths, e.g. \'composition\', \'lighting\', \'candid moment\'>], '
    '"summary": "<2-3 sentence expanded review for the detail view>", '
    '"categories": ['
    '{"name": "Composition", "score": <0-100>, "comment": "<one sentence>"}, '
    '{"name": "Lighting", "score": <0-100>, "comment": "<one sentence>"}, '
    '{"name": "Subject & Moment", "score": <0-100>, "comment": "<one sentence>"}, '
    '{"name": "Technical Quality", "score": <0-100>, "comment": "<one sentence>"}'
    '], '
    '"tip": "<one specific, actionable suggestion for an even better shot next time>"}'
)

_SETTINGS_DIR = (
    Path.home() / "Library" / "Application Support" / "SkylightCropping"
    if sys.platform == "darwin"
    else Path.home() / ".skylight_cropping"
)
RATINGS_CACHE_FILE = _SETTINGS_DIR / "ratings_cache.json"

LogFn = Callable[[str], None]
ProgressFn = Callable[[int, int], None]


@dataclass
class RatingResult:
    """Per-photo outcome, surfaced to callers (e.g. the GUI gallery)."""
    path: str
    status: str  # "analyzing" | "rated" | "failed"
    score: Optional[int] = None
    headline: Optional[str] = None
    feedback: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    # In-depth fields, shown in a detail view opened by clicking the photo.
    # Fetched in the same API call as the list-view fields above, so the
    # extra detail doesn't cost a second request.
    summary: Optional[str] = None
    categories: list[dict] = field(default_factory=list)  # [{"name", "score", "comment"}]
    tip: Optional[str] = None
    error: Optional[str] = None
    cached: bool = False  # True when served from the local cache (no API call)


ResultFn = Callable[[RatingResult], None]


def _noop_result(result: RatingResult) -> None:
    pass


def _noop_progress(done: int, total: int) -> None:
    pass


def score_tier(score: int) -> str:
    """Bucket a 0-100 score into a display tier name."""
    if score >= 85:
        return "stunning"
    if score >= 70:
        return "great"
    if score >= 50:
        return "good"
    return "meh"


# ---------------------------------------------------------------------------
# Cache — avoids re-billing the API for a photo that's already been rated.
# ---------------------------------------------------------------------------

def load_cache() -> dict:
    if RATINGS_CACHE_FILE.exists():
        try:
            return json.loads(RATINGS_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cache(cache: dict) -> None:
    # Written after every rated photo (so a crash mid-run loses as little
    # progress/spend as possible), so this must be atomic — a partial write
    # to the real path would corrupt the whole cache, not just the latest
    # entry.
    RATINGS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = RATINGS_CACHE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    os.replace(tmp, RATINGS_CACHE_FILE)


def _cache_key(path: Path, model: str) -> str:
    st = path.stat()
    return f"{path}|{st.st_size}|{int(st.st_mtime)}|{model}"


def _cache_entry_to_result(path: str, entry: dict) -> RatingResult:
    # .get() with defaults so ratings cached before the detail fields existed
    # still load fine — they just show no detail view until re-rated.
    return RatingResult(
        path=path, status="rated", score=entry["score"], headline=entry["headline"],
        feedback=entry["feedback"], tags=list(entry.get("tags", [])),
        summary=entry.get("summary"), categories=list(entry.get("categories", [])),
        tip=entry.get("tip"), cached=True,
    )


# ---------------------------------------------------------------------------
# Rating
# ---------------------------------------------------------------------------

def _encode_for_rating(path: Path) -> tuple[str, str]:
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        if max(img.size) > _RATE_VISION_MAX_PX:
            img = img.copy()
            img.thumbnail((_RATE_VISION_MAX_PX, _RATE_VISION_MAX_PX), Image.LANCZOS)
        buf = io.BytesIO()
        # Modest quality — still plenty for a quick aesthetic judgment and
        # noticeably smaller than the cropper's quality=85 payload.
        img.save(buf, format="JPEG", quality=75)
    data = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
    return data, "image/jpeg"


def get_rating(client: anthropic.Anthropic, image_path: Path, model: str) -> dict:
    """Ask Claude for a score/headline/feedback/tags JSON blob for one photo."""
    data, media_type = _encode_for_rating(image_path)
    response = client.messages.create(
        model=model,
        max_tokens=600,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": data},
                    },
                    {
                        "type": "text",
                        "text": RATE_PROMPT,
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
    parsed = json.loads(text[start:end])
    score = max(0, min(100, int(parsed.get("score", 50))))
    headline = str(parsed.get("headline", "")).strip() or "Nice Shot"
    feedback = str(parsed.get("feedback", "")).strip()
    tags = [str(t).strip().lower() for t in parsed.get("tags", []) if str(t).strip()][:3]
    summary = str(parsed.get("summary", "")).strip()
    categories = []
    for c in parsed.get("categories", [])[:6]:
        if not isinstance(c, dict):
            continue
        try:
            categories.append({
                "name": str(c.get("name", "")).strip() or "Category",
                "score": max(0, min(100, int(c.get("score", score)))),
                "comment": str(c.get("comment", "")).strip(),
            })
        except (TypeError, ValueError):
            continue
    tip = str(parsed.get("tip", "")).strip()
    return {
        "score": score, "headline": headline, "feedback": feedback, "tags": tags,
        "summary": summary, "categories": categories, "tip": tip,
    }


def run_rate(
    inputs: list[str],
    model: str,
    api_key: str,
    force: bool = False,
    log_fn: LogFn = print,
    progress_fn: ProgressFn = _noop_progress,
    result_fn: ResultFn = _noop_result,
) -> tuple[list[tuple[str, str]], int]:
    """
    Rate each photo in inputs. Returns (failures, total).

    Photos already present in the on-disk cache (unchanged size/mtime, same
    model) are served from cache with zero API calls unless force=True. This
    is the main cost lever: re-running on a large library you've already
    rated costs nothing.
    """
    client = anthropic.Anthropic(api_key=api_key)
    images = collect_images(inputs, log=log_fn)
    if not images:
        log_fn("No supported images found.")
        progress_fn(0, 0)
        return [], 0

    cache = load_cache()
    total = len(images)
    log_fn(f"Rating {total} photo(s) with {model}")
    progress_fn(0, total)
    failures: list[tuple[str, str]] = []

    for i, img_path in enumerate(images, start=1):
        key = _cache_key(img_path, model)
        result_fn(RatingResult(path=str(img_path), status="analyzing"))

        if not force and key in cache:
            result = _cache_entry_to_result(str(img_path), cache[key])
            log_fn(f"[{i}/{total}] {img_path.name} — cached, no API call ({result.score}/100)")
            result_fn(result)
            progress_fn(i, total)
            continue

        try:
            data = get_rating(client, img_path, model)
        except anthropic.AuthenticationError:
            msg = "Invalid API key — verify your key at console.anthropic.com"
            log_fn(f"  ✗ {msg}")
            result_fn(RatingResult(path=str(img_path), status="failed", error=msg))
            failures.extend((img.name, msg) for img in images[i - 1:])
            break
        except Exception as exc:
            log_fn(f"[{i}/{total}] {img_path.name} — ✗ failed: {exc}")
            failures.append((img_path.name, str(exc)))
            result_fn(RatingResult(path=str(img_path), status="failed", error=str(exc)))
        else:
            cache[key] = data
            save_cache(cache)
            log_fn(f"[{i}/{total}] {img_path.name} — {data['score']}/100 \"{data['headline']}\"")
            result_fn(RatingResult(
                path=str(img_path), status="rated", score=data["score"],
                headline=data["headline"], feedback=data["feedback"], tags=data["tags"],
                summary=data["summary"], categories=data["categories"], tip=data["tip"],
            ))
        progress_fn(i, total)

    return failures, total


def clear_cache() -> None:
    save_cache({})
