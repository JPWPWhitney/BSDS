/** Shared "present a decoded run" block used by the player page and the
 * Mission Lab: clock + 3D scene + charts + metrics + title. */

import type { Viewer } from "cesium";

import { buildCharts } from "./charts";
import type { RunData } from "./bsd1";
import { buildScene } from "./scene";
import { initClock, type Timeline } from "./timeline";

export interface Presented {
  timeline: Timeline;
  dispose(): void;
}

export function renderMetrics(panel: HTMLElement, run: RunData): void {
  const rows = Object.entries(run.header.metrics)
    .filter(([, v]) => typeof v === "number" || typeof v === "boolean")
    .map(([k, v]) => {
      const val = typeof v === "number" ? Number(v.toPrecision(5)).toString() : String(v);
      return `<tr><td>${k.replace(/_/g, " ")}</td><td>${val}</td></tr>`;
    })
    .join("");
  panel.innerHTML = `<h3>Run metrics</h3><table><tbody>${rows}</tbody></table>`;
}

export function presentRun(
  viewer: Viewer,
  run: RunData,
  els: { title: HTMLElement; charts: HTMLElement; metrics: HTMLElement },
): Presented {
  const timeline = initClock(viewer, run.header.epoch, run.time);
  const scene = buildScene(viewer, run, timeline);
  els.title.textContent = run.header.title;
  renderMetrics(els.metrics, run);
  const disposeCharts = buildCharts(els.charts, run, timeline);
  (window as unknown as Record<string, unknown>).__BSDS = { viewer, run, timeline };
  return {
    timeline,
    dispose() {
      scene.dispose();
      disposeCharts();
    },
  };
}
