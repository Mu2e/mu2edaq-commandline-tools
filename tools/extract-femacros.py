#!/usr/bin/env python3
"""Extract the FE macro inventory from the otsdaq-mu2e* sources.

Scans every registerFEMacroFunction(...) call site under the otsdaq-mu2e*
submodules and writes a machine-readable inventory. Re-run it after updating
those submodules to refresh data/otsdaq-femacros.json.

The call sites span many lines and are heavily interleaved with comments, and a
sizeable fraction are commented out, so this uses a brace-matching scanner
rather than a regex over lines, and records whether each registration is active.

See doc/otsdaq-command-surface.md for what the output means.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CALL = "registerFEMacroFunction"
DEFAULT_GLOB = "otsdaq-mu2e*"
SOURCE_SUFFIXES = (".cc", ".h", ".hh", ".cpp")

# Emits registration *source text* rather than registering anything itself.
GENERATORS = ("otsdaq_import_tracker_test_stand",)


def strip_comments(s: str) -> str:
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    return re.sub(r"//[^\n]*", "", s)


def split_args(body: str) -> list:
    """Split a C++ argument list on top-level commas."""
    args, depth, cur, in_str, esc = [], 0, [], False, False
    for ch in body:
        if in_str:
            cur.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            cur.append(ch)
        elif ch in "([{<":
            depth += 1
            cur.append(ch)
        elif ch in ")]}>":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            args.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        args.append("".join(cur).strip())
    return args


def cat_strings(expr: str) -> str:
    """Concatenate adjacent C++ string literals: "a" "b" -> ab."""
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', expr)
    return "".join(parts).replace('\\"', '"').replace("\\n", " ").strip()


def vector_items(expr: str) -> list:
    """Pull the string literals out of std::vector<std::string>{...}."""
    m = re.search(r"\{(.*)\}", expr, flags=re.S)
    if not m:
        return []
    return [cat_strings(a) for a in split_args(m.group(1)) if a.strip()]


def find_calls(text: str):
    """Yield (offset, argument-string) for each registerFEMacroFunction call."""
    for m in re.finditer(re.escape(CALL) + r"\s*\(", text):
        start = m.end()
        depth, i, in_str, esc = 1, start, False, False
        while i < len(text) and depth:
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            i += 1
        yield m.start(), text[start:i - 1]


def commented_out(text: str, off: int) -> bool:
    """True if the call sits in a /* */ block or on a // commented line."""
    before = text[:off]
    if before.rfind("/*") > before.rfind("*/"):
        return True
    return "//" in text[before.rfind("\n") + 1:off]


def scan(root: Path, pattern: str) -> list:
    rows = []
    for path in sorted(root.glob(pattern + "/**/*")):
        if path.suffix not in SOURCE_SUFFIXES or ".git" in path.parts:
            continue
        text = path.read_text(errors="replace")
        if CALL not in text:
            continue
        rel = path.relative_to(root)
        for off, body in find_calls(text):
            args = split_args(strip_comments(body))
            if not args:
                continue
            fn = re.sub(r"\s+", " ", strip_comments(args[1])) if len(args) > 1 else ""
            handler = re.search(r"&\s*([\w:]+)", fn)
            rows.append(dict(
                package=rel.parts[0],
                file=str(rel),
                line=text.count("\n", 0, off) + 1,
                active=not commented_out(text, off),
                generator=any(g in path.name for g in GENERATORS),
                name=cat_strings(args[0]),
                handler=handler.group(1) if handler else "",
                inputs=vector_items(args[2]) if len(args) > 2 else [],
                outputs=vector_items(args[3]) if len(args) > 3 else [],
                permission=args[4].strip() if len(args) > 4 else "",
                callers=cat_strings(args[5]) if len(args) > 5 else "",
                description=cat_strings(args[6]) if len(args) > 6 else "",
            ))
    return rows


def summarize(rows: list) -> str:
    real = [r for r in rows if r["active"] and not r["generator"]]
    by_pkg = {}
    for r in real:
        by_pkg[r["package"]] = by_pkg.get(r["package"], 0) + 1
    lines = [
        "call sites found      : %d" % len(rows),
        "  active              : %d" % sum(r["active"] for r in rows),
        "  commented out       : %d" % sum(not r["active"] for r in rows),
        "  code-generator noise: %d" % sum(r["generator"] for r in rows),
        "real registrations    : %d" % len(real),
        "  with a literal name : %d" % sum(1 for r in real if r["name"]),
        "  with a description  : %d" % sum(1 for r in real if r["description"]),
        "",
        "by package:",
    ]
    lines += ["  %-28s %3d" % (k, v) for k, v in sorted(by_pkg.items())]
    return "\n".join(lines)


def main(argv=None) -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        prog="extract-femacros.py",
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-r", "--root", type=Path, default=here.parent.parent,
        help="directory holding the otsdaq-mu2e* checkouts "
             "(default: the mu2edaq-main parent of this checkout)")
    parser.add_argument(
        "-o", "--output", type=Path,
        default=here.parent / "data" / "otsdaq-femacros.json",
        help="where to write the inventory (default: %(default)s); - for stdout")
    parser.add_argument(
        "-p", "--pattern", default=DEFAULT_GLOB,
        help="submodule glob to scan (default: %(default)s)")
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="suppress the summary")
    args = parser.parse_args(argv)

    if not args.root.is_dir():
        print("error: no such directory: %s" % args.root, file=sys.stderr)
        return 1
    if not any(args.root.glob(args.pattern)):
        print("error: no %s checkouts under %s" % (args.pattern, args.root),
              file=sys.stderr)
        return 1

    rows = scan(args.root, args.pattern)
    payload = json.dumps(rows, indent=1)
    if str(args.output) == "-":
        print(payload)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
        if not args.quiet:
            print("wrote %s" % args.output)
    if not args.quiet:
        print(summarize(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
