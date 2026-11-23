"""Print the Python manifests as JSON for tests/test_parity.mjs: {"<preset>/<mode>": "<manifest text>"}.

Also covers edge cases: a grey palette (zero saturation tints), a document with invalid values
and one with non-ASCII text.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator import lumen_chrome as lc  # noqa: E402

CASES = {name: json.loads((lc.PRESETS / f"{name}.json").read_text(encoding="utf-8")) for name in lc.PRESET_ORDER}
CASES["grey"] = {"meta": {"name": "Grau – Test", "description": "Graue Töne " * 20},
                 "color": {"dark": {"textMuted": "#888888", "text": "#FFFFFF"}, "light": {"textMuted": "#555555"}}}
CASES["invalid"] = {"version": 1, "meta": {"name": "<b>"}, "color": {"dark": {"accent": "red", "surface": "#12345"}},
                    "layout": {"backgroundGlow": "yes"}}
CASES["empty"] = {}


def main() -> None:
    out = {"cases": CASES, "manifests": {}, "problems": {}, "defaults": {}}
    for name, doc in CASES.items():
        tokens, problems = lc.normalize(doc)
        out["problems"][name] = problems
        for mode in lc.MODES:
            for image in (True, False):
                out["manifests"][f"{name}/{mode}/{int(image)}"] = lc.manifest_bytes(
                    lc.build_manifest(tokens, mode, "1.2.3", image)).decode()
            for pattern in lc.PATTERNS:
                out["defaults"][f"{name}/{mode}/{pattern}"] = lc.default_ntp_image(mode, pattern, tokens)
    json.dump(out, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
