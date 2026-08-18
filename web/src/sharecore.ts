/** Pure helpers for sharing and loading lab code (unit-tested; no DOM). */

import { base64ToArrayBuffer } from "./labcore";

/** Share links whose encoded payload exceeds this may be truncated by some
 * apps; the UI warns but still produces the link. */
export const SHARE_WARN_LENGTH = 14 * 1024;

function bytesToBase64Url(bytes: Uint8Array): string {
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(bin).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
}

function base64UrlToBytes(b64url: string): Uint8Array<ArrayBuffer> {
  if (!/^[A-Za-z0-9_-]+$/.test(b64url)) throw new Error("not base64url");
  const b64 = b64url.replaceAll("-", "+").replaceAll("_", "/");
  const pad = b64.length % 4 ? "=".repeat(4 - (b64.length % 4)) : "";
  return new Uint8Array(base64ToArrayBuffer(b64 + pad));
}

async function pumpThrough(
  bytes: Uint8Array<ArrayBuffer>,
  transform: { readable: ReadableStream<Uint8Array>; writable: WritableStream<BufferSource> },
): Promise<Uint8Array> {
  const writer = transform.writable.getWriter();
  const writing = writer.write(bytes).then(() => writer.close());
  writing.catch(() => undefined); // surfaced via the readable side or the await below
  const buffer = await new Response(transform.readable).arrayBuffer();
  await writing;
  return new Uint8Array(buffer);
}

/** Editor code → gzip → base64url, ready for a `#code=` fragment. */
export async function encodeShareCode(code: string): Promise<string> {
  const gz = await pumpThrough(new TextEncoder().encode(code), new CompressionStream("gzip"));
  return bytesToBase64Url(gz);
}

/** Inverse of encodeShareCode. Throws on anything that isn't base64url'd gzip. */
export async function decodeShareCode(fragment: string): Promise<string> {
  const bytes = await pumpThrough(base64UrlToBytes(fragment), new DecompressionStream("gzip"));
  return new TextDecoder().decode(bytes);
}

/** Current-page URL with `#code=<encoded>` replacing any previous fragment.
 * ?src=/?gist= are dropped so the link carries one unambiguous source. */
export function buildShareUrl(href: string, encoded: string): string {
  const url = new URL(href);
  url.hash = `code=${encoded}`;
  url.searchParams.delete("src");
  url.searchParams.delete("gist");
  return url.toString();
}

export type LoadRequest =
  | { kind: "code"; payload: string }
  | { kind: "src"; url: string }
  | { kind: "gist"; id: string };

const GIST_ID = /^[A-Za-z0-9]{1,64}$/;

function safeSrcUrl(raw: string): string | null {
  try {
    const u = new URL(raw, "https://example.invalid/");
    return u.protocol === "https:" || u.protocol === "http:" ? raw : null;
  } catch {
    return null;
  }
}

/** What (if anything) the page URL asks us to load into the editor.
 * Precedence: `#code=` over `?src=` over `?gist=`; null means default template. */
export function parseLoadRequest(hash: string, search: string): LoadRequest | null {
  const code = new URLSearchParams(hash.replace(/^#/, "")).get("code");
  if (code) return { kind: "code", payload: code };
  const query = new URLSearchParams(search);
  const src = query.get("src");
  if (src) {
    const url = safeSrcUrl(src);
    if (url) return { kind: "src", url };
  }
  const gist = query.get("gist");
  if (gist && GIST_ID.test(gist)) return { kind: "gist", id: gist };
  return null;
}

export function gistApiUrl(id: string): string {
  return `https://api.github.com/gists/${id}`;
}

interface GistFile {
  filename?: string;
  content?: string;
  truncated?: boolean;
  raw_url?: string;
}

/** Choose the scenario file from a gist API response: first .py file, else the
 * first file. Truncated files must be re-fetched from their raw_url. */
export function pickGistFile(gist: unknown): { content: string } | { rawUrl: string } | null {
  if (!gist || typeof gist !== "object") return null;
  const files = (gist as { files?: Record<string, GistFile | null> }).files;
  if (!files || typeof files !== "object") return null;
  const entries = Object.values(files).filter((f): f is GistFile => !!f);
  const file = entries.find((f) => f.filename?.toLowerCase().endsWith(".py")) ?? entries[0];
  if (!file) return null;
  if (!file.truncated && typeof file.content === "string") return { content: file.content };
  if (typeof file.raw_url === "string") return { rawUrl: file.raw_url };
  return null;
}

const MISSING_MODULE = /No module named '(Basilisk[\w.]*)'/;
const IMPORT_ERROR = /ImportError: .*'(Basilisk[\w.]*)'/;

/** A friendly first line for tracebacks caused by Basilisk modules that the
 * in-browser wheel doesn't carry; null for every other error. */
export function friendlyWasmError(stderr: string): string | null {
  const m = MISSING_MODULE.exec(stderr) ?? IMPORT_ERROR.exec(stderr);
  if (!m) return null;
  return (
    `This scenario needs ${m[1]}, which isn't part of the in-browser Basilisk build yet. ` +
    `The WASM Lab carries a small subset of Basilisk — the recorded missions and the Mission Lab ` +
    `support the full library. The raw Python error is below.`
  );
}
