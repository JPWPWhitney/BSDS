// Visual verification harness (dev tool, not shipped).
// Usage: node screenshot.mjs <url> <outfile> [waitMs]
import { chromium } from "playwright";

const [url, outfile, waitMs = "9000"] = process.argv.slice(2);
const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

const errors = [];
page.on("console", (msg) => {
  if (msg.type() === "error") errors.push(msg.text());
});
page.on("pageerror", (err) => errors.push(String(err)));

await page.goto(url, { waitUntil: "networkidle" });
await page.waitForTimeout(Number(waitMs));

await page.screenshot({ path: outfile });
console.log("SCREENSHOT", outfile);
console.log("CONSOLE_ERRORS", errors.length);
for (const e of errors.slice(0, 10)) console.log("ERR:", e.slice(0, 300));
await browser.close();
