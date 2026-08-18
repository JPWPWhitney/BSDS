import { describe, expect, it } from "vitest";

import {
  buildShareUrl,
  decodeShareCode,
  encodeShareCode,
  friendlyWasmError,
  gistApiUrl,
  parseLoadRequest,
  pickGistFile,
  SHARE_WARN_LENGTH,
} from "../src/sharecore";

describe("encodeShareCode / decodeShareCode", () => {
  it("round-trips a small scenario", async () => {
    const code = 'def run(params):\n    return "orbit"\n';
    expect(await decodeShareCode(await encodeShareCode(code))).toBe(code);
  });

  it("round-trips unicode", async () => {
    const code = "# Δv budget — 100 m/s → GEO 🛰️\nprint('héllo')\n";
    expect(await decodeShareCode(await encodeShareCode(code))).toBe(code);
  });

  it("round-trips and compresses multi-KB code", async () => {
    const code = Array.from(
      { length: 200 },
      (_, i) => `    sc_${i} = spacecraft.Spacecraft()  # vehicle number ${i}`,
    ).join("\n");
    expect(code.length).toBeGreaterThan(8000);
    const encoded = await encodeShareCode(code);
    expect(encoded).toMatch(/^[A-Za-z0-9_-]+$/);
    expect(encoded.length).toBeLessThan(code.length / 2);
    expect(await decodeShareCode(encoded)).toBe(code);
  });

  it("round-trips the empty string", async () => {
    expect(await decodeShareCode(await encodeShareCode(""))).toBe("");
  });

  it("rejects non-base64url input", async () => {
    await expect(decodeShareCode("#code=abc")).rejects.toThrow(/base64url/);
    await expect(decodeShareCode("")).rejects.toThrow();
  });

  it("rejects base64url that is not gzip", async () => {
    await expect(decodeShareCode("AAAAAAAA")).rejects.toThrow();
  });
});

describe("buildShareUrl", () => {
  it("adds the fragment and keeps the page", () => {
    expect(buildShareUrl("https://x.test/lab.html", "abc")).toBe("https://x.test/lab.html#code=abc");
  });
  it("replaces an existing fragment on re-share", () => {
    expect(buildShareUrl("https://x.test/wasm.html#code=old", "new")).toBe(
      "https://x.test/wasm.html#code=new",
    );
  });
  it("drops src/gist params so the link has one source", () => {
    expect(buildShareUrl("https://x.test/lab.html?src=https%3A%2F%2Fa.test%2Fs.py&gist=123", "abc")).toBe(
      "https://x.test/lab.html#code=abc",
    );
  });
});

describe("parseLoadRequest", () => {
  it("reads #code= from the fragment", () => {
    expect(parseLoadRequest("#code=abc123", "")).toEqual({ kind: "code", payload: "abc123" });
  });
  it("prefers #code= over ?src= over ?gist=", () => {
    expect(parseLoadRequest("#code=abc", "?src=https://a.test/s.py&gist=deadbeef")).toEqual({
      kind: "code",
      payload: "abc",
    });
    expect(parseLoadRequest("", "?src=https://a.test/s.py&gist=deadbeef")).toEqual({
      kind: "src",
      url: "https://a.test/s.py",
    });
    expect(parseLoadRequest("", "?gist=deadbeef")).toEqual({ kind: "gist", id: "deadbeef" });
  });
  it("accepts relative and same-origin src urls", () => {
    expect(parseLoadRequest("", "?src=/data/templates/hohmann.py")).toEqual({
      kind: "src",
      url: "/data/templates/hohmann.py",
    });
  });
  it("rejects non-http src schemes", () => {
    expect(parseLoadRequest("", "?src=javascript:alert(1)")).toBeNull();
    expect(parseLoadRequest("", "?src=javascript:alert(1)&gist=abc123")).toEqual({
      kind: "gist",
      id: "abc123",
    });
  });
  it("rejects malformed gist ids", () => {
    expect(parseLoadRequest("", "?gist=../evil")).toBeNull();
    expect(parseLoadRequest("", "?gist=abc%2F123")).toBeNull();
  });
  it("ignores empty values and unrelated params", () => {
    expect(parseLoadRequest("", "")).toBeNull();
    expect(parseLoadRequest("#code=", "?other=1")).toBeNull();
    expect(parseLoadRequest("#section-2", "")).toBeNull();
  });
});

describe("gistApiUrl / pickGistFile", () => {
  it("builds the API url", () => {
    expect(gistApiUrl("deadbeef123")).toBe("https://api.github.com/gists/deadbeef123");
  });
  it("prefers the first .py file", () => {
    const gist = {
      files: {
        "README.md": { filename: "README.md", content: "# hi" },
        "orbit.py": { filename: "orbit.py", content: "print(1)" },
      },
    };
    expect(pickGistFile(gist)).toEqual({ content: "print(1)" });
  });
  it("falls back to the first file when no .py exists", () => {
    const gist = { files: { "notes.txt": { filename: "notes.txt", content: "n" } } };
    expect(pickGistFile(gist)).toEqual({ content: "n" });
  });
  it("returns raw_url for truncated files", () => {
    const gist = {
      files: {
        "big.py": { filename: "big.py", content: "partial", truncated: true, raw_url: "https://r.test/big.py" },
      },
    };
    expect(pickGistFile(gist)).toEqual({ rawUrl: "https://r.test/big.py" });
  });
  it("handles malformed responses", () => {
    expect(pickGistFile(null)).toBeNull();
    expect(pickGistFile({})).toBeNull();
    expect(pickGistFile({ files: {} })).toBeNull();
    expect(pickGistFile({ files: { "a.py": {} } })).toBeNull();
  });
});

describe("friendlyWasmError", () => {
  it("explains a missing Basilisk module", () => {
    const tb =
      "PythonError: Traceback (most recent call last):\n" +
      '  File "/tmp/user_scenario.py", line 3, in <module>\n' +
      "    from Basilisk.simulation import msisAtmosphere\n" +
      "ModuleNotFoundError: No module named 'Basilisk.simulation.msisAtmosphere'";
    const msg = friendlyWasmError(tb);
    expect(msg).toContain("Basilisk.simulation.msisAtmosphere");
    expect(msg).toContain("in-browser");
    expect(msg).toContain("Mission Lab");
  });
  it("explains an ImportError from a Basilisk module", () => {
    const tb = "ImportError: cannot import name 'vizSupport' from 'Basilisk.utilities'";
    expect(friendlyWasmError(tb)).toContain("Basilisk");
  });
  it("stays silent for non-Basilisk modules", () => {
    expect(friendlyWasmError("ModuleNotFoundError: No module named 'scipy'")).toBeNull();
  });
  it("stays silent for unrelated errors", () => {
    expect(friendlyWasmError("ZeroDivisionError: division by zero")).toBeNull();
    expect(friendlyWasmError("")).toBeNull();
  });
});

describe("SHARE_WARN_LENGTH", () => {
  it("is far above a typical encoded scenario", async () => {
    const typical = "x = 1\n".repeat(1000); // ~6 KB source
    expect((await encodeShareCode(typical)).length).toBeLessThan(SHARE_WARN_LENGTH);
  });
});
