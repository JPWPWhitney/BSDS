/** Self-contained three.js renderer for runs whose central body is not Earth
 * (asteroids, moons, ...): dark sky + star field, matte central body sphere,
 * spacecraft point + full orbit trail, body-axes triad, optional second body
 * from r_moon_N, orbit controls, and a minimal play/pause + slider bar that
 * drives the shared rAF Timeline (charts.ts works unchanged against it).
 * The three scene works in kilometers; BSD1 channels are meters. */

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

import { mrpToDcm } from "./attitude";
import { nearestIndex, type RunData } from "./bsd1";
import {
  bodyColorHex,
  bodyRadiusKm,
  cameraRangesKm,
  formatSimClock,
  sampleVec3Km,
  starField,
  triadLengthKm,
} from "./exoticcore";
import type { RafTimeline } from "./timeline";

const TRAIL_COLOR = 0xffd45a;
const TRIAD_COLORS = [0xff5a5a, 0x6aff6a, 0x5aa9ff];

export interface ExoticHandles {
  dispose(): void;
}

/** Round-dot texture drawn on a canvas so the spacecraft point matches the
 * Cesium look (filled disc + thin dark outline) without external assets. */
function discTexture(fill: string): THREE.Texture {
  const size = 32;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  ctx.beginPath();
  ctx.arc(size / 2, size / 2, size / 2 - 2, 0, 2 * Math.PI);
  ctx.fillStyle = fill;
  ctx.fill();
  ctx.lineWidth = 2;
  ctx.strokeStyle = "#000000";
  ctx.stroke();
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

export function buildExoticScene(
  host: HTMLElement,
  run: RunData,
  timeline: RafTimeline,
): ExoticHandles {
  const r = run.channel("r_BN_N");
  if (!r) throw new Error("run has no r_BN_N channel");
  const n = run.header.n;
  const body = run.header.bodies[0];
  const disposables: { dispose(): void }[] = [];

  // ---- renderer + scene + camera -----------------------------------------
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x05070c);

  const rMoon = run.channel("r_moon_N");
  const moonRadius = rMoon && rMoon.components === 3 ? bodyRadiusKm(run.header.bodies, "moon") : null;

  let maxOrbitKm = 0;
  for (let k = 0; k < n; k++) {
    maxOrbitKm = Math.max(maxOrbitKm, Math.hypot(r.at(k, 0), r.at(k, 1), r.at(k, 2)) / 1000);
    if (rMoon && moonRadius !== null) {
      maxOrbitKm = Math.max(
        maxOrbitKm,
        Math.hypot(rMoon.at(k, 0), rMoon.at(k, 1), rMoon.at(k, 2)) / 1000,
      );
    }
  }
  const ranges = cameraRangesKm(maxOrbitKm);

  const camera = new THREE.PerspectiveCamera(55, 1, ranges.near, ranges.far);
  camera.position.set(...ranges.position);
  camera.lookAt(0, 0, 0);

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.domElement.className = "exotic-canvas";
  host.appendChild(renderer.domElement);
  disposables.push(renderer);

  // ---- sky ---------------------------------------------------------------
  const starGeom = new THREE.BufferGeometry();
  starGeom.setAttribute("position", new THREE.BufferAttribute(starField(1600, ranges.starRadius), 3));
  const starMat = new THREE.PointsMaterial({
    color: 0x9aa4b8,
    size: 1.6,
    sizeAttenuation: false,
    transparent: true,
    opacity: 0.85,
    depthWrite: false,
  });
  scene.add(new THREE.Points(starGeom, starMat));
  disposables.push(starGeom, starMat);

  // ---- lights ------------------------------------------------------------
  const sun = new THREE.DirectionalLight(0xffffff, 2.4);
  sun.position.set(1, 0.4, 0.6);
  scene.add(sun, new THREE.AmbientLight(0xffffff, 0.35));

  // ---- central body ------------------------------------------------------
  const bodyGeom = new THREE.SphereGeometry(body.radius_km, 64, 48);
  const bodyMat = new THREE.MeshStandardMaterial({
    color: bodyColorHex(body.name),
    roughness: 1.0,
    metalness: 0.0,
  });
  scene.add(new THREE.Mesh(bodyGeom, bodyMat));
  disposables.push(bodyGeom, bodyMat);

  // ---- spacecraft point + full trail -------------------------------------
  const trailPositions = new Float32Array(n * 3);
  for (let k = 0; k < n; k++) {
    trailPositions[3 * k] = r.at(k, 0) / 1000;
    trailPositions[3 * k + 1] = r.at(k, 1) / 1000;
    trailPositions[3 * k + 2] = r.at(k, 2) / 1000;
  }
  const trailGeom = new THREE.BufferGeometry();
  trailGeom.setAttribute("position", new THREE.BufferAttribute(trailPositions, 3));
  const trailMat = new THREE.LineBasicMaterial({ color: TRAIL_COLOR, transparent: true, opacity: 0.7 });
  scene.add(new THREE.Line(trailGeom, trailMat));
  disposables.push(trailGeom, trailMat);

  const scTex = discTexture("#ffd45a");
  const scGeom = new THREE.BufferGeometry();
  scGeom.setAttribute("position", new THREE.BufferAttribute(new Float32Array(3), 3));
  const scMat = new THREE.PointsMaterial({
    map: scTex,
    size: 11,
    sizeAttenuation: false,
    transparent: true,
    alphaTest: 0.4,
    depthWrite: false,
  });
  const scPoint = new THREE.Points(scGeom, scMat);
  scPoint.renderOrder = 2;
  scene.add(scPoint);
  disposables.push(scTex, scGeom, scMat);

  // ---- body-axes triad ---------------------------------------------------
  const sigma = run.channel("sigma_BN");
  const radius0Km = Math.hypot(r.at(0, 0), r.at(0, 1), r.at(0, 2)) / 1000;
  const axisLenKm = triadLengthKm(radius0Km, body.radius_km);
  const triadGeoms: THREE.BufferGeometry[] = [];
  if (sigma && sigma.components === 3) {
    for (let axis = 0; axis < 3; axis++) {
      const geom = new THREE.BufferGeometry();
      geom.setAttribute("position", new THREE.BufferAttribute(new Float32Array(6), 3));
      const mat = new THREE.LineBasicMaterial({ color: TRIAD_COLORS[axis] });
      scene.add(new THREE.Line(geom, mat));
      triadGeoms.push(geom);
      disposables.push(geom, mat);
    }
  }

  // ---- optional moon -----------------------------------------------------
  let moonMesh: THREE.Mesh | null = null;
  if (rMoon && rMoon.components === 3 && moonRadius !== null) {
    const moonGeom = new THREE.SphereGeometry(moonRadius, 40, 30);
    const moonMat = new THREE.MeshStandardMaterial({ color: 0xb8bcc4, roughness: 1.0, metalness: 0.0 });
    moonMesh = new THREE.Mesh(moonGeom, moonMat);
    scene.add(moonMesh);
    disposables.push(moonGeom, moonMat);
  }

  // ---- controls + sizing -------------------------------------------------
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.12;
  controls.minDistance = ranges.near * 20;
  controls.maxDistance = ranges.starRadius * 0.5;
  disposables.push(controls);

  const resize = () => {
    const w = Math.max(1, host.clientWidth);
    const h = Math.max(1, host.clientHeight);
    renderer.setSize(w, h, false);
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  };
  resize();
  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(host);

  // ---- scrubber bar ------------------------------------------------------
  const bar = document.createElement("div");
  bar.className = "exotic-bar";
  const playBtn = document.createElement("button");
  playBtn.type = "button";
  playBtn.setAttribute("aria-label", "Play or pause");
  const slider = document.createElement("input");
  slider.type = "range";
  slider.min = String(run.time[0]);
  slider.max = String(run.time[n - 1]);
  slider.step = String(Math.max(timeline.durationS / 2000, 1e-3));
  slider.setAttribute("aria-label", "Simulation time");
  const readout = document.createElement("span");
  readout.className = "exotic-time";
  bar.append(playBtn, slider, readout);
  host.appendChild(bar);

  const syncPlayBtn = () => {
    playBtn.textContent = timeline.playing() ? "❚❚" : "▶";
  };
  syncPlayBtn();
  playBtn.addEventListener("click", () => {
    timeline.setPlaying(!timeline.playing());
    syncPlayBtn();
  });
  let scrubbing = false;
  slider.addEventListener("pointerdown", () => (scrubbing = true));
  slider.addEventListener("pointerup", () => (scrubbing = false));
  slider.addEventListener("input", () => timeline.seekSeconds(Number(slider.value)));

  // ---- per-frame update (driven by the shared rAF clock) -----------------
  const scPos: [number, number, number] = [0, 0, 0];
  const moonPos: [number, number, number] = [0, 0, 0];
  const unsubscribe = timeline.onTick((tSim) => {
    sampleVec3Km(run.time, r, tSim, scPos);
    (scGeom.attributes.position as THREE.BufferAttribute).setXYZ(0, scPos[0], scPos[1], scPos[2]);
    scGeom.attributes.position.needsUpdate = true;

    if (sigma && triadGeoms.length === 3) {
      const k = nearestIndex(run.time, tSim);
      const dcmBN = mrpToDcm([sigma.at(k, 0), sigma.at(k, 1), sigma.at(k, 2)]);
      for (let axis = 0; axis < 3; axis++) {
        const attr = triadGeoms[axis].attributes.position as THREE.BufferAttribute;
        attr.setXYZ(0, scPos[0], scPos[1], scPos[2]);
        attr.setXYZ(
          1,
          scPos[0] + dcmBN[axis][0] * axisLenKm,
          scPos[1] + dcmBN[axis][1] * axisLenKm,
          scPos[2] + dcmBN[axis][2] * axisLenKm,
        );
        attr.needsUpdate = true;
      }
    }

    if (moonMesh && rMoon) {
      sampleVec3Km(run.time, rMoon, tSim, moonPos);
      moonMesh.position.set(moonPos[0], moonPos[1], moonPos[2]);
    }

    if (!scrubbing) slider.value = String(tSim);
    readout.textContent = `${formatSimClock(tSim)} ×${timeline.multiplier}`;

    controls.update();
    renderer.render(scene, camera);
  });

  return {
    dispose() {
      unsubscribe();
      resizeObserver.disconnect();
      for (const d of disposables) d.dispose();
      bar.remove();
      renderer.domElement.remove();
    },
  };
}
