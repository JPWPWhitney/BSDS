/** Playback clock shared by the 3D scene and the charts, wrapping Cesium's clock. */

import { ClockRange, ClockStep, JulianDate, type Viewer } from "cesium";

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
