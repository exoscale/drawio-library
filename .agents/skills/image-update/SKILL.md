---
name: image-update
description: Ingest newly added SVG icons from new-icons/ into the drawio icon library by a 3-step pipeline: minimize the SVGs (make_mini-variants.py), generate the four color variants (make_color_variants.py), and render the PNG variants into exo_png/ (make_png_variants.py), ending with a one-line status report.
---

# Image Update Pipeline

Use this skill when the user asks to add, onboard, ingest, or process newly
added icons, or to "update the icon library" after dropping new SVGs into
`new-icons/`.

Run all commands from the project root. The three Python scripts already
default to the correct staging and library folders; pass extra flags only if
the user explicitly asks.

## Prerequisites

- Step 1 needs `svgo` on PATH (or `npx` as a fallback; `brew install svgo`).
- Step 3 needs `rsvg-convert` (brew install librsvg`) or `inkscape`.
- Check with `command -v <tool>` before running; report a missing tool instead
  of guessing an install.

## Step 1 — Minimize the new SVGs

```bash
python3 make_mini-variants.py
```

- Reads the new icons from `new-icons/` (default input dir).
- Optimizes each SVG in place (svgo + house-style post-processing) and copies
  the results into the `exo_svg/svg/` library folder without overwriting
  existing library files.
- If it exits with "no SVG files found in new-icons", there is nothing to
  update: report that and stop.
- If it exits non-zero (svgo failure or a file failing the final style check),
  stop the pipeline and report the failing files; do not run steps 2 and 3.

## Step 2 — Generate the color variants

Only after step 1 succeeded:

```bash
python3 make_color_variants.py
```

- Reads the minimized SVGs from `new-icons/` and writes `_bk`, `_rd`, `_wh`
  and `_bl` variants into `exo_svg/svg_bk/`, `svg_rd/`, `svg_wh/`, `svg_bl/`
  respectively.
- Existing variant files are skipped unless the user asked to regenerate
  (then add `--force`).
- If it exits non-zero or reports `SKIPPED (no inline fill styles...)`, stop
  and report; do not run step 3.

## Step 3 — Render the PNG variants

Only after steps 1 and 2 both succeeded:

```bash
python3 make_png_variants.py
```

- Mirrors every `exo_svg/svg*` folder into the matching `exo_png/png*` folder
  at 256 px with transparent backgrounds.
- Rendering is incremental: PNGs newer than their SVG source are skipped, so
  only the newly added/changed icons are re-rendered.

## Status report

Finish with exactly one short status line summarizing the pipeline, built
from the scripts' own output, e.g.:

```
Icon update: 3 SVGs optimized (-68%) → 12 color variants written → 15 PNGs rendered (45 up to date).
```

If a step was skipped or failed, say so in that same line (e.g. `Icon
update: stopped after step 1 — 2 files failed the style check`). Do not
commit anything unless the user explicitly asks.
