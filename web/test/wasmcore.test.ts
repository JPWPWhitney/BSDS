import { describe, expect, it } from "vitest";

import { filterWasmTemplates, PY_DRIVER, WASM_TEMPLATE_IDS } from "../src/wasmcore";

describe("filterWasmTemplates", () => {
  it("keeps only wheel-supported scenarios", () => {
    const all = [
      { id: "basic_orbit", title: "B", file: "templates/basic_orbit.py" },
      { id: "drag_deorbit", title: "D", file: "templates/drag_deorbit.py" },
      { id: "hohmann", title: "H", file: "templates/hohmann.py" },
    ];
    expect(filterWasmTemplates(all).map((t) => t.id)).toEqual([
      "basic_orbit",
      "drag_deorbit",
      "hohmann",
    ]);
  });
  it("supported list stays in sync with intent", () => {
    expect(WASM_TEMPLATE_IDS).toContain("basic_orbit");
    expect(WASM_TEMPLATE_IDS).toContain("drag_deorbit");
    expect(WASM_TEMPLATE_IDS).not.toContain("asteroid_arrival");
  });
});

describe("PY_DRIVER", () => {
  it("takes user code as a parameter, never interpolated", () => {
    expect(PY_DRIVER).toContain("def _bsds_run(code)");
    expect(PY_DRIVER).not.toContain("${");
  });
});
