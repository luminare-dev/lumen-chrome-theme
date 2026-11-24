# Install the Lumen Chrome theme

Each theme is one mode: install the dark or the light one (a browser theme cannot follow the
system setting). Incognito windows always use the dark palette.

## Get a theme

- **Prebuilt:** open the latest run of the `themes` workflow under the repository's Actions tab
  and download the `themes` artifact. It holds one ZIP per preset and mode, for example
  `lumen-luminare-dark.zip`.
- **From the customizer:** open [`customizer/index.html`](../customizer/index.html), pick or set
  your colours and press **Download theme ZIP**.
- **From source:** `python3 generator/lumen_chrome.py --all --out dist` (Python 3.10 or newer,
  nothing else to install).

## Load it (Chrome, Edge, Brave, Vivaldi, Opera and other Chromium browsers)

1. Unzip the ZIP into a folder you keep; the browser reads the theme from there.
2. Open `chrome://extensions` (Edge: `edge://extensions`).
3. Turn on **Developer mode** (top right; Edge: left sidebar).
4. Choose **Load unpacked** and select the folder that holds `manifest.json`.

The window changes at once. Loading another theme replaces it: a browser has one theme at a
time.

Notes:

- Some browsers ignore parts of a theme or only take themes from their own store. Edge and Opera
  apply the colours; Brave and Vivaldi have their own theme systems and may only use some of them.
- Unpacked themes stay installed after a restart. On managed computers, a policy may block
  developer mode.

## Update or switch

Load the new folder the same way; it replaces the old theme. To switch between dark and light,
load the other folder.

## Remove

Open the browser settings, **Appearance**, and choose **Reset to default** next to *Theme*. Then
delete the folder.

## Chrome Web Store

Not listed yet. A free listing of the stock themes is planned; until then, load the folder as
above. The store needs a packed upload of the same files, so nothing about the themes changes.
