import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { decodeRun, nearestIndex } from "../src/bsd1";

function loadFixture() {
  const dir = resolve(__dirname, "fixtures");
  const raw = readFileSync(resolve(dir, "sample.bsd1"));
  const buf = raw.buffer.slice(raw.byteOffset, raw.byteOffset + raw.byteLength);
  const expected = JSON.parse(readFileSync(resolve(dir, "sample.expected.json"), "utf-8"));
  return { run: decodeRun(buf as ArrayBuffer), expected };
}

describe("bsd1 decoder", () => {
  it("decodes the Python-written fixture header", () => {
    const { run, expected } = loadFixture();
    const h = expected.header_subset;
    expect(run.header.scenario).toBe(h.scenario);
    expect(run.header.run).toBe(h.run);
    expect(run.header.epoch).toBe(h.epoch);
    expect(run.header.n).toBe(h.n);
    expect(run.header.params).toEqual(h.params);
    expect(run.header.metrics).toEqual(h.metrics);
  });

  it("decodes time exactly", () => {
    const { run, expected } = loadFixture();
    expect(run.time.length).toBe(expected.header_subset.n);
    for (let i = 0; i < 5; i++) expect(run.time[i]).toBe(expected.time_first5[i]);
    expect(run.time[run.time.length - 1]).toBe(expected.time_last);
  });

  it("decodes f32 channels to identical doubles", () => {
    const { run, expected } = loadFixture();
    const r = run.channel("r_BN_N")!;
    expect(r.components).toBe(3);
    for (let k = 0; k < 3; k++)
      for (let c = 0; c < 3; c++) expect(r.at(k, c)).toBe(expected.r_BN_N_first3[k][c]);
    const last = run.header.n - 1;
    for (let c = 0; c < 3; c++) expect(r.at(last, c)).toBe(expected.r_BN_N_last[c]);
  });

  it("dequantizes i16 within the scale/2 bound of the raw values", () => {
    const { run, expected } = loadFixture();
    const s = run.channel("sigma_BN")!;
    for (let k = 0; k < 3; k++)
      for (let c = 0; c < 3; c++) {
        const err = Math.abs(s.at(k, c) - expected.sigma_BN_raw_first3[k][c]);
        expect(err).toBeLessThanOrEqual(expected.sigma_scale_bound[c] + 1e-12);
      }
    // and matches the Python reader's dequantized output exactly
    for (let k = 0; k < 3; k++)
      for (let c = 0; c < 3; c++)
        expect(s.at(k, c)).toBeCloseTo(expected.sigma_BN_first3[k][c], 12);
  });

  it("returns null for missing channels", () => {
    const { run } = loadFixture();
    expect(run.channel("nope")).toBeNull();
  });

  it("rejects garbage", () => {
    expect(() => decodeRun(new ArrayBuffer(4))).toThrow();
    const bad = new Uint8Array(16).fill(65);
    expect(() => decodeRun(bad.buffer)).toThrow(/magic/);
  });
});

describe("nearestIndex", () => {
  const t = Float64Array.from([0, 10, 20, 30, 40]);
  it("clamps below and above", () => {
    expect(nearestIndex(t, -5)).toBe(0);
    expect(nearestIndex(t, 99)).toBe(4);
  });
  it("finds exact and midpoint values", () => {
    expect(nearestIndex(t, 20)).toBe(2);
    expect(nearestIndex(t, 14)).toBe(1);
    expect(nearestIndex(t, 16)).toBe(2);
  });
});
