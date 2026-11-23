#!/usr/bin/env python3
"""Check unpacked theme folders (or ZIPs) against the keys Chrome reads from a theme manifest.

    python3 generator/validate.py dist/lumen-*-dark dist/lumen-*-light dist/*.zip

The key lists follow Chromium's theme pack (chrome/browser/themes/browser_theme_pack.cc:
kPersistingImages, kTintTable, kColorTable, kDisplayProperties) as of Chromium 131. An unknown
key is an error: Chrome ignores it silently, so it is a typo or a key that never worked. Contrast
pairs that a reader depends on must reach WCAG 4.5:1 (3:1 for the toolbar icons).
Standard library only.
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import png  # type: ignore[no-redef]
    from lumen_chrome import contrast  # type: ignore[no-redef]
else:
    from . import png
    from .lumen_chrome import contrast

IMAGE_KEYS = {
    "theme_frame", "theme_frame_inactive", "theme_frame_incognito", "theme_frame_incognito_inactive",
    "theme_frame_overlay", "theme_frame_overlay_inactive", "theme_toolbar", "theme_tab_background",
    "theme_tab_background_inactive", "theme_tab_background_incognito",
    "theme_tab_background_incognito_inactive", "theme_tab_background_v", "theme_ntp_background",
    "theme_ntp_attribution", "theme_button_background", "theme_window_control_background",
}
COLOR_KEYS = {
    "frame", "frame_inactive", "frame_incognito", "frame_incognito_inactive",
    "background_tab", "background_tab_inactive", "background_tab_incognito", "background_tab_incognito_inactive",
    "toolbar", "toolbar_text", "toolbar_button_icon",
    "tab_text", "tab_background_text", "tab_background_text_inactive", "tab_background_text_incognito",
    "tab_background_text_incognito_inactive", "bookmark_text",
    "ntp_background", "ntp_text", "ntp_link", "ntp_header", "ntp_section", "ntp_section_text", "ntp_section_link",
    "control_button_background", "button_background", "omnibox_background", "omnibox_text",
}
TINT_KEYS = {"buttons", "frame", "frame_inactive", "frame_incognito", "frame_incognito_inactive", "background_tab"}
PROPERTY_VALUES = {
    "ntp_background_alignment": {"center", "top", "bottom", "left", "right", "top left", "top right",
                                 "bottom left", "bottom right", "left top", "right top", "left bottom",
                                 "right bottom"},
    "ntp_background_repeat": {"no-repeat", "repeat", "repeat-x", "repeat-y"},
    "ntp_logo_alternate": {0, 1},
}
TOP_KEYS = {"manifest_version", "name", "version", "description", "icons", "theme", "update_url",
            "minimum_chrome_version", "key"}
CONTRAST_PAIRS = [
    ("tab_text", "toolbar", 4.5), ("toolbar_text", "toolbar", 4.5), ("bookmark_text", "toolbar", 4.5),
    ("tab_background_text", "frame", 4.5), ("omnibox_text", "omnibox_background", 4.5),
    ("ntp_text", "ntp_background", 4.5), ("ntp_link", "ntp_background", 4.5),
    ("toolbar_button_icon", "toolbar", 3.0), ("tab_background_text_incognito", "frame_incognito", 4.5),
]
MAX_IMAGE_BYTES = 4 * 1024 * 1024


class Package:
    def __init__(self, path: Path):
        self.path = path
        self.zip = zipfile.ZipFile(path) if path.suffix == ".zip" else None

    def read(self, rel: str) -> bytes | None:
        if ".." in Path(rel).parts or rel.startswith("/"):
            return None
        if self.zip:
            try:
                return self.zip.read(rel)
            except KeyError:
                return None
        f = self.path / rel
        return f.read_bytes() if f.is_file() else None


def _is_colour(v: object) -> bool:
    return (isinstance(v, list) and len(v) in (3, 4) and all(isinstance(c, int) and not isinstance(c, bool)
                                                            and 0 <= c <= 255 for c in v[:3])
            and (len(v) == 3 or isinstance(v[3], (int, float)) and 0 <= v[3] <= 1))


def check(path: Path) -> list[str]:
    errors: list[str] = []
    pkg = Package(path)
    raw = pkg.read("manifest.json")
    if raw is None:
        return ["manifest.json is missing"]
    try:
        m = json.loads(raw)
    except ValueError as exc:
        return [f"manifest.json is not JSON: {exc}"]
    for k in m:
        if k not in TOP_KEYS:
            errors.append(f"unknown top-level key {k!r} (a theme may not carry code or permissions)")
    if m.get("manifest_version") != 3:
        errors.append("manifest_version must be 3")
    name = m.get("name")
    if not isinstance(name, str) or not 0 < len(name) <= 75:
        errors.append("name must be 1-75 characters")
    if not isinstance(m.get("version"), str) or not all(p.isdigit() for p in m["version"].split(".")):
        errors.append("version must be dot-separated numbers")
    if len(m.get("description", "")) > 132:
        errors.append("description is longer than 132 characters")
    for size, rel in (m.get("icons") or {}).items():
        data = pkg.read(rel)
        if data is None:
            errors.append(f"icon {rel} is missing")
            continue
        try:
            w, h = png.read_size(data)
        except ValueError:
            errors.append(f"icon {rel} is not a PNG")
            continue
        if (w, h) != (int(size), int(size)):
            errors.append(f"icon {rel} is {w}x{h}, expected {size}x{size}")
    theme = m.get("theme")
    if not isinstance(theme, dict):
        return errors + ["theme is missing"]
    for k in theme:
        if k not in ("images", "colors", "tints", "properties"):
            errors.append(f"unknown theme key {k!r}")
    for k, rel in (theme.get("images") or {}).items():
        if k not in IMAGE_KEYS:
            errors.append(f"unknown image key {k!r}")
        data = pkg.read(rel) if isinstance(rel, str) else None
        if data is None:
            errors.append(f"image {k}: {rel} is missing")
            continue
        try:
            png.read_size(data)
        except ValueError:
            errors.append(f"image {k}: {rel} is not a PNG (Chrome themes take PNG only)")
        if len(data) > MAX_IMAGE_BYTES:
            errors.append(f"image {k}: {rel} is larger than 4 MiB")
    colors = theme.get("colors") or {}
    for k, v in colors.items():
        if k not in COLOR_KEYS:
            errors.append(f"unknown colour key {k!r}")
        elif not _is_colour(v):
            errors.append(f"colour {k} must be [r, g, b] or [r, g, b, a]")
    for k, v in (theme.get("tints") or {}).items():
        if k not in TINT_KEYS:
            errors.append(f"unknown tint key {k!r}")
        elif not (isinstance(v, list) and len(v) == 3 and all(isinstance(x, (int, float)) and (x == -1 or 0 <= x <= 1) for x in v)):
            errors.append(f"tint {k} must be [h, s, l] with values 0-1 or -1")
    for k, v in (theme.get("properties") or {}).items():
        if k not in PROPERTY_VALUES:
            errors.append(f"unknown property {k!r}")
        elif v not in PROPERTY_VALUES[k]:
            errors.append(f"property {k} has an invalid value {v!r}")
    for fg, bg, minimum in CONTRAST_PAIRS:
        if fg in colors and bg in colors and _is_colour(colors[fg]) and _is_colour(colors[bg]):
            ratio = contrast(tuple(colors[fg][:3]), tuple(colors[bg][:3]))
            if ratio < minimum:
                errors.append(f"contrast {fg} on {bg} is {ratio:.2f}:1, needs {minimum}:1")
    return errors


def main(argv: list[str] | None = None) -> int:
    paths = [Path(p) for p in (argv if argv is not None else sys.argv[1:])]
    if not paths:
        print("usage: validate.py THEME_DIR_OR_ZIP...", file=sys.stderr)
        return 2
    failed = 0
    for p in paths:
        errors = check(p)
        if errors:
            failed += 1
            for e in errors:
                print(f"::error title={p.name}::{e}" if "GITHUB_ACTIONS" in __import__("os").environ else f"{p}: {e}")
        else:
            print(f"{p}: ok")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
