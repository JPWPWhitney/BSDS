import { describe, expect, it } from "vitest";

import { stationFromMetrics } from "../src/station";

describe("stationFromMetrics", () => {
  it("is null when lat or lon is missing or non-numeric", () => {
    expect(stationFromMetrics({})).toBeNull();
    expect(stationFromMetrics({ station_lat_deg: 40.0 })).toBeNull();
    expect(stationFromMetrics({ station_lon_deg: -105.3 })).toBeNull();
    expect(stationFromMetrics({ station_lat_deg: "40", station_lon_deg: -105.3 })).toBeNull();
    expect(stationFromMetrics({ station_lat_deg: NaN, station_lon_deg: -105.3 })).toBeNull();
  });

  it("returns the position with the given name", () => {
    const s = stationFromMetrics({
      station_lat_deg: 40.015,
      station_lon_deg: -105.2705,
      station_name: "Boulder",
      deorbit_time_h: 2, // unrelated metrics ignored
    })!;
    expect(s).toEqual({ latDeg: 40.015, lonDeg: -105.2705, name: "Boulder" });
  });

  it("defaults the name to 'station' when absent or empty", () => {
    expect(stationFromMetrics({ station_lat_deg: 1, station_lon_deg: 2 })!.name).toBe("station");
    expect(
      stationFromMetrics({ station_lat_deg: 1, station_lon_deg: 2, station_name: "  " })!.name,
    ).toBe("station");
    expect(
      stationFromMetrics({ station_lat_deg: 1, station_lon_deg: 2, station_name: 7 })!.name,
    ).toBe("station");
  });
});
