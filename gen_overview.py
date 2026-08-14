#!/usr/bin/env python3
"""Generate a paginated PDF overview of image files in subfolders."""

from argparse import ArgumentParser
from html import escape
from pathlib import Path
from typing import Tuple
import shutil
import subprocess
import tempfile


PAGE_CSS = """
@page { size: A4 landscape; margin: 10mm 8mm; background: #b3b3b3; }
* { box-sizing: border-box; }
body { margin: 0; font-family: Arial, Helvetica, sans-serif; color: #222; background: #b3b3b3; }
section { page-break-before: always; height: 100%; }
section:first-child { page-break-before: auto; }
h1 { margin: 0 0 3mm; font-size: 14pt; font-weight: 600; text-align: center; }
.grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  grid-auto-rows: 17.5mm;
  column-gap: 1mm;
  row-gap: 0.5mm;
}
.item {
  min-width: 0;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.icon {
  width: 100%;
  height: 12mm;
  display: flex;
  align-items: center;
  justify-content: center;
}
.icon img {
  display: block;
  width: 10.5mm;
  height: 10.5mm;
  object-fit: contain;
}
.caption {
  width: 100%;
  margin-top: 0.5mm;
  font-size: 5.5pt;
  line-height: 6pt;
  overflow-wrap: anywhere;
}
"""


def build_html(image_root: Path, extension: str) -> Tuple[str, int, int]:
    pattern = f"*.{extension}"
    folders = sorted(
        path for path in image_root.iterdir()
        if path.is_dir() and any(path.glob(pattern))
    )
    if not folders:
        raise SystemExit(f"No subfolders containing {pattern} files found in {image_root}")

    sections = []
    image_count = 0
    for folder in folders:
        cells = []
        files = sorted(folder.glob(pattern), key=lambda path: path.name.lower())
        image_count += len(files)
        for image in files:
            caption = image.stem
            cells.append(
                f'<div class="item"><div class="icon">'
                f'<img src="{escape(image.resolve().as_uri())}" alt="{escape(caption)}">'
                f'</div><div class="caption">{escape(caption)}</div></div>'
            )
        sections.append(
            f'<section><h1>{escape(folder.name)}</h1>'
            f'<div class="grid">{"".join(cells)}</div></section>'
        )

    html = (
        '<!doctype html><html><head><meta charset="utf-8"><style>'
        + PAGE_CSS
        + f'</style></head><body>{"".join(sections)}</body></html>'
    )
    return html, len(folders), image_count


def generate_pdf(image_root: Path, output: Path, extension: str, weasyprint: str) -> None:
    image_root = image_root.expanduser().resolve()
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    html, folder_count, image_count = build_html(image_root, extension)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", encoding="utf-8", dir=output.parent, delete=False
    ) as html_file:
        html_file.write(html)
        html_path = Path(html_file.name)

    try:
        subprocess.run([weasyprint, str(html_path), str(output)], check=True)
    finally:
        html_path.unlink(missing_ok=True)

    print(f"Created {output} ({folder_count} pages, {image_count} {extension.upper()}s)")


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    project_root = Path(__file__).parent
    parser.add_argument(
        "--svg-input", type=Path, default=project_root / "exo_svg",
        help="Directory containing SVG subfolders (default: ./exo_svg)",
    )
    parser.add_argument(
        "--png-input", type=Path, default=project_root / "exo_png",
        help="Directory containing PNG subfolders (default: ./exo_png)",
    )
    parser.add_argument(
        "--svg-output", type=Path, default=project_root / "exo_svg_overview.pdf",
        help="SVG overview output path (default: ./exo_svg_overview.pdf)",
    )
    parser.add_argument(
        "--png-output", type=Path, default=project_root / "exo_png_overview.pdf",
        help="PNG overview output path (default: ./exo_png_overview.pdf)",
    )
    args = parser.parse_args()

    weasyprint = shutil.which("weasyprint")
    if weasyprint is None:
        raise SystemExit(
            "The 'weasyprint' command is required. Install it and ensure it is on PATH."
        )

    generate_pdf(args.svg_input, args.svg_output, "svg", weasyprint)
    generate_pdf(args.png_input, args.png_output, "png", weasyprint)


if __name__ == "__main__":
    main()
