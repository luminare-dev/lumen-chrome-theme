#!/usr/bin/env python3
"""Copy the presets and version.txt into customizer/index.html, so the page stays one file.

    python3 generator/embed.py           # rewrite the page
    python3 generator/embed.py --check   # exit 1 if the page is out of date (CI)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "customizer" / "index.html"
ORDER = ["luminare", "graphite", "aurora", "contrast"]
PRESETS_RE = re.compile(r'(<script type="application/json" id="lumen-presets">\n)(.*?)(\n</script>)', re.S)
VERSION_RE = re.compile(r'(var VERSION = ")([^"]*)(";)')


def render(page: str) -> str:
    presets = {k: json.loads((ROOT / "presets" / f"{k}.json").read_text(encoding="utf-8")) for k in ORDER}
    body = json.dumps(presets, indent=1, ensure_ascii=False).replace("</", "<\\/")
    version = (ROOT / "version.txt").read_text(encoding="utf-8").strip()
    page, n1 = PRESETS_RE.subn(lambda m: m.group(1) + body + m.group(3), page, count=1)
    page, n2 = VERSION_RE.subn(lambda m: m.group(1) + version + m.group(3), page, count=1)
    if n1 != 1 or n2 != 1:
        raise SystemExit("customizer/index.html: preset or version marker not found")
    return page


def main(argv: list[str]) -> int:
    current = PAGE.read_text(encoding="utf-8")
    wanted = render(current)
    if "--check" in argv:
        if current != wanted:
            print("customizer/index.html is out of date: run python3 generator/embed.py", file=sys.stderr)
            return 1
        print("customizer/index.html is up to date")
        return 0
    PAGE.write_text(wanted, encoding="utf-8")
    print("customizer/index.html updated")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
