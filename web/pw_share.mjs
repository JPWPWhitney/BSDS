// E2E: share links, ?src= loading, and #code= loading in the lab pages.
// Usage: node pw_share.mjs <baseURL>
import { readFileSync } from "node:fs";
import { chromium } from "playwright";

const [baseURL] = process.argv.slice(2);

async function gzipBase64Url(text) {
  const cs = new CompressionStream("gzip");
  const writer = cs.writable.getWriter();
  const writing = writer.write(new TextEncoder().encode(text)).then(() => writer.close());
  const gz = await new Response(cs.readable).arrayBuffer();
  await writing;
  return Buffer.from(gz).toString("base64url");
}

const editorHas = (needle) =>
  `document.querySelector(".cm-content")?.textContent?.includes(${JSON.stringify(needle)})`;

const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });

try {
  // (a) edit code in the Mission Lab, click Share, open the produced link elsewhere
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errorsA = [];
  page.on("pageerror", (err) => errorsA.push(String(err)));
  await page.goto(`${baseURL}/lab.html`, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(editorHas("basic_orbit"), null, { timeout: 30000 });

  await page.locator(".cm-content").click();
  await page.keyboard.press("Control+a");
  await page.keyboard.type('# shared via link\nprint("hello from a shared link")');
  await page.waitForFunction(editorHas("hello from a shared link"), null, { timeout: 10000 });

  await page.locator("#share-btn").click();
  await page.waitForFunction(
    () => document.getElementById("lab-output-text")?.textContent?.includes("#code="),
    null,
    { timeout: 10000 },
  );
  const outText = await page.locator("#lab-output-text").textContent();
  const shareUrl = outText.split("\n").find((l) => l.startsWith("http"));
  if (!shareUrl) throw new Error(`no share URL in output panel:\n${outText}`);
  console.log("SHARE-URL:", `${shareUrl.slice(0, 80)}… (${shareUrl.length} chars)`);

  const page2 = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page2.goto(shareUrl, { waitUntil: "domcontentloaded" });
  await page2.waitForFunction(editorHas("hello from a shared link"), null, { timeout: 30000 });
  const marker = await page2.locator("#template-select option[data-external]").textContent();
  if (marker !== "shared code") throw new Error(`unexpected select marker: ${marker}`);
  if (errorsA.length) throw new Error(`page errors: ${errorsA.join("; ")}`);
  console.log("E2E-A PASS: share link round-trips edited code between pages");
  await page2.close();
  await page.close();

  // (b) ?src= loads a same-origin file into the editor
  const pageB = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await pageB.goto(`${baseURL}/lab.html?src=/data/templates/hohmann.py`, {
    waitUntil: "domcontentloaded",
  });
  await pageB.waitForFunction(editorHas("hohmann"), null, { timeout: 30000 });
  console.log("E2E-B PASS: ?src= loaded hohmann.py into the editor");
  await pageB.close();

  // (c) wasm.html#code= loads an edited basic_orbit variant; no page errors for 5s
  const template = readFileSync(new URL("./public/data/templates/basic_orbit.py", import.meta.url), "utf8");
  const encoded = await gzipBase64Url(`# shared variant for e2e\n${template}`);
  const pageC = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errorsC = [];
  pageC.on("pageerror", (err) => errorsC.push(String(err)));
  await pageC.goto(`${baseURL}/wasm.html#code=${encoded}`, { waitUntil: "domcontentloaded" });
  await pageC.waitForFunction(editorHas("shared variant for e2e"), null, { timeout: 30000 });
  await pageC.waitForTimeout(5000);
  if (errorsC.length) throw new Error(`page errors: ${errorsC.join("; ")}`);
  console.log("STATUS-C:", await pageC.locator("#run-status").textContent());
  console.log("E2E-C PASS: wasm.html#code= loaded shared code, no page errors for 5s");
  await pageC.close();

  console.log("E2E PASS");
} finally {
  await browser.close();
}
