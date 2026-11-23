# Customize a Lumen browser theme

There are two ways, and both give the same `manifest.json` for the same token file (a CI test
compares them byte for byte).

## The customizer page

[`customizer/index.html`](../customizer/index.html) is one self-contained file: download it and
open it in a current browser, from disk or from any static host. It loads nothing from the
network (its Content Security Policy forbids it) and stores nothing.

1. **Preset**: Luminare, Graphite, Aurora or High contrast.
2. **Mode**: dark or light. The colour list and the preview follow the mode; each mode is its own
   theme.
3. **Name**: shown in `chrome://extensions` as *Lumen &lt;name&gt; Dark* or *Light*.
4. **Accent light** and **New tab pattern**: the soft light at the top of the new tab page and an
   optional dot grid.
5. **Colours**: every colour role of the token schema. Roles marked *panel only* do not change the
   browser theme but are kept for the export.
6. Contrast warnings list every text pair below WCAG 4.5:1 (3:1 for icons). They do not block the
   download.
7. **Download theme ZIP** builds the current mode, **Dark and light** builds both. The images are
   drawn on a canvas in the page.
8. **Import tokens** takes a pasted token JSON or a file, **Export tokens** saves the current one.
   Keys the browser theme does not use (fonts, radius, layout, branding) are kept as they are, so
   a file can go back and forth between this page and the Lumen panel themes.

Invalid values in an imported file (a colour that is not `#RRGGBB`, an unknown version) are
replaced by the Luminare default, and the page says which paths it replaced.

## From the command line

```bash
python3 generator/lumen_chrome.py tokens.json --out dist              # both modes, folders and ZIPs
python3 generator/lumen_chrome.py tokens.json --mode light --out dist/light
python3 generator/lumen_chrome.py tokens.json --out dist --pattern none --no-zip
python3 generator/validate.py dist/lumen-*-dark dist/lumen-*-light
```

`--ntp-size WxH` changes the new tab image (default 2560x1440). Only the Python standard library
is needed. To preview, install Pillow and run `python3 generator/preview.py dist previews`.

## Token mapping

The token schema is documented in lumen-hydrodactyl-theme (`docs/tokens.md`). This target reads
`meta.name`, `meta.description`, `color.dark.*`, `color.light.*` and `layout.backgroundGlow`.

| Theme colour | From (mode palette) |
|---|---|
| `frame` | dark: `canvas`; light: `surfaceSunken` 45 % towards `border` |
| `frame_inactive` | `frame` halfway to `surfaceSunken` (dark) or `canvas` (light) |
| `toolbar` | `surface`, nudged towards `text` until it differs from the frame (1.12:1) |
| `tab_text`, `toolbar_text`, `bookmark_text`, `omnibox_text`, `ntp_text` | `text` |
| `tab_background_text` | `textMuted` |
| `toolbar_button_icon` | `textMuted` 35 % towards `text` |
| `omnibox_background` | `surfaceSunken`, nudged until it differs from the toolbar |
| `ntp_background` | `canvas` |
| `ntp_link`, `ntp_header` | `accentText`, `accent` |
| `frame_incognito*`, `*_incognito*` | the dark palette: `canvas` darkened 25 %, `textMuted` |
| `background_tab*` | the matching frame colour (tabs sit flat on the frame) |

Images: the frame PNGs carry a faint accent light at the top, the toolbar PNG is the toolbar
colour, and the new tab PNG is `canvas` with two lights (`accent`, `accentSecondary`) and the dot
grid in `accentText`. Its edges are the plain background, so wider windows show no seam. The
icon is a rounded square in the accent gradient with a ring in `accentContrast`.

`theme.tints.buttons` is the icon colour as HSL; the other tints are `-1` (no change), because
every frame has its own colour and image. `ntp_logo_alternate` is 1 in dark themes.
