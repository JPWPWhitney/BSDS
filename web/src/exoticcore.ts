/** Pure logic for the non-Earth ("exotic") three.js renderer: run detection,
 * star field generation, body styling, camera ranges, channel sampling, and
 * the requestAnimationFrame clock arithmetic. No three.js/Cesium/DOM imports
 * so everything here is unit-testable. All distances are kilometers. */

import type { DecodedChannel, RunHeader } from "./bsd1";
import { nearestIndex } from "./bsd1";

/** A run needs the exotic renderer when its central body is not Earth.
 * Runs without body metadata keep the Cesium path (nothing better to draw). */
export function isExoticRun(header: RunHeader): boolean {
  const first = header.bodies?.[0];
  return first !== undefined && first.name.toLowerCase() !== "earth";
}

/** Radius (km) of the bodies[] entry with the given name, or null. */
export function bodyRadiusKm(
  bodies: { name: string; radius_km: number }[],
  name: string,
): number | null {
  const hit = bodies.find((b) => b.name.toLowerCase() === name.toLowerCase());
  return hit ? hit.radius_km : null;
}

/** Matte central-body color: gray for bennu, pale gray for anything else. */
export function bodyColorHex(name: string): number {
  return name.toLowerCase() === "bennu" ? 0x6f6a64 : 0xb8bcc4;
}

/** Deterministic PRNG (mulberry32) so the star field is stable frame to
 * frame and screenshot to screenshot. */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** `count` star positions (xyz triples, km) uniformly distributed on a
 * sphere shell of the given radius. */
export function starField(count: number, radiusKm: number, seed = 20260818): Float32Array {
  const rand = mulberry32(seed);
  const out = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    const z = 2 * rand() - 1;
    const phi = 2 * Math.PI * rand();
    const s = Math.sqrt(Math.max(0, 1 - z * z));
    out[3 * i] = radiusKm * s * Math.cos(phi);
    out[3 * i + 1] = radiusKm * s * Math.sin(phi);
    out[3 * i + 2] = radiusKm * z;
  }
  return out;
}

export interface CameraRangesKm {
  near: number;
  far: number;
  /** Initial camera position, framing the whole orbit like the Cesium path. */
  position: [number, number, number];
  starRadius: number;
}

/** Camera near/far and framing from the largest orbit radius (km). Works from
 * Bennu scale (0.245 km body, km orbits) up to planetary scale. */
export function cameraRangesKm(maxOrbitRadiusKm: number): CameraRangesKm {
  const r = Math.max(maxOrbitRadiusKm, 1e-3);
  return {
    near: r * 1e-4,
    far: r * 1e4,
    position: [r * 2.4, r * 0.6, r * 1.2],
    starRadius: r * 400,
  };
}

/** Body-axes triad length (km): scaled to the orbit but never smaller than
 * the central body. */
export function triadLengthKm(orbitRadiusKm: number, bodyRadiusKm: number): number {
  return Math.max(0.12 * orbitRadiusKm, 0.6 * bodyRadiusKm);
}

/** Linearly interpolate a 3-component channel at sim time t (seconds) into
 * `out` (km — channel data is meters per the BSD1 contract). */
export function sampleVec3Km(
  time: Float64Array,
  ch: Pick<DecodedChannel, "at">,
  tSim: number,
  out: [number, number, number] = [0, 0, 0],
): [number, number, number] {
  const n = time.length;
  let k = nearestIndex(time, tSim);
  if (time[k] > tSim && k > 0) k -= 1; // left sample of the bracketing pair
  const k1 = Math.min(k + 1, n - 1);
  const dt = time[k1] - time[k];
  const f = dt > 0 ? Math.min(Math.max((tSim - time[k]) / dt, 0), 1) : 0;
  for (let c = 0; c < 3; c++) {
    out[c] = ((1 - f) * ch.at(k, c) + f * ch.at(k1, c)) / 1000;
  }
  return out;
}

/** Default playback speed: full run in ~45 wall seconds (same policy as the
 * Cesium clock in timeline.ts). */
export function defaultMultiplier(durationS: number): number {
  return Math.max(1, Math.round(durationS / 45));
}

/** Advance the sim clock by a wall-clock delta, looping past the end like
 * Cesium's ClockRange.LOOP_STOP, and clamping into [t0, t1]. */
export function stepSimTime(
  t: number,
  dtWallS: number,
  multiplier: number,
  t0: number,
  t1: number,
): number {
  let next = t + dtWallS * multiplier;
  if (next > t1) next = t0 + ((next - t0) % (t1 - t0));
  return Math.min(Math.max(next, t0), t1);
}

/** hh:mm:ss readout for the scrubber bar. */
export function formatSimClock(tS: number): string {
  const t = Math.max(0, Math.round(tS));
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = t % 60;
  const pad = (v: number) => String(v).padStart(2, "0");
  return `${pad(h)}:${pad(m)}:${pad(s)}`;
}
