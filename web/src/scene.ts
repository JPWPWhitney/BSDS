/** Cesium scene: viewer construction and per-run entities (spacecraft point,
 * orbit trail, body-axes triad). Positions live in the inertial frame; Cesium
 * converts to its fixed world frame for rendering.
 */

import {
  ArcType,
  buildModuleUrl,
  Cartesian3,
  Color,
  CallbackProperty,
  ImageryLayer,
  JulianDate,
  LagrangePolynomialApproximation,
  Matrix3,
  Matrix4,
  PathGraphics,
  ReferenceFrame,
  SampledPositionProperty,
  TileMapServiceImageryProvider,
  TimeInterval,
  TimeIntervalCollection,
  Transforms,
  Viewer,
  type Entity,
} from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";

import { mrpToDcm } from "./attitude";
import type { RunData } from "./bsd1";
import { nearestIndex } from "./bsd1";
import { SERIES } from "./charts";
import type { Timeline } from "./timeline";

export function createViewer(container: HTMLElement): Viewer {
  const viewer = new Viewer(container, {
    baseLayer: ImageryLayer.fromProviderAsync(
      TileMapServiceImageryProvider.fromUrl(buildModuleUrl("Assets/Textures/NaturalEarthII")),
      {},
    ),
    baseLayerPicker: false,
    geocoder: false,
    homeButton: false,
    infoBox: false,
    navigationHelpButton: false,
    sceneModePicker: false,
    selectionIndicator: false,
    timeline: true,
    animation: true,
    shouldAnimate: true,
  });
  viewer.scene.globe.enableLighting = true;
  return viewer;
}

const TRIAD_COLORS = [
  Color.fromCssColorString("#ff5a5a"),
  Color.fromCssColorString("#6aff6a"),
  Color.fromCssColorString("#5aa9ff"),
];

export interface SceneHandles {
  dispose(): void;
}

export function buildScene(viewer: Viewer, run: RunData, timeline: Timeline): SceneHandles {
  const r = run.channel("r_BN_N");
  if (!r) throw new Error("run has no r_BN_N channel");
  const n = run.header.n;

  const position = new SampledPositionProperty(ReferenceFrame.INERTIAL);
  position.setInterpolationOptions({
    interpolationDegree: 5,
    interpolationAlgorithm: LagrangePolynomialApproximation,
  });
  const times: JulianDate[] = [];
  const positions: Cartesian3[] = [];
  for (let k = 0; k < n; k++) {
    times.push(JulianDate.addSeconds(timeline.epoch, run.time[k], new JulianDate()));
    positions.push(new Cartesian3(r.at(k, 0), r.at(k, 1), r.at(k, 2)));
  }
  position.addSamples(times, positions);

  const availability = new TimeIntervalCollection([
    new TimeInterval({ start: times[0], stop: times[n - 1] }),
  ]);

  viewer.entities.add({
    id: "spacecraft",
    availability,
    position,
    point: {
      pixelSize: 9,
      color: Color.fromCssColorString("#ffd45a"),
      outlineColor: Color.BLACK,
      outlineWidth: 1,
    },
    path: new PathGraphics({
      material: Color.fromCssColorString("#ffd45a").withAlpha(0.7),
      width: 1.6,
      leadTime: timeline.durationS,
      trailTime: timeline.durationS,
      resolution: Math.max(10, timeline.durationS / 2000),
    }),
  });

  // Optional second spacecraft (rendezvous/formation runs): its own sampled
  // inertial position and full-orbit path in a distinct palette color, no triad.
  const r2 = run.channel("r2_BN_N");
  const hasSecond = r2 !== null && r2.components === 3;
  if (r2 && hasSecond) {
    const position2 = new SampledPositionProperty(ReferenceFrame.INERTIAL);
    position2.setInterpolationOptions({
      interpolationDegree: 5,
      interpolationAlgorithm: LagrangePolynomialApproximation,
    });
    const positions2: Cartesian3[] = [];
    for (let k = 0; k < n; k++) {
      positions2.push(new Cartesian3(r2.at(k, 0), r2.at(k, 1), r2.at(k, 2)));
    }
    position2.addSamples(times, positions2);
    viewer.entities.add({
      id: "spacecraft-2",
      availability,
      position: position2,
      point: {
        pixelSize: 9,
        color: Color.fromCssColorString(SERIES[3]),
        outlineColor: Color.BLACK,
        outlineWidth: 1,
      },
      path: new PathGraphics({
        material: Color.fromCssColorString(SERIES[3]).withAlpha(0.7),
        width: 1.6,
        leadTime: timeline.durationS,
        trailTime: timeline.durationS,
        resolution: Math.max(10, timeline.durationS / 2000),
      }),
    });
  }

  // Body-axes triad: dynamic polylines driven by a CallbackProperty so the
  // geometry is per-frame without rebuilds (rebuilding every tick keeps the
  // DataSourceDisplay un-ready, which freezes the Viewer clock).
  const sigma = run.channel("sigma_BN");
  const triadEntities: Entity[] = [];
  if (sigma) {
    const radius0 = Math.hypot(r.at(0, 0), r.at(0, 1), r.at(0, 2));
    const axisLen = Math.max(0.12 * radius0, 400_000);
    const icrfToFixed = new Matrix3();
    for (let axis = 0; axis < 3; axis++) {
      const positionsAt = (time: JulianDate | undefined): Cartesian3[] => {
        if (!time) return [];
        const fixedFrame = Transforms.computeIcrfToFixedMatrix(time, icrfToFixed);
        if (!fixedFrame) return []; // Earth-orientation data not ready this frame
        const tSim = JulianDate.secondsDifference(time, timeline.epoch);
        const k = nearestIndex(run.time, tSim);
        const posInertial = new Cartesian3(r.at(k, 0), r.at(k, 1), r.at(k, 2));
        const originFixed = Matrix3.multiplyByVector(fixedFrame, posInertial, new Cartesian3());
        const dcmBN = mrpToDcm([sigma.at(k, 0), sigma.at(k, 1), sigma.at(k, 2)]);
        // Body axis `axis` expressed in N is row `axis` of [BN].
        const axisN = new Cartesian3(dcmBN[axis][0], dcmBN[axis][1], dcmBN[axis][2]);
        const axisFixed = Matrix3.multiplyByVector(fixedFrame, axisN, new Cartesian3());
        const tip = Cartesian3.add(
          originFixed,
          Cartesian3.multiplyByScalar(axisFixed, axisLen, new Cartesian3()),
          new Cartesian3(),
        );
        return [originFixed, tip];
      };
      triadEntities.push(
        viewer.entities.add({
          id: `triad-${axis}`,
          availability,
          polyline: {
            positions: new CallbackProperty((time) => positionsAt(time as JulianDate), false),
            width: 2,
            material: TRIAD_COLORS[axis],
            arcType: ArcType.NONE,
          },
        }),
      );
    }
  }

  // Frame the whole orbit, then release the camera lock for free navigation.
  let maxRadius = 0;
  for (let k = 0; k < n; k++) {
    maxRadius = Math.max(maxRadius, Math.hypot(r.at(k, 0), r.at(k, 1), r.at(k, 2)));
  }
  viewer.camera.lookAt(
    Cartesian3.ZERO,
    new Cartesian3(maxRadius * 2.4, maxRadius * 0.6, maxRadius * 1.2),
  );
  viewer.camera.lookAtTransform(Matrix4.IDENTITY);

  return {
    dispose() {
      viewer.entities.removeById("spacecraft");
      if (hasSecond) viewer.entities.removeById("spacecraft-2");
      for (const ent of triadEntities) viewer.entities.remove(ent);
    },
  };
}
