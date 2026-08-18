import { describe, expect, it } from "vitest";

import { mrpToDcm, mrpToQuaternion, type Vec3 } from "../src/attitude";

describe("mrpToQuaternion", () => {
  it("maps zero MRP to identity", () => {
    expect(mrpToQuaternion([0, 0, 0])).toEqual([1, 0, 0, 0]);
  });

  it("maps sigma_z = tan(pi/8) to a 90-degree z rotation", () => {
    const q = mrpToQuaternion([0, 0, Math.tan(Math.PI / 8)]);
    const c = Math.cos(Math.PI / 4);
    expect(q[0]).toBeCloseTo(c, 12);
    expect(q[1]).toBeCloseTo(0, 12);
    expect(q[2]).toBeCloseTo(0, 12);
    expect(q[3]).toBeCloseTo(c, 12);
  });

  it("is always unit norm", () => {
    for (const s of [[0.1, -0.2, 0.3], [0.9, 0.9, 0.9], [-0.5, 0, 0.01]] as Vec3[]) {
      const q = mrpToQuaternion(s);
      const n = Math.hypot(q[0], q[1], q[2], q[3]);
      expect(n).toBeCloseTo(1, 12);
    }
  });
});

describe("mrpToDcm", () => {
  it("is identity for zero MRP", () => {
    const c = mrpToDcm([0, 0, 0]);
    for (let i = 0; i < 3; i++)
      for (let j = 0; j < 3; j++) expect(c[i][j]).toBeCloseTo(i === j ? 1 : 0, 12);
  });

  it("rotates x into -y for a 90-degree z rotation (BN convention)", () => {
    // sigma_BN = 90° about z: a vector along N-x expressed in B is along -y? No:
    // v_B = [BN] v_N. Rotating the frame +90° about z sends N-x to B(+cos component):
    // [BN] = Rz(+90°) as a frame rotation → v_B = [ [0,1,0], [-1,0,0], [0,0,1] ] v_N.
    const c = mrpToDcm([0, 0, Math.tan(Math.PI / 8)]);
    const expected = [
      [0, 1, 0],
      [-1, 0, 0],
      [0, 0, 1],
    ];
    for (let i = 0; i < 3; i++)
      for (let j = 0; j < 3; j++) expect(c[i][j]).toBeCloseTo(expected[i][j], 12);
  });

  it("is orthonormal for arbitrary MRPs", () => {
    const s: Vec3 = [0.3, -0.15, 0.22];
    const c = mrpToDcm(s);
    for (let i = 0; i < 3; i++)
      for (let j = 0; j < 3; j++) {
        const dot = c[i][0] * c[j][0] + c[i][1] * c[j][1] + c[i][2] * c[j][2];
        expect(dot).toBeCloseTo(i === j ? 1 : 0, 12);
      }
    // det = +1
    const det =
      c[0][0] * (c[1][1] * c[2][2] - c[1][2] * c[2][1]) -
      c[0][1] * (c[1][0] * c[2][2] - c[1][2] * c[2][0]) +
      c[0][2] * (c[1][0] * c[2][1] - c[1][1] * c[2][0]);
    expect(det).toBeCloseTo(1, 12);
  });
});
