---
name: regen-libs
description: Regenerate the exo-ico-lib draw.io library XML files (base plus the bk, bl, rd, wh color variants) from the SVG folders under exo_svg, using the 2-character color naming convention for folders, filenames, entry titles, and library filenames.
---

# Regenerate Icon Libraries

Use this skill when the user asks to rebuild, refresh, sync, or re-generate the
`exo-ico-lib*.xml` draw.io library files from the SVG sources.

## Source of truth

The SVGs under `exo_svg/` are the only source of truth. Each icon exists in a
base folder and four color-variant folders; variant filenames carry a 2-character
color suffix:

| Folder          | Filename pattern    | Library file            | Color      |
| :-------------- | :------------------ | :---------------------- | :--------- |
| `exo_svg/svg`   | `<name>.svg`        | `exo-ico-lib.xml`       | full color |
| `exo_svg/svg_bk`| `<name>_bk.svg`     | `exo-ico-lib_bk.xml`    | black      |
| `exo_svg/svg_bl`| `<name>_bl.svg`     | `exo-ico-lib_bl.xml`    | light blue |
| `exo_svg/svg_rd`| `<name>_rd.svg`     | `exo-ico-lib_rd.xml`    | red        |
| `exo_svg/svg_wh`| `<name>_wh.svg`     | `exo-ico-lib_wh.xml`    | white      |

The 2-character code (`bk`, `bl`, `rd`, `wh`) must appear consistently in the
folder name, the SVG filename suffix, the library entry **title** (the filename
stem, e.g. `2fa_bk`), and the library filename. The legacy 1-character naming
(`exo-ico-lib_b/_r/_w.xml` with space-suffixed titles like `2fa b`) is retired;
when you encounter those files, migrate them to the new names rather than
updating them in place.

`new-icons/` is a staging folder; do not build libraries from it until the
icons have been moved into `exo_svg/` and color variants generated.

## Generator

Use `make_lib_updates.py` in the project root. Stdlib only, no dependencies.
Always run it from the project root.

For a full regeneration under the naming convention, rebuild each library from
its SVG folder. `--rebuild` regenerates every entry a-z by title (the SVGs, not
the old library, define the entry set) and writes to `--out`:

```bash
python3 make_lib_updates.py --rebuild --out exo-ico-lib.xml
python3 make_lib_updates.py --rebuild --svg-dir exo_svg/svg_bk --out exo-ico-lib_bk.xml
python3 make_lib_updates.py --rebuild --svg-dir exo_svg/svg_bl --out exo-ico-lib_bl.xml
python3 make_lib_updates.py --rebuild --svg-dir exo_svg/svg_rd --out exo-ico-lib_rd.xml
python3 make_lib_updates.py --rebuild --svg-dir exo_svg/svg_wh --out exo-ico-lib_wh.xml
```

Add `--dry-run` to any command first to report drift (added/updated/unchanged
counts) without writing.

## Preserving per-icon sizes

Rebuild resets every entry to the default 62x62. If the existing library has
per-icon size overrides, seed a sizes file from it **before** rebuilding and
pass it back:

```bash
python3 make_lib_updates.py --emit-sizes /tmp/sizes.json
python3 make_lib_updates.py --sizes /tmp/sizes.json --rebuild --out <lib>
```

Size precedence is: `--sizes` overrides file > `--size` global > existing
entry's w/h > 62x62. Variant libraries can reuse the base library's sizes file
so all variants of an icon share one footprint.

## Incremental sync (no rebuild)

Without `--rebuild` the script only adds/updates changed entries, keeps
unchanged entries byte-for-byte, and appends new ones alphabetically:

```bash
python3 make_lib_updates.py --dry-run                # report drift only
python3 make_lib_updates.py                          # apply adds/updates
python3 make_lib_updates.py --prune                  # also drop entries with no SVG
```

Omitting `--prune` keeps stale entries with a `!` warning; mention those
warnings to the user if they appear.

## Verification

After writing, verify each library:

```bash
python3 - <<'EOF'
import json, re, glob
for f in sorted(glob.glob("exo-ico-lib*.xml")):
    e = json.loads(re.search(r"<mxlibrary>(.*)</mxlibrary>", open(f).read(), re.S).group(1))
    bad = [x["title"] for x in e if "&quot;" in x.get("xml", "")]
    print(f, len(e), "entries;", "bad escaping!" if bad else "ok")
EOF
```

Check: entry count equals the SVG count in the source folder, entries are a-z by
title, titles match the SVG filename stems, and no entry contains `&quot;`
(draw.io entity-decodes the file before JSON parsing, so only `<>&` may be
escaped in the embedded XML).

If legacy 1-character libraries (`_b`, `_r`, `_w`) still exist after the new
ones are built, report them to the user and offer to delete them; also flag
references to the old names in `README.md`.
