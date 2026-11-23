// CI only: load each unpacked theme into Playwright's Chromium and screenshot its new tab page.
//   node ntp.mjs <dist folder> <output folder>
// Writes <output>/<theme>-ntp.png and <output>/ntp-report.json. A theme that does not apply
// (a pixel near the bottom left is not the theme's ntp_background) is reported and fails the run.

// The colour of a 1x1 PNG screenshot: one row, so every PNG filter leaves the bytes unchanged.
function pixel(buf) {
    let pos = 8;
    const idat = [];
    while (pos < buf.length) {
        const len = buf.readUInt32BE(pos);
        if (buf.toString("latin1", pos + 4, pos + 8) === "IDAT") idat.push(buf.subarray(pos + 8, pos + 8 + len));
        pos += 12 + len;
    }
    const raw = inflateSync(Buffer.concat(idat));
    return [raw[1], raw[2], raw[3]];
}
import { chromium } from "playwright";
import { mkdirSync, mkdtempSync, readdirSync, existsSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { inflateSync } from "node:zlib";
import { join, resolve } from "node:path";

const [dist, out] = process.argv.slice(2).map((p) => resolve(p));
mkdirSync(out, { recursive: true });
const themes = readdirSync(dist).filter((n) => existsSync(join(dist, n, "manifest.json"))).sort();
const report = [];
let failed = 0;

for (const name of themes) {
    const dir = join(dist, name);
    const manifest = JSON.parse(readFileSync(join(dir, "manifest.json"), "utf8"));
    const want = manifest.theme.colors.ntp_background;
    const profile = mkdtempSync(join(tmpdir(), "lumen-ntp-"));
    const context = await chromium.launchPersistentContext(profile, {
        channel: "chromium", // the full browser in new headless mode: it loads extensions and themes
        headless: true,
        viewport: { width: 1280, height: 800 },
        args: [`--disable-extensions-except=${dir}`, `--load-extension=${dir}`, "--no-first-run"],
    });
    const entry = { theme: name, expected: want };
    try {
        const page = context.pages()[0] ?? (await context.newPage());
        await page.goto("chrome://new-tab-page/", { waitUntil: "load" });
        await page.waitForTimeout(1500);
        const m = pixel(await page.screenshot({ clip: { x: 20, y: 790, width: 1, height: 1 } }));
        entry.background = `rgb(${m.join(", ")})`;
        entry.applied = m.every((v, i) => Math.abs(v - want[i]) <= 3);
        await page.screenshot({ path: join(out, `${name}-ntp.png`) });
    } catch (err) {
        entry.error = String(err);
        entry.applied = false;
    } finally {
        await context.close();
        rmSync(profile, { recursive: true, force: true });
    }
    if (!entry.applied) failed++;
    report.push(entry);
    console.log(`${entry.applied ? "ok  " : "FAIL"} ${name}: page ${entry.background ?? entry.error}, theme rgb(${want.join(", ")})`);
}
writeFileSync(join(out, "ntp-report.json"), JSON.stringify(report, null, 2) + "\n");
if (failed) {
    console.error(`${failed} theme(s) did not apply on the new tab page`);
    process.exit(1);
}
