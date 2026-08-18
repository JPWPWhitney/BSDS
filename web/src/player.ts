import "./style.css";

import { decodeRun, type RunData } from "./bsd1";
import { buildScene, createViewer, type SceneHandles } from "./scene";
import { initClock, type Timeline } from "./timeline";

export interface RunMeta {
  id: string;
  params: Record<string, number>;
  file: string;
  bytes: number;
  metrics: Record<string, unknown>;
}

export interface Manifest {
  schema: number;
  id: string;
  title: string;
  kind: "single" | "sweep";
  description: string;
  hero: string;
  axes: { param: string; label: string; values: number[] }[];
  runs: RunMeta[];
}

const statusEl = () => document.getElementById("run-status")!;
const titleEl = () => document.getElementById("run-title")!;

function fail(message: string): never {
  const main = document.getElementById("main")!;
  const div = document.createElement("div");
  div.className = "error-banner";
  div.textContent = message;
  main.replaceChildren(div);
  statusEl().textContent = "error";
  throw new Error(message);
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) fail(`Failed to load ${url}: HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

async function fetchRun(scenarioId: string, meta: RunMeta): Promise<RunData> {
  const res = await fetch(`./data/${scenarioId}/${meta.file}`);
  if (!res.ok) fail(`Failed to load run ${meta.file}: HTTP ${res.status}`);
  return decodeRun(await res.arrayBuffer());
}

function renderMetrics(run: RunData) {
  const panel = document.getElementById("metrics-panel")!;
  const rows = Object.entries(run.header.metrics)
    .filter(([, v]) => typeof v === "number" || typeof v === "boolean")
    .map(([k, v]) => {
      const val = typeof v === "number" ? Number(v.toPrecision(5)).toString() : String(v);
      return `<tr><td>${k.replace(/_/g, " ")}</td><td>${val}</td></tr>`;
    })
    .join("");
  panel.innerHTML = `<h3>Run metrics</h3><table><tbody>${rows}</tbody></table>`;
}

class Player {
  private scene: SceneHandles | null = null;
  private timeline: Timeline | null = null;
  private viewer = createViewer(document.getElementById("cesium-container")!);
  private disposeCharts: (() => void) | null = null;

  constructor(private scenarioId: string, private manifest: Manifest) {}

  async load(runId: string) {
    const meta = this.manifest.runs.find((r) => r.id === runId) ?? fail(`Unknown run ${runId}`);
    statusEl().textContent = `loading ${meta.file} (${(meta.bytes / 1024).toFixed(0)} kB)…`;
    const run = await fetchRun(this.scenarioId, meta);

    this.scene?.dispose();
    this.disposeCharts?.();

    this.timeline = initClock(this.viewer, run.header.epoch, run.time);
    this.scene = buildScene(this.viewer, run, this.timeline);
    // Debug/console handle (also used by the visual-verification harness).
    (window as unknown as Record<string, unknown>).__BSDS = {
      viewer: this.viewer,
      run,
      timeline: this.timeline,
    };
    titleEl().textContent = run.header.title;
    renderMetrics(run);
    this.disposeCharts = await installCharts(run, this.timeline);
    statusEl().textContent = "";
    return run;
  }
}

/** Charts module hook — implemented in charts.ts (Task 8); resolves to a
 * disposer. Kept dynamic so the player works before charts land. */
async function installCharts(run: RunData, timeline: Timeline): Promise<(() => void) | null> {
  try {
    const mod = await import("./charts");
    return mod.buildCharts(document.getElementById("charts-panel")!, run, timeline);
  } catch {
    return null;
  }
}

async function boot() {
  const params = new URLSearchParams(location.search);
  const scenarioId = params.get("scenario") ?? fail("Missing ?scenario= parameter");
  const manifest = await fetchJson<Manifest>(`./data/${scenarioId}/manifest.json`);
  const player = new Player(scenarioId, manifest);

  const requestedRun = params.get("run") ?? manifest.hero;
  await player.load(requestedRun);

  if (manifest.kind === "sweep") {
    try {
      const mod = await import("./sweep");
      const panel = document.getElementById("sweep-panel")!;
      panel.hidden = false;
      mod.initSweep(panel, manifest, (runId: string) => void player.load(runId));
    } catch {
      /* sweep module not present yet */
    }
  }
}

void boot();
