#!/usr/bin/env python3
"""Preview images of built themes and one contact sheet (needs Pillow; CI installs it).

    python3 generator/preview.py dist previews

For every unpacked theme folder in DIST (one with a manifest.json) it draws a browser window the
way the theme colours it: frame with tabs, toolbar with the address field, bookmarks bar and the
new tab page with its background image. Writes PREVIEWS/<theme>.png and PREVIEWS/contact-sheet.png.
It is a drawing, not a screenshot; the Playwright job in CI takes real new-tab screenshots.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 800
FRAME_H, TOOLBAR_H, BOOKMARKS_H = 46, 48, 34


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    for name in (("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),):
        for base in ("/usr/share/fonts/truetype/dejavu/", ""):
            try:
                return ImageFont.truetype(base + name, size)
            except OSError:
                continue
    return ImageFont.load_default(size)


def tile(canvas: Image.Image, img: Image.Image, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    for x in range(x0, x1, img.width):
        canvas.paste(img.crop((0, 0, min(img.width, x1 - x), min(img.height, y1 - y0))), (x, y0))


def render(theme_dir: Path) -> Image.Image:
    m = json.loads((theme_dir / "manifest.json").read_text(encoding="utf-8"))
    c = {k: tuple(v[:3]) for k, v in m["theme"]["colors"].items()}
    images = m["theme"]["images"]
    im = Image.new("RGB", (W, H), c["ntp_background"])
    d = ImageDraw.Draw(im)

    # Frame and tabs.
    d.rectangle((0, 0, W, FRAME_H), fill=c["frame"])
    if "theme_frame" in images:
        tile(im, Image.open(theme_dir / images["theme_frame"]).convert("RGB"), (0, 0, W, FRAME_H))
    f_tab, f_small = font(13), font(12)
    x = 12
    tabs = [("New Tab", True), ("Documentation", False), ("Pull requests", False)]
    for title, active in tabs:
        tw = 220
        if active:
            d.rounded_rectangle((x, 8, x + tw, FRAME_H + 10), radius=10, fill=c["toolbar"])
        else:
            d.line((x + tw + 1, 18, x + tw + 1, FRAME_H - 10), fill=c["tab_background_text"], width=1)
        colour = c["tab_text"] if active else c["tab_background_text"]
        d.ellipse((x + 14, 21, x + 28, 35), outline=colour, width=2)
        d.text((x + 38, 20), title, font=f_tab, fill=colour)
        d.text((x + tw - 24, 19), "×", font=f_tab, fill=colour)
        x += tw + 6
    d.text((x + 8, 15), "+", font=font(20), fill=c["tab_background_text"])
    for i, sym in enumerate(("–", "□", "×")):
        d.text((W - 120 + i * 40, 14), sym, font=font(16), fill=c["tab_background_text"])

    # Toolbar.
    top = FRAME_H
    d.rectangle((0, top, W, top + TOOLBAR_H + BOOKMARKS_H), fill=c["toolbar"])
    if "theme_toolbar" in images:
        tile(im, Image.open(theme_dir / images["theme_toolbar"]).convert("RGB"), (0, top, W, top + TOOLBAR_H + BOOKMARKS_H))
    icon = c["toolbar_button_icon"]
    for i, sym in enumerate(("←", "→", "↻")):
        d.text((18 + i * 36, top + 12), sym, font=font(18), fill=icon)
    d.rounded_rectangle((128, top + 8, W - 130, top + TOOLBAR_H - 8), radius=16, fill=c["omnibox_background"])
    d.ellipse((144, top + 18, 156, top + 30), outline=icon, width=2)
    d.text((170, top + 15), "Search or type a web address", font=f_tab, fill=c["omnibox_text"])
    for i in range(3):
        cx = W - 104 + i * 34
        d.ellipse((cx, top + 16, cx + 16, top + 32), outline=icon, width=2)
    by = top + TOOLBAR_H
    for i, label in enumerate(("Docs", "Status", "Panel", "Mail", "Reading list")):
        d.text((20 + i * 120, by + 9), "▪ " + label, font=f_small, fill=c["bookmark_text"])

    # New tab page.
    ntp_top = by + BOOKMARKS_H
    if "theme_ntp_background" in images:
        bg = Image.open(theme_dir / images["theme_ntp_background"]).convert("RGB")
        left = (bg.width - W) // 2
        im.paste(bg.crop((left, 0, left + W, H - ntp_top)), (0, ntp_top))
    d.text((W // 2, ntp_top + 150), "Lumen", font=font(54, True), fill=c["ntp_text"], anchor="mm")
    d.rounded_rectangle((W // 2 - 290, ntp_top + 210, W // 2 + 290, ntp_top + 256), radius=23,
                        fill=c["omnibox_background"])
    d.text((W // 2 - 260, ntp_top + 233), "Search the web", font=font(15), fill=c["omnibox_text"], anchor="lm")
    for i, label in enumerate(("Docs", "Status", "Panel", "Mail", "Add")):
        cx = W // 2 - 240 + i * 120
        d.rounded_rectangle((cx - 28, ntp_top + 300, cx + 28, ntp_top + 356), radius=14, fill=c["toolbar"])
        d.text((cx, ntp_top + 328), label[0], font=font(20, True), fill=c["ntp_link"], anchor="mm")
        d.text((cx, ntp_top + 372), label, font=f_small, fill=c["ntp_text"], anchor="mm")
    d.text((W // 2, H - 40), "Customize this page", font=f_small, fill=c["ntp_link"], anchor="mm")
    return im


def contact_sheet(items: list[tuple[str, Image.Image]]) -> Image.Image:
    tw, th, pad, label = 640, 400, 24, 30
    cols = 2
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tw + pad) + pad, rows * (th + pad + label) + pad), (14, 18, 28))
    d = ImageDraw.Draw(sheet)
    for i, (name, im) in enumerate(items):
        x = pad + (i % cols) * (tw + pad)
        y = pad + (i // cols) * (th + pad + label)
        d.text((x, y + 4), name, font=font(16, True), fill=(235, 240, 248))
        sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, y + label))
    return sheet


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 2:
        print("usage: preview.py DIST PREVIEWS", file=sys.stderr)
        return 2
    dist, out = Path(args[0]), Path(args[1])
    out.mkdir(parents=True, exist_ok=True)
    order = ["luminare", "graphite", "aurora", "contrast"]

    def key(p: Path) -> tuple:
        slug = p.name.removeprefix("lumen-").rsplit("-", 1)[0]
        return (order.index(slug) if slug in order else len(order), slug, p.name.endswith("-light"))

    folders = sorted((p for p in dist.iterdir() if (p / "manifest.json").is_file()), key=key)
    if not folders:
        print(f"no theme folders in {dist}", file=sys.stderr)
        return 1
    items = []
    for folder in folders:
        im = render(folder)
        im.save(out / f"{folder.name}.png", optimize=True)
        items.append((json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["name"], im))
        print(f"{folder.name}.png")
    contact_sheet(items).save(out / "contact-sheet.png", optimize=True)
    print("contact-sheet.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
