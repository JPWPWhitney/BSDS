import "./style.css";

import { decodeRun, type RunData } from "./bsd1";
import { presentRun, type Presented } from "./present";
import { createViewer } from "./scene";

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

class Player {
  private presented: Presented | null = null;
  private viewer = createViewer(document.getElementById("cesium-container")!);

  constructor(private scenarioId: string, private manifest: Manifest) {}

  async load(runId: string) {
    const meta = this.manifest.runs.find((r) => r.id === runId) ?? fail(`Unknown run ${runId}`);
    statusEl().textContent = `loading ${meta.file} (${(meta.bytes / 1024).toFixed(0)} kB)…`;
    const run = await fetchRun(this.scenarioId, meta);

    this.presented?.dispose();
    this.presented = presentRun(this.viewer, run, {
      title: document.getElementById("run-title")!,
      charts: document.getElementById("charts-panel")!,
      metrics: document.getElementById("metrics-panel")!,
    });
    statusEl().textContent = "";
    return run;
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
    const mod = await import("./sweep");
    const panel = document.getElementById("sweep-panel")!;
    panel.hidden = false;
    mod.initSweep(panel, manifest, (runId: string) => void player.load(runId), requestedRun);
  }
}

void boot();
