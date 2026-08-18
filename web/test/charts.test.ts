import { describe, expect, it } from "vitest";

import { altitudeSeries, formatTimeTick } from "../src/charts";
import { decodeRun } from "../src/bsd1";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

function fixtureRun() {
  const raw = readFileSync(resolve(__dirname, "fixtures", "sample.bsd1"));
  return decodeRun(raw.buffer.slice(raw.byteOffset, raw.byteOffset + raw.byteLength) as ArrayBuffer);
}

describe("altitudeSeries", () => {
  it("derives altitude in km from |r| minus the body radius when no altitude channel exists", () => {
    const run = fixtureRun(); // fixture has r_BN_N but no altitude channel
    const s = altitudeSeries(run)!;
    expect(s.values.length).toBe(run.header.n);
    const r = run.channel("r_BN_N")!;
    const k = 7;
    const mag = Math.hypot(r.at(k, 0), r.at(k, 1), r.at(k, 2));
    const expected = mag / 1000 - run.header.bodies[0].radius_km;
    expect(s.values[k]).toBeCloseTo(expected, 9);
    expect(s.unit).toBe("km");
  });

  it("prefers the altitude channel (meters) when present", () => {
    const run = fixtureRun();
    // Fake an altitude channel by monkey-patching channel lookup
    const alt = new Float64Array(run.header.n).fill(123_000);
    const patched = {
      ...run,
      channel(name: string) {
        if (name === "altitude")
          return { info: {} as never, components: 1, data: alt, component: () => alt, at: (k: number) => alt[k] };
        return run.channel(name);
      },
      channelNames: run.channelNames,
    };
    const s = altitudeSeries(patched as never)!;
    expect(s.values[0]).toBeCloseTo(123, 9);
  });
});

describe("formatTimeTick", () => {
  it("uses minutes for short runs and hours for long ones", () => {
    expect(formatTimeTick(600, 3000)).toBe("10m");
    expect(formatTimeTick(7200, 90000)).toBe("2h");
    expect(formatTimeTick(5400, 90000)).toBe("1.5h");
  });
});
