import { describe, expect, it } from "vitest";

import { base64ToArrayBuffer, describeRunError, normalizeLabConfig } from "../src/labcore";

describe("normalizeLabConfig", () => {
  it("accepts a valid https endpoint", () => {
    expect(normalizeLabConfig({ endpoint: "https://x.modal.run", gated: true })).toEqual({
      endpoint: "https://x.modal.run",
      gated: true,
    });
  });
  it("rejects junk endpoints and defaults", () => {
    expect(normalizeLabConfig({ endpoint: "http://insecure", gated: false }).endpoint).toBeNull();
    expect(normalizeLabConfig(null)).toEqual({ endpoint: null, gated: false });
    expect(normalizeLabConfig({}).gated).toBe(false);
  });
});

describe("base64ToArrayBuffer", () => {
  it("round-trips bytes", () => {
    const original = new Uint8Array([66, 83, 68, 83, 0, 255, 128, 1]);
    const b64 = btoa(String.fromCharCode(...original));
    const back = new Uint8Array(base64ToArrayBuffer(b64));
    expect([...back]).toEqual([...original]);
  });
});

describe("describeRunError", () => {
  it("prefers the info error string", () => {
    expect(
      describeRunError({ ok: false, bsd1_b64: null, info: { error: "boom" }, user_stdout: "", truncated: false }),
    ).toBe("boom");
  });
  it("falls back when missing", () => {
    expect(
      describeRunError({ ok: false, bsd1_b64: null, info: {}, user_stdout: "", truncated: false }),
    ).toMatch(/no error message/);
  });
});
