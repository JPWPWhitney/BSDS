// Generic Pyodide-in-Node runner.
// Usage: node run_in_pyodide.mjs <script.py> [wheel1.whl wheel2.whl ...]
// Loads pyodide, installs the given wheels via unpackArchive, runs the python
// script, prints its stdout. Exits non-zero on any python exception.
import { loadPyodide } from "pyodide";
import { readFileSync } from "node:fs";
import { basename } from "node:path";

const [, , pyFile, ...wheels] = process.argv;
if (!pyFile) {
  console.error("usage: node run_in_pyodide.mjs <script.py> [wheels...]");
  process.exit(2);
}

const t0 = Date.now();
const pyodide = await loadPyodide();
const tLoad = Date.now();
console.error(`[harness] pyodide ${pyodide.version} booted in ${tLoad - t0} ms`);

for (const w of wheels) {
  const raw = readFileSync(w);
  // pyodide 0.29 unpackArchive rejects Node's Buffer subclass -> plain Uint8Array view
  const buf = new Uint8Array(raw.buffer, raw.byteOffset, raw.byteLength);
  const tw = Date.now();
  if (w.endsWith(".whl")) {
    pyodide.unpackArchive(buf, "wheel");
  } else if (w.endsWith(".zip")) {
    pyodide.unpackArchive(buf, "zip");
  } else {
    throw new Error(`unknown archive type: ${w}`);
  }
  console.error(`[harness] installed ${basename(w)} (${(buf.length / 1e6).toFixed(2)} MB) in ${Date.now() - tw} ms`);
}

const code = readFileSync(pyFile, "utf8");
try {
  await pyodide.runPythonAsync(code);
} catch (err) {
  console.error(err);
  process.exit(1);
}
console.error(`[harness] total wall time ${Date.now() - t0} ms`);
