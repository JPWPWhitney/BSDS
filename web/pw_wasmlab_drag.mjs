// E2E: WASM Lab runs the Drag Deorbit template in a real browser.
// Usage: node pw_wasmlab_drag.mjs <baseURL> <screenshot.png>
import { chromium } from "playwright";

const [baseURL, shot] = process.argv.slice(2);
const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on("pageerror", (err) => errors.push(String(err)));

try {
  await page.goto(`${baseURL}/wasm.html`, { waitUntil: "domcontentloaded" });

  // 1. wait for pyodide + wheels + bsds_sims boot
  await page.waitForFunction(
    () => document.getElementById("run-status")?.textContent?.includes("ready"),
    null,
    { timeout: 120000 },
  );
  console.log("STATUS-1:", await page.locator("#run-status").textContent());

  // 2. pick the Drag Deorbit template and wait for its code to load
  await page.selectOption("#template-select", { label: "Drag Deorbit" });
  await page.waitForFunction(
    () => document.querySelector(".cm-content")?.textContent?.includes("dragDynamicEffector"),
    null,
    { timeout: 15000 },
  );
  console.log("TEMPLATE: Drag Deorbit loaded into editor");

  // 3. run it (default params BC=25, alt=300 -> ~8 days sim, heavier than the
  //    validation point but still fine in-browser). The run blocks the main
  //    thread, so skip Playwright's post-click settling or the click times out.
  await page.locator("#run-btn").dispatchEvent("click");
  await page.waitForFunction(
    () => {
      const s = document.getElementById("run-status")?.textContent ?? "";
      return s.includes("simulated in your browser") || s.includes("failed");
    },
    null,
    { timeout: 600000 },
  );
  const status = await page.locator("#run-status").textContent();
  console.log("STATUS-2:", status);
  const metrics = await page.locator("#metrics-panel").textContent().catch(() => "");
  console.log("METRICS:", (metrics ?? "").replace(/\s+/g, " ").trim().slice(0, 300));
  await page.screenshot({ path: shot });
  console.log("SCREENSHOT", shot);
  if (!status?.includes("simulated in your browser")) {
    const out = await page.locator("#lab-output-text").textContent().catch(() => "");
    console.log("OUTPUT:", (out ?? "").slice(0, 2000));
    throw new Error("run did not succeed");
  }
  console.log("PAGEERRORS:", errors.length);
  console.log("E2E PASS");
} finally {
  await browser.close();
}
