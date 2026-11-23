"""Tests for the theme generator, the validator and the customizer page (standard library only)."""

from __future__ import annotations

import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from generator import embed, png, validate  # noqa: E402
from generator import lumen_chrome as lc  # noqa: E402

SMALL = (320, 180)


def tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="lumen-chrome-test-"))
    unittest.addModuleCleanup(shutil.rmtree, d, ignore_errors=True)
    return d


def decode_png(data: bytes) -> tuple[int, int, int, bytes]:
    """Width, height, channels and raw pixel rows (filter bytes removed) of our own PNGs."""
    w, h = png.read_size(data)
    channels = 4 if data[25] == 6 else 3
    pos, idat = 8, b""
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        if kind == b"IDAT":
            idat += data[pos + 8:pos + 8 + length]
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = w * channels + 1
    return w, h, channels, b"".join(raw[i * stride + 1:(i + 1) * stride] for i in range(h))


class TokenTests(unittest.TestCase):
    def test_presets_are_valid(self):
        for name in lc.PRESET_ORDER:
            doc = json.loads((lc.PRESETS / f"{name}.json").read_text(encoding="utf-8"))
            _, problems = lc.normalize(doc)
            self.assertEqual(problems, [], name)

    def test_invalid_values_fall_back_and_are_reported(self):
        tokens, problems = lc.normalize({"meta": {"name": "<x>"}, "color": {"light": {"accent": "blue"}},
                                         "layout": {"backgroundGlow": 1}})
        self.assertEqual(problems, ["meta.name", "color.light.accent", "layout.backgroundGlow"])
        self.assertEqual(tokens["meta"]["name"], "Luminare")
        self.assertEqual(tokens["color"]["light"]["accent"], "#1F47C4")

    def test_not_a_document(self):
        tokens, problems = lc.normalize([1, 2])
        self.assertEqual(problems, ["(document)"])
        self.assertEqual(tokens["meta"]["name"], "Luminare")

    def test_light_frame_differs_from_toolbar(self):
        for name in lc.PRESET_ORDER:
            tokens, _ = lc.normalize(json.loads((lc.PRESETS / f"{name}.json").read_text(encoding="utf-8")))
            for mode in lc.MODES:
                c = lc.theme_colors(tokens, mode)
                self.assertGreaterEqual(lc.contrast(c["frame"], c["toolbar"]), 1.12, f"{name}/{mode}")

    def test_mix_rounds_half_up(self):
        self.assertEqual(lc.mix((0, 0, 0), (1, 3, 255), 0.5), (1, 2, 128))

    def test_hsl_tint_whole_numbers_are_ints(self):
        self.assertEqual(lc.hsl_tint((255, 255, 255)), [0, 0, 1])
        self.assertIsInstance(lc.hsl_tint((128, 128, 128))[0], int)


class PngTests(unittest.TestCase):
    def test_solid_round_trip(self):
        w, h, ch, raw = decode_png(png.solid(4, 3, (1, 2, 3)))
        self.assertEqual((w, h, ch), (4, 3, 3))
        self.assertEqual(raw, bytes([1, 2, 3]) * 12)

    def test_ntp_edges_are_plain_background(self):
        tokens, _ = lc.normalize(json.loads((lc.PRESETS / "luminare.json").read_text(encoding="utf-8")))
        w, h, _, raw = decode_png(lc.ntp_image(tokens, "dark", "dots", SMALL))
        base = bytes(lc.rgb(tokens["color"]["dark"]["canvas"]))
        for y in range(h):
            row = raw[y * w * 3:(y + 1) * w * 3]
            self.assertEqual(row[:3], base, f"left edge, row {y}")
            self.assertEqual(row[-3:], base, f"right edge, row {y}")
        self.assertEqual(raw[-w * 3:], base * w, "bottom row")
        self.assertNotEqual(raw[:w * 3], base * w, "the light shows at the top")

    def test_icon_is_rgba_with_transparent_corner(self):
        tokens, _ = lc.normalize({})
        w, h, ch, raw = decode_png(lc.icon_image(tokens, "dark", 48))
        self.assertEqual((w, h, ch), (48, 48, 4))
        self.assertEqual(raw[3], 0)
        self.assertEqual(raw[(24 * 48 + 24) * 4 + 3], 255)


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = tmp()
        for name in lc.PRESET_ORDER:
            tokens, _ = lc.normalize(json.loads((lc.PRESETS / f"{name}.json").read_text(encoding="utf-8")))
            for mode in lc.MODES:
                files = lc.build_files(tokens, mode, "0.1.0", ntp_size=SMALL)
                lc.write_dir(files, cls.out / f"lumen-{name}-{mode}")
                lc.write_zip(files, cls.out / f"lumen-{name}-{mode}.zip")

    def test_every_package_validates(self):
        for p in sorted(self.out.iterdir()):
            self.assertEqual(validate.check(p), [], p.name)

    def test_zip_is_deterministic(self):
        tokens, _ = lc.normalize({})
        a, b = self.out / "a.zip", self.out / "b.zip"
        lc.write_zip(lc.build_files(tokens, "dark", "0.1.0", ntp_size=SMALL), a)
        lc.write_zip(lc.build_files(tokens, "dark", "0.1.0", ntp_size=SMALL), b)
        self.assertEqual(a.read_bytes(), b.read_bytes())
        with zipfile.ZipFile(a) as z:
            self.assertIn("manifest.json", z.namelist())

    def test_validator_catches_mistakes(self):
        d = self.out / "broken"
        shutil.copytree(self.out / "lumen-luminare-dark", d)
        m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        m["theme"]["colors"]["toolbar_colour"] = [1, 2, 3]
        m["theme"]["colors"]["tab_text"] = list(m["theme"]["colors"]["toolbar"])
        m["theme"]["properties"]["ntp_background_repeat"] = "tile"
        m["background"] = {"service_worker": "x.js"}
        (d / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
        (d / "images" / "toolbar.png").write_bytes(b"GIF89a")
        errors = "\n".join(validate.check(d))
        for needle in ("toolbar_colour", "tab_text on toolbar", "ntp_background_repeat", "'background'", "not a PNG"):
            self.assertIn(needle, errors)

    def test_cli_single_file(self):
        out = tmp()
        code = lc.main([str(lc.PRESETS / "aurora.json"), "--mode", "light", "--out", str(out), "--ntp-size", "64x36"])
        self.assertEqual(code, 0)
        self.assertTrue((out / "manifest.json").is_file())
        self.assertTrue((out / "lumen-aurora-light.zip").is_file())


class CustomizerTests(unittest.TestCase):
    page = (ROOT / "customizer" / "index.html").read_text(encoding="utf-8")

    def test_presets_and_version_are_embedded(self):
        self.assertEqual(embed.render(self.page), self.page, "run python3 generator/embed.py")

    def test_no_external_requests(self):
        self.assertIn("Content-Security-Policy", self.page)
        self.assertIn("default-src 'none'", self.page)
        for pattern in (r'\b(?:src|href)="(?:https?:)?//', r"url\(\s*['\"]?(?:https?:)?//", r"\bfetch\(",
                        r"XMLHttpRequest", r"\bimport\(", r"<link\b", r"WebSocket"):
            self.assertIsNone(re.search(pattern, self.page), pattern)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_parity_with_the_python_generator(self):
        r = subprocess.run(["node", str(ROOT / "tests" / "test_parity.mjs")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
