/** BSD1 run-file decoder — mirrors sims/bsds_sims/bsd1.py exactly.
 *
 * Layout: 8-byte magic "BSDS0001" | uint32 LE header length | UTF-8 JSON
 * header | binary payload. Channel columns are contiguous column-major per
 * channel. i16 dequantization: real = (stored + 32767) * scale + offset.
 */

export interface ChannelInfo {
  name: string;
  components: number;
  unit: string;
  frame: string;
  dtype: "f32" | "i16";
  byte_offset: number;
  byte_length: number;
  scale?: number[];
  offset?: number[];
}

export interface RunHeader {
  schema: number;
  scenario: string;
  run: string;
  title: string;
  epoch: string;
  params: Record<string, unknown>;
  n: number;
  bodies: { name: string; mu: number; radius_km: number }[];
  time: { dtype: string; unit: string; byte_offset: number; byte_length: number };
  channels: ChannelInfo[];
  metrics: Record<string, unknown>;
  [key: string]: unknown;
}

export interface DecodedChannel {
  info: ChannelInfo;
  components: number;
  /** Column-major storage: all samples of component 0, then component 1, ... */
  data: Float64Array;
  component(i: number): Float64Array;
  /** Value of component c at sample k. */
  at(k: number, c: number): number;
}

export interface RunData {
  header: RunHeader;
  time: Float64Array;
  channel(name: string): DecodedChannel | null;
  channelNames(): string[];
}

const MAGIC = "BSDS0001";
const QBIAS = 32767;

export function decodeRun(buf: ArrayBuffer): RunData {
  const bytes = new Uint8Array(buf);
  if (bytes.length < 12) throw new Error("not a BSD1 file (too short)");
  const magic = new TextDecoder().decode(bytes.subarray(0, 8));
  if (magic !== MAGIC) throw new Error("not a BSD1 file (bad magic)");
  const hlen = new DataView(buf).getUint32(8, true);
  if (bytes.length < 12 + hlen) throw new Error("truncated BSD1 file (header)");
  const header = JSON.parse(new TextDecoder().decode(bytes.subarray(12, 12 + hlen))) as RunHeader;

  // Slice payload into a fresh, 0-based ArrayBuffer so internal offsets are
  // naturally aligned for typed-array views.
  const payload = buf.slice(12 + hlen);
  const view = (off: number, len: number): ArrayBuffer => {
    if (off + len > payload.byteLength) throw new Error("truncated BSD1 file (payload)");
    return payload.slice(off, off + len);
  };

  const n = header.n;
  const time = new Float64Array(view(header.time.byte_offset, header.time.byte_length));
  if (time.length !== n) throw new Error("time length mismatch");

  const channels = new Map<string, DecodedChannel>();
  for (const info of header.channels) {
    const comps = info.components;
    const data = new Float64Array(n * comps);
    if (info.dtype === "f32") {
      const flat = new Float32Array(view(info.byte_offset, info.byte_length));
      for (let i = 0; i < n * comps; i++) data[i] = flat[i];
    } else if (info.dtype === "i16") {
      const flat = new Int16Array(view(info.byte_offset, info.byte_length));
      for (let c = 0; c < comps; c++) {
        const scale = info.scale![c];
        const offset = info.offset![c];
        for (let k = 0; k < n; k++) {
          data[c * n + k] = (flat[c * n + k] + QBIAS) * scale + offset;
        }
      }
    } else {
      continue; // unknown dtype: ignore channel (forward compatibility)
    }
    channels.set(info.name, {
      info,
      components: comps,
      data,
      component(i: number) {
        return data.subarray(i * n, (i + 1) * n);
      },
      at(k: number, c: number) {
        return data[c * n + k];
      },
    });
  }

  return {
    header,
    time,
    channel: (name) => channels.get(name) ?? null,
    channelNames: () => [...channels.keys()],
  };
}

/** Binary search: index of the last sample with time[i] <= t, clamped to [0, n-1]. */
export function nearestIndex(time: Float64Array, t: number): number {
  if (t <= time[0]) return 0;
  const n = time.length;
  if (t >= time[n - 1]) return n - 1;
  let lo = 0;
  let hi = n - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (time[mid] <= t) lo = mid;
    else hi = mid;
  }
  return t - time[lo] <= time[hi] - t ? lo : hi;
}
