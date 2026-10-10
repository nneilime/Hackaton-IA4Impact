// Scènes 3D du diapo (three.js) : une Occitanie en relief, ses voies, ses gares et des TER liO.
// - Deck3D.play(slide, nom, retardMs, onCaption) : une scène sur la carte, caméra par plans avec des « coups de
//   fouet » entre deux plans ; ensuite la caméra tourne lentement, sans fin.
//   · intro : la région seule, son liseré jaune qui se dessine, 3,2 s
//   · introFull : la première intro, 10 s — voies, gares, noms des villes et petits trains qui circulent
//   · follow : « Suivez le train », la rame parcourt Perpignan → Toulouse → Albi
// - Deck3D.transition(kind, dir, hooks) : un vrai TER 3D traverse l'écran pendant un changement de slide.
// Chargé à la demande (import dynamique) : three.js n'alourdit pas le reste du diapo.
import * as THREE from "three";
import { NETWORK } from "../data";
import { box, buildTrain, mat, MATS } from "./train3d";

export type SceneName = "intro" | "introFull" | "follow";
export type Caption = (text: string | null) => void;

const N = NETWORK, ST = N.stations;
const RED = 0xc90c0f, YELLOW = 0xffd500;
const SCALE = 45, TOP = 0.35;
const V = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z);
/** Point de la carte SVG (x, y dans le repère 1000 × 820 : une gare ou un point du contour) → monde 3D */
const w = (p: readonly unknown[], h = TOP) => V(((p[0] as number) - 500) / SCALE, h, ((p[1] as number) - 410) / SCALE);
const byId = (id: string) => ST[N.ids[id]];
const PLACES = { perpignan: w(byId("87784009")), toulouse: w(byId("87611004")), albi: w(byId("87615005")), montpellier: w(byId("87773002")), nimes: w(byId("87775007")) };

// ═══ Scène de la carte ═══════════════════════════════
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(1);
renderer.setSize(1920, 1080, false);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap; // PCFSoft coûte bien plus pour une différence invisible en projection
renderer.domElement.className = "gl";
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x060f26);
scene.fog = new THREE.Fog(0x060f26, 24, 62);
const camera = new THREE.PerspectiveCamera(35, 16 / 9, 0.02, 200);
scene.add(new THREE.HemisphereLight(0xffffff, 0x223366, 1.3));
const sun = new THREE.DirectionalLight(0xffffff, 2.6);
sun.position.set(6, 12, 5);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048); // 4096 : ombre de 16 M de pixels recalculée à chaque image
Object.assign(sun.shadow.camera, { left: -13, right: 13, top: 11, bottom: -11, near: 1, far: 40 });
sun.shadow.bias = -0.0004;
scene.add(sun);
const rimLight = new THREE.DirectionalLight(0x8fb3ff, 0.9);
rimLight.position.set(-8, 5, -8);
scene.add(rimLight);

// La région en relief
const pts = N.outline.replace(/[MZ]/g, "").split("L").map((p) => p.split(",").map(Number));
const shape = new THREE.Shape(pts.map(([x, y]) => new THREE.Vector2((x - 500) / SCALE, -(y - 410) / SCALE)));
const land = new THREE.ExtrudeGeometry(shape, { depth: TOP, bevelEnabled: true, bevelSize: 0.04, bevelThickness: 0.04, bevelSegments: 2 });
land.rotateX(-Math.PI / 2);
const landMesh = new THREE.Mesh(land, new THREE.MeshStandardMaterial({ color: 0x24397a, roughness: 0.85, metalness: 0.05 }));
landMesh.receiveShadow = true;
scene.add(landMesh);

// Liseré jaune en tube (une ligne WebGL ne fait qu'un pixel) : deux traits partent du sud, face à la caméra,
// font le tour de la région chacun de leur côté et se rejoignent au nord, une étincelle en tête de chaque trait
const outline = (() => {
  const P = pts.map((p) => w(p, TOP + 0.05));
  const s = P.reduce((b, p, i) => (p.z > P[b].z ? i : b), 0), n = P.reduce((b, p, i) => (p.z < P[b].z ? i : b), 0);
  const ring = P.slice(s).concat(P.slice(0, s)), k = (n - s + P.length) % P.length;
  const halves = [ring.slice(0, k + 1), ring.slice(k).concat([ring[0]]).reverse()];
  const core = new THREE.MeshBasicMaterial({ color: YELLOW });
  const glowMat = new THREE.MeshBasicMaterial({ color: YELLOW, transparent: true, opacity: 0.22, blending: THREE.AdditiveBlending, depthWrite: false });
  const spark = new THREE.SphereGeometry(0.075, 14, 10), halo = new THREE.SphereGeometry(0.26, 14, 10);
  const haloMat = new THREE.MeshBasicMaterial({ color: 0xfff1a0, transparent: true, opacity: 0.4, blending: THREE.AdditiveBlending, depthWrite: false });
  const parts = halves.map((h) => {
    const curve = new THREE.CatmullRomCurve3(h, false, "centripetal"), seg = h.length * 3;
    const geo = new THREE.TubeGeometry(curve, seg, 0.03, 6, false), glow = new THREE.TubeGeometry(curve, seg, 0.1, 8, false);
    const head = new THREE.Group();
    head.add(new THREE.Mesh(spark, new THREE.MeshBasicMaterial({ color: 0xfffbe6 })), new THREE.Mesh(halo, haloMat));
    scene.add(new THREE.Mesh(geo, core), new THREE.Mesh(glow, glowMat), head);
    return { curve, geo, glow, head };
  });
  const count = (g: THREE.BufferGeometry) => g.index?.count ?? 0;
  // p : avancement 0 → 1 ; flash : éclat du halo quand les deux traits se rejoignent
  return (p: number, flash = 0) => {
    for (const o of parts) {
      o.geo.setDrawRange(0, Math.floor((count(o.geo) * p) / 3) * 3);
      o.glow.setDrawRange(0, Math.floor((count(o.glow) * p) / 3) * 3);
      o.head.visible = p > 0 && p < 1;
      if (o.head.visible) o.head.position.copy(o.curve.getPointAt(p));
    }
    glowMat.opacity = 0.22 + 0.5 * flash;
  };
})();

// Sol pointillé à perte de vue
{
  const g: number[] = [];
  for (let x = -40; x <= 40; x += 0.8) for (let z = -40; z <= 40; z += 0.8) g.push(x, -0.02, z);
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(g, 3));
  scene.add(new THREE.Points(geo, new THREE.PointsMaterial({ color: 0x2a3f78, size: 0.06 })));
}

// Voies : un ruban par tronçon, révélé depuis le centre
const center = V(0, TOP, 0);
const dist = (i: number) => w(ST[i]).distanceTo(center);
const edges = N.edges.slice().sort((a, b) => Math.min(dist(a[0]), dist(a[1])) - Math.min(dist(b[0]), dist(b[1])));
const TRACK_Y = TOP + 0.048;
const tracks = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 0.012, 0.026), new THREE.MeshStandardMaterial({ color: 0xdfe3ec, roughness: 0.4, metalness: 0.3, emissive: 0x334477, emissiveIntensity: 0.4 }), edges.length);
tracks.receiveShadow = true;
{
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = V(1, 1, 1);
  edges.forEach(([a, b], k) => {
    const A = w(ST[a], TRACK_Y), B = w(ST[b], TRACK_Y);
    q.setFromAxisAngle(V(0, 1, 0), -Math.atan2(B.z - A.z, B.x - A.x));
    s.set(A.distanceTo(B) + 0.02, 1, 1);
    tracks.setMatrixAt(k, m.compose(A.clone().lerp(B, 0.5), q, s));
  });
  scene.add(tracks);
}

// Gares : un quai blanc liseré de jaune, orienté le long de la voie ; un vrai bâtiment pour les grandes gares
const adj: number[][] = ST.map(() => []);
N.edges.forEach(([a, b]) => { adj[a].push(b); adj[b].push(a); });
const stOrder = ST.map((_, i) => i).sort((a, b) => dist(a) - dist(b));
const majors = new Set(Object.values(N.ids));
const heading = (i: number) => { const n = adj[i][0]; if (n == null) return 0; const A = w(ST[i]), B = w(ST[n]); return -Math.atan2(B.z - A.z, B.x - A.x); };
const platforms = new THREE.InstancedMesh(new THREE.BoxGeometry(0.12, 0.03, 0.045), new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.5 }), ST.length);
const platEdges = new THREE.InstancedMesh(new THREE.BoxGeometry(0.122, 0.006, 0.012), new THREE.MeshBasicMaterial({ color: YELLOW }), ST.length);
platforms.castShadow = platforms.receiveShadow = true;
{
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), one = V(1, 1, 1);
  stOrder.forEach((i, k) => {
    q.setFromAxisAngle(V(0, 1, 0), heading(i));
    const side = V(0, 0, 0.034).applyQuaternion(q);
    const p = w(ST[i], TOP + 0.06).add(side);
    platforms.setMatrixAt(k, m.compose(p, q, one));
    platEdges.setMatrixAt(k, m.compose(p.clone().add(V(0, 0.017, 0)).addScaledVector(side, -0.6), q, one));
  });
  scene.add(platforms, platEdges);
}
const buildings = new THREE.Group();
for (const i of majors) {
  const g = new THREE.Group();
  const hall = box(0.22, 0.1, 0.1, MATS.white, 0, 0.05, 0);
  const roof = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.24, 16, 1, false, 0, Math.PI), MATS.navy);
  roof.rotation.z = Math.PI / 2; roof.position.y = 0.1;
  const sign = box(0.08, 0.035, 0.005, new THREE.MeshBasicMaterial({ color: RED }), 0, 0.075, 0.053);
  const clock = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.018, 0.01, 16), new THREE.MeshBasicMaterial({ color: YELLOW }));
  clock.rotation.x = Math.PI / 2; clock.position.set(0, 0.13, 0.03);
  g.add(hall, roof, sign, clock);
  g.traverse((o) => { if (o instanceof THREE.Mesh) o.castShadow = o.receiveShadow = true; });
  g.position.copy(w(ST[i], TOP + 0.045)).add(V(0, 0, -0.12).applyAxisAngle(V(0, 1, 0), heading(i)));
  g.rotation.y = heading(i);
  buildings.add(g);
}
scene.add(buildings);

function reveal(p: number) {
  tracks.count = Math.floor(edges.length * p);
  platforms.count = platEdges.count = Math.floor(ST.length * Math.min(1, p * 1.1));
  buildings.children.forEach((b, i) => b.scale.setScalar(THREE.MathUtils.clamp(p * 3 - 1.5 - i * 0.1, 0.001, 1)));
}

// Étiquettes : taille constante à l'écran
const labels = new THREE.Group();
scene.add(labels);
function label(text: string, pos: THREE.Vector3) {
  const c = document.createElement("canvas"), x = c.getContext("2d")!, fs = 48;
  x.font = `800 ${fs}px Barlow, sans-serif`;
  c.width = x.measureText(text).width + fs * 1.2; c.height = fs * 1.7;
  x.font = `800 ${fs}px Barlow, sans-serif`;
  x.fillStyle = "#0f2149"; x.beginPath(); x.roundRect(0, 0, c.width, c.height, c.height / 2); x.fill();
  x.fillStyle = "#fff"; x.textBaseline = "middle"; x.fillText(text, fs * 0.6, c.height / 2 + 2);
  const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true, sizeAttenuation: false }));
  s.scale.set((0.036 * c.width) / c.height, 0.036, 1);
  s.center.set(0.5, -0.4);
  s.position.copy(pos).add(V(0, 0.2, 0));
  s.renderOrder = 10;
  labels.add(s);
}
([["Perpignan", PLACES.perpignan], ["Toulouse", PLACES.toulouse], ["Albi", PLACES.albi], ["Montpellier", PLACES.montpellier], ["Nîmes", PLACES.nimes]] as const).forEach(([t, p]) => label(t, p));

// Trajet Perpignan → Albi : ruban lumineux au-dessus des voies
const legs = N.route.legs.map((l, i) => {
  const curve = new THREE.CatmullRomCurve3(l.stops.map((s) => w(ST[s], TOP + 0.075)), false, "centripetal");
  const geo = new THREE.TubeGeometry(curve, 600, 0.018, 8, false);
  const glow = new THREE.TubeGeometry(curve, 600, 0.05, 8, false);
  scene.add(new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: i ? YELLOW : RED })),
    new THREE.Mesh(glow, new THREE.MeshBasicMaterial({ color: i ? YELLOW : RED, transparent: true, opacity: 0.25, depthWrite: false })));
  return { curve, geo, glow, count: geo.index?.count ?? 0, gcount: glow.index?.count ?? 0 };
});
function drawRoute(p0: number, p1: number) {
  [p0, p1].forEach((p, i) => { const l = legs[i]; l.geo.setDrawRange(0, Math.floor((l.count * p) / 3) * 3); l.glow.setDrawRange(0, Math.floor((l.gcount * p) / 3) * 3); });
}

// Le héros : un TER de deux voitures. Et une douzaine de petites rames qui circulent sur le réseau
const hero = buildTrain();
hero.train.rotation.y = -Math.PI / 2; // nez vers +z : lookAt oriente la rame dans le sens de la marche
const heroRig = new THREE.Group(); heroRig.add(hero.train); heroRig.scale.setScalar(0.12);
scene.add(heroRig);
const ambient = Array.from({ length: 12 }, () => {
  const t = buildTrain();
  t.train.rotation.y = -Math.PI / 2;
  const rig = new THREE.Group(); rig.add(t.train); rig.scale.setScalar(0.055);
  scene.add(rig);
  const starts = ST.map((_, i) => i).filter((i) => adj[i].length);
  const a = starts[Math.floor(Math.random() * starts.length)];
  return { rig, wheels: t.wheels, a, b: adj[a][0], t: Math.random(), speed: 0.5 + Math.random() * 0.4 };
});
function moveAmbient(dt: number, on: boolean) {
  for (const tr of ambient) {
    tr.rig.visible = on;
    if (!on) continue;
    const A = w(ST[tr.a], TRACK_Y + 0.006), B = w(ST[tr.b], TRACK_Y + 0.006), len = A.distanceTo(B) || 0.01;
    tr.t += (tr.speed * dt) / len;
    if (tr.t >= 1) {
      const next = adj[tr.b].filter((n) => n !== tr.a), pick = next.length ? next : adj[tr.b];
      tr.a = tr.b; tr.b = pick[Math.floor(Math.random() * pick.length)]; tr.t = 0;
      continue;
    }
    tr.rig.position.lerpVectors(A, B, tr.t);
    tr.rig.lookAt(B.x, tr.rig.position.y, B.z);
    tr.wheels.forEach((wh) => (wh.rotation.z -= dt * 12));
  }
}

/** Ce qui est sur la carte : la région seule (intro courte) ou tout le réseau */
function network(on: boolean) {
  tracks.visible = platforms.visible = platEdges.visible = buildings.visible = labels.visible = on;
  legs.forEach((l) => l.geo.setDrawRange(0, 0));
}

// ── Caméra par plans ─────────────────────────────────
interface Shot { at: number; blend?: number; caption?: string; pos: (t: number) => THREE.Vector3; tgt: (t: number) => THREE.Vector3 }
const easeExpo = (p: number) => (p <= 0 ? 0 : p >= 1 ? 1 : p < 0.5 ? Math.pow(2, 20 * p - 10) / 2 : (2 - Math.pow(2, -20 * p + 10)) / 2);
const easeSine = (p: number) => -(Math.cos(Math.PI * Math.min(1, Math.max(0, p))) - 1) / 2;
const easeInOutCubic = (p: number) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
const orbit = (c: THREE.Vector3, r: number, h: number, a: number) => V(c.x + Math.cos(a) * r, c.y + h, c.z + Math.sin(a) * r);
const state: { shot: number; onCaption: Caption | null } = { shot: -1, onCaption: null };
function shoot(shots: Shot[], t: number) {
  let i = 0;
  while (i + 1 < shots.length && t >= shots[i + 1].at) i++;
  const s = shots[i], p = s.pos(t), g = s.tgt(t);
  camera.fov = 35;
  if (i > 0 && t - s.at < (s.blend ?? 1)) {
    const k = easeExpo((t - s.at) / (s.blend ?? 1)), prev = shots[i - 1];
    p.lerpVectors(prev.pos(t), p, k);
    g.lerpVectors(prev.tgt(t), g, k);
    camera.fov = 35 + Math.sin(k * Math.PI) * 10; // coup de zoom pendant le fouet
  }
  camera.updateProjectionMatrix();
  camera.position.copy(p);
  camera.lookAt(g);
  if (state.shot !== i) { state.shot = i; state.onCaption?.(s.caption ?? null); }
}

// Le héros sur le trajet, en 10 s : marche, correspondance à Toulouse, arrivée à Albi
const RIDE0 = [1, 6.3], WAIT = [6.3, 7.1], RIDE1 = [7.1, 9.4];
function heroAt(t: number) {
  let leg = 0, u: number;
  if (t < RIDE0[1]) u = easeSine((t - RIDE0[0]) / (RIDE0[1] - RIDE0[0]));
  else if (t < WAIT[1]) u = 1;
  else { leg = 1; u = easeSine((t - RIDE1[0]) / (RIDE1[1] - RIDE1[0])); }
  u = Math.min(0.999, Math.max(0.001, u));
  const c = legs[leg].curve, pos = c.getPointAt(u), tan = c.getTangentAt(u);
  pos.y = TRACK_Y + 0.006;
  const moving = (t > RIDE0[0] && t < RIDE0[1]) || (t > RIDE1[0] && t < RIDE1[1]);
  return { pos, tan, side: V(-tan.z, 0, tan.x), moving };
}

interface Scene3D { setup(): void; update(t: number, dt: number): void }
const SCENES: Record<SceneName, Scene3D> = {
  // 3,2 s, un seul plan continu : l'orbite tourne dès la première image et la descente s'y fond à vitesse nulle,
  // sans raccord (un raccord faisait sauter le champ de vision pendant une image)
  intro: {
    setup() { network(false); heroRig.visible = false; moveAmbient(0, false); },
    update(t) {
      const p = Math.min(1, Math.max(0, (t - 0.25) / 2.6)), d = easeInOutCubic(p);
      outline(d, p >= 1 ? Math.exp(-(t - 2.85) * 2.2) : 0);
      const C = V(0.5, 0, 1.2), e = easeInOutCubic(Math.min(1, t / 3.2));
      const a = 1.25 + t * 0.025 - 0.35 * (1 - e);
      camera.position.copy(V(0, 46, 34).lerp(orbit(V(0.5, 0, 1), 17, 14, a), e));
      camera.lookAt(V(0, 0, 0).lerp(C, e));
    },
  },
  // 10 s : chute depuis le ciel, la côte de Perpignan à Montpellier, Toulouse, puis la région entière qui tourne
  introFull: {
    setup() { network(true); reveal(0); heroRig.visible = false; },
    update(t, dt) {
      reveal(Math.min(1, Math.max(0, (t - 0.4) / 4.6)));
      outline(easeInOutCubic(Math.min(1, Math.max(0, (t - 0.25) / 2.6))));
      moveAmbient(dt, true);
      const P = PLACES.perpignan, M = PLACES.montpellier, T = PLACES.toulouse;
      shoot([
        { at: 0, pos: (t) => V(0, 46, 34).lerp(V(P.x + 4, 5, P.z + 6), easeSine(t / 2.2)), tgt: (t) => V(0, 0, 0).lerp(P, easeSine(t / 2.2)) },
        { at: 2.2, blend: 0.8, pos: (t) => P.clone().lerp(M, easeSine((t - 2.2) / 2.8)).add(V(1.8, 1.3, 2.6)), tgt: (t) => P.clone().lerp(M, easeSine((t - 2.2) / 2.8)) },
        { at: 5, blend: 0.9, pos: (t) => orbit(T, 2.8, 1.9 + (t - 5) * 0.3, 2.2 + (t - 5) * 0.35), tgt: () => T.clone() },
        { at: 7.4, blend: 1.4, pos: (t) => orbit(V(0.5, 0, 1), 17, 14, 1.25 + (t - 7.4) * 0.025), tgt: () => V(0.5, 0, 1.2) },
      ], t);
    },
  },
  // 10 s : le trajet se dessine, la caméra suit la rame sous plusieurs angles, puis tourne autour d'Albi
  follow: {
    setup() { network(true); reveal(1); outline(1); heroRig.visible = true; },
    update(t, dt) {
      drawRoute(Math.min(1, t / 1), Math.min(1, Math.max(0, (t - 0.7) / 0.6)));
      moveAmbient(dt, t < 1 || t > 9.5);
      const h = heroAt(t);
      heroRig.position.copy(h.pos);
      heroRig.lookAt(h.pos.clone().add(h.tan));
      hero.wheels.forEach((wh) => (wh.rotation.z -= h.moving ? 0.4 : 0));
      hero.caisses.forEach((c, i) => (c.rotation.x = h.moving ? 0.025 * Math.sin(t * 9 + i) : 0));
      const T = PLACES.toulouse, A = PLACES.albi, mid = PLACES.perpignan.clone().lerp(T, 0.5);
      shoot([
        { at: 0, pos: () => V(mid.x + 1, 9, mid.z + 7), tgt: () => mid.clone(), caption: "Perpignan → Albi" },
        { at: 1.3, blend: 0.6, pos: (k) => { const s = heroAt(k); return s.pos.clone().addScaledVector(s.tan, -0.7).add(V(0, 0.3, 0)); }, tgt: (k) => { const s = heroAt(k); return s.pos.clone().addScaledVector(s.tan, 0.6); } },
        { at: 3.2, blend: 0.45, pos: (k) => { const s = heroAt(k); return s.pos.clone().addScaledVector(s.side, 0.55).add(V(0, 0.07, 0)); }, tgt: (k) => heroAt(k).pos.clone().add(V(0, 0.04, 0)) },
        { at: 4.8, blend: 0.45, pos: (k) => heroAt(k).pos.clone().add(V(Math.sin(k * 0.8) * 0.4, 1.5, Math.cos(k * 0.8) * 0.4)), tgt: (k) => heroAt(k).pos.clone() },
        { at: 6.3, blend: 0.5, pos: (k) => orbit(T, 1.1, 0.6, k * 0.9), tgt: () => T.clone(), caption: "Correspondance à Toulouse" },
        { at: 7.1, blend: 0.45, pos: (k) => { const s = heroAt(k); return s.pos.clone().addScaledVector(s.tan, 0.6).addScaledVector(s.side, 0.16).add(V(0, 0.05, 0)); }, tgt: (k) => heroAt(k).pos.clone().add(V(0, 0.04, 0)), caption: "Toulouse → Albi" },
        { at: 9.3, blend: 1.2, pos: (k) => orbit(A, 2.4, 1.4 + Math.min(1.2, (k - 9.3) * 0.25), 0.8 + (k - 9.3) * 0.08), tgt: () => A.clone(), caption: "Albi · 4 h 00" },
      ], t);
    },
  },
};

let current: SceneName | null = null, start = 0, raf = 0, last = 0;
function frame(now: number) {
  raf = requestAnimationFrame(frame);
  const t = Math.max(0, (now - start) / 1000), dt = last ? Math.min(0.05, (now - last) / 1000) : 0;
  last = now;
  SCENES[current!].update(t, dt);
  renderer.render(scene, camera);
}

// ═══ Transitions : un TER 3D grandeur écran ══════════
const tRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
tRenderer.setPixelRatio(1);
tRenderer.setSize(1920, 1080, false);
tRenderer.toneMapping = THREE.ACESFilmicToneMapping;
tRenderer.domElement.className = "gl-trans";
const tScene = new THREE.Scene();
tScene.add(new THREE.HemisphereLight(0xffffff, 0x334477, 1.6));
const tSun = new THREE.DirectionalLight(0xffffff, 2.4); tSun.position.set(3, 6, 5); tScene.add(tSun);
const tCam = new THREE.PerspectiveCamera(48, 16 / 9, 0.05, 300);
const ter = buildTrain({ cars: 4 });
const tTrain = new THREE.Group(); tTrain.add(ter.train);
tScene.add(tTrain);
// Voie : deux rails et des traverses
const track = new THREE.Group();
for (const z of [-0.24, 0.24]) track.add(box(400, 0.04, 0.04, MATS.grey, 0, 0.02, z));
{
  const sl = new THREE.InstancedMesh(new THREE.BoxGeometry(0.12, 0.03, 0.75), mat(0x3b3226), 900), m = new THREE.Matrix4();
  for (let i = 0; i < 900; i++) sl.setMatrixAt(i, m.makeTranslation(-200 + i * (400 / 900), 0, 0));
  track.add(sl);
}
tScene.add(track);

export type Trans3D = "ter3d" | "front";
export interface TransHooks { onReveal?: (px: number) => void; onCover?: () => void; done: () => void }

let tRaf = 0;
function runTransition(layer: HTMLElement, kind: Trans3D, dir: 1 | -1, { onReveal, onCover, done }: TransHooks) {
  cancelAnimationFrame(tRaf);
  layer.append(tRenderer.domElement);
  const L = ter.length, t0 = performance.now();
  let covered = false;
  if (kind === "ter3d") {
    // De profil, au ras du quai : la rame occupe l'écran, la nouvelle slide est découverte derrière sa queue
    const D = 1450;
    tCam.fov = 50; tCam.position.set(0, 0.5, 1.9); tCam.lookAt(dir * 0.5, 0.4, 0); tCam.updateProjectionMatrix();
    track.rotation.y = 0; tTrain.rotation.y = dir > 0 ? 0 : Math.PI;
    const span = 7 + L;
    const f = (now: number) => {
      const p = Math.min(1, (now - t0) / D), e = 0.3 * p + 0.7 * (p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2);
      const head = -3.5 + e * span; // position du nez, dans le sens de la marche
      tTrain.position.set(dir * head, Math.sin(now / 40) * 0.006, 0);
      ter.wheels.forEach((wh) => (wh.rotation.z -= 0.6));
      tCam.position.y = 0.5 + Math.sin(now / 33) * 0.008; // la caméra tremble au passage
      const tail = V(dir * (head - L), 0.5, 0).project(tCam), x = ((tail.x + 1) / 2) * 1920;
      onReveal?.(Math.max(0, Math.min(1920, dir > 0 ? x : 1920 - x)));
      tRenderer.render(tScene, tCam);
      if (p < 1) tRaf = requestAnimationFrame(f);
      else { tRenderer.domElement.remove(); done(); }
    };
    f(t0);
  } else {
    // De face : la rame fonce vers la caméra, phares allumés, remplit l'écran — on change de slide derrière elle
    const D = 1700;
    tCam.fov = 40; tCam.position.set(0.55, 0.62, 0); tCam.lookAt(0.2, 0.5, -20); tCam.updateProjectionMatrix();
    track.rotation.y = Math.PI / 2; tTrain.rotation.y = -Math.PI / 2; // nez vers +z : vers la caméra
    const f = (now: number) => {
      const p = Math.min(1, (now - t0) / D);
      const z = -70 + Math.pow(p, 2.2) * (70 + L + 4); // accélère jusqu'à dépasser la caméra
      tTrain.position.set(-0.05, 0, z);
      ter.wheels.forEach((wh) => (wh.rotation.z -= 0.6));
      MATS.head.color.setHex(0xfff3b0).multiplyScalar(1 + 0.6 * Math.sin(now / 50));
      tCam.position.x = 0.55 + Math.sin(now / 27) * 0.01 * p;
      if (!covered && z > -1.2) { covered = true; onCover?.(); }
      tRenderer.domElement.style.opacity = z > L - 2 ? String(Math.max(0, 1 - (z - (L - 2)) / 3)) : "1";
      tRenderer.render(tScene, tCam);
      if (p < 1) tRaf = requestAnimationFrame(f);
      else { tRenderer.domElement.remove(); tRenderer.domElement.style.opacity = "1"; if (!covered) onCover?.(); done(); }
    };
    f(t0);
  }
}

export const Deck3D = {
  play(slide: HTMLElement, name: SceneName = "intro", delayMs = 0, onCaption: Caption | null = null) {
    this.stop();
    slide.querySelector(".stage3d")?.append(renderer.domElement);
    current = name; state.shot = -1; state.onCaption = onCaption;
    SCENES[name].setup();
    // Première image dessinée tout de suite, horloge arrêtée : compilation des shaders et envoi au GPU se font
    // ici, pas pendant le mouvement (sinon la caméra « saute » de la durée de la compilation)
    SCENES[name].update(0, 0);
    renderer.render(scene, camera);
    start = performance.now() + delayMs; last = 0;
    raf = requestAnimationFrame(frame);
  },
  stop(slide?: HTMLElement) {
    if (slide && !slide.contains(renderer.domElement)) return; // une autre scène a déjà pris le canvas
    cancelAnimationFrame(raf);
    current = null;
  },
  transition: runTransition,
};

// Préchauffage hors écran dès que le navigateur souffle : la première image d'une scène compile ses shaders
const idle = (f: () => void) => ("requestIdleCallback" in window ? requestIdleCallback(f, { timeout: 2000 }) : setTimeout(f, 300));
const warm = (name: SceneName) => {
  if (current) return; // une scène joue déjà : elle est chaude
  const keep = state.onCaption; state.onCaption = null;
  SCENES[name].setup(); SCENES[name].update(0, 0); renderer.render(scene, camera);
  state.onCaption = keep; state.shot = -1;
};
idle(() => warm("follow"));
idle(() => warm("intro"));
idle(() => { tCam.position.set(0, 0.5, 1.9); tCam.lookAt(0, 0.4, 0); tRenderer.render(tScene, tCam); });
