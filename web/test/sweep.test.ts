import { describe, expect, it } from "vitest";

import { neighborFiles, runForParams } from "../src/sweep";
import type { Manifest } from "../src/player";

const manifest: Manifest = {
  schema: 1,
  id: "drag_deorbit",
  title: "Drag Deorbit",
  kind: "sweep",
  description: "",
  hero: "alt300_bal25",
  axes: [
    { param: "ballistic_coeff", label: "BC", values: [12.5, 25, 50, 100] },
    { param: "alt_km", label: "Altitude", values: [200, 250, 300, 350] },
  ],
  runs: [12.5, 25, 50, 100].flatMap((bc) =>
    [200, 250, 300, 350].map((alt) => ({
      id: `alt${alt}_bal${bc}`,
      params: { ballistic_coeff: bc, alt_km: alt },
      file: `alt${alt}_bal${bc}.bsd1`,
      bytes: 1000,
      metrics: { deorbit_time_h: bc + alt },
    })),
  ),
};

describe("runForParams", () => {
  it("finds the exact grid run", () => {
    const run = runForParams(manifest, { ballistic_coeff: 25, alt_km: 300 });
    expect(run?.id).toBe("alt300_bal25");
  });
  it("returns null off-grid", () => {
    expect(runForParams(manifest, { ballistic_coeff: 26, alt_km: 300 })).toBeNull();
  });
});

describe("neighborFiles", () => {
  it("lists files one step away along each axis, excluding self", () => {
    const files = neighborFiles(manifest, { ballistic_coeff: 25, alt_km: 300 });
    expect(files.sort()).toEqual(
      ["alt300_bal12.5.bsd1", "alt300_bal50.bsd1", "alt250_bal25.bsd1", "alt350_bal25.bsd1"].sort(),
    );
  });
  it("clamps at grid edges", () => {
    const files = neighborFiles(manifest, { ballistic_coeff: 12.5, alt_km: 200 });
    expect(files.sort()).toEqual(["alt200_bal25.bsd1", "alt250_bal12.5.bsd1"].sort());
  });
});
