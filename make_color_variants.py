#!/usr/bin/env python3
"""Create the black/red/white/blue color variants of the icon library.

The library ships each icon in five flavors (color codes: bl, bk, rd, wh):

    svg/<name>.svg         red background circle + white details   (source)
    svg_bk/<name>_bk.svg   transparent background + black   details (#000)
    svg_rd/<name>_rd.svg   transparent background + red     details (#da291c)
    svg_wh/<name>_wh.svg   transparent background + white   details (#fff)
    svg_bl/<name>_bl.svg   transparent background + light-blue details (#9cb6d8)

The recolor rule (verified against the whole existing library):

    fill:#da291c  ->  fill:none        (background circle becomes transparent)
    fill:#fff     ->  variant color    (per target color code)

The _bl variant is derived from the _bk variant (fill:#000 -> fill:#9cb6d8),
because svg_bk carries hand-tuned geometry for a few icons.

Usage:
    python3 make_color_variants.py [INPUT_DIR] [--dry-run] [--force]

INPUT_DIR defaults to the new-icons/ staging folder and must contain SVGs
already minimized by make_mini_variants.py (inline style="fill:#hex" only).
The color variant folders (svg_bk, ...) are expected under the exo_svg/
library root (override with --svg-root DIR).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RED = {"fill:#da291c", "fill:#d9291c"}
STYLE_RE = re.compile(r'style="([^"]*)"')

HERE = Path(__file__).resolve().parent

VARIANTS = {
    "bk": {"dir": "svg_bk", "suffix": "_bk", "detail": "fill:#000"},
    "rd": {"dir": "svg_rd", "suffix": "_rd", "detail": "fill:#da291c"},
    "wh": {"dir": "svg_wh", "suffix": "_wh", "detail": "fill:#fff"},
    # bl is derived from the black variant, which carries hand-tuned
    # geometry for a few icons (svg_bk/vmpool_bk.svg, scale_bk, db-valkey_bk)
    "bl": {"dir": "svg_bl", "suffix": "_bl", "detail": "fill:#9cb6d8",
           "from": "bk"},
}


def recolor_from_black(xml: str, detail: str) -> tuple[str, int]:
    """Recolor an _bk variant: black details -> detail color, keep fill:none."""
    count = 0

    def sub(m: re.Match) -> str:
        nonlocal count
        if m.group(1).strip().rstrip(";") == "fill:#000":
            count += 1
            return f'style="{detail}"'
        return m.group(0)

    return STYLE_RE.sub(sub, xml), count


def recolor(xml: str, detail: str) -> tuple[str, int]:
    """Rewrite every inline fill style; returns (result, n_styles_replaced)."""
    count = 0

    def sub(m: re.Match) -> str:
        nonlocal count
        style = m.group(1).strip().rstrip(";")
        if style in RED:
            new = "fill:none"
        elif style == "fill:#fff":
            new = detail
        else:
            print(f"    ! keeping unknown style {style!r}", file=sys.stderr)
            return m.group(0)
        count += 1
        return f'style="{new}"'

    return STYLE_RE.sub(sub, xml), count


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("input_dir", nargs="?",
                        default=str(HERE / "new-icons"),
                        help="folder of minimized source SVGs "
                             "(default: new-icons)")
    parser.add_argument("--svg-root", metavar="DIR",
                        default=str(HERE / "exo_svg"),
                        help="library root holding the svg* variant folders "
                             "(default: exo_svg)")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be written without writing")
    parser.add_argument("--force", action="store_true",
                        help="overwrite existing variant files")
    parser.add_argument("--variant", action="append", choices=sorted(VARIANTS),
                        metavar="NAME",
                        help="only generate this variant (repeatable; "
                             "default: all)")
    args = parser.parse_args()

    selected = {k: VARIANTS[k] for k in (args.variant or VARIANTS)}

    base = Path(args.svg_root)
    in_dir = Path(args.input_dir)
    files = sorted(in_dir.glob("*.svg"))
    if not files:
        sys.exit(f"error: no SVG files found in {in_dir}")

    written = 0
    for path in files:
        stem = path.stem
        xml = path.read_text(encoding="utf-8")

        styles = STYLE_RE.findall(xml)
        if not styles:
            print(f"{path.name}: SKIPPED (no inline fill styles; run "
                  f"make_mini_variants.py first)", file=sys.stderr)
            continue
        reds = [s for s in styles if s.strip().rstrip(";") in RED]
        if len(reds) > 1:
            print(f"    ! {path.name}: {len(reds)} red elements, all become "
                  f"transparent - check if hand-tuning is needed "
                  f"(see svg_bk/vmpool_bk.svg)", file=sys.stderr)

        for var in selected.values():
            out_dir = base / var["dir"]
            out_path = out_dir / f"{stem}{var['suffix']}.svg"
            source = xml
            from_black = False
            if "from" in var:
                src_var = VARIANTS[var["from"]]
                black_path = base / src_var["dir"] / f"{stem}{src_var['suffix']}.svg"
                if black_path.exists():
                    source = black_path.read_text(encoding="utf-8")
                    from_black = True
            if from_black:
                result, n = recolor_from_black(source, var["detail"])
                n_total = len(STYLE_RE.findall(source))
            else:
                result, n = recolor(source, var["detail"])
                n_total = len(styles)
            if n != n_total:
                print(f"    ! {out_path.name}: only {n}/{len(styles)} "
                      f"styles recolored", file=sys.stderr)
            if out_path.exists() and not args.force:
                print(f"= {out_path}: exists, use --force to overwrite")
                continue
            print(f"  {out_path}: {len(result)} bytes")
            if not args.dry_run:
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path.write_text(result, encoding="utf-8")
            written += 1

    kind = "would write" if args.dry_run else "wrote"
    print(f"\n{kind} {written} variant files from {len(files)} icons")


if __name__ == "__main__":
    main()
