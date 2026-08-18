import { describe, expect, it } from "vitest";

import { moonSpec } from "../src/moon";

const R_BN_N = { name: "r_BN_N", components: 3 };
const R_MOON_N = { name: "r_moon_N", components: 3 };
const EARTH = { name: "earth", radius_km: 6378.1366 };
const MOON = { name: "moon", radius_km: 1737.4 };

describe("moonSpec", () => {
  it("returns the radius in meters when channel and bodies entry are present", () => {
    const spec = moonSpec({ bodies: [EARTH, MOON], channels: [R_BN_N, R_MOON_N] });
    expect(spec).toEqual({ radiusM: 1_737_400 });
  });

  it("is null when the r_moon_N channel is missing", () => {
    expect(moonSpec({ bodies: [EARTH, MOON], channels: [R_BN_N] })).toBeNull();
    expect(moonSpec({ bodies: [EARTH, MOON], channels: [] })).toBeNull();
  });

  it("is null when the bodies list has no moon entry", () => {
    expect(moonSpec({ bodies: [EARTH], channels: [R_BN_N, R_MOON_N] })).toBeNull();
    expect(moonSpec({ bodies: [], channels: [R_MOON_N] })).toBeNull();
  });

  it("is null for a malformed r_moon_N (not 3 components)", () => {
    expect(
      moonSpec({ bodies: [EARTH, MOON], channels: [{ name: "r_moon_N", components: 1 }] }),
    ).toBeNull();
  });

  it("matches the moon body name case-insensitively", () => {
    expect(
      moonSpec({ bodies: [{ name: "Moon", radius_km: 1737.4 }], channels: [R_MOON_N] }),
    ).toEqual({ radiusM: 1_737_400 });
  });
});
