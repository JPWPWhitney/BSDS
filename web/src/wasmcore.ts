/** Pure helpers for the WASM Lab (unit-tested; no DOM, no Pyodide). */

export interface TemplateEntry {
  id: string;
  title: string;
  file: string;
}

/** Scenarios whose full dependency closure exists in the bskcore wheel. */
export const WASM_TEMPLATE_IDS = ["basic_orbit", "hohmann", "drag_deorbit"];

export function filterWasmTemplates(entries: TemplateEntry[]): TemplateEntry[] {
  return entries.filter((t) => WASM_TEMPLATE_IDS.includes(t.id));
}

/** Python driver installed once at boot. User code is passed via a Pyodide
 * global (`__user_code`), never interpolated into this source. Returns a dict
 * {bsd1: bytes, stdout: str, elapsed: float} or raises (JS sees the traceback). */
export const PY_DRIVER = `
import base64, contextlib, importlib.util, io, os, sys, tempfile, time

_bsds_run_counter = 0

def _bsds_run(code):
    global _bsds_run_counter
    _bsds_run_counter += 1
    name = f"user_scenario_{_bsds_run_counter}"
    path = "/tmp/user_scenario.py"
    with open(path, "w") as f:
        f.write(code)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    buf = io.StringIO()
    t0 = time.time()
    with contextlib.redirect_stdout(buf):
        spec.loader.exec_module(mod)
        if not hasattr(mod, "run"):
            raise RuntimeError("Your scenario must define run(params) -> RunResult (see the templates).")
        result = mod.run({})
    from bsds_sims import bsd1
    channels = []
    for n, d in result.channels.items():
        unit = "m" if n in ("r_BN_N", "altitude") else ""
        frame = "inertial" if n.endswith("_N") else ""
        channels.append(bsd1.Channel(n, d, unit=unit, frame=frame, dtype="f32"))
    fd, tmp = tempfile.mkstemp(suffix=".bsd1")
    os.close(fd)
    bsd1.write_run(
        tmp,
        scenario="wasm-lab",
        run="user",
        title=getattr(result, "title", "WASM run"),
        epoch=result.epoch,
        params={},
        time_s=result.time_s,
        channels=channels,
        bodies=result.bodies,
        metrics=result.metrics,
    )
    with open(tmp, "rb") as f:
        raw = f.read()
    os.unlink(tmp)
    return {"bsd1": raw, "stdout": buf.getvalue()[-20000:], "elapsed": round(time.time() - t0, 3)}
`;
