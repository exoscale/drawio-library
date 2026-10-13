#!/usr/bin/env python3
"""Sync the exo-ico-lib.xml draw.io library from exo_svg/svg/*.svg.

Stdlib only. Safe by default: entries whose image data and size already match
are kept byte-for-byte untouched; only added/changed icons are rewritten.

Usage:
    python3 make_lib_updates.py --dry-run                # report drift, change nothing
    python3 make_lib_updates.py                          # apply adds/updates in place
    python3 make_lib_updates.py --prune                  # also drop entries with no SVG
    python3 make_lib_updates.py --sizes sizes.json       # per-icon w/h overrides
    python3 make_lib_updates.py --emit-sizes sizes.json  # seed an overrides file from current lib
    python3 make_lib_updates.py --rebuild                # regenerate all entries a-z by title
                                                       # into exo-ico-lib_2.xml (--out to change)
"""
import argparse
import base64
import html
import json
import re
import sys
from pathlib import Path

DATA_URI_RE = re.compile(r"image=(data:image/svg\+xml[^,]*,[A-Za-z0-9+/=]+)")

CELL_XML = (
    '<mxGraphModel><root>'
    '<mxCell id="0"/><mxCell id="1" parent="0"/>'
    '<mxCell id="2" value="" style="shape=image;verticalLabelPosition=bottom;'
    'verticalAlign=top;imageAspect=0;aspect=fixed;image={uri}" vertex="1" parent="1">'
    '<mxGeometry width="{w}" height="{h}" as="geometry"/>'
    '</mxCell></root></mxGraphModel>'
)


def parse_size(text):
    """Parse '62' or '62x44' into (w, h)."""
    parts = text.lower().split("x")
    if len(parts) == 1:
        return int(parts[0]), int(parts[0])
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])
    raise argparse.ArgumentTypeError(f"bad size {text!r} (use W or WxH)")


def load_sizes(path):
    """Read per-icon overrides: {"vm": [62, 44]} or {"vm": {"w": 62, "h": 44}}."""
    raw = json.loads(Path(path).read_text())
    sizes = {}
    for title, val in raw.items():
        if isinstance(val, dict):
            sizes[title] = (int(val["w"]), int(val["h"]))
        else:
            w, h = val
            sizes[title] = (int(w), int(h))
    return sizes


def existing_image_uri(entry):
    """Pull the embedded data URI out of an existing entry ('xml' or 'data' form)."""
    if "data" in entry:
        return entry["data"]
    xml = html.unescape(entry.get("xml", ""))
    m = DATA_URI_RE.search(xml)
    return m.group(1) if m else None


def build_entry(title, svg_bytes, w, h):
    uri = "data:image/svg+xml," + base64.b64encode(svg_bytes).decode("ascii")
    xml = CELL_XML.format(uri=uri, w=w, h=h)
    # draw.io entity-decodes the whole file before JSON.parse, so only <>& may
    # be escaped here; quotes must stay literal (json.dumps backslash-escapes them).
    return {
        "xml": html.escape(xml, quote=False),
        "w": w,
        "h": h,
        "title": title,
        "aspect": "fixed",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    root = Path(__file__).resolve().parent
    ap.add_argument("--library", default=root / "exo-ico-lib.xml", type=Path)
    ap.add_argument("--svg-dir", default=root / "exo_svg" / "svg", type=Path)
    ap.add_argument("--sizes", type=Path,
                    help="JSON file mapping icon title -> [w, h] per-icon overrides")
    ap.add_argument("--size", type=parse_size, default=None,
                    help="global default size, e.g. 62 or 62x44")
    ap.add_argument("--prune", action="store_true",
                    help="remove library entries that have no matching SVG")
    ap.add_argument("--rebuild", action="store_true",
                    help="regenerate all entries from the SVG dir, sorted a-z by title, "
                         "writing to --out (default: <library> with '_2' before .xml)")
    ap.add_argument("--out", type=Path, default=None,
                    help="output file for --rebuild (default: <library>_2.xml)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--emit-sizes", type=Path, metavar="FILE",
                    help="write current per-icon sizes to FILE and exit")
    args = ap.parse_args()

    out_path = args.out
    if args.rebuild and out_path is None:
        out_path = args.library.with_name(args.library.stem + "_2" + args.library.suffix)

    text = args.library.read_text() if args.library.exists() else ""
    m = re.search(r"<mxlibrary>\s*(.*?)\s*</mxlibrary>", text, re.DOTALL)
    if m:
        entries = json.loads(m.group(1))
    elif args.rebuild:
        entries = []  # full rebuild does not need an existing library
    else:
        sys.exit(f"error: {args.library} has no <mxlibrary> wrapper")
    by_title = {e.get("title"): e for e in entries}

    if args.emit_sizes:
        dump = {e["title"]: [e.get("w", 62), e.get("h", 62)] for e in entries}
        args.emit_sizes.write_text(json.dumps(dump, indent=2, sort_keys=True) + "\n")
        print(f"wrote {args.emit_sizes} ({len(dump)} icons)")
        return

    overrides = load_sizes(args.sizes) if args.sizes else {}

    svgs = {p.stem: p for p in sorted(args.svg_dir.glob("*.svg"))}
    if not svgs:
        sys.exit(f"error: no SVGs found in {args.svg_dir}")

    def pick_size(title, existing):
        # precedence: per-icon overrides file > --size global > existing entry > 62
        if title in overrides:
            return overrides[title]
        if args.size:
            return args.size
        if existing and "w" in existing and "h" in existing:
            return existing["w"], existing["h"]
        return 62, 62

    added = updated = unchanged = 0
    regenerated = {}

    for title, path in svgs.items():
        existing = by_title.get(title)
        w, h = pick_size(title, existing)
        entry = build_entry(title, path.read_bytes(), w, h)
        if existing is None or args.rebuild:
            print(f"  + {title} ({w}x{h})" if existing is None else f"  # {title} ({w}x{h})")
            regenerated[title] = entry
            added += 1
        elif (existing_image_uri(existing) == existing_image_uri(entry)
              and (existing.get("w"), existing.get("h")) == (w, h)
              and "&quot;" not in existing.get("xml", "")):  # fix bad escaping too
            unchanged += 1  # keep the original entry exactly as-is
        else:
            print(f"  ~ {title} ({w}x{h})")
            regenerated[title] = entry
            updated += 1

    if args.rebuild:
        # Rebuild mode: strict a-z order by title, SVGs are the only source of truth.
        ordered = [regenerated[t] for t in sorted(svgs)]
        print(f"\nrebuilt={len(ordered)} (from {len(entries)} existing entries)")
    else:
        # Rebuild: existing entries keep their original position; new ones append alphabetically.
        ordered, placed = [], set()
        for e in entries:
            t = e.get("title")
            if t in svgs:
                ordered.append(regenerated.get(t, e))
                placed.add(t)
            elif args.prune:
                print(f"  - {t} (no SVG, pruned)")
            else:
                print(f"  ! {t} (no SVG, kept; use --prune to drop)")
                ordered.append(e)
        for t in sorted(set(svgs) - placed):
            ordered.append(regenerated[t])

        missing = [e["title"] for e in entries if e.get("title") not in svgs]
        print(f"\nadded={added} updated={updated} unchanged={unchanged} "
              f"missing_svg={len(missing)} total={len(ordered)}")

    if args.dry_run:
        print("dry run: file not written")
        return

    target = out_path or args.library
    out = "<mxlibrary>" + json.dumps(ordered, indent=2) + "</mxlibrary>"
    target.write_text(out)
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
