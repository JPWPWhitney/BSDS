/** Telemetry charts rail, synced to the playback clock.
 *
 * Design per the dataviz method: series colors are the validated dark-mode
 * categorical slots (validated against surface #141a26 — all checks pass);
 * single-series charts carry no legend (the title names the series); the
 * 3-series attitude chart gets a legend plus direct end-labels; text wears
 * text tokens, never series color; grid/axes are recessive; hover shows a
 * crosshair readout and click seeks the clock.
 */

import { nearestIndex, type RunData } from "./bsd1";
import type { Timeline } from "./timeline";

// Validated categorical slots (dark mode, surface #141a26).
export const SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500"];
const GRID = "rgba(139, 151, 173, 0.18)";
const TEXT_DIM = "#8b97ad";
const TEXT = "#dde4f0";
const PLAYHEAD = "rgba(221, 228, 240, 0.8)";

export interface Series {
  name: string;
  values: Float64Array;
  unit: string;
}

export function altitudeSeries(run: RunData): Series | null {
  const alt = run.channel("altitude");
  const n = run.header.n;
  const values = new Float64Array(n);
  if (alt) {
    for (let k = 0; k < n; k++) values[k] = alt.at(k, 0) / 1000;
    return { name: "Altitude", values, unit: "km" };
  }
  const r = run.channel("r_BN_N");
  if (!r || !run.header.bodies.length) return null;
  const radiusKm = run.header.bodies[0].radius_km;
  for (let k = 0; k < n; k++) {
    values[k] = Math.hypot(r.at(k, 0), r.at(k, 1), r.at(k, 2)) / 1000 - radiusKm;
  }
  return { name: "Altitude", values, unit: "km" };
}

const RAD_S_TO_RPM = 60 / (2 * Math.PI);

/** One series per reaction wheel, rad/s converted to rpm; null when the
 * optional `rw_speeds` channel is absent. */
export function wheelSpeedSeries(run: RunData): Series[] | null {
  const rw = run.channel("rw_speeds");
  if (!rw) return null;
  const n = run.header.n;
  const series: Series[] = [];
  for (let c = 0; c < rw.components; c++) {
    const values = new Float64Array(n);
    for (let k = 0; k < n; k++) values[k] = rw.at(k, c) * RAD_S_TO_RPM;
    series.push({ name: `RW${c + 1}`, values, unit: "rpm" });
  }
  return series;
}

/** Optional (n,1) channels charted when present: name -> display rule.
 * Channels not listed here are ignored (forward compatibility). */
export const EXTRA_SCALAR_CHARTS: Record<string, { title: string; unit: string; convert: (v: number) => number }> = {
  separation: { title: "Separation", unit: "km", convert: (v) => v / 1000 },
  pointing_error: { title: "Pointing error", unit: "deg", convert: (v) => (v * 180) / Math.PI },
};

/** One converted series per allowlisted scalar channel present in the run,
 * in allowlist order. */
export function extraScalarSeries(run: RunData): { title: string; unit: string; values: Float64Array }[] {
  const out: { title: string; unit: string; values: Float64Array }[] = [];
  const n = run.header.n;
  for (const [name, rule] of Object.entries(EXTRA_SCALAR_CHARTS)) {
    const ch = run.channel(name);
    if (!ch || ch.components !== 1) continue;
    const values = new Float64Array(n);
    for (let k = 0; k < n; k++) values[k] = rule.convert(ch.at(k, 0));
    out.push({ title: rule.title, unit: rule.unit, values });
  }
  return out;
}

export function formatTimeTick(tS: number, durationS: number): string {
  if (durationS < 3 * 3600) {
    return `${Math.round(tS / 60)}m`;
  }
  const h = tS / 3600;
  return `${Number(h.toFixed(1))}h`;
}

interface ChartSpec {
  title: string;
  unit: string;
  series: { name: string; values: Float64Array; color: string }[];
  legend: boolean;
}

const W = 320;
const H = 130;
const PAD = { l: 44, r: 10, t: 8, b: 20 };

function buildChart(spec: ChartSpec, time: Float64Array, timeline: Timeline): { el: HTMLElement; dispose: () => void } {
  const wrap = document.createElement("div");
  wrap.className = "chart";
  const durationS = time[time.length - 1] - time[0];

  let lo = Infinity;
  let hi = -Infinity;
  for (const s of spec.series)
    for (const v of s.values) {
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
  if (!(hi > lo)) {
    hi = lo + 1;
  }
  const pad = (hi - lo) * 0.06;
  lo -= pad;
  hi += pad;

  const x = (t: number) => PAD.l + ((t - time[0]) / durationS) * (W - PAD.l - PAD.r);
  const y = (v: number) => PAD.t + (1 - (v - lo) / (hi - lo)) * (H - PAD.t - PAD.b);

  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", spec.title);

  // Recessive grid: 3 horizontal lines + y tick labels in muted ink.
  for (let i = 0; i <= 2; i++) {
    const v = lo + ((hi - lo) * i) / 2;
    const gy = y(v);
    const line = document.createElementNS(ns, "line");
    line.setAttribute("x1", String(PAD.l));
    line.setAttribute("x2", String(W - PAD.r));
    line.setAttribute("y1", String(gy));
    line.setAttribute("y2", String(gy));
    line.setAttribute("stroke", GRID);
    line.setAttribute("stroke-width", "1");
    svg.appendChild(line);
    const label = document.createElementNS(ns, "text");
    label.setAttribute("x", String(PAD.l - 5));
    label.setAttribute("y", String(gy + 3));
    label.setAttribute("text-anchor", "end");
    label.setAttribute("fill", TEXT_DIM);
    label.setAttribute("font-size", "9");
    label.textContent = Number(v.toPrecision(3)).toString();
    svg.appendChild(label);
  }
  // Time ticks.
  for (let i = 0; i <= 3; i++) {
    const t = time[0] + (durationS * i) / 3;
    const label = document.createElementNS(ns, "text");
    label.setAttribute("x", String(x(t)));
    label.setAttribute("y", String(H - 6));
    label.setAttribute("text-anchor", i === 0 ? "start" : i === 3 ? "end" : "middle");
    label.setAttribute("fill", TEXT_DIM);
    label.setAttribute("font-size", "9");
    label.textContent = formatTimeTick(t, durationS);
    svg.appendChild(label);
  }

  // Series polylines (2px), with direct end-labels when multi-series.
  const n = time.length;
  spec.series.forEach((s, si) => {
    const pts: string[] = [];
    for (let k = 0; k < n; k++) pts.push(`${x(time[k]).toFixed(1)},${y(s.values[k]).toFixed(1)}`);
    const line = document.createElementNS(ns, "polyline");
    line.setAttribute("points", pts.join(" "));
    line.setAttribute("fill", "none");
    line.setAttribute("stroke", s.color);
    line.setAttribute("stroke-width", "2");
    line.setAttribute("stroke-linejoin", "round");
    svg.appendChild(line);
    if (spec.series.length > 1) {
      const label = document.createElementNS(ns, "text");
      label.setAttribute("x", String(W - PAD.r - 2));
      label.setAttribute("y", String(y(s.values[n - 1]) + (si === 0 ? -4 : si === 1 ? 10 : -4) * (si === 2 ? -1 : 1)));
      label.setAttribute("text-anchor", "end");
      label.setAttribute("fill", TEXT_DIM);
      label.setAttribute("font-size", "9");
      label.textContent = s.name;
      svg.appendChild(label);
    }
  });

  // Playhead + hover crosshair share one vertical line + readout.
  const playhead = document.createElementNS(ns, "line");
  playhead.setAttribute("y1", String(PAD.t));
  playhead.setAttribute("y2", String(H - PAD.b));
  playhead.setAttribute("stroke", PLAYHEAD);
  playhead.setAttribute("stroke-width", "1");
  svg.appendChild(playhead);

  const readout = document.createElementNS(ns, "text");
  readout.setAttribute("x", String(PAD.l + 4));
  readout.setAttribute("y", String(PAD.t + 10));
  readout.setAttribute("fill", TEXT);
  readout.setAttribute("font-size", "10");
  svg.appendChild(readout);

  const setCursor = (tSim: number) => {
    const cx = x(Math.min(Math.max(tSim, time[0]), time[n - 1]));
    playhead.setAttribute("x1", cx.toFixed(1));
    playhead.setAttribute("x2", cx.toFixed(1));
    const k = nearestIndex(time, tSim);
    const vals = spec.series
      .map((s) => `${Number(s.values[k].toPrecision(4))}`)
      .join(" · ");
    readout.textContent = `${vals} ${spec.unit}`;
  };
  setCursor(0);

  const unsub = timeline.onTick((tSim) => setCursor(tSim));

  const toSimTime = (evt: MouseEvent): number => {
    const rect = svg.getBoundingClientRect();
    const frac = (evt.clientX - rect.left) / rect.width;
    const px = frac * W;
    return time[0] + Math.min(Math.max((px - PAD.l) / (W - PAD.l - PAD.r), 0), 1) * durationS;
  };
  svg.addEventListener("mousemove", (evt) => setCursor(toSimTime(evt)));
  svg.addEventListener("mouseleave", () => setCursor(timeline.simSeconds()));
  svg.addEventListener("click", (evt) => timeline.seekSeconds(toSimTime(evt)));

  const heading = document.createElement("h3");
  heading.textContent = spec.unit ? `${spec.title} (${spec.unit})` : spec.title;
  wrap.appendChild(heading);
  if (spec.legend) {
    const legend = document.createElement("div");
    legend.style.cssText = "display:flex;gap:0.8rem;font-size:0.75rem;color:var(--text-dim);margin-bottom:2px;";
    for (const [si, s] of spec.series.entries()) {
      const item = document.createElement("span");
      item.innerHTML = `<span style="display:inline-block;width:10px;height:2px;background:${spec.series[si].color};vertical-align:middle;margin-right:4px;"></span>`;
      item.append(s.name);
      legend.appendChild(item);
    }
    wrap.appendChild(legend);
  }
  wrap.appendChild(svg);
  return { el: wrap, dispose: unsub };
}

export function buildCharts(container: HTMLElement, run: RunData, timeline: Timeline): () => void {
  container.innerHTML = "<h3>Telemetry</h3>";
  const disposers: (() => void)[] = [];
  const time = run.time;

  const alt = altitudeSeries(run);
  if (alt) {
    const chart = buildChart(
      { title: "Altitude", unit: "km", series: [{ name: "Altitude", values: alt.values, color: SERIES[0] }], legend: false },
      time,
      timeline,
    );
    container.appendChild(chart.el);
    disposers.push(chart.dispose);
  }

  const sigma = run.channel("sigma_BN");
  if (sigma && sigma.components === 3) {
    const names = ["σ₁", "σ₂", "σ₃"];
    const chart = buildChart(
      {
        title: "Attitude (MRP)",
        unit: "",
        series: names.map((name, c) => ({
          name,
          values: Float64Array.from(sigma.component(c)),
          color: SERIES[c],
        })),
        legend: true,
      },
      time,
      timeline,
    );
    container.appendChild(chart.el);
    disposers.push(chart.dispose);
  }

  for (const extra of extraScalarSeries(run)) {
    const chart = buildChart(
      {
        title: extra.title,
        unit: extra.unit,
        series: [{ name: extra.title, values: extra.values, color: SERIES[0] }],
        legend: false,
      },
      time,
      timeline,
    );
    container.appendChild(chart.el);
    disposers.push(chart.dispose);
  }

  const wheels = wheelSpeedSeries(run);
  if (wheels) {
    const chart = buildChart(
      {
        title: "Wheel speeds",
        unit: "rpm",
        series: wheels.map((s, c) => ({ name: s.name, values: s.values, color: SERIES[c % SERIES.length] })),
        legend: true,
      },
      time,
      timeline,
    );
    container.appendChild(chart.el);
    disposers.push(chart.dispose);
  }

  return () => {
    for (const d of disposers) d();
    container.innerHTML = "";
  };
}
