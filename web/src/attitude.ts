/** Attitude math: Modified Rodrigues Parameters (Basilisk's sigma_BN) to
 * quaternion / DCM. sigma_BN maps inertial (N) to body (B).
 */

export type Vec3 = [number, number, number];
export type Quat = [number, number, number, number]; // [w, x, y, z]

/** MRP -> unit quaternion [w, x, y, z]. */
export function mrpToQuaternion(s: Vec3): Quat {
  const s2 = s[0] * s[0] + s[1] * s[1] + s[2] * s[2];
  const d = 1 + s2;
  return [(1 - s2) / d, (2 * s[0]) / d, (2 * s[1]) / d, (2 * s[2]) / d];
}

/** MRP -> direction cosine matrix [BN] (row-major 3x3): maps N-frame vectors
 * into the B frame. Schaub & Junkins eq. (3.147). */
export function mrpToDcm(s: Vec3): number[][] {
  const s2 = s[0] * s[0] + s[1] * s[1] + s[2] * s[2];
  const d = (1 + s2) * (1 + s2);
  // tilde(s): skew-symmetric cross-product matrix
  const t = [
    [0, -s[2], s[1]],
    [s[2], 0, -s[0]],
    [-s[1], s[0], 0],
  ];
  // t2 = tilde(s) * tilde(s)
  const t2 = Array.from({ length: 3 }, (_, i) =>
    Array.from({ length: 3 }, (_, j) => t[i][0] * t[0][j] + t[i][1] * t[1][j] + t[i][2] * t[2][j]),
  );
  const c: number[][] = [];
  for (let i = 0; i < 3; i++) {
    c.push([]);
    for (let j = 0; j < 3; j++) {
      const eye = i === j ? 1 : 0;
      c[i].push(eye + (8 * t2[i][j] - 4 * (1 - s2) * t[i][j]) / d);
    }
  }
  return c;
}
