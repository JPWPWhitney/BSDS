import { describe, expect, it } from "vitest";

import type { RunHeader } from "../src/bsd1";
import {
  bodyColorHex,
  bodyRadiusKm,
  cameraRangesKm,
  defaultMultiplier,
  formatSimClock,
  isExoticRun,
  sampleVec3Km,
  starField,
  stepSimTime,
  triadLengthKm,
} from "../src/exoticcore";

function header(bodies: { name: string; mu: number; radius_km: number }[]): RunHeader {
  return { bodies } as unknown as RunHeader;
}

describe("isExoticRun", () => {
  it("keeps Cesium for earth-centered runs (any case) and body-less runs", () => {
    expect(isExoticRun(header([{ name: "earth", mu: 1, radius_km: 6378 }]))).toBe(false);
    expect(isExoticRun(header([{ name: "Earth", mu: 1, radius_km: 6378 }]))).toBe(false);
    expect(isExoticRun(header([]))).toBe(false);
  });

  it("selects the exotic renderer for non-Earth central bodies", () => {
    expect(isExoticRun(header([{ name: "bennu", mu: 4.9, radius_km: 0.245 }]))).toBe(true);
    expect(
      isExoticRun(
        header([
          { name: "moon", mu: 4.9e12, radius_km: 1737 },
          { name: "earth", mu: 4e14, radius_km: 6378 },
        ]),
      ),
    ).toBe(true); // only bodies[0] decides
  });
});

describe("bodyRadiusKm / bodyColorHex", () => {
  const bodies = [
    { name: "bennu", mu: 4.9, radius_km: 0.245 },
    { name: "moon", mu: 0.05, radius_km: 0.06 },
  ];
  it("finds radii case-insensitively and returns null for unknown bodies", () => {
    expect(bodyRadiusKm(bodies, "moon")).toBe(0.06);
    expect(bodyRadiusKm(bodies, "Bennu")).toBe(0.245);
    expect(bodyRadiusKm(bodies, "phobos")).toBeNull();
  });
  it("colors bennu gray and everything else pale gray", () => {
    expect(bodyColorHex("bennu")).toBe(0x6f6a64);
    expect(bodyColorHex("ryugu")).toBe(0xb8bcc4);
  });
});

describe("starField", () => {
  it("is deterministic and lies on the requested shell", () => {
    const a = starField(300, 100, 7);
    const b = starField(300, 100, 7);
    expect(a).toEqual(b);
    expect(a.length).toBe(900);
    for (let i = 0; i < 300; i++) {
      const mag = Math.hypot(a[3 * i], a[3 * i + 1], a[3 * i + 2]);
      expect(mag).toBeCloseTo(100, 3);
    }
    const c = starField(300, 100, 8);
    expect(c).not.toEqual(a); // different seed, different sky
  });
});

describe("cameraRangesKm / triadLengthKm", () => {
  it("scales near/far/framing to the orbit size (bennu-scale works)", () => {
    const r = cameraRangesKm(1.2); // km-scale orbit around a 0.245 km body
    expect(r.near).toBeCloseTo(1.2e-4, 12);
    expect(r.far).toBeCloseTo(1.2e4, 8);
    expect(r.position).toEqual([1.2 * 2.4, 1.2 * 0.6, 1.2 * 1.2]);
    expect(r.starRadius).toBeLessThan(r.far);
  });
  it("never draws a triad smaller than the body", () => {
    expect(triadLengthKm(1.0, 0.245)).toBeCloseTo(0.147, 12); // 0.6 * body wins
    expect(triadLengthKm(7000, 0.245)).toBeCloseTo(840, 9); // 0.12 * orbit wins
  });
});

describe("sampleVec3Km", () => {
  const time = Float64Array.from([0, 10, 20]);
  const data = Float64Array.from([
    // column-major: comp0 samples, comp1 samples, comp2 samples (meters)
    0, 1000, 2000,
    0, 2000, 4000,
    1000, 1000, 1000,
  ]);
  const ch = { at: (k: number, c: number) => data[c * 3 + k] };

  it("hits samples exactly and clamps outside the range", () => {
    expect(sampleVec3Km(time, ch, 10)).toEqual([1, 2, 1]);
    expect(sampleVec3Km(time, ch, -5)).toEqual([0, 0, 1]);
    expect(sampleVec3Km(time, ch, 99)).toEqual([2, 4, 1]);
  });

  it("interpolates linearly between samples", () => {
    expect(sampleVec3Km(time, ch, 5)).toEqual([0.5, 1, 1]);
    expect(sampleVec3Km(time, ch, 17.5)).toEqual([1.75, 3.5, 1]);
  });
});

describe("rAF clock arithmetic", () => {
  it("plays a full run in ~45 wall seconds by default", () => {
    expect(defaultMultiplier(90000)).toBe(2000);
    expect(defaultMultiplier(10)).toBe(1);
  });

  it("advances by wall dt x multiplier and loops past the end", () => {
    expect(stepSimTime(100, 0.5, 10, 0, 1000)).toBe(105);
    expect(stepSimTime(990, 1, 20, 0, 1000)).toBeCloseTo(10, 9); // wraps to start
    expect(stepSimTime(500, 0, 10, 0, 1000)).toBe(500);
    expect(stepSimTime(-50, 0, 1, 0, 1000)).toBe(0); // clamps into range
  });

  it("formats the readout as hh:mm:ss", () => {
    expect(formatSimClock(0)).toBe("00:00:00");
    expect(formatSimClock(3765)).toBe("01:02:45");
    expect(formatSimClock(45 * 3600 + 6)).toBe("45:00:06");
  });
});
