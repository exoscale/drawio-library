#!/usr/bin/env python3
"""Minimize SVG icons for the Hugo icons library.

Pipeline (per file):
  1. Run `svgo --multipass` (default preset) for geometry/attribute cleanup.
  2. Post-process to the house style used in exo_svg/svg/:
       - <svg> keeps only xmlns and viewBox
       - no <defs>, <style>, ids, data-name attributes or empty <g> wrappers
       - every class="stN" is replaced by the inline style="fill:#hex" it
         refers to (svgo's reuseStyles plugin keeps class+<style> whenever
         two or more shapes share a class, so we inline it ourselves)

Usage:
    python3 make_mini-variants.py [INPUT_DIR] [-o OUT_DIR] [--dry-run] [--no-svgo]

INPUT_DIR defaults to the new-icons/ staging folder.
By default files are rewritten in place and the results are also copied
into the exo_svg/svg/ library folder (override with --copy-to DIR, disable
with --no-copy); existing library files are never overwritten unless
--force.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
SVG_ROOT = HERE / "exo_svg"
NEW_ICONS = HERE / "new-icons"

# ---------------------------------------------------------------- regexes

# .st0{fill:#fff}  (inside <style> blocks)
CSS_RULE_RE = re.compile(r"\.([A-Za-z_][\w-]*)\s*\{([^}]*)\}")
STYLE_BLOCK_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.DOTALL)
START_TAG_RE = re.compile(r"<([A-Za-z][\w:-]*)((?:\s+[\w:-]+(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'))?)*)(\s*/?)\s*>")
ATTR_RE = re.compile(r'([\w:-]+)\s*=\s*("([^"]*)"|\'([^\']*)\')')

DROP_TAGS = {"style", "defs", "title", "desc", "metadata"}


# ---------------------------------------------------------------- helpers

def find_svgo() -> list[str]:
    exe = shutil.which("svgo")
    if exe:
        return [exe]
    if shutil.which("npx"):
        return ["npx", "--yes", "svgo"]
    sys.exit("error: svgo not found. Install it with 'brew install svgo' or "
             "'npm install -g svgo' (npx is used as a fallback).")


def run_svgo(data: str, svgo_cmd: list[str]) -> str:
    cmd = svgo_cmd + ["--multipass", "-q", "-i", "-", "-o", "-"]
    proc = subprocess.run(cmd, input=data, capture_output=True, text=True,
                          check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"svgo failed: {proc.stderr.strip()}")
    return proc.stdout


def parse_style_classes(xml: str) -> dict[str, dict[str, str]]:
    """Return {class-name: {property: value}} from every <style> block."""
    rules: dict[str, dict[str, str]] = {}
    for block in STYLE_BLOCK_RE.findall(xml):
        for name, body in CSS_RULE_RE.findall(block):
            decls: dict[str, str] = {}
            for decl in body.split(";"):
                if ":" in decl:
                    prop, _, value = decl.partition(":")
                    decls[prop.strip().lower()] = value.strip()
            rules.setdefault(name, {}).update(decls)
    return rules


def style_string(decls: dict[str, str]) -> str:
    return ";".join(f"{p}:{v}" for p, v in decls.items())


def inline_classes(xml: str, class_rules: dict[str, dict[str, str]]) -> tuple[str, list[str]]:
    """Replace class="..." attributes with inline style="..." declarations."""
    warnings: list[str] = []

    def fix_tag(m: re.Match) -> str:
        tag, attrs_text, selfclose = m.group(1), m.group(2), m.group(3)
        attrs = ATTR_RE.findall(attrs_text)
        if not any(name == "class" for name, _, _, _ in attrs):
            return m.group(0)

        # existing inline style wins over class styles (CSS precedence)
        inline_decls: dict[str, str] = {}
        for name, _, dq, sq in attrs:
            if name == "style":
                for decl in (dq or sq).split(";"):
                    if ":" in decl:
                        prop, _, value = decl.partition(":")
                        inline_decls[prop.strip().lower()] = value.strip()

        class_decls: dict[str, str] = {}
        for name, _, dq, sq in attrs:
            if name == "class":
                for cls in (dq or sq).split():
                    if cls in class_rules:
                        class_decls.update(class_rules[cls])
                    else:
                        warnings.append(f"class '{cls}' has no style rule; dropped")

        merged = {**class_decls, **inline_decls}
        kept = [(n, q) for (n, q) in ((a[0], a[1]) for a in attrs)
                if n not in ("class", "style")]
        rebuilt = " ".join(f"{n}={q}" for n, q in kept)
        if merged:
            rebuilt += f' style="{style_string(merged)}"'
        rebuilt = (" " + rebuilt) if rebuilt else ""
        return f"<{tag}{rebuilt}{selfclose}>"

    # operate only on start tags that actually carry a class attribute
    xml = re.sub(
        r"<([A-Za-z][\w:-]*)((?:\s+[\w:-]+(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'))?)*\sclass=(?:\"[^\"]*\"|'[^']*')(?:\s+[\w:-]+(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'))?)*)(\s*/?)>",
        fix_tag, xml)
    return xml, warnings


def drop_attrs(xml: str, names: set[str]) -> str:
    def fix_tag(m: re.Match) -> str:
        tag, attrs_text, selfclose = m.group(1), m.group(2), m.group(3)
        kept = " ".join(f"{name}={q}" for name, q in
                        ((a[0], a[1]) for a in ATTR_RE.findall(attrs_text))
                        if name not in names)
        kept = (" " + kept) if kept else ""
        return f"<{tag}{kept}{selfclose}>"

    alt = "|".join(sorted(names))
    pattern = rf"<([A-Za-z][\w:-]*)((?=[^>]*\s(?:{alt})\s*=)(?:\s+[\w:-]+(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'))?)+)(\s*/?)>"
    return re.sub(pattern, fix_tag, xml)


def unwrap_empty_groups(xml: str) -> tuple[str, list[str]]:
    """Remove <g> wrappers that carry no attributes (rendering-neutral)."""
    warnings: list[str] = []

    def fix_open(m: re.Match) -> str:
        attrs = ATTR_RE.findall(m.group(1))
        if attrs:
            kept = {a: (c or d) for a, _, c, d in attrs}
            warnings.append(f"kept <g> with attributes: {kept}")
            return m.group(0)
        return ""

    xml = re.sub(r"<g((?:\s+[\w:-]+(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'))?)*)\s*>", fix_open, xml)
    xml = xml.replace("</g>", "")
    return xml, warnings


def normalize_svg_root(xml: str) -> str:
    """Keep only xmlns and viewBox on the root <svg> element."""
    def fix_root(m: re.Match) -> str:
        attrs = {name: (dq or sq) for name, _, dq, sq in ATTR_RE.findall(m.group(1))}
        parts = ['xmlns="http://www.w3.org/2000/svg"']
        if "viewBox" in attrs:
            parts.append(f'viewBox="{attrs["viewBox"]}"')
        return "<svg " + " ".join(parts) + ">"

    return re.sub(r"<svg((?:\s+[\w:-]+(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'))?)+)\s*>",
                  fix_root, xml, count=1)


def remove_nodes(xml: str) -> str:
    prev = None
    while prev != xml:
        prev = xml
        for tag in DROP_TAGS:
            xml = re.sub(rf"<{tag}\b[^>]*>[^<]*</{tag}>", "", xml)  # non-nesting tags
            xml = re.sub(rf"<{tag}\b[^>]*/>", "", xml)
            xml = re.sub(rf"<{tag}\b[^>]*>\s*</{tag}>", "", xml)  # emptied by inner removal
    return xml


def collapse_whitespace(xml: str) -> str:
    xml = re.sub(r">\s+<", "><", xml)
    return xml.strip()


def check_final(xml: str) -> list[str]:
    problems: list[str] = []
    for needle in ("class=", "<style", "<defs", "<g ", "</g>", "id=", "data-name="):
        if needle in xml:
            problems.append(f"unexpected {needle!r} in output")
    try:
        ET.fromstring(xml)
    except ET.ParseError as exc:
        problems.append(f"output is not well-formed XML: {exc}")
    return problems


# ---------------------------------------------------------------- driver

def minimize(data: str, svgo_cmd: list[str] | None) -> tuple[str, list[str]]:
    warnings: list[str] = []
    xml = data

    if svgo_cmd is not None:
        xml = run_svgo(xml, svgo_cmd)

    class_rules = parse_style_classes(xml)
    xml, warn = inline_classes(xml, class_rules)
    warnings += warn
    xml = remove_nodes(xml)
    xml = drop_attrs(xml, {"id", "data-name", "version"})
    xml, warn = unwrap_empty_groups(xml)
    warnings += warn
    xml = normalize_svg_root(xml)
    xml = collapse_whitespace(xml)

    problems = check_final(xml)
    if problems:
        warnings += problems
    return xml, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("input_dir", nargs="?",
                        default=str(NEW_ICONS),
                        help="folder containing the SVG files (default: new-icons)")
    parser.add_argument("-o", "--out", metavar="DIR",
                        help="write results to DIR instead of rewriting in place")
    parser.add_argument("--dry-run", action="store_true",
                        help="report size savings without writing")
    parser.add_argument("--no-svgo", action="store_true",
                        help="skip the svgo --multipass step (post-processing only)")
    parser.add_argument("--copy-to", metavar="DIR", default=str(SVG_ROOT / "svg"),
                        help="also copy the optimized SVGs into DIR "
                             "(default: the exo_svg/svg library folder)")
    parser.add_argument("--no-copy", action="store_true",
                        help="do not copy results into the --copy-to folder")
    parser.add_argument("--force", action="store_true",
                        help="overwrite existing files in the --copy-to folder")
    args = parser.parse_args()

    in_dir = Path(args.input_dir)
    out_dir = Path(args.out) if args.out else in_dir
    copy_dir = None if args.no_copy else Path(args.copy_to).resolve()
    files = sorted(in_dir.glob("*.svg"))
    if not files:
        sys.exit(f"error: no SVG files found in {in_dir}")

    svgo_cmd = None if args.no_svgo else find_svgo()
    out_dir.mkdir(parents=True, exist_ok=True)

    total_before = total_after = 0
    copied = 0
    failed = False
    for path in files:
        data = path.read_text(encoding="utf-8")
        try:
            result, warnings = minimize(data, svgo_cmd)
        except RuntimeError as exc:
            print(f"{path.name}: FAILED ({exc})", file=sys.stderr)
            failed = True
            continue

        total_before += len(data)
        total_after += len(result)
        flag = " "
        if len(result) >= len(data):
            flag = "="
        print(f"{flag} {path.name}: {len(data)} -> {len(result)} bytes")
        for w in warnings:
            print(f"    ! {w}", file=sys.stderr)
            if w.startswith(("unexpected", "output is not")):
                failed = True

        if not args.dry_run:
            out_file = out_dir / path.name
            if not out_file.exists() or out_file.read_text(encoding="utf-8") != result:
                out_file.write_text(result, encoding="utf-8")

        if copy_dir is not None and copy_dir != out_dir.resolve():
            dest = copy_dir / path.name
            if dest.exists() and not args.force:
                print(f"    ! {dest}: exists, use --force to overwrite",
                      file=sys.stderr)
            elif not args.dry_run:
                copy_dir.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(out_dir / path.name, dest)
                copied += 1

    saved = total_before - total_after
    pct = 100.0 * saved / total_before if total_before else 0.0
    print(f"\n{len(files)} files, {total_before} -> {total_after} bytes "
          f"(-{saved} bytes, -{pct:.1f}%)")
    if copy_dir is not None:
        print(f"copied {copied} files to {copy_dir}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
