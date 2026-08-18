/** Playback clock shared by the 3D scene and the charts, wrapping Cesium's clock.
 * For runs rendered without Cesium (exotic bodies), initRafClock provides the
 * same Timeline interface on top of requestAnimationFrame. */

import { ClockRange, ClockStep, JulianDate, type Viewer } from "cesium";

import { defaultMultiplier, stepSimTime } from "./exoticcore";

export interface Timeline {
  epoch: JulianDate;
  durationS: number;
  /** Current sim time in seconds from epoch. */
  simSeconds(): number;
  /** Seek to a sim time in seconds from epoch. */
  seekSeconds(t: number): void;
  /** Subscribe to clock ticks; returns an unsubscribe function. */
  onTick(cb: (tSim: number) => void): () => void;
}

export function initClock(viewer: Viewer, epochIso: string, time: Float64Array): Timeline {
  const epoch = JulianDate.fromIso8601(epochIso);
  const durationS = time[time.length - 1] - time[0];
  const start = JulianDate.addSeconds(epoch, time[0], new JulianDate());
  const stop = JulianDate.addSeconds(epoch, time[time.length - 1], new JulianDate());

  const clock = viewer.clock;
  clock.startTime = start;
  clock.stopTime = stop;
  clock.currentTime = start.clone();
  clock.clockRange = ClockRange.LOOP_STOP;
  clock.clockStep = ClockStep.SYSTEM_CLOCK_MULTIPLIER;
  // Full run plays in ~45 wall seconds by default.
  clock.multiplier = Math.max(1, Math.round(durationS / 45));
  clock.shouldAnimate = true;
  viewer.timeline?.zoomTo(start, stop);

  const timeline: Timeline = {
    epoch,
    durationS,
    simSeconds() {
      return JulianDate.secondsDifference(clock.currentTime, epoch);
    },
    seekSeconds(t: number) {
      const clamped = Math.min(Math.max(t, time[0]), time[time.length - 1]);
      clock.currentTime = JulianDate.addSeconds(epoch, clamped, new JulianDate());
    },
    onTick(cb) {
      const remove = clock.onTick.addEventListener(() => cb(timeline.simSeconds()));
      return remove;
    },
  };
  return timeline;
}

/** Timeline plus the play/pause controls the exotic scrubber bar needs. */
export interface RafTimeline extends Timeline {
  playing(): boolean;
  setPlaying(on: boolean): void;
  multiplier: number;
  dispose(): void;
}

/** requestAnimationFrame-driven clock with the same Timeline contract as the
 * Cesium wrapper, for scenes without a Cesium Viewer. Ticks fire every frame
 * (playing or paused), matching Cesium's clock.onTick behavior, so chart
 * cursors stay live. */
export function initRafClock(epochIso: string, time: Float64Array): RafTimeline {
  const epoch = JulianDate.fromIso8601(epochIso);
  const t0 = time[0];
  const t1 = time[time.length - 1];
  const durationS = t1 - t0;
  const listeners = new Set<(tSim: number) => void>();

  let tSim = t0;
  let playing = true;
  let lastWallMs: number | null = null;
  let rafId = 0;
  let disposed = false;

  const frame = (wallMs: number) => {
    if (disposed) return;
    const dtWallS = lastWallMs === null ? 0 : (wallMs - lastWallMs) / 1000;
    lastWallMs = wallMs;
    if (playing) tSim = stepSimTime(tSim, dtWallS, timeline.multiplier, t0, t1);
    for (const cb of listeners) cb(tSim);
    rafId = requestAnimationFrame(frame);
  };
  rafId = requestAnimationFrame(frame);

  const timeline: RafTimeline = {
    epoch,
    durationS,
    multiplier: defaultMultiplier(durationS),
    simSeconds: () => tSim,
    seekSeconds(t: number) {
      tSim = Math.min(Math.max(t, t0), t1);
    },
    onTick(cb) {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    playing: () => playing,
    setPlaying(on: boolean) {
      playing = on;
    },
    dispose() {
      disposed = true;
      cancelAnimationFrame(rafId);
      listeners.clear();
    },
  };
  return timeline;
}
