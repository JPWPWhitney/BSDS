/** Ground-station description parsed from run header metrics. Pure logic
 * (no Cesium imports) so it stays unit-testable; scene.ts renders it. */

export interface StationSpec {
  latDeg: number;
  lonDeg: number;
  name: string;
}

/** A station exists when both station_lat_deg and station_lon_deg are finite
 * numbers; station_name (non-empty string) is optional and defaults to
 * "station". Returns null otherwise — runs without a station are unaffected. */
export function stationFromMetrics(metrics: Record<string, unknown>): StationSpec | null {
  const lat = metrics["station_lat_deg"];
  const lon = metrics["station_lon_deg"];
  if (typeof lat !== "number" || !Number.isFinite(lat)) return null;
  if (typeof lon !== "number" || !Number.isFinite(lon)) return null;
  const rawName = metrics["station_name"];
  const name = typeof rawName === "string" && rawName.trim() !== "" ? rawName : "station";
  return { latDeg: lat, lonDeg: lon, name };
}
