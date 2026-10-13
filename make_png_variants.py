#!/usr/bin/env python3
"""Rasterize the SVG icon library into PNG variants.

Mirrors the exo_svg tree into exo_png (color codes: bl, bk, rd, wh):

    exo_svg/svg/<name>.svg           -> exo_png/png/<name>.png
    exo_svg/svg_bk/<name>_bk.svg     -> exo_png/png_bk/<name>_bk.png
    exo_svg/svg_rd/<name>_rd.svg     -> exo_png/png_rd/<name>_rd.png
    exo_svg/svg_wh/<name>_wh.svg     -> exo_png/png_wh/<name>_wh.png
    exo_svg/svg_bl/<name>_bl.svg     -> exo_png/png_bl/<name>_bl.png

Icons are rendered with transparent backgrounds (the variant fills
"none" stay transparent). Uses rsvg-convert, falling back to inkscape.

Usage:
    python3 make_png_variants.py [--size 256] [--variant NAME]... [--force] [--dry-run]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# color-code -> (svg folder, png folder, filename suffix)
VARIANTS = {
    "base": {"svg": "svg", "png": "png", "suffix": ""},
    "bk": {"dir": "svg_bk", "png": "png_bk", "suffix": "_bk"},
    "rd": {"dir": "svg_rd", "png": "png_rd", "suffix": "_rd"},
    "wh": {"dir": "svg_wh", "png": "png_wh", "suffix": "_wh"},
    "bl": {"dir": "svg_bl", "png": "png_bl", "suffix": "_bl"},
}
# normalize: every variant uses a "dir" key for the svg source folder
VARIANTS["base"]["dir"] = VARIANTS["base"].pop("svg")


def find_rasterizer() -> tuple[list[str], str]:
    """Return (command-prefix, name) for the first available rasterizer."""
    if shutil.which("rsvg-convert"):
        return ["rsvg-convert"], "rsvg-convert"
    if shutil.which("inkscape"):
        return ["inkscape"], "inkscape"
    sys.exit("error: need rsvg-convert (brew install librsvg) or inkscape "
             "to render PNGs.")


def render(cmd_prefix: list[str], name: str, svg: Path, png: Path, size: int) -> None:
    if name == "rsvg-convert":
        cmd = cmd_prefix + ["-w", str(size), "-h", str(size),
                            "--output", str(png), str(svg)]
    else:  # inkscape >= 1.x
        cmd = cmd_prefix + ["--export-type=png", "--export-filename", str(png),
                            "-w", str(size), "-h", str(size), str(svg)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not png.exists():
        png.unlink(missing_ok=True)
        raise RuntimeError(proc.stderr.strip() or f"{name} failed")


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--root", type=Path, default=HERE / "exo_svg",
                        help="folder containing the svg* variant tree "
                             "(default: ./exo_svg)")
    parser.add_argument("--size", type=int, default=256,
                        help="PNG width/height in pixels (default: 256)")
    parser.add_argument("--variant", action="append", choices=sorted(VARIANTS),
                        metavar="NAME",
                        help="only this variant (repeatable; default: all)")
    parser.add_argument("--force", action="store_true",
                        help="re-render even if the PNG is up to date")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be rendered without rendering")
    args = parser.parse_args()

    root = args.root.resolve()
    svg_root = root  # exo_svg/ contains the svg* folders
    png_root = (root.parent / "exo_png").resolve()
    if not svg_root.is_dir():
        sys.exit(f"error: {svg_root} is not a directory")

    selected = {k: VARIANTS[k] for k in (args.variant or VARIANTS)}
    cmd_prefix, rasterizer = find_rasterizer()

    rendered = skipped = 0
    for key in selected.values():
        in_dir = svg_root / key["dir"]
        out_dir = png_root / key["png"]
        if not in_dir.is_dir():
            print(f"! {in_dir} missing, skipped", file=sys.stderr)
            continue
        for svg in sorted(in_dir.glob("*.svg")):
            png = out_dir / svg.with_suffix(".png").name
            if png.exists() and png.stat().st_mtime >= svg.stat().st_mtime \
                    and not args.force:
                skipped += 1
                continue
            print(f"  {png.relative_to(png_root.parent)}: {key['suffix'] or 'base'} "
                  f"{args.size}px")
            rendered += 1
            if args.dry_run:
                continue
            out_dir.mkdir(parents=True, exist_ok=True)
            try:
                render(cmd_prefix, rasterizer, svg, png, args.size)
            except RuntimeError as exc:
                print(f"! {svg.name}: {exc}", file=sys.stderr)
                rendered -= 1

    if not args.dry_run:
        print(f"\nrendered {rendered} PNGs with {rasterizer} "
              f"({skipped} up to date) under {png_root}")
    else:
        print(f"\nwould render {rendered} PNGs ({skipped} up to date)")


if __name__ == "__main__":
    main()
