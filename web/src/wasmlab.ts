import "./style.css";

import { python } from "@codemirror/lang-python";
import { oneDark } from "@codemirror/theme-one-dark";
import { basicSetup, EditorView } from "codemirror";

import { decodeRun } from "./bsd1";
import { presentRun, type Presented } from "./present";
import { createViewer } from "./scene";
import { filterWasmTemplates, PY_DRIVER, type TemplateEntry } from "./wasmcore";

const WHEELS = [
  "./wasm/numpy-2.2.5-cp313-cp313-pyemscripten_2025_0_wasm32.whl",
  "./wasm/bskcore-2.11.1-cp313-cp313-pyemscripten_2025_0_wasm32.whl",
];
const PYLIB_FILES = ["__init__.py", "bsd1.py", "recording.py"];

const statusEl = () => document.getElementById("run-status")!;
const outputBox = () => document.getElementById("lab-output")!;
const outputText = () => document.getElementById("lab-output-text")!;

interface PyodideLike {
  version: string;
  FS: {
    mkdirTree(path: string): void;
    writeFile(path: string, data: string): void;
  };
  globals: { set(name: string, value: unknown): void };
  runPython(code: string): unknown;
  unpackArchive(buffer: ArrayBuffer, format: string): void;
}

async function bootPyodide(onStatus: (msg: string) => void): Promise<PyodideLike> {
  onStatus("booting Python runtime…");
  const moduleUrl = new URL("./pyodide/pyodide.mjs", document.baseURI).href;
  const { loadPyodide } = await import(/* @vite-ignore */ moduleUrl);
  const indexURL = new URL("./pyodide/", document.baseURI).href;
  const pyodide = (await loadPyodide({ indexURL })) as PyodideLike;

  for (const wheel of WHEELS) {
    const name = wheel.split("/").pop()!;
    onStatus(`installing ${name.split("-")[0]}…`);
    const res = await fetch(wheel);
    if (!res.ok) throw new Error(`failed to fetch ${wheel}: HTTP ${res.status}`);
    pyodide.unpackArchive(await res.arrayBuffer(), "wheel");
  }

  onStatus("installing bsds_sims…");
  pyodide.FS.mkdirTree("/home/pyodide/bsds_sims");
  for (const f of PYLIB_FILES) {
    const res = await fetch(`./data/pylib/bsds_sims/${f}`);
    if (!res.ok) throw new Error(`failed to fetch pylib ${f}: HTTP ${res.status}`);
    pyodide.FS.writeFile(`/home/pyodide/bsds_sims/${f}`, await res.text());
  }
  pyodide.runPython('import sys; sys.path.insert(0, "/home/pyodide")');
  pyodide.runPython(PY_DRIVER);
  return pyodide;
}

async function boot() {
  const editor = new EditorView({
    parent: document.getElementById("editor")!,
    extensions: [basicSetup, python(), oneDark, EditorView.lineWrapping],
  });

  const select = document.getElementById("template-select") as HTMLSelectElement;
  const templates: TemplateEntry[] = await (async () => {
    try {
      const res = await fetch("./data/templates.json");
      if (!res.ok) return [];
      return filterWasmTemplates(((await res.json()) as { templates: TemplateEntry[] }).templates ?? []);
    } catch {
      return [];
    }
  })();
  for (const t of templates) {
    const opt = document.createElement("option");
    opt.value = t.file;
    opt.textContent = t.title;
    select.appendChild(opt);
  }
  async function loadTemplate(file: string) {
    const res = await fetch(`./data/${file}`);
    const code = res.ok ? await res.text() : "# failed to load template";
    editor.dispatch({ changes: { from: 0, to: editor.state.doc.length, insert: code } });
  }
  select.addEventListener("change", () => void loadTemplate(select.value));
  if (templates.length) await loadTemplate(templates[0].file);

  const viewer = createViewer(document.getElementById("cesium-container")!);
  let presented: Presented | null = null;

  const runBtn = document.getElementById("run-btn") as HTMLButtonElement;

  let pyodide: PyodideLike;
  try {
    pyodide = await bootPyodide((msg) => (statusEl().textContent = msg));
  } catch (err) {
    statusEl().textContent = `WASM runtime failed to load: ${String(err)}`;
    return;
  }
  statusEl().textContent = "ready — Basilisk is loaded in your browser";
  runBtn.disabled = false;

  runBtn.addEventListener("click", () => {
    runBtn.disabled = true;
    outputBox().hidden = true;
    statusEl().textContent = "flying your mission (in this tab)…";
    // Yield a frame so the status paints before the synchronous run.
    requestAnimationFrame(() => {
      setTimeout(() => {
        try {
          pyodide.globals.set("__user_code", editor.state.doc.toString());
          const proxy = pyodide.runPython("_bsds_run(__user_code)") as {
            toJs(opts: { dict_converter: typeof Object.fromEntries }): {
              bsd1: Uint8Array;
              stdout: string;
              elapsed: number;
            };
            destroy(): void;
          };
          const result = proxy.toJs({ dict_converter: Object.fromEntries });
          proxy.destroy();
          if (result.stdout) {
            outputText().textContent = result.stdout;
            outputBox().hidden = false;
          }
          const bytes = result.bsd1;
          const buf = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
          const run = decodeRun(buf as ArrayBuffer);
          presented?.dispose();
          presented = presentRun(viewer, run, {
            title: document.getElementById("run-title")!,
            charts: document.getElementById("charts-panel")!,
            metrics: document.getElementById("metrics-panel")!,
          });
          statusEl().textContent = `simulated in your browser in ${result.elapsed}s`;
        } catch (err) {
          const msg = String(err);
          outputText().textContent = msg;
          outputBox().hidden = false;
          statusEl().textContent = "run failed — see output";
        } finally {
          runBtn.disabled = false;
        }
      }, 30);
    });
  });
}

void boot();
