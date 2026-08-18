/** Parameter sweep explorer: snapping sliders per axis, a metric heatmap
 * (sequential single-hue ramp per the dataviz method; capped cells rendered
 * as a distinct muted state, never a ramp color), nearest-run selection and
 * neighbor prefetch.
 */

import type { Manifest, RunMeta } from "./player";

export function runForParams(manifest: Manifest, params: Record<string, number>): RunMeta | null {
  return (
    manifest.runs.find((r) =>
      manifest.axes.every((axis) => r.params[axis.param] === params[axis.param]),
    ) ?? null
  );
}

export function neighborFiles(manifest: Manifest, params: Record<string, number>): string[] {
  const files: string[] = [];
  for (const axis of manifest.axes) {
    const idx = axis.values.indexOf(params[axis.param]);
    for (const step of [-1, 1]) {
      const j = idx + step;
      if (j < 0 || j >= axis.values.length) continue;
      const neighbor = { ...params, [axis.param]: axis.values[j] };
      const run = runForParams(manifest, neighbor);
      if (run) files.push(run.file);
    }
  }
  return files;
}

// Sequential blue ramp endpoints (dark mode): light -> dark, one hue.
const RAMP_LIGHT = [207, 227, 255];
const RAMP_DARK = [22, 69, 126];
const CAPPED_FILL = "rgba(139, 151, 173, 0.25)";

function rampColor(frac: number): string {
  const f = Math.min(Math.max(frac, 0), 1);
  const c = RAMP_LIGHT.map((lo, i) => Math.round(lo + (RAMP_DARK[i] - lo) * f));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}

export function initSweep(
  container: HTMLElement,
  manifest: Manifest,
  onSelectRun: (runId: string) => void,
  initialRunId?: string,
): void {
  const initial =
    manifest.runs.find((r) => r.id === initialRunId) ??
    manifest.runs.find((r) => r.id === manifest.hero) ??
    manifest.runs[0];
  const current: Record<string, number> = { ...initial.params };

  container.innerHTML = "<h3>Explore the sweep</h3>";

  // --- sliders, one per axis, snapping to grid values -----------------------
  const valueEls: Record<string, HTMLElement> = {};
  for (const axis of manifest.axes) {
    const row = document.createElement("div");
    row.className = "sweep-axis";
    const label = document.createElement("label");
    const valueEl = document.createElement("span");
    valueEl.className = "value";
    valueEl.textContent = String(current[axis.param]);
    label.append(`${axis.label}: `, valueEl);
    valueEls[axis.param] = valueEl;

    const slider = document.createElement("input");
    slider.type = "range";
    slider.min = "0";
    slider.max = String(axis.values.length - 1);
    slider.step = "1";
    slider.value = String(axis.values.indexOf(current[axis.param]));
    slider.setAttribute("aria-label", axis.label);
    slider.addEventListener("input", () => {
      current[axis.param] = axis.values[Number(slider.value)];
      apply();
    });
    row.append(label, slider);
    container.appendChild(row);
  }

  // --- heatmap over the first two axes --------------------------------------
  const [ax, ay] = manifest.axes;
  const metricOf = (r: RunMeta) => Number(r.metrics["deorbit_time_h"] ?? NaN);
  const isCapped = (r: RunMeta) => r.metrics["capped"] === true;
  const finite = manifest.runs.filter((r) => !isCapped(r) && Number.isFinite(metricOf(r)));
  const mLo = Math.min(...finite.map(metricOf));
  const mHi = Math.max(...finite.map(metricOf));

  const heat = document.createElement("div");
  heat.className = "heatmap";
  const cellW = 56;
  const cellH = 34;
  const padL = 52;
  const padB = 30;
  const padT = 18;
  const w = padL + ax.values.length * cellW + 8;
  const h = padT + ay.values.length * cellH + padB;
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Deorbit time heatmap");

  const cellRects: Record<string, SVGRectElement> = {};
  for (let i = 0; i < ax.values.length; i++) {
    for (let j = 0; j < ay.values.length; j++) {
      const params = { [ax.param]: ax.values[i], [ay.param]: ay.values[j] };
      const run = runForParams(manifest, params);
      if (!run) continue;
      const x = padL + i * cellW;
      const y = padT + (ay.values.length - 1 - j) * cellH;
      const g = document.createElementNS(ns, "g");
      g.setAttribute("cursor", "pointer");

      const rect = document.createElementNS(ns, "rect");
      rect.setAttribute("x", String(x + 1));
      rect.setAttribute("y", String(y + 1));
      rect.setAttribute("width", String(cellW - 2));
      rect.setAttribute("height", String(cellH - 2));
      rect.setAttribute("rx", "3");
      const capped = isCapped(run);
      const frac = (metricOf(run) - mLo) / Math.max(mHi - mLo, 1e-9);
      rect.setAttribute("fill", capped ? CAPPED_FILL : rampColor(frac));
      cellRects[run.id] = rect;
      g.appendChild(rect);

      const label = document.createElementNS(ns, "text");
      label.setAttribute("x", String(x + cellW / 2));
      label.setAttribute("y", String(y + cellH / 2 + 3));
      label.setAttribute("text-anchor", "middle");
      label.setAttribute("font-size", "9");
      // Text wears text tokens; pick ink vs paper by ramp position for contrast.
      label.setAttribute("fill", capped ? "#8b97ad" : frac > 0.55 ? "#dde4f0" : "#10151f");
      const tHours = metricOf(run);
      label.textContent = capped ? `≥${Math.round(tHours / 24)}d` : tHours >= 48 ? `${(tHours / 24).toFixed(1)}d` : `${Math.round(tHours)}h`;
      g.appendChild(label);

      const title = document.createElementNS(ns, "title");
      title.textContent = `${ax.label} ${ax.values[i]}, ${ay.label} ${ay.values[j]} — ${
        capped ? "still in orbit at the cap" : `deorbits in ${tHours.toFixed(1)} h`
      }`;
      g.appendChild(title);

      g.addEventListener("click", () => {
        current[ax.param] = ax.values[i];
        current[ay.param] = ay.values[j];
        for (const axis of manifest.axes) {
          const slider = container.querySelectorAll<HTMLInputElement>("input[type=range]")[manifest.axes.indexOf(axis)];
          slider.value = String(axis.values.indexOf(current[axis.param]));
        }
        apply();
      });
      svg.appendChild(g);
    }
  }

  // Axis tick labels (muted ink).
  for (let i = 0; i < ax.values.length; i++) {
    const t = document.createElementNS(ns, "text");
    t.setAttribute("x", String(padL + i * cellW + cellW / 2));
    t.setAttribute("y", String(padT + ay.values.length * cellH + 12));
    t.setAttribute("text-anchor", "middle");
    t.setAttribute("font-size", "9");
    t.setAttribute("fill", "#8b97ad");
    t.textContent = String(ax.values[i]);
    svg.appendChild(t);
  }
  for (let j = 0; j < ay.values.length; j++) {
    const t = document.createElementNS(ns, "text");
    t.setAttribute("x", String(padL - 6));
    t.setAttribute("y", String(padT + (ay.values.length - 1 - j) * cellH + cellH / 2 + 3));
    t.setAttribute("text-anchor", "end");
    t.setAttribute("font-size", "9");
    t.setAttribute("fill", "#8b97ad");
    t.textContent = String(ay.values[j]);
    svg.appendChild(t);
  }
  const xTitle = document.createElementNS(ns, "text");
  xTitle.setAttribute("x", String(padL + (ax.values.length * cellW) / 2));
  xTitle.setAttribute("y", String(h - 4));
  xTitle.setAttribute("text-anchor", "middle");
  xTitle.setAttribute("font-size", "9");
  xTitle.setAttribute("fill", "#8b97ad");
  xTitle.textContent = ax.label;
  svg.appendChild(xTitle);
  const yTitle = document.createElementNS(ns, "text");
  yTitle.setAttribute("x", "10");
  yTitle.setAttribute("y", String(padT - 6));
  yTitle.setAttribute("font-size", "9");
  yTitle.setAttribute("fill", "#8b97ad");
  yTitle.textContent = ay.label;
  svg.appendChild(yTitle);

  heat.appendChild(svg);
  container.appendChild(heat);

  // --- selection + prefetch --------------------------------------------------
  let selectedId: string | null = null;

  function highlight(runId: string) {
    if (selectedId && cellRects[selectedId]) cellRects[selectedId].setAttribute("stroke", "none");
    selectedId = runId;
    const rect = cellRects[runId];
    if (rect) {
      rect.setAttribute("stroke", "#dde4f0");
      rect.setAttribute("stroke-width", "2");
    }
  }

  function prefetchNeighbors() {
    const idle =
      (window as { requestIdleCallback?: (cb: () => void) => void }).requestIdleCallback ??
      ((cb: () => void) => setTimeout(cb, 500));
    idle(() => {
      for (const file of neighborFiles(manifest, current)) {
        void fetch(`./data/${manifest.id}/${file}`).catch(() => {});
      }
    });
  }

  function apply() {
    for (const axis of manifest.axes) valueEls[axis.param].textContent = String(current[axis.param]);
    const run = runForParams(manifest, current);
    if (!run || run.id === selectedId) return;
    highlight(run.id);
    onSelectRun(run.id);
    prefetchNeighbors();
  }

  highlight(initial.id);
  prefetchNeighbors();
}
