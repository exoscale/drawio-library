---
name: image-overview
description: Regenerate the project's SVG and PNG overview PDFs from exo_svg and exo_png, preserving the 24-icons-per-page A4 landscape layout, centered filename captions, light/dark page backgrounds, and per-subfolder page grouping.
---

# Image Overview Generation

Use this skill when the user asks to create, refresh, or update the image overview PDFs for this drawio library.

## Existing generator

Use the project generator at `make_overview.py`. Do not create a separate one-off script unless the user explicitly asks for a different workflow.

Run it from the project root:

```bash
python3 make_overview.py
```

The command creates or refreshes:

- `exo_svg_overview.pdf` from `exo_svg/`
- `exo_png_overview.pdf` from `exo_png/`

The generator uses WeasyPrint, so verify that the `weasyprint` executable is available on `PATH` before running it. It reports the number of pages and images generated.

## Output requirements

Preserve these behaviors unless the user requests a change:

- Landscape A4 pages with 24 icons per page (8 columns x 3 rows); folders with
  more than 24 icons continue on numbered pages like `svg_bl (2/4)`.
- Captions centered beneath each image, using the filename without its extension.
- Each immediate subfolder starts on a new page.
- Light gray page background (`#d9d9d9`) by default; with `--bg per-variant`,
  the `svg_wh`/`png_wh` and `svg_bl`/`png_bl` pages use a dark gray background
  (`#4d4d4d`) with light captions so white and light-blue icons stay visible.
- The staging folder `new/` is excluded by default (`--exclude NAME` to change).
- Temporary HTML files are removed after PDF generation.

## Custom paths

If the source or output locations differ, use the generator's separate options:

```bash
python3 make_overview.py \
  --svg-input path/to/svg-root \
  --png-input path/to/png-root \
  --svg-output path/to/svg-overview.pdf \
  --png-output path/to/png-overview.pdf \
  --bg light|per-variant
```

After generation, report the output PDF paths and the image/page counts shown by the script. Do not commit changes unless the user explicitly requests it.
