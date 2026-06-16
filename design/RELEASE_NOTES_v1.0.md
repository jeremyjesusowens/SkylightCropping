# Skylight Cropping v1.0

**AI-powered 16:9 photo cropping for Windows and macOS.**
No centre-crops — Claude finds your subject, you get the frame.

---

## Why I built this

Skylight frames don't cleanly display 16:9 photos
unless you give them a *mix* of aspect ratios to arrange together. My photos all
come from a Micro Four Thirds camera (a 4:3 sensor), so every shot needs cropping
to 16:9 before it looks right on the frame. Doing that by hand for hundreds of
bird and wildlife photos — and framing the subject well each time — was tedious,
so I automated it. Claude looks at each photo, finds the subject, and crops to a
clean 16:9 that keeps the animal in frame.

---

## Highlights

**Smart subject detection.** Claude identifies the primary subject
(*"great blue heron"*, *"blue dragonfly"*), draws a bounding box around its body
mass — excluding extremities like beaks, tails, and wingtips — and targets the
geometric centre. The crop frames the animal, not its beak tip. No silent
fallback to centre-cropping: if Claude can't find a subject, the photo is skipped
and reported.

**One-click target adjustment.** Click anywhere on the preview to move the target
point. The crop box updates instantly and the file re-saves in the background —
no re-analysing, no extra API call.

**Live, persistent preview.** Watch each crop happen — target crosshair, 16:9 box,
dimmed surroundings, rule-of-thirds grid. Every result is stored per-image, so you
can click back through the queue to review any crop after a batch finishes.

**Batch processing & email delivery.** Add files or whole folders with live
progress tracking. The Send tab emails each cropped photo individually — handy
for pushing straight to a Skylight frame. Uses Yahoo Mail by default: after
testing several providers, Yahoo proved the most consistent with the least
aggressive rate limiting and filtering. SMTP host and port are configurable.

**Dry run mode.** Preview every crop box without writing a file.

---

## Getting started

1. Download `SkylightCropping.exe` (Windows) or `SkylightCropping` (macOS) from
   the **Assets** below — no install, just run it.
2. Open the **Settings** tab and paste your
   [Anthropic API key](https://console.anthropic.com). Email credentials are
   optional (only needed for the Send tab).
3. Add photos on the **Crop** tab and hit **Crop Photos**.

`claude-opus-4-7` gives the most reliable targeting; `claude-sonnet-4-6` is
cheaper and works well too — and one-click adjust makes any miss trivial to fix.

---

## Supported formats

JPEG · PNG · WebP · GIF
