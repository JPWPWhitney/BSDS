import "./style.css";

import { python } from "@codemirror/lang-python";
import { oneDark } from "@codemirror/theme-one-dark";
import { basicSetup, EditorView } from "codemirror";

import { decodeRun } from "./bsd1";
import {
  base64ToArrayBuffer,
  describeRunError,
  normalizeLabConfig,
  type LabConfig,
  type RunResponse,
} from "./labcore";
import { presentRun, type Presented } from "./present";
import { createViewer } from "./scene";

interface TemplateEntry {
  id: string;
  title: string;
  file: string;
}

const statusEl = () => document.getElementById("run-status")!;
const outputBox = () => document.getElementById("lab-output")!;
const outputText = () => document.getElementById("lab-output-text")!;

async function loadConfig(): Promise<LabConfig> {
  try {
    const res = await fetch("./data/lab-config.json");
    if (!res.ok) return { endpoint: null, gated: false };
    return normalizeLabConfig(await res.json());
  } catch {
    return { endpoint: null, gated: false };
  }
}

async function loadTemplates(): Promise<TemplateEntry[]> {
  try {
    const res = await fetch("./data/templates.json");
    if (!res.ok) return [];
    const json = (await res.json()) as { templates: TemplateEntry[] };
    return json.templates ?? [];
  } catch {
    return [];
  }
}

async function boot() {
  const config = await loadConfig();
  const templates = await loadTemplates();

  const editor = new EditorView({
    parent: document.getElementById("editor")!,
    extensions: [basicSetup, python(), oneDark, EditorView.lineWrapping],
  });

  const select = document.getElementById("template-select") as HTMLSelectElement;
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

  const runBtn = document.getElementById("run-btn") as HTMLButtonElement;
  const passcode = document.getElementById("passcode") as HTMLInputElement;

  if (!config.endpoint) {
    statusEl().textContent = "backend not deployed yet — editing only";
    runBtn.title = "The Mission Lab backend has not been deployed (owner setup pending).";
  } else {
    runBtn.disabled = false;
    if (config.gated) {
      passcode.hidden = false;
      passcode.value = localStorage.getItem("bsds-passcode") ?? "";
    }
  }

  const viewer = createViewer(document.getElementById("cesium-container")!);
  let presented: Presented | null = null;

  runBtn.addEventListener("click", async () => {
    if (!config.endpoint) return;
    runBtn.disabled = true;
    outputBox().hidden = true;
    statusEl().textContent = "flying your mission…";
    if (config.gated) localStorage.setItem("bsds-passcode", passcode.value);
    try {
      const res = await fetch(`${config.endpoint}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: editor.state.doc.toString(),
          passcode: config.gated ? passcode.value : null,
        }),
      });
      if (res.status === 401) {
        statusEl().textContent = "bad passcode";
        return;
      }
      if (!res.ok) {
        statusEl().textContent = `backend error: HTTP ${res.status}`;
        return;
      }
      const body = (await res.json()) as RunResponse;
      if (body.user_stdout) {
        outputText().textContent = body.user_stdout + (body.truncated ? "\n…[truncated]" : "");
        outputBox().hidden = false;
      }
      if (!body.ok || !body.bsd1_b64) {
        outputText().textContent = `${describeRunError(body)}\n\n${body.user_stdout ?? ""}`;
        outputBox().hidden = false;
        statusEl().textContent = "run failed — see output";
        return;
      }
      const run = decodeRun(base64ToArrayBuffer(body.bsd1_b64));
      presented?.dispose();
      presented = presentRun(viewer, run, {
        title: document.getElementById("run-title")!,
        charts: document.getElementById("charts-panel")!,
        metrics: document.getElementById("metrics-panel")!,
      });
      const elapsed = body.info["elapsed_s"];
      statusEl().textContent = typeof elapsed === "number" ? `simulated in ${elapsed}s` : "";
    } catch (err) {
      statusEl().textContent = `request failed: ${String(err)}`;
    } finally {
      runBtn.disabled = !config.endpoint;
    }
  });
}

void boot();
