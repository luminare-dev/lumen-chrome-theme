#!/usr/bin/env python3
"""Lumen browser themes: turn a Lumen token document and a mode into a Chrome theme package.

    python3 generator/lumen_chrome.py presets/luminare.json --mode dark --out dist/luminare-dark
    python3 generator/lumen_chrome.py --all --out dist          # every preset, dark and light, plus ZIPs

A theme is a manifest.json with colours, tints and properties plus PNG images; it has no code and
cannot follow the system light or dark setting, so each mode is its own package. Only the colour
roles, meta.name, meta.description and layout.backgroundGlow of the token document are used.
The colour mapping is mirrored in customizer/index.html; tests/test_parity.mjs checks both give
the same manifest. Standard library only.
"""

from __future__ import annotations

import argparse
import colorsys
import json
import math
import re
import sys
import zipfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import png  # type: ignore[no-redef]
else:
    from . import png

ROOT = Path(__file__).resolve().parent.parent
PRESETS = ROOT / "presets"
PRESET_ORDER = ["luminare", "graphite", "aurora", "contrast"]
MODES = ("dark", "light")
ROLES = ["canvas", "surfaceSunken", "surface", "surfaceRaised", "border", "text", "textMuted", "accent",
         "accentSecondary", "accentText", "accentContrast", "success", "warning", "danger", "info", "focus"]
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
PATTERNS = ("dots", "none")
NTP_SIZE = (2560, 1440)
FRAME_SIZE = (32, 128)
ICON_SIZES = (16, 32, 48, 128)
ZIP_DATE = (2026, 1, 1, 0, 0, 0)


# ------------------------------------------------------------------------------------------
# Tokens
# ------------------------------------------------------------------------------------------

def load_default() -> dict:
    return json.loads((PRESETS / "luminare.json").read_text(encoding="utf-8"))


def normalize(doc: object) -> tuple[dict, list[str]]:
    """The parts of a token document this target uses, with defaults and the replaced paths."""
    default = load_default()
    problems: list[str] = []
    if not isinstance(doc, dict):
        return normalize(default)[0], ["(document)"]
    if doc.get("version", 1) != 1:
        problems.append("version")
    out: dict = {"meta": {}, "color": {}, "glow": True}
    meta = doc.get("meta") if isinstance(doc.get("meta"), dict) else {}
    for key in ("name", "description"):
        value = meta.get(key, default["meta"][key])
        if not isinstance(value, str) or len(value) > 200 or "<" in value or ">" in value:
            problems.append(f"meta.{key}")
            value = default["meta"][key]
        out["meta"][key] = value.strip()
    colors = doc.get("color") if isinstance(doc.get("color"), dict) else {}
    for mode in MODES:
        given = colors.get(mode) if isinstance(colors.get(mode), dict) else {}
        palette = {}
        for role in ROLES:
            value = given.get(role, default["color"][mode][role])
            if not isinstance(value, str) or not HEX_RE.match(value):
                problems.append(f"color.{mode}.{role}")
                value = default["color"][mode][role]
            palette[role] = value.upper()
        out["color"][mode] = palette
    layout = doc.get("layout") if isinstance(doc.get("layout"), dict) else {}
    glow = layout.get("backgroundGlow", True)
    if not isinstance(glow, bool):
        problems.append("layout.backgroundGlow")
        glow = True
    out["glow"] = glow
    return out, problems


# ------------------------------------------------------------------------------------------
# Colour arithmetic (mirrored in customizer/index.html: keep the rounding identical)
# ------------------------------------------------------------------------------------------

def rgb(hex_colour: str) -> tuple[int, int, int]:
    return int(hex_colour[1:3], 16), int(hex_colour[3:5], 16), int(hex_colour[5:7], 16)


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    """a moved towards b by t (0..1), rounded half up."""
    return tuple(int(math.floor(a[i] + (b[i] - a[i]) * t + 0.5)) for i in range(3))  # type: ignore[return-value]


def luminance(c: tuple[int, int, int]) -> float:
    def lin(v: int) -> float:
        s = v / 255
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2])


def contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def separate(c: tuple[int, int, int], ref: tuple[int, int, int], toward: tuple[int, int, int],
             minimum: float = 1.12) -> tuple[int, int, int]:
    """Move c towards `toward` in 4 % steps until it differs from ref by `minimum` (max 10 steps)."""
    out = c
    step = 0
    while contrast(out, ref) < minimum and step < 10:
        step += 1
        out = mix(c, toward, 0.04 * step)
    return out


def theme_colors(tokens: dict, mode: str) -> dict[str, tuple[int, int, int]]:
    """Chrome theme colours for one mode. Incognito windows use the dark palette in both modes."""
    p = {k: rgb(v) for k, v in tokens["color"][mode].items()}
    d = {k: rgb(v) for k, v in tokens["color"]["dark"].items()}
    black = (0, 0, 0)
    if mode == "dark":
        frame = p["canvas"]
        frame_inactive = mix(frame, p["surfaceSunken"], 0.5)
    else:
        frame = mix(p["surfaceSunken"], p["border"], 0.45)
        frame_inactive = mix(frame, p["canvas"], 0.5)
    toolbar = separate(p["surface"], frame, p["text"])
    omnibox = separate(p["surfaceSunken"], toolbar, p["text"], 1.08)
    incognito = mix(d["canvas"], black, 0.25)
    incognito_inactive = mix(incognito, d["surfaceSunken"], 0.5)
    icon = mix(p["textMuted"], p["text"], 0.35)
    return {
        "frame": frame,
        "frame_inactive": frame_inactive,
        "frame_incognito": incognito,
        "frame_incognito_inactive": incognito_inactive,
        "background_tab": frame,
        "background_tab_inactive": frame_inactive,
        "background_tab_incognito": incognito,
        "background_tab_incognito_inactive": incognito_inactive,
        "toolbar": toolbar,
        "toolbar_text": p["text"],
        "toolbar_button_icon": icon,
        "tab_text": p["text"],
        "tab_background_text": p["textMuted"],
        "tab_background_text_inactive": mix(p["textMuted"], frame_inactive, 0.25),
        "tab_background_text_incognito": d["textMuted"],
        "tab_background_text_incognito_inactive": mix(d["textMuted"], incognito_inactive, 0.25),
        "bookmark_text": p["text"],
        "omnibox_background": omnibox,
        "omnibox_text": p["text"],
        "ntp_background": p["canvas"],
        "ntp_text": p["text"],
        "ntp_link": p["accentText"],
        "ntp_header": p["accent"],
    }


def hsl_tint(c: tuple[int, int, int]) -> list[float]:
    """[h, s, l] rounded half up to 3 places; whole numbers as ints (the customizer's JSON matches)."""
    h, l, s = colorsys.rgb_to_hls(c[0] / 255, c[1] / 255, c[2] / 255)
    out: list[float] = []
    for x in (h, s, l):
        r = math.floor(x * 1000 + 0.5) / 1000
        out.append(int(r) if r == int(r) else r)
    return out


def theme_name(tokens: dict, mode: str) -> str:
    return f"Lumen {tokens['meta']['name'] or 'Custom'} {mode.capitalize()}"[:75]


def build_manifest(tokens: dict, mode: str, version: str, ntp_image: bool = True) -> dict:
    colors = theme_colors(tokens, mode)
    description = tokens["meta"]["description"] or "A Lumen browser theme."
    if len(description) > 132:
        description = description[:131].rstrip() + "…"
    none = [-1, -1, -1]
    manifest = {
        "manifest_version": 3,
        "name": theme_name(tokens, mode),
        "version": version,
        "description": description,
        "icons": {str(s): f"icons/icon{s}.png" for s in ICON_SIZES},
        "theme": {
            "images": {
                "theme_frame": "images/frame.png",
                "theme_frame_inactive": "images/frame_inactive.png",
                "theme_frame_incognito": "images/frame_incognito.png",
                "theme_frame_incognito_inactive": "images/frame_incognito_inactive.png",
                "theme_toolbar": "images/toolbar.png",
                "theme_ntp_background": "images/ntp_background.png",
            },
            "colors": {k: list(v) for k, v in colors.items()},
            "tints": {
                "buttons": hsl_tint(colors["toolbar_button_icon"]),
                "frame": none,
                "frame_inactive": none,
                "frame_incognito": none,
                "frame_incognito_inactive": none,
                "background_tab": none,
            },
            "properties": {
                "ntp_background_alignment": "top",
                "ntp_background_repeat": "no-repeat",
                "ntp_logo_alternate": 1 if mode == "dark" else 0,
            },
        },
    }
    if not ntp_image:
        del manifest["theme"]["images"]["theme_ntp_background"]
        del manifest["theme"]["properties"]["ntp_background_alignment"]
        del manifest["theme"]["properties"]["ntp_background_repeat"]
    return manifest


# ------------------------------------------------------------------------------------------
# Images
# ------------------------------------------------------------------------------------------

BAYER4 = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def frame_image(base: tuple[int, int, int], accent: tuple[int, int, int], strength: float,
                size: tuple[int, int] = FRAME_SIZE) -> bytes:
    """The tab strip: a faint accent light at the top that fades into the frame colour."""
    w, h = size
    fade = h // 2
    rows = []
    for y in range(h):
        t = strength * max(0.0, 1 - y / fade) ** 2
        row = bytearray()
        for x in range(w):
            dither = (BAYER4[y % 4][x % 4] + 0.5) / 16 - 0.5
            for i in range(3):
                v = base[i] + (accent[i] - base[i]) * t + (dither if t > 0 else 0)
                row.append(max(0, min(255, int(math.floor(v + 0.5)))))
        rows.append(bytes(row))
    return png.encode(w, h, rows)


def glows(w: int, h: int, tokens: dict, mode: str) -> list[tuple[float, float, float, float, tuple[int, int, int], float]]:
    """(cx, cy, rx, ry, colour, alpha) of the two NTP lights; they end inside the image edges."""
    p = {k: rgb(v) for k, v in tokens["color"][mode].items()}
    a1, a2 = (0.34, 0.26) if mode == "dark" else (0.20, 0.15)
    return [
        (0.30 * w, -0.08 * h, 0.28 * w, 0.30 * w, p["accent"], a1),
        (0.72 * w, -0.04 * h, 0.26 * w, 0.27 * w, p["accentSecondary"], a2),
    ]


def ntp_image(tokens: dict, mode: str, pattern: str = "dots", size: tuple[int, int] = NTP_SIZE) -> bytes:
    """New tab page: the canvas colour with the Lumen light at the top and an optional dot grid.
    Every edge pixel is the plain ntp_background colour, so a wider window shows no seam."""
    w, h = size
    p = {k: rgb(v) for k, v in tokens["color"][mode].items()}
    base = p["canvas"]
    base_row = bytes(base) * w
    lights = glows(w, h, tokens, mode) if tokens.get("glow", True) else []
    spacing = max(8, round(w / 90))
    dot_alpha = (0.14 if mode == "dark" else 0.10) if pattern == "dots" else 0.0
    dot_colour = p["accentText"]
    dot_bottom = 0.55 * h
    edge = 0.08 * w
    rows = []
    for y in range(h):
        spans = []
        for cx, cy, rx, ry, colour, alpha in lights:
            dy = (y - cy) / ry
            if dy * dy < 1:
                half = rx * math.sqrt(1 - dy * dy)
                spans.append((max(0, int(cx - half)), min(w, int(cx + half) + 1), cx, rx, dy * dy, colour, alpha))
        on_dot_row = dot_alpha > 0 and y < dot_bottom and y % spacing in (0, 1)
        if not spans and not on_dot_row:
            rows.append(base_row)
            continue
        row = bytearray(base_row)
        touched: dict[int, list[float]] = {}
        for x0, x1, cx, rx, dy2, colour, alpha in spans:
            for x in range(x0, x1):
                dx = (x - cx) / rx
                d = math.sqrt(dx * dx + dy2)
                if d >= 1:
                    continue
                a = alpha * (1 - d) ** 1.6
                c = touched.get(x)
                if c is None:
                    c = [float(base[0]), float(base[1]), float(base[2])]
                    touched[x] = c
                c[0] += (colour[0] - c[0]) * a
                c[1] += (colour[1] - c[1]) * a
                c[2] += (colour[2] - c[2]) * a
        if on_dot_row:
            fade_y = 1 - y / dot_bottom
            for x in range(spacing // 2, w, spacing):
                fade_x = min(1.0, x / edge, (w - 1 - x) / edge)
                a = dot_alpha * fade_y * fade_x
                if a <= 0:
                    continue
                for xx in (x, x + 1):
                    if xx >= w:
                        continue
                    c = touched.get(xx)
                    if c is None:
                        c = [float(base[0]), float(base[1]), float(base[2])]
                        touched[xx] = c
                    c[0] += (dot_colour[0] - c[0]) * a
                    c[1] += (dot_colour[1] - c[1]) * a
                    c[2] += (dot_colour[2] - c[2]) * a
        bayer = BAYER4[y % 4]
        for x, c in touched.items():
            dither = (bayer[x % 4] + 0.5) / 16 - 0.5
            o = 3 * x
            row[o] = max(0, min(255, int(math.floor(c[0] + dither + 0.5))))
            row[o + 1] = max(0, min(255, int(math.floor(c[1] + dither + 0.5))))
            row[o + 2] = max(0, min(255, int(math.floor(c[2] + dither + 0.5))))
        rows.append(bytes(row))
    return png.encode(w, h, rows)


def icon_image(tokens: dict, mode: str, size: int) -> bytes:
    """The theme icon: a rounded square with the accent gradient and a light ring (no logo)."""
    p = {k: rgb(v) for k, v in tokens["color"][mode].items()}
    a, b, fg = p["accent"], p["accentSecondary"], p["accentContrast"]
    ss = 4
    radius = 0.22 * size
    ring_r, ring_w = 0.25 * size, 0.09 * size
    centre = size / 2
    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            cover = 0
            ring = 0
            for sy in range(ss):
                for sx in range(ss):
                    px = x + (sx + 0.5) / ss
                    py = y + (sy + 0.5) / ss
                    qx = max(radius - px, 0, px - (size - radius))
                    qy = max(radius - py, 0, py - (size - radius))
                    if qx * qx + qy * qy <= radius * radius:
                        cover += 1
                        d = math.hypot(px - centre, py - centre)
                        if abs(d - ring_r) <= ring_w / 2 or d <= ring_w * 0.55:
                            ring += 1
            n = ss * ss
            t = (x + y) / (2 * size)
            fill = mix(a, b, t)
            colour = mix(fill, fg, ring / cover) if cover else (0, 0, 0)
            row += bytes(colour) + bytes([round(255 * cover / n)])
        rows.append(bytes(row))
    return png.encode(size, size, rows, alpha=True)


# ------------------------------------------------------------------------------------------
# Packages
# ------------------------------------------------------------------------------------------

def default_ntp_image(mode: str, pattern: str, tokens: dict) -> bool:
    """Chrome treats any new tab image as a photo: white logo, white shortcut titles and a dark
    scrim at the top. That suits the dark themes; light themes and plain backgrounds skip it."""
    return mode == "dark" and (tokens.get("glow", True) or pattern == "dots")


def default_pattern(tokens: dict) -> str:
    return "dots" if tokens.get("glow", True) else "none"


def build_files(tokens: dict, mode: str, version: str, pattern: str | None = None,
                ntp_size: tuple[int, int] = NTP_SIZE, ntp_image_on: bool | None = None) -> dict[str, bytes]:
    """Every file of one theme package, by its path inside the package."""
    pattern = pattern or default_pattern(tokens)
    if pattern not in PATTERNS:
        raise ValueError(f"pattern must be one of {', '.join(PATTERNS)}")
    if ntp_image_on is None:
        ntp_image_on = default_ntp_image(mode, pattern, tokens)
    colors = theme_colors(tokens, mode)
    p = {k: rgb(v) for k, v in tokens["color"][mode].items()}
    d = {k: rgb(v) for k, v in tokens["color"]["dark"].items()}
    strong = 0.10 if mode == "dark" else 0.06
    files = {
        "manifest.json": manifest_bytes(build_manifest(tokens, mode, version, ntp_image_on)),
        "images/frame.png": frame_image(colors["frame"], p["accent"], strong if tokens["glow"] else 0),
        "images/frame_inactive.png": frame_image(colors["frame_inactive"], p["accent"], strong / 2 if tokens["glow"] else 0),
        "images/frame_incognito.png": frame_image(colors["frame_incognito"], d["accent"], 0.06 if tokens["glow"] else 0),
        "images/frame_incognito_inactive.png": frame_image(colors["frame_incognito_inactive"], d["accent"], 0),
        "images/toolbar.png": png.solid(*FRAME_SIZE, colors["toolbar"]),
    }
    if ntp_image_on:
        files["images/ntp_background.png"] = ntp_image(tokens, mode, pattern, ntp_size)
    for s in ICON_SIZES:
        files[f"icons/icon{s}.png"] = icon_image(tokens, mode, s)
    return files


def manifest_bytes(manifest: dict) -> bytes:
    """Two-space JSON with every number list on one line (the customizer writes the same bytes)."""
    text = json.dumps(manifest, indent=2, ensure_ascii=False)
    text = re.sub(r"\[\s*(-?[0-9.]+),\s*(-?[0-9.]+),\s*(-?[0-9.]+)\s*\]", r"[\1, \2, \3]", text)
    return (text + "\n").encode()


def write_dir(files: dict[str, bytes], out: Path) -> None:
    for rel, data in files.items():
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def write_zip(files: dict[str, bytes], out: Path) -> None:
    """A deterministic ZIP (fixed dates, sorted names); PNGs are stored, the manifest deflated."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w") as z:
        for rel in sorted(files):
            info = zipfile.ZipInfo(rel, ZIP_DATE)
            info.compress_type = zipfile.ZIP_STORED if rel.endswith(".png") else zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, files[rel])


def read_version() -> str:
    return (ROOT / "version.txt").read_text(encoding="utf-8").strip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("tokens", nargs="?", help="token JSON file (a preset or an export)")
    ap.add_argument("--mode", choices=MODES, help="dark or light (default: both)")
    ap.add_argument("--all", action="store_true", help="every preset in presets/, both modes")
    ap.add_argument("--out", required=True, help="output folder")
    ap.add_argument("--pattern", choices=PATTERNS, help="NTP pattern (default: dots when the glow is on)")
    ap.add_argument("--ntp-image", choices=("auto", "on", "off"), default="auto",
                    help="new tab background image (auto: dark themes with the light or the dots)")
    ap.add_argument("--no-zip", action="store_true", help="write folders only")
    ap.add_argument("--ntp-size", default=f"{NTP_SIZE[0]}x{NTP_SIZE[1]}", help="NTP image size, WxH")
    args = ap.parse_args(argv)
    if bool(args.tokens) == bool(args.all):
        ap.error("give one token file or --all")
    w, h = (int(v) for v in args.ntp_size.lower().split("x"))
    out = Path(args.out)
    version = read_version()
    jobs: list[tuple[str, dict]] = []
    if args.all:
        for slug in PRESET_ORDER:
            tokens, problems = normalize(json.loads((PRESETS / f"{slug}.json").read_text(encoding="utf-8")))
            if problems:
                print(f"error: presets/{slug}.json: invalid {', '.join(problems)}", file=sys.stderr)
                return 1
            jobs.append((slug, tokens))
    else:
        src = Path(args.tokens)
        try:
            doc = json.loads(src.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"error: {src}: {exc}", file=sys.stderr)
            return 1
        tokens, problems = normalize(doc)
        for path in problems:
            print(f"warning: {src}: {path} is invalid; the default is used", file=sys.stderr)
        slug = re.sub(r"[^a-z0-9]+", "-", tokens["meta"]["name"].lower()).strip("-") or "custom"
        jobs.append((slug, tokens))
    for slug, tokens in jobs:
        for mode in ([args.mode] if args.mode else MODES):
            image = None if args.ntp_image == "auto" else args.ntp_image == "on"
            files = build_files(tokens, mode, version, args.pattern, (w, h), image)
            name = f"lumen-{slug}-{mode}"
            folder = out / name if (args.all or not args.mode) else out
            write_dir(files, folder)
            if not args.no_zip:
                write_zip(files, out / f"{name}.zip")
            print(f"{name}: {len(files)} files -> {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
