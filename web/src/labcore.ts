/** Pure helpers for the Mission Lab page (unit-tested; no DOM). */

export interface LabConfig {
  endpoint: string | null;
  gated: boolean;
}

export function normalizeLabConfig(raw: unknown): LabConfig {
  if (raw && typeof raw === "object") {
    const o = raw as Record<string, unknown>;
    const endpoint = typeof o.endpoint === "string" && o.endpoint.startsWith("https://") ? o.endpoint : null;
    return { endpoint, gated: o.gated === true };
  }
  return { endpoint: null, gated: false };
}

export function base64ToArrayBuffer(b64: string): ArrayBuffer {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
}

export interface RunResponse {
  ok: boolean;
  bsd1_b64: string | null;
  info: Record<string, unknown>;
  user_stdout: string;
  truncated: boolean;
}

export function describeRunError(resp: RunResponse): string {
  const err = typeof resp.info?.error === "string" ? resp.info.error : "The run failed with no error message.";
  return err;
}
