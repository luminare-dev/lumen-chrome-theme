// The customizer's colour core (the "lumen-core" script in customizer/index.html) must give the
// same manifest bytes and the same replaced paths as generator/lumen_chrome.py.
//   node tests/test_parity.mjs
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const root = fileURLToPath(new URL("..", import.meta.url));
const page = readFileSync(root + "customizer/index.html", "utf8");
const core = page.match(/<script id="lumen-core">([\s\S]*?)<\/script>/)[1];
const presets = JSON.parse(page.match(/<script type="application\/json" id="lumen-presets">([\s\S]*?)<\/script>/)[1]);
const sandbox = {};
vm.runInNewContext(core, sandbox);
const LC = sandbox.LumenChrome;

const py = JSON.parse(execFileSync("python3", [root + "tests/parity_dump.py"], { encoding: "utf8" }));
let failed = 0;
for (const [name, doc] of Object.entries(py.cases)) {
    const res = LC.normalize(doc, presets.luminare);
    if (JSON.stringify(res.problems) !== JSON.stringify(py.problems[name])) {
        failed++;
        console.error(`${name}: problems differ\n  js: ${res.problems}\n  py: ${py.problems[name]}`);
    }
    for (const mode of ["dark", "light"]) {
      for (const pattern of ["dots", "none"]) {
        if (LC.defaultNtpImage(mode, pattern, res.tokens) !== py.defaults[`${name}/${mode}/${pattern}`]) {
            failed++;
            console.error(`${name}/${mode}/${pattern}: default new tab image differs`);
        }
      }
      for (const image of [1, 0]) {
        const js = LC.manifestText(res.tokens, mode, "1.2.3", Boolean(image));
        const want = py.manifests[`${name}/${mode}/${image}`];
        if (js !== want) {
            failed++;
            const a = js.split("\n"), b = want.split("\n");
            const i = a.findIndex((l, k) => l !== b[k]);
            console.error(`${name}/${mode}/${image}: manifest differs at line ${i + 1}\n  js: ${a[i]}\n  py: ${b[i]}`);
        } else {
            console.log(`ok ${name}/${mode}/${image}`);
        }
      }
    }
}
if (failed) {
    console.error(`${failed} difference(s)`);
    process.exit(1);
}
