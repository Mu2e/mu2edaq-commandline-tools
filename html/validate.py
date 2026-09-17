#!/usr/bin/env python3
"""Validate the static walkthrough's local links and basic page structure."""

from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import unquote, urlsplit


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: List[str] = []
        self.references: List[Tuple[str, str]] = []
        self.lang: Optional[str] = None
        self.title_count = 0
        self.h1_count = 0

    def handle_starttag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        values: Dict[str, Optional[str]] = dict(attrs)
        if tag == "html":
            self.lang = values.get("lang")
        if tag == "title":
            self.title_count += 1
        if tag == "h1":
            self.h1_count += 1
        if values.get("id"):
            self.ids.append(str(values["id"]))
        for attribute in ("href", "src"):
            value = values.get(attribute)
            if value:
                self.references.append((attribute, value))


def parse_page(path: Path) -> PageParser:
    parser = PageParser()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    return parser


def main() -> int:
    root = Path(__file__).resolve().parent
    pages = sorted(root.glob("*.html"))
    parsed = {page.resolve(): parse_page(page) for page in pages}
    errors: List[str] = []

    for page, parser in parsed.items():
        label = page.relative_to(root)
        duplicates = sorted(
            item for item in set(parser.ids) if parser.ids.count(item) > 1
        )
        if duplicates:
            errors.append("%s: duplicate IDs: %s" % (label, ", ".join(duplicates)))
        if parser.lang != "en":
            errors.append("%s: expected html lang=\"en\"" % label)
        if parser.title_count != 1:
            errors.append("%s: expected one title element" % label)
        if parser.h1_count != 1:
            errors.append("%s: expected one h1, found %d" % (label, parser.h1_count))

        for attribute, reference in parser.references:
            parts = urlsplit(reference)
            if parts.scheme or parts.netloc:
                continue
            target_path = unquote(parts.path)
            target = (page.parent / target_path).resolve() if target_path else page
            if not target.exists():
                errors.append(
                    "%s: broken %s=%r" % (label, attribute, reference)
                )
                continue
            if parts.fragment and target.suffix == ".html":
                target_parser = parsed.get(target)
                if target_parser is None:
                    target_parser = parse_page(target)
                    parsed[target] = target_parser
                if parts.fragment not in set(target_parser.ids):
                    errors.append(
                        "%s: missing fragment #%s in %s"
                        % (label, parts.fragment, target.name)
                    )

    if errors:
        for error in errors:
            print("ERROR:", error)
        return 1
    print(
        "Validated %d HTML pages: structure, local assets, links, and fragments OK"
        % len(pages)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
