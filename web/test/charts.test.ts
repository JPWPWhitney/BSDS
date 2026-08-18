import { describe, expect, it } from "vitest";

import { altitudeSeries, formatTimeTick, wheelSpeedSeries } from "../src/charts";
import { decodeRun, type DecodedChannel, type RunData } from "../src/bsd1";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

function fixtureRun() {
  const raw = readFileSync(resolve(__dirname, "fixtures", "sample.bsd1"));
  return decodeRun(raw.buffer.slice(raw.byteOffset, raw.byteOffset + raw.byteLength) as ArrayBuffer);
}

/** Fixture run with an extra fake channel spliced in (column-major data). */
function withChannel(run: RunData, name: string, components: number, data: Float64Array): RunData {
  const n = run.header.n;
  const fake: DecodedChannel = {
    info: { name, components } as DecodedChannel["info"],
    components,
    data,
    component: (i) => data.subarray(i * n, (i + 1) * n),
    at: (k, c) => data[c * n + k],
  };
  return {
    header: run.header,
    time: run.time,
    channel: (want) => (want === name ? fake : run.channel(want)),
    channelNames: () => [...run.channelNames(), name],
  };
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

describe("wheelSpeedSeries", () => {
  it("is null when the rw_speeds channel is absent", () => {
    expect(wheelSpeedSeries(fixtureRun())).toBeNull();
  });

  it("makes one series per wheel, converted rad/s -> rpm", () => {
    const run = fixtureRun();
    const n = run.header.n;
    const data = new Float64Array(4 * n);
    for (let c = 0; c < 4; c++) for (let k = 0; k < n; k++) data[c * n + k] = (c + 1) * Math.PI;
    const series = wheelSpeedSeries(withChannel(run, "rw_speeds", 4, data))!;
    expect(series.length).toBe(4);
    expect(series.map((s) => s.name)).toEqual(["RW1", "RW2", "RW3", "RW4"]);
    // pi rad/s = 30 rpm
    for (let c = 0; c < 4; c++) {
      expect(series[c].values.length).toBe(n);
      expect(series[c].values[0]).toBeCloseTo(30 * (c + 1), 10);
      expect(series[c].unit).toBe("rpm");
    }
  });
});

describe("formatTimeTick", () => {
  it("uses minutes for short runs and hours for long ones", () => {
    expect(formatTimeTick(600, 3000)).toBe("10m");
    expect(formatTimeTick(7200, 90000)).toBe("2h");
    expect(formatTimeTick(5400, 90000)).toBe("1.5h");
  });
});
