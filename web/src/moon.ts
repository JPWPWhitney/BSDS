/** Moon description parsed from a run header. Pure logic (no Cesium imports)
 * so it stays unit-testable; scene.ts renders it. Per the BSD1 contract the
 * moon is optional: runs without the channel or body degrade gracefully. */

import { bodyRadiusKm } from "./exoticcore";

export interface MoonSpec {
  /** Moon radius in meters (BSD1 bodies[] carries kilometers). */
  radiusM: number;
}

/** A moon exists when the header declares an `r_moon_N` channel (3 components)
 * AND a bodies[] entry named "moon" (case-insensitive) carrying its radius.
 * Returns null otherwise — runs without a moon are unaffected. */
export function moonSpec(header: {
  bodies?: { name: string; radius_km: number }[];
  channels?: { name: string; components: number }[];
}): MoonSpec | null {
  const ch = header.channels?.find((c) => c.name === "r_moon_N" && c.components === 3);
  if (!ch) return null;
  const radiusKm = bodyRadiusKm(header.bodies ?? [], "moon");
  if (radiusKm === null) return null;
  return { radiusM: radiusKm * 1000 };
}
