/** Shared "present a decoded run" block used by the player page and the
 * Mission Lab: clock + 3D scene + charts + metrics + title.
 *
 * presentRun picks the renderer per run: Earth-centered runs keep the Cesium
 * viewer; runs whose bodies[0] is not Earth get the self-contained three.js
 * exotic renderer with its own rAF clock and scrubber bar. Passing a raw
 * Cesium Viewer (the pre-stage signature) still works and always uses the
 * Cesium path; pages that call createViewer() get a PlayerStage that can
 * swap renderers between runs. */

import type { Viewer } from "cesium";

import { buildCharts } from "./charts";
import type { RunData } from "./bsd1";
import { buildExoticScene } from "./exotic";
import { isExoticRun } from "./exoticcore";
import { buildScene, type PlayerStage } from "./scene";
import { initClock, initRafClock, type Timeline } from "./timeline";

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

function isStage(target: Viewer | PlayerStage): target is PlayerStage {
  return (target as PlayerStage).kind === "bsds-stage";
}

export function presentRun(
  target: Viewer | PlayerStage,
  run: RunData,
  els: { title: HTMLElement; charts: HTMLElement; metrics: HTMLElement },
): Presented {
  let timeline: Timeline;
  let disposeScene: () => void;
  let debugViewer: Viewer | null;
  let pause: () => void;

  if (isStage(target) && isExoticRun(run.header)) {
    const host = target.ensureExoticHost();
    const rafTimeline = initRafClock(run.header.epoch, run.time);
    const scene = buildExoticScene(host, run, rafTimeline);
    timeline = rafTimeline;
    debugViewer = null;
    pause = () => rafTimeline.setPlaying(false);
    disposeScene = () => {
      scene.dispose();
      rafTimeline.dispose();
    };
  } else {
    const viewer = isStage(target) ? target.ensureCesium() : target;
    timeline = initClock(viewer, run.header.epoch, run.time);
    const scene = buildScene(viewer, run, timeline);
    debugViewer = viewer;
    pause = () => {
      viewer.clock.shouldAnimate = false;
    };
    disposeScene = () => scene.dispose();
  }

  els.title.textContent = run.header.title;
  renderMetrics(els.metrics, run);
  const disposeCharts = buildCharts(els.charts, run, timeline);
  (window as unknown as Record<string, unknown>).__BSDS = {
    viewer: debugViewer,
    run,
    timeline,
    pause,
  };
  return {
    timeline,
    dispose() {
      disposeScene();
      disposeCharts();
    },
  };
}
