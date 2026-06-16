# Skylight Cropping — UI redesign mockups

Four exploratory directions for redesigning the desktop app, each shown as a
redesign of the main **Crop** screen (file queue, options, crop CTA, and the
progress/activity-log footer). These are visual concepts for iteration — not
yet wired to the app.

| # | Style | Vibe |
|---|-------|------|
| 1 | **Metro / Zune** | Black canvas, oversized lowercase pivot titles bleeding off-edge, bright live-tiles, edge-to-edge type. The Windows Phone / Zune HD aesthetic. |
| 2 | **Fluent 2 / Windows 11 Mica** | Acrylic nav rail, rounded cards, soft depth, toggle switches, accent blue. The polished modern Windows look (Files / PowerToys / Settings). |
| 3 | **Darkroom Pro** | Image-first. Big 16:9 preview with rule-of-thirds + focal marker, amber accent, queue panel, film-strip. DaVinci / Lightroom energy. |
| 4 | **Editorial / Swiss Light** | Warm paper, serif display type, hairline rules, lots of air. Magazine feel. |

Renders live in [`mockups/`](mockups/).

## Regenerating

The mockups are hand-authored SVG rendered to PNG with `cairosvg`:

```bash
pip install cairosvg
python design/generate_mockups.py
```

Output PNGs are written to `design/mockups/`. Edit `generate_mockups.py` to
iterate on a direction.
