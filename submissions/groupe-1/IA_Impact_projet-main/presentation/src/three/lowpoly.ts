// L'histoire de Claire en 3D low poly : tout est modélisé ici, à facettes (flatShading), dans une palette chaude.
// Six scènes de 10 s — la salle des profs, le plateau de conférence, la classe, le quai, le trajet, Carcassonne — puis la caméra continue de dériver lentement.
// Chargé à la demande (import dynamique, seulement avec ?story) : DeckStory.play(slide, nom, retardMs) / stop(slide).
import * as THREE from "three";
import { buildTrain } from "./train3d";

const V = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z);
const easeIO = (p: number) => { p = Math.min(1, Math.max(0, p)); return p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2; };
const flat = (color: number, extra: THREE.MeshStandardMaterialParameters = {}) => new THREE.MeshStandardMaterial({ color, flatShading: true, roughness: 0.9, metalness: 0, ...extra });
const C = {
  skin: 0xe8b894, skinDark: 0xa86f4c, hair: 0x2b1d16, hairKid: [0x5a3a22, 0xc89a5a, 0x1e1a18, 0x8a4a22],
  navy: 0x0f2149, red: 0xc90c0f, yellow: 0xffd500, white: 0xf4f1ea, jeans: 0x3d5a8a, grass: 0x8cbf5f, grassDark: 0x6fa24a,
  stone: 0xdcc59a, stoneDark: 0xb89c6e, terracotta: 0xc8643c, slate: 0x5d6b8a, wood: 0xb98552, floor: 0xd2a679,
  wall: 0xf1e3c8, water: 0x4fa3c7, leaf: 0x5f9e45, leaf2: 0x7fb24e, trunk: 0x7a5434, rail: 0x9aa0ad, sleeper: 0x5b4632,
};
const box = (w: number, h: number, d: number, m: THREE.Material) => new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
const shadowAll = (o: THREE.Object3D) => o.traverse((c) => { if (c instanceof THREE.Mesh) { c.castShadow = true; c.receiveShadow = true; } });

// ── Personnages : jambes, bras et tête articulés ; marche, assis, frappe au clavier ──
interface PersonOpts { kid?: boolean; top?: number; bottom?: number; hair?: number; skin?: number; glasses?: boolean; curly?: boolean; bag?: number | null }
function person({ kid = false, top = C.red, bottom = C.jeans, hair = C.hair, skin = C.skin, glasses = false, curly = false, bag = null }: PersonOpts = {}) {
  const g = new THREE.Group(), body = new THREE.Group();
  const S = kid ? 0.68 : 1;
  const mSkin = flat(skin), mTop = flat(top), mBottom = flat(bottom), mHair = flat(hair), mShoe = flat(0x2a2a30);
  const limb = (w: number, h: number, m: THREE.Material) => { const p = new THREE.Group(), b = box(w, h, w, m); b.position.y = -h / 2; p.add(b); return p; };
  const legL = limb(0.13, 0.48, mBottom), legR = limb(0.13, 0.48, mBottom);
  legL.position.set(-0.08, 0.5, 0); legR.position.set(0.08, 0.5, 0);
  for (const l of [legL, legR]) { const s = box(0.14, 0.06, 0.2, mShoe); s.position.set(0, -0.48, 0.04); l.add(s); }
  const torso = new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.2, 0.5, 6), mTop);
  torso.position.y = 0.75;
  const armL = limb(0.1, 0.44, mTop), armR = limb(0.1, 0.44, mTop);
  armL.position.set(-0.24, 0.98, 0); armR.position.set(0.24, 0.98, 0);
  for (const a of [armL, armR]) { const h = new THREE.Mesh(new THREE.IcosahedronGeometry(0.06, 0), mSkin); h.position.y = -0.46; a.add(h); }
  const head = new THREE.Group();
  head.position.y = 1.18;
  head.add(new THREE.Mesh(new THREE.IcosahedronGeometry(0.17, 1), mSkin));
  const cap = new THREE.Mesh(new THREE.SphereGeometry(0.185, 7, 5, 0, Math.PI * 2, 0, Math.PI * 0.55), mHair);
  cap.rotation.x = -0.25; cap.position.set(0, 0.02, -0.02);
  head.add(cap);
  if (curly) for (let i = 0; i < 14; i++) {
    const a = (i / 14) * Math.PI * 2, c = new THREE.Mesh(new THREE.IcosahedronGeometry(0.075, 0), mHair);
    c.position.set(Math.cos(a) * 0.17, -0.06 - Math.abs(Math.sin(a * 1.5)) * 0.08, Math.sin(a) * 0.15 - 0.05);
    if (c.position.z < 0.08) head.add(c);
  }
  if (glasses) {
    const mg = flat(0x1a1a22);
    for (const x of [-0.065, 0.065]) { const r = new THREE.Mesh(new THREE.TorusGeometry(0.045, 0.01, 4, 10), mg); r.position.set(x, 0.01, 0.16); head.add(r); }
  }
  for (const x of [-0.06, 0.06]) { const e = new THREE.Mesh(new THREE.IcosahedronGeometry(0.018, 0), flat(0x1a1a22)); e.position.set(x, 0.01, 0.158); head.add(e); }
  body.add(legL, legR, torso, armL, armR, head);
  if (bag) { const b = box(0.28, 0.32, 0.14, flat(bag)); b.position.set(0, 0.8, -0.21); body.add(b); }
  g.add(body);
  g.scale.setScalar(S);
  shadowAll(g);
  const phase = Math.random() * 6;
  return {
    g,
    walk(t: number, k = 1) {
      const s = Math.sin(t * 9 + phase) * 0.55 * k;
      legL.rotation.x = s; legR.rotation.x = -s; armL.rotation.x = -s * 0.8; armR.rotation.x = s * 0.8;
      body.position.y = Math.abs(Math.cos(t * 9 + phase)) * 0.04 * k;
      head.rotation.y = Math.sin(t * 1.3 + phase) * 0.15;
    },
    sit() { legL.rotation.x = legR.rotation.x = -1.45; body.position.y = -0.04; },
    type(t: number) {
      armL.rotation.x = -1.15 + Math.sin(t * 18) * 0.06; armR.rotation.x = -1.15 + Math.sin(t * 18 + 2) * 0.06;
      armL.rotation.z = 0.25; armR.rotation.z = -0.25;
      head.rotation.x = 0.18 + Math.sin(t * 0.8) * 0.04;
    },
    point(t: number) { armR.rotation.x = -2.6 + Math.sin(t * 3) * 0.1; },
    /** Accroche un objet (tasse, stylo) dans la main droite */
    hold(o: THREE.Object3D) { o.position.y = -0.5; armR.add(o); },
    /** Boit à petites gorgées : la main monte à la bouche toutes les ~6 s, la tête bascule un peu */
    sip(t: number) {
      const c = ((t + phase) % 6) / 6, up = c < 0.35 ? Math.sin((c / 0.35) * Math.PI) : 0;
      armR.rotation.x = -0.75 - up * 1.35; armR.rotation.z = -0.1 - up * 0.25;
      head.rotation.x = -up * 0.25;
    },
    /** Parle : main qui accompagne la phrase, tête qui hoche et se tourne vers l'interlocuteur */
    talk(t: number, toward = 0) {
      armL.rotation.x = -0.8 + Math.sin(t * 2.3 + phase) * 0.25; armL.rotation.z = 0.15 + Math.sin(t * 1.7) * 0.1;
      head.rotation.y = toward + Math.sin(t * 0.9 + phase) * 0.12; head.rotation.x = Math.sin(t * 3.1) * 0.06;
    },
    /** Corrige des copies : tête penchée, le stylo gratte, on lève les yeux de temps en temps */
    write(t: number) {
      armR.rotation.x = -1.05 + Math.sin(t * 11 + phase) * 0.05; armR.rotation.z = Math.sin(t * 2.2) * 0.08;
      armL.rotation.x = -0.95; armL.rotation.z = 0.2;
      const look = ((t + phase) % 7) > 6.1 ? 0 : 1;
      head.rotation.x = 0.42 * look;
    },
    /** Debout, poids d'une jambe sur l'autre */
    stand(t: number) {
      body.rotation.z = Math.sin(t * 0.7 + phase) * 0.025;
      head.rotation.y = Math.sin(t * 0.45 + phase) * 0.2;
    },
  };
}

function tree(scale = 1, kind = 0) {
  const g = new THREE.Group();
  const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.09, 0.8, 5), flat(C.trunk));
  trunk.position.y = 0.4; g.add(trunk);
  const leaf = flat(kind % 2 ? C.leaf2 : C.leaf);
  if (kind === 2) { // cyprès
    const c = new THREE.Mesh(new THREE.ConeGeometry(0.25, 1.6, 6), leaf); c.position.y = 1.3; g.add(c);
  } else for (let i = 0; i < 3; i++) {
    const c = new THREE.Mesh(new THREE.IcosahedronGeometry(0.42 - i * 0.06, 0), leaf);
    c.position.set((i - 1) * 0.25, 1.0 + (i % 2) * 0.25, (i % 2) * 0.15); g.add(c);
  }
  g.scale.setScalar(scale);
  shadowAll(g);
  return g;
}

function track(len: number, z = 0) {
  const g = new THREE.Group();
  for (const dz of [-0.24, 0.24]) { const r = box(len, 0.05, 0.05, flat(C.rail, { metalness: 0.4, roughness: 0.4 })); r.position.set(0, 0.06, z + dz); g.add(r); }
  const n = Math.floor(len / 0.45), sl = new THREE.InstancedMesh(new THREE.BoxGeometry(0.14, 0.04, 0.75), flat(C.sleeper), n), m = new THREE.Matrix4();
  for (let i = 0; i < n; i++) sl.setMatrixAt(i, m.makeTranslation(-len / 2 + i * 0.45, 0.02, z));
  g.add(sl);
  const ballast = box(len, 0.03, 1.1, flat(0x9d8f7e)); ballast.position.set(0, 0.005, z); g.add(ballast);
  shadowAll(g);
  return g;
}

function hills(size: number, seg: number, amp: number, color: number, seed = 1) {
  const geo = new THREE.PlaneGeometry(size, size, seg, seg);
  geo.rotateX(-Math.PI / 2);
  const p = geo.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), z = p.getZ(i), d = Math.min(1, Math.max(0, (Math.abs(z) - 3) / 8));
    p.setY(i, (Math.sin(x * 0.35 + seed) * Math.cos(z * 0.3 + seed * 2) * 0.5 + 0.5 + Math.sin(x * 0.9 + z * 0.7) * 0.15) * amp * d);
  }
  geo.computeVertexNormals();
  const m = new THREE.Mesh(geo, flat(color));
  m.receiveShadow = true;
  return m;
}

// ── Moteur ───────────────────────────────────────────
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(1);
renderer.setSize(1920, 1080, false);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap; // PCFSoft coûte bien plus pour une différence invisible en projection
renderer.domElement.className = "gl";
const camera = new THREE.PerspectiveCamera(38, 16 / 9, 0.05, 300);

function baseScene(sky: number, sunPos: THREE.Vector3, sunColor = 0xfff1d6) {
  const s = new THREE.Scene();
  s.background = new THREE.Color(sky);
  s.fog = new THREE.Fog(sky, 30, 90);
  s.add(new THREE.HemisphereLight(0xffffff, 0x8a7a66, 1.3));
  const sun = new THREE.DirectionalLight(sunColor, 2.6);
  sun.position.copy(sunPos);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -14, right: 14, top: 14, bottom: -14, near: 1, far: 80 });
  sun.shadow.bias = -0.0005;
  s.add(sun);
  return s;
}

const ui = new THREE.TextureLoader().load("assets/story/ui-scolaire.jpg");
ui.colorSpace = THREE.SRGBColorSpace;

interface StoryScene { scene: THREE.Scene; update: (t: number) => void }
const SCENES: Record<string, StoryScene> = {};

// 0 · La salle des profs, à midi : on corrige, on boit le café, on parle de la sortie — Claire cherche déjà un train
{
  const s = baseScene(0xf3e4c8, V(-7, 8, 4));
  s.fog = new THREE.Fog(0xf3e4c8, 18, 40);
  const floor = box(16, 0.1, 12, flat(0xc7b08c)); floor.position.set(0, -0.05, 1); floor.receiveShadow = true; s.add(floor);
  // Lino en dalles : un damier très doux, pour sentir la profondeur quand la caméra avance
  const tiles = new THREE.InstancedMesh(new THREE.BoxGeometry(0.98, 0.01, 0.98), flat(0xbda582), 48), tm = new THREE.Matrix4();
  for (let i = 0; i < 48; i++) { const x = (i % 8) * 2 - 7 + (Math.floor(i / 8) % 2), z = Math.floor(i / 8) - 2.5; tiles.setMatrixAt(i, tm.makeTranslation(x, 0.006, z)); }
  tiles.receiveShadow = true; s.add(tiles);
  const mWall = flat(C.wall), mDado = flat(0x9fb89a);
  const back = box(16, 4.4, 0.2, mWall); back.position.set(0, 2.2, -3); back.receiveShadow = true; s.add(back);
  const left = box(0.2, 4.4, 12, mWall); left.position.set(-5.6, 2.2, 1); left.receiveShadow = true; s.add(left);
  const right = box(0.2, 4.4, 12, mWall); right.position.set(6.1, 2.2, 1); right.receiveShadow = true; s.add(right);
  // Soubassement vert d'école, sur les trois murs
  const dB = box(16, 1, 0.04, mDado); dB.position.set(0, 0.5, -2.88); s.add(dB);
  for (const x of [-5.48, 5.98]) { const d = box(0.04, 1, 12, mDado); d.position.set(x, 0.5, 1); s.add(d); }

  // Fenêtres à gauche : le soleil de midi entre
  const glass = new THREE.MeshBasicMaterial({ color: 0xd6ecff });
  for (const z of [-1.4, 1.6]) {
    const w = box(0.06, 1.9, 1.7, glass); w.position.set(-5.49, 2.3, z); s.add(w);
    const f1 = box(0.12, 2.05, 0.08, flat(C.white)); f1.position.set(-5.45, 2.3, z); s.add(f1);
    const f2 = box(0.12, 0.08, 1.8, flat(C.white)); f2.position.set(-5.45, 2.3, z); s.add(f2);
    const sill = box(0.3, 0.06, 1.9, flat(C.white)); sill.position.set(-5.38, 1.32, z); s.add(sill);
  }

  // Casiers des profs : sept colonnes, quatre rangs, des copies et des chemises qui dépassent
  const lockers = new THREE.Group(), mFrame = flat(0x8a6038), mCell = flat(0x5e4128);
  const cols = 7, rows = 4, cw = 0.36, ch = 0.36;
  const lb = box(cols * cw + 0.08, rows * ch + 0.08, 0.36, mFrame); lockers.add(lb);
  const paper = [C.white, C.white, 0xf6d36b, 0x8fc3e8, C.white, 0xf29b7c, 0xa8d08d];
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    const x = (c - (cols - 1) / 2) * cw, y = (r - (rows - 1) / 2) * ch;
    const cell = box(cw - 0.05, ch - 0.06, 0.05, mCell); cell.position.set(x, y + 0.01, 0.17); lockers.add(cell);
    const tag = box(0.16, 0.035, 0.01, flat(C.white)); tag.position.set(x, y - ch / 2 + 0.03, 0.19); lockers.add(tag);
    if ((r * 3 + c * 5) % 4 !== 0) {
      const p = box(cw - 0.1, 0.03 + ((r + c) % 3) * 0.025, 0.3, flat(paper[(r * 2 + c) % paper.length]));
      p.position.set(x + ((c % 2) - 0.5) * 0.02, y - ch / 2 + 0.07, 0.2 + ((r + c) % 2) * 0.06); p.rotation.y = ((c + r) % 3 - 1) * 0.08; lockers.add(p);
    }
  }
  shadowAll(lockers); lockers.position.set(-2.6, 1.85, -2.72); s.add(lockers);

  // Panneau de liège : notes, emploi du temps, et une affiche liO (rouge et marine)
  const cork = box(2.3, 1.3, 0.05, flat(0xc89a62)); cork.position.set(0.7, 2.1, -2.87); s.add(cork);
  const corkF = box(2.42, 1.42, 0.04, flat(C.wood)); corkF.position.set(0.7, 2.1, -2.89); s.add(corkF);
  [[-0.85, 0.3, 0xfff07a], [-0.5, -0.25, 0x9fd8ff], [-0.9, -0.3, 0xffb0c8], [0.05, 0.38, C.white], [0.4, 0.4, 0xfff07a], [0.95, -0.35, 0xb8f0a0]].forEach(([x, y, c], i) => {
    const n = box(0.3, 0.3, 0.012, flat(c)); n.position.set(0.7 + x, 2.1 + y, -2.84); n.rotation.z = (i % 3 - 1) * 0.12; s.add(n);
    const pin = new THREE.Mesh(new THREE.IcosahedronGeometry(0.022, 0), flat(C.red)); pin.position.set(0.7 + x, 2.1 + y + 0.11, -2.82); s.add(pin);
  });
  const sheet = box(0.55, 0.42, 0.012, flat(C.white)); sheet.position.set(0.6, 1.98, -2.84); s.add(sheet);
  for (let i = 0; i < 4; i++) { const l = box(0.42, 0.018, 0.005, flat(0x9aa0ad)); l.position.set(0.6, 2.1 - i * 0.08, -2.83); s.add(l); }
  const poster = new THREE.Group();
  const pBg = box(0.6, 0.85, 0.012, flat(C.navy)); poster.add(pBg);
  const pBand = box(0.6, 0.22, 0.014, flat(C.red)); pBand.position.y = -0.2; poster.add(pBand);
  const pLine = box(0.6, 0.03, 0.016, flat(C.yellow)); pLine.position.y = -0.07; poster.add(pLine);
  const pSun = new THREE.Mesh(new THREE.CircleGeometry(0.1, 10), flat(C.yellow)); pSun.position.set(0.12, 0.2, 0.008); poster.add(pSun);
  poster.position.set(1.45, 2.12, -2.84); poster.rotation.z = -0.03; s.add(poster);

  // Horloge : l'aiguille des secondes tourne vraiment
  const clock = new THREE.Group();
  const face = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.28, 0.05, 20), flat(C.white)); face.rotation.x = Math.PI / 2; clock.add(face);
  const rim = new THREE.Mesh(new THREE.TorusGeometry(0.28, 0.025, 4, 20), flat(C.navy)); clock.add(rim);
  const hand = (len: number, w: number, c: number) => { const g = new THREE.Group(), b = box(w, len, 0.01, flat(c)); b.position.y = len / 2; g.add(b); g.position.z = 0.035; clock.add(g); return g; };
  const hH = hand(0.13, 0.03, C.navy), hM = hand(0.2, 0.02, C.navy), hS = hand(0.22, 0.008, C.red);
  hH.rotation.z = -Math.PI * 0.05; hM.rotation.z = -Math.PI; // midi et demi
  clock.position.set(0.7, 3.35, -2.86); s.add(clock);

  // Coin café : meuble bas, cafetière qui fume, bouilloire, tasses, évier, placards, frigo
  const kit = new THREE.Group(), mCab = flat(0xe9e2d2), mTop = flat(C.wood);
  const base = box(2.4, 0.86, 0.62, mCab); base.position.set(0, 0.43, 0); kit.add(base);
  for (let i = 0; i < 4; i++) { const d = box(0.56, 0.74, 0.02, flat(0xf6f1e6)); d.position.set(-0.9 + i * 0.6, 0.45, 0.32); kit.add(d); const k = box(0.08, 0.02, 0.03, flat(0x8a8f99)); k.position.set(-0.9 + i * 0.6, 0.72, 0.34); kit.add(k); }
  const top = box(2.5, 0.05, 0.68, mTop); top.position.set(0, 0.885, 0.02); kit.add(top);
  const upper = box(2.4, 0.6, 0.36, mCab); upper.position.set(0, 2.1, -0.13); kit.add(upper);
  for (let i = 0; i < 4; i++) { const d = box(0.56, 0.52, 0.02, flat(0xf6f1e6)); d.position.set(-0.9 + i * 0.6, 2.1, 0.06); kit.add(d); }
  const machine = box(0.36, 0.46, 0.34, flat(0x2a2a30)); machine.position.set(-0.8, 1.14, -0.05); kit.add(machine);
  const spout = box(0.3, 0.08, 0.14, flat(0x2a2a30)); spout.position.set(-0.8, 1.32, 0.18); kit.add(spout);
  const carafe = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.11, 0.2, 8), flat(0x6b3f22, { roughness: 0.3 })); carafe.position.set(-0.8, 1.0, 0.16); kit.add(carafe);
  const ledOn = new THREE.MeshBasicMaterial({ color: 0xff3b30 }), led = new THREE.Mesh(new THREE.IcosahedronGeometry(0.02, 0), ledOn); led.position.set(-0.68, 1.22, 0.125); kit.add(led);
  const kettle = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.11, 0.24, 8), flat(C.red)); kettle.position.set(-0.2, 1.03, 0); kit.add(kettle);
  [C.yellow, C.white, 0x3fa7d6, C.red, C.white].forEach((c, i) => { const m = new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.04, 0.1, 8), flat(c)); m.position.set(0.15 + i * 0.12, 0.96, 0.12 - (i % 2) * 0.1); kit.add(m); });
  const sink = box(0.5, 0.04, 0.4, flat(0x9aa0ad, { metalness: 0.6, roughness: 0.3 })); sink.position.set(0.85, 0.9, 0); kit.add(sink);
  const tap = box(0.03, 0.22, 0.03, flat(0x9aa0ad, { metalness: 0.6, roughness: 0.3 })); tap.position.set(0.85, 1.02, -0.2); kit.add(tap);
  const fridge = box(0.7, 1.75, 0.66, flat(C.white)); fridge.position.set(1.62, 0.875, 0); kit.add(fridge);
  const fHandle = box(0.03, 0.4, 0.04, flat(0x8a8f99)); fHandle.position.set(1.33, 1.2, 0.35); kit.add(fHandle);
  [[0xffd500, 1.75, 1.45], [0x3fa7d6, 1.55, 1.2], [0xff8a5b, 1.78, 1.05]].forEach(([c, x, y]) => { const m = box(0.12, 0.12, 0.01, flat(c)); m.position.set(x, y, 0.335); kit.add(m); });
  shadowAll(kit); kit.position.set(3.75, 0, -2.55); s.add(kit);

  // Photocopieuse au fond à gauche : la barre de lumière balaie la vitre
  const copier = new THREE.Group();
  const cBody = box(0.85, 0.95, 0.62, flat(0xd5d8de)); cBody.position.y = 0.475; copier.add(cBody);
  const cLid = box(0.87, 0.06, 0.64, flat(0x8a8f99)); cLid.position.y = 0.98; copier.add(cLid);
  const tray = box(0.4, 0.03, 0.3, flat(0x8a8f99)); tray.position.set(0.55, 0.7, 0); tray.rotation.z = -0.15; copier.add(tray);
  const outPile = box(0.32, 0.05, 0.24, flat(C.white)); outPile.position.set(0.56, 0.74, 0); outPile.rotation.z = -0.15; copier.add(outPile);
  const scan = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.01, 0.56), new THREE.MeshBasicMaterial({ color: 0x9effc8 })); scan.position.y = 0.94; copier.add(scan);
  const cLed = new THREE.Mesh(new THREE.IcosahedronGeometry(0.02, 0), new THREE.MeshBasicMaterial({ color: 0x4cd964 })); cLed.position.set(-0.3, 0.88, 0.32); copier.add(cLed);
  shadowAll(copier); copier.position.set(-4.7, 0, -2.4); s.add(copier);

  // Plantes : une grande près des fenêtres, une petite sur le comptoir
  function plant(h: number) {
    const g = new THREE.Group();
    const pot = new THREE.Mesh(new THREE.CylinderGeometry(0.2 * h, 0.15 * h, 0.35 * h, 7), flat(C.terracotta)); pot.position.y = 0.175 * h; g.add(pot);
    for (let i = 0; i < 5; i++) {
      const l = new THREE.Mesh(new THREE.IcosahedronGeometry((0.28 - i * 0.03) * h, 0), flat(i % 2 ? C.leaf : C.leaf2));
      l.position.set(Math.cos(i * 2.4) * 0.12 * h, (0.55 + i * 0.22) * h, Math.sin(i * 2.4) * 0.12 * h); g.add(l);
    }
    shadowAll(g); return g;
  }
  const ficus = plant(1.5); ficus.position.set(-4.9, 0, 0.1); s.add(ficus);
  const small = plant(0.45); small.position.set(5.1, 0.9, -2.45); s.add(small);

  // Canapé rouge fatigué, coin repos
  const sofa = new THREE.Group(), mSofa = flat(0xb5262a);
  const sSeat = box(1.9, 0.38, 0.8, mSofa); sSeat.position.y = 0.3; sofa.add(sSeat);
  const sBack = box(1.9, 0.6, 0.22, mSofa); sBack.position.set(0, 0.65, -0.32); sofa.add(sBack);
  for (const x of [-0.95, 0.95]) { const a = box(0.2, 0.55, 0.8, mSofa); a.position.set(x, 0.4, 0); sofa.add(a); }
  const cushion = box(0.42, 0.36, 0.12, flat(C.yellow)); cushion.position.set(-0.55, 0.65, -0.15); cushion.rotation.z = 0.2; sofa.add(cushion);
  shadowAll(sofa); sofa.position.set(-4.95, 0, 2.6); sofa.rotation.y = Math.PI / 2; s.add(sofa);

  // La grande table commune et ses chaises
  const table = new THREE.Group();
  const tTop = box(4.4, 0.07, 1.35, flat(0xd9b27c)); tTop.position.y = 0.76; table.add(tTop);
  for (const [x, z] of [[-2.05, -0.58], [2.05, -0.58], [-2.05, 0.58], [2.05, 0.58]]) { const l = box(0.07, 0.76, 0.07, flat(0x8a8f99)); l.position.set(x, 0.38, z); table.add(l); }
  shadowAll(table); table.position.set(0.2, 0, 0.6); s.add(table);
  function chair(x: number, z: number, ry: number, color: number) {
    const g = new THREE.Group(), m = flat(color), mLeg = flat(0x5d6470);
    const seat = box(0.46, 0.05, 0.44, m); seat.position.y = 0.46; g.add(seat);
    const backr = box(0.46, 0.42, 0.05, m); backr.position.set(0, 0.74, -0.22); backr.rotation.x = -0.08; g.add(backr);
    for (const [lx, lz] of [[-0.2, -0.19], [0.2, -0.19], [-0.2, 0.19], [0.2, 0.19]]) { const l = box(0.035, 0.46, 0.035, mLeg); l.position.set(lx, 0.23, lz); g.add(l); }
    shadowAll(g); g.position.set(x, 0, z); g.rotation.y = ry; s.add(g);
  }
  // Les profs : deux face à nous, deux de dos (dont Claire et son portable), une debout au coin café
  const mug = (c: number) => { const m = new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.04, 0.1, 8), flat(c)); m.castShadow = true; return m; };
  const seats: [number, number, number][] = [[-1.1, -0.42, 0], [0.95, -0.42, 0], [-0.75, 1.62, Math.PI], [1.35, 1.62, Math.PI]];
  seats.forEach(([x, z, ry], i) => chair(x, z, ry, [0x3fa7d6, C.yellow, 0x8fd16a, C.navy][i]));
  const marc = person({ top: 0x6f8f72, bottom: 0x4a4a52, hair: 0x6b6b6b, glasses: true });      // corrige ses copies
  const nadia = person({ top: 0xd9774a, bottom: 0x2d3a55, skin: C.skinDark, hair: 0x1e1a18 }); // raconte, sa tasse à la main
  const paul = person({ top: 0x3fa7d6, bottom: 0x3d4a5e, hair: 0x8a4a22 });                       // écoute, boit
  const claire = person({ top: C.navy, bottom: 0x2d3a55, glasses: true, curly: true });            // cherche un train
  const lea = person({ top: C.red, bottom: C.jeans, hair: 0xc89a5a });                             // debout, au café
  const sitters = [marc, nadia, paul, claire];
  sitters.forEach((p, i) => {
    const [x, z, ry] = seats[i];
    p.g.position.set(x, 0, z + (ry ? -0.08 : 0.08)); p.g.rotation.y = ry; p.sit(); s.add(p.g);
  });
  const pen = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.16, 5), flat(C.red)); pen.rotation.x = Math.PI / 2; marc.hold(pen);
  nadia.hold(mug(C.white)); paul.hold(mug(C.yellow)); lea.hold(mug(0x3fa7d6));
  lea.g.position.set(3.2, 0, -1.55); lea.g.rotation.y = -0.9; s.add(lea.g);

  // Sur la table : copies, cahiers, corbeille de fruits, tasses, le portable de Claire
  const props = new THREE.Group();
  for (let i = 0; i < 6; i++) { const c = box(0.32, 0.012, 0.42, flat(C.white)); c.position.set(-1.1 + (i % 2) * 0.03, 0.8 + i * 0.012, 0.05); c.rotation.y = (i % 3 - 1) * 0.06; props.add(c); }
  const open = box(0.34, 0.006, 0.44, flat(0xfffdf6)); open.position.set(-1.45, 0.8, 0.12); open.rotation.y = 0.25; props.add(open);
  [0xf29b7c, 0x8fc3e8, 0xa8d08d, 0xf6d36b].forEach((c, i) => { const n = box(0.28, 0.02, 0.38, flat(c)); n.position.set(-1.75 + i * 0.02, 0.81 + i * 0.02, 0.55); n.rotation.y = 0.3 + i * 0.07; props.add(n); });
  const bowl = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.13, 0.1, 9), flat(0xe9e2d2)); bowl.position.set(0.1, 0.85, 0.6); props.add(bowl);
  [[0xff8a2b, -0.07, 0.02], [0xc90c0f, 0.07, -0.03], [0x9fd14a, 0, 0.08], [0xff8a2b, 0.05, 0.08]].forEach(([c, x, z]) => { const f = new THREE.Mesh(new THREE.IcosahedronGeometry(0.07, 0), flat(c)); f.position.set(0.1 + x, 0.93, 0.6 + z); props.add(f); });
  const tMugs = [mug(0x3fa7d6), mug(C.yellow)]; tMugs[0].position.set(-0.4, 0.84, 1.0); tMugs[1].position.set(1.85, 0.84, 1.05); props.add(...tMugs);
  const lapBase = box(0.5, 0.025, 0.34, flat(0xc9cdd8, { metalness: 0.5, roughness: 0.4 })); lapBase.position.set(1.35, 0.81, 0.98); props.add(lapBase);
  const lid = new THREE.Group(); lid.position.set(1.35, 0.82, 0.81); lid.rotation.x = -0.28;
  const lidBack = box(0.5, 0.34, 0.02, flat(0xc9cdd8, { metalness: 0.5, roughness: 0.4 })); lidBack.position.y = 0.17; lid.add(lidBack);
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(0.46, 0.3), new THREE.MeshBasicMaterial({ map: ui })); screen.position.set(0, 0.17, 0.012); lid.add(screen);
  props.add(lid);
  shadowAll(props); s.add(props);

  // Vapeur : des bouffées qui montent des tasses posées et de la cafetière, puis s'effacent
  const puffs: { m: THREE.Mesh; o: THREE.Vector3; ph: number }[] = [];
  const sources = [V(-0.4, 0.9, 1.0), V(1.85, 0.9, 1.05), V(3.75 - 0.8, 1.12, -2.39)];
  sources.forEach((o, si) => { for (let i = 0; i < 5; i++) {
    const m = new THREE.Mesh(new THREE.IcosahedronGeometry(0.03, 0), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, depthWrite: false }));
    s.add(m); puffs.push({ m, o, ph: i / 5 + si * 0.13 });
  } });

  const look0 = V(-0.4, 1.05, -0.6), look1 = V(0.15, 1.0, 0.45);
  SCENES.salleProfs = {
    scene: s,
    update(t: number) {
      marc.write(t); nadia.talk(t, 0.35); nadia.sip(t + 2); paul.sip(t); claire.type(t);
      lea.stand(t); lea.sip(t + 4); lea.talk(t + 1, 0.2);
      // Petits détails vivants : horloge, voyant de la cafetière, scanner, vapeur
      hS.rotation.z = -Math.floor(t) * (Math.PI / 30);
      ledOn.color.setHex(Math.sin(t * 2.5) > 0 ? 0xff3b30 : 0x6a1a16);
      scan.position.x = -0.38 + ((t * 0.45) % 1) * 0.76;
      for (const p of puffs) {
        const c = (t * 0.33 + p.ph) % 1;
        p.m.position.set(p.o.x + Math.sin(c * 6 + p.ph * 9) * 0.04, p.o.y + c * 0.45, p.o.z + Math.cos(c * 5) * 0.02);
        p.m.scale.setScalar(0.6 + c * 1.6);
        (p.m.material as THREE.MeshBasicMaterial).opacity = Math.sin(c * Math.PI) * 0.45;
      }
      // Plan large depuis l'entrée, puis on s'approche de la table ; l'action reste à droite, le texte vit à gauche
      const k = easeIO(Math.min(t, 10) / 10);
      const p = V(-3.6, 3.0, 7.4).lerp(V(-0.9, 1.85, 4.3), k), tg = look0.clone().lerp(look1, k);
      if (t > 10) { p.x += Math.sin((t - 10) * 0.25) * 0.25; p.y += Math.sin((t - 10) * 0.4) * 0.04; }
      camera.position.copy(p); camera.lookAt(tg);
    },
  };
}

// 0 bis · Le plateau de conférence : salle plongée dans le noir, écran géant, projecteurs, l'intervenant sur scène
{
  const s = new THREE.Scene();
  s.background = new THREE.Color(0x070d22);
  s.fog = new THREE.Fog(0x070d22, 14, 34);
  s.add(new THREE.HemisphereLight(0x6f86c8, 0x1a1420, 0.8));
  const glow = (c: number, o = 1) => new THREE.MeshBasicMaterial({ color: c, transparent: o < 1, opacity: o, toneMapped: false });

  // Salle : moquette, murs sombres, gradins du public
  const floor = box(30, 0.1, 30, flat(0x1d2442)); floor.position.set(0, -0.05, 4); floor.receiveShadow = true; s.add(floor);
  const back = box(30, 9, 0.2, flat(0x0e1530)); back.position.set(0, 4.5, -7.2); s.add(back);
  for (const x of [-9, 9]) { const w = box(0.2, 9, 30, flat(0x101833)); w.position.set(x, 4.5, 4); s.add(w); }

  // Scène : estrade, nez de scène lumineux, marches
  const stage = box(14, 0.8, 4.6, flat(0x161b2e)); stage.position.set(0, 0.4, -4.6); stage.receiveShadow = true; s.add(stage);
  const deck = box(14, 0.02, 4.6, flat(0x2a3150, { roughness: 0.5 })); deck.position.set(0, 0.81, -4.6); deck.receiveShadow = true; s.add(deck);
  const lip = box(14, 0.05, 0.05, glow(0xc90c0f)); lip.position.set(0, 0.78, -2.28); s.add(lip);
  for (let i = 0; i < 3; i++) { const st = box(1.4, 0.27 * (i + 1), 0.35, flat(0x161b2e)); st.position.set(5.2, 0.135 * (i + 1), -1.6 - i * 0.35); s.add(st); }

  // Écran géant 16:9 : le titre du diapo, dessiné dans un canvas aux polices du site
  const cv = document.createElement("canvas"); cv.width = 1920; cv.height = 1080;
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 4;
  const drawScreen = () => {
    const g = cv.getContext("2d")!;
    const bg = g.createLinearGradient(0, 0, 1920, 1080); bg.addColorStop(0, "#0f2149"); bg.addColorStop(1, "#1b3570");
    g.fillStyle = bg; g.fillRect(0, 0, 1920, 1080);
    // Trame de points façon charte liO, en bas à droite
    const pal = ["#c90c0f", "#ffd500", "#ffffff"];
    for (let r = 0; r < 5; r++) for (let c = 0; c < 22; c++) { g.globalAlpha = 0.25 + ((r * 7 + c * 3) % 5) * 0.15; g.fillStyle = pal[(r + c) % 3]; g.beginPath(); g.arc(1000 + c * 38, 820 + r * 38, 9, 0, Math.PI * 2); g.fill(); }
    g.globalAlpha = 1;
    g.fillStyle = "#c90c0f"; g.beginPath(); g.roundRect(150, 250, 330, 72, 36); g.fill();
    g.fillStyle = "#ffd500"; g.font = "700 40px 'Barlow Semi Condensed', sans-serif"; g.textBaseline = "middle"; g.fillText("I A   I M P A C T", 190, 288);
    g.fillStyle = "#ffffff"; g.font = "800 190px 'Barlow Semi Condensed', sans-serif"; g.textBaseline = "alphabetic";
    g.fillText("L'Occitanie", 140, 540);
    g.fillText("en train", 140, 730);
    const w = g.measureText("en train").width;
    g.fillStyle = "#c90c0f"; g.beginPath(); g.roundRect(140, 752, w, 20, 10); g.fill();
    tex.needsUpdate = true;
  };
  drawScreen();
  document.fonts.load("800 190px 'Barlow Semi Condensed'").then(() => document.fonts.load("700 40px 'Barlow Semi Condensed'")).then(drawScreen);
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(8, 4.5), new THREE.MeshBasicMaterial({ map: tex, toneMapped: false }));
  screen.position.set(0, 4.1, -6.95); s.add(screen);
  const bezel = box(8.3, 4.8, 0.1, flat(0x05070f)); bezel.position.set(0, 4.1, -7.02); s.add(bezel);
  // Halo de l'écran sur la scène
  const fill = new THREE.PointLight(0x5c7fe0, 6, 12, 1.2); fill.position.set(0, 3.5, -5.5); s.add(fill);

  // Colonnes LED de part et d'autre de l'écran
  const leds: THREE.MeshBasicMaterial[] = [];
  for (const x of [-5.2, 5.2]) for (let i = 0; i < 12; i++) {
    const m = glow(i % 3 === 0 ? 0xffd500 : 0xc90c0f); leds.push(m);
    const b = box(0.5, 0.26, 0.06, m); b.position.set(x, 1.4 + i * 0.4, -6.9); s.add(b);
  }

  // Pupitre aux couleurs liO, micro
  const lect = new THREE.Group();
  const lBody = box(0.75, 1.1, 0.5, flat(0xf4f1ea)); lBody.position.y = 0.55; lect.add(lBody);
  const lBand = box(0.76, 0.26, 0.02, flat(C.red)); lBand.position.set(0, 0.75, 0.26); lect.add(lBand);
  const lLine = box(0.76, 0.04, 0.025, flat(C.yellow)); lLine.position.set(0, 0.6, 0.26); lect.add(lLine);
  const lTop = box(0.85, 0.05, 0.6, flat(0xdcd6c8)); lTop.position.set(0, 1.12, 0); lTop.rotation.x = 0.18; lect.add(lTop);
  const mic = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, 0.35, 4), flat(0x222222)); mic.position.set(0.18, 1.3, 0.1); mic.rotation.x = 0.5; lect.add(mic);
  shadowAll(lect); lect.position.set(-3.6, 0.82, -3.6); s.add(lect);
  // Table basse, fauteuils et plante pour le plateau
  const tbl = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 0.4, 0.45, 10), flat(0xf4f1ea)); tbl.position.set(3.3, 1.05, -4.6); s.add(tbl);
  const water = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.16, 6), flat(0x9fd8ff, { roughness: 0.2 })); water.position.set(3.25, 1.36, -4.55); s.add(water);
  for (const x of [2.4, 4.2]) {
    const a = new THREE.Group(), m = flat(0x8a1418);
    const seat = box(0.75, 0.35, 0.7, m); seat.position.y = 0.2; a.add(seat);
    const bk = box(0.75, 0.6, 0.16, m); bk.position.set(0, 0.55, -0.3); a.add(bk);
    shadowAll(a); a.position.set(x, 0.82, -4.9); a.rotation.y = x < 3 ? 0.35 : -0.35; s.add(a);
  }

  // L'intervenant : marche lentement d'un bord à l'autre en parlant au public
  const speaker = person({ top: C.navy, bottom: 0x2b2f3a, hair: 0x5a3a22, glasses: true });
  speaker.g.position.set(0, 0.82, -3.5); s.add(speaker.g);
  const clicker = box(0.04, 0.03, 0.12, flat(0x222222)); speaker.hold(clicker);

  // Projecteurs : des faisceaux visibles depuis la passerelle, l'un suit l'intervenant
  const truss = box(14, 0.18, 0.18, flat(0x3a3f52, { metalness: 0.6, roughness: 0.4 })); truss.position.set(0, 7.2, -1.2); s.add(truss);
  const beams: { light: THREE.SpotLight; cone: THREE.Mesh; from: THREE.Vector3 }[] = [];
  [[-4.5, 0xfff1d6, true], [0, 0xfff6e8, false], [4.5, 0xffe2b0, false]].forEach(([x, c, shadow]) => {
    const from = V(x as number, 7.05, -1.2);
    const can = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.22, 0.4, 8), flat(0x1a1d28)); can.position.copy(from); s.add(can);
    const light = new THREE.SpotLight(c as number, 5, 0, 0.3, 0.6, 0);
    light.position.copy(from); light.castShadow = shadow as boolean;
    if (shadow) { light.shadow.mapSize.set(1024, 1024); light.shadow.bias = -0.0005; }
    s.add(light, light.target);
    const coneGeo = new THREE.ConeGeometry(1.6, 1, 20, 1, true); coneGeo.translate(0, -0.5, 0);
    const cone = new THREE.Mesh(coneGeo, new THREE.MeshBasicMaterial({ color: c as number, transparent: true, opacity: 0.035, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide, toneMapped: false }));
    s.add(cone); beams.push({ light, cone, from });
  });
  const aim = (b: (typeof beams)[number], to: THREE.Vector3) => {
    b.light.target.position.copy(to);
    const d = to.clone().sub(b.from), len = d.length();
    b.cone.position.copy(b.from); b.cone.scale.set(len * 0.24, len, len * 0.24);
    b.cone.quaternion.setFromUnitVectors(V(0, -1, 0), d.normalize());
  };

  // Le public, de dos : rangées de fauteuils rouges, une allée centrale, la salle presque pleine
  const mSeat = flat(0x7a1418), seats = new THREE.Group();
  const audience: ReturnType<typeof person>[] = [];
  const tops = [C.red, C.yellow, 0x3fa7d6, 0x8fd16a, 0xff8a5b, 0x9b7bff, C.white, 0x5d6b8a, 0xd9774a, 0x2d3a55];
  let n = 0;
  for (let r = 0; r < 6; r++) for (let c = 0; c < 12; c++) {
    const x = (c - 5.5) * 0.85 + (c < 6 ? -0.45 : 0.45), z = 0.6 + r * 1.15, y = r * 0.18;
    const ch = new THREE.Group();
    const seat = box(0.6, 0.12, 0.5, mSeat); seat.position.y = 0.42; ch.add(seat);
    const bk = box(0.6, 0.7, 0.1, mSeat); bk.position.set(0, 0.75, 0.25); ch.add(bk);
    const riser = box(0.7, y + 0.01, 1.15, flat(0x1d2442)); riser.position.set(0, -y / 2, 0); if (y) ch.add(riser);
    ch.position.set(x, y, z); seats.add(ch);
    if ((r * 5 + c * 7) % 9 !== 4) {
      const p = person({ top: tops[n++ % tops.length], bottom: 0x2d3a55, hair: [C.hair, 0x6b4a2a, 0xc89a5a, 0x1e1a18, 0x8a8a8a][(r + c) % 5], skin: (r + c) % 4 === 1 ? C.skinDark : C.skin, curly: (r * c) % 7 === 3 });
      p.g.position.set(x, y, z - 0.08); p.g.rotation.y = Math.PI; p.sit(); s.add(p.g); audience.push(p);
    }
  }
  seats.traverse((o) => { if (o instanceof THREE.Mesh) o.receiveShadow = true; }); s.add(seats);

  SCENES.conference = {
    scene: s,
    update(t: number) {
      // L'intervenant va et vient sur le devant de la scène, s'arrête pour parler, se tourne vers la salle
      const cyc = (t % 16) / 16, dir = cyc < 0.5 ? 1 : -1, ph = (cyc % 0.5) * 2;
      const moving = ph > 0.15 && ph < 0.65, k = easeIO(Math.min(1, Math.max(0, (ph - 0.15) / 0.5)));
      const x = dir > 0 ? -1.6 + k * 3.2 : 1.6 - k * 3.2;
      speaker.g.position.x = x;
      speaker.g.rotation.y = moving ? dir * 1.1 : Math.sin(t * 0.6) * 0.35;
      speaker.walk(t, moving ? 0.8 : 0);
      if (!moving) speaker.talk(t, 0);
      aim(beams[0], V(x, 0.8, -3.5)); aim(beams[1], V(0, 0.8, -4.2)); aim(beams[2], V(3.3, 0.8, -4.6));
      audience.forEach((p) => p.stand(t));
      leds.forEach((m, i) => m.color.setHex(Math.sin(t * 2 - i * 0.5) > 0.6 ? 0xffd500 : (i % 2 ? 0xc90c0f : 0x6a0a0c)));
      // Du fond de la salle, au-dessus des têtes, la caméra avance vers la scène
      const kk = easeIO(Math.min(t, 10) / 10);
      const p = V(-2.6, 4.6, 12.5).lerp(V(1.1, 2.4, 6.4), kk), tg = V(-0.6, 3.2, -5).lerp(V(0, 2.5, -4.5), kk);
      if (t > 10) { p.x += Math.sin((t - 10) * 0.22) * 0.5; p.y += Math.sin((t - 10) * 0.35) * 0.06; }
      camera.position.copy(p); camera.lookAt(tg);
    },
  };
}

// 1 · La classe : Claire tape sur son portable, l'écran montre le vrai site
{
  const s = baseScene(0xf6e6cc, V(-6, 7, 5));
  const floor = box(14, 0.1, 10, flat(C.floor)); floor.position.y = -0.05; floor.receiveShadow = true; s.add(floor);
  const back = box(14, 5, 0.2, flat(C.wall)); back.position.set(0, 2.5, -3); back.receiveShadow = true; s.add(back);
  const left = box(0.2, 5, 10, flat(C.wall)); left.position.set(-5, 2.5, 2); s.add(left);
  // Fenêtres lumineuses sur le mur de gauche, tableau vert et dessins d'enfants au fond
  for (const z of [-1, 1.8]) { const w = box(0.25, 1.9, 1.5, new THREE.MeshBasicMaterial({ color: 0xcfe8ff })); w.position.set(-4.95, 2.4, z); s.add(w); const f = box(0.3, 2.05, 0.08, flat(C.white)); f.position.set(-4.9, 2.4, z); s.add(f); }
  const board = box(3.4, 1.4, 0.08, flat(0x2f5a46)); board.position.set(1.6, 2.4, -2.88); s.add(board);
  const frame = box(3.6, 1.6, 0.06, flat(C.wood)); frame.position.set(1.6, 2.4, -2.9); s.add(frame);
  [0xff8a5b, 0x5bb0ff, 0xffd34d, 0x8fd16a, 0xff6fa8, 0x9b7bff].forEach((c, i) => {
    const p = box(0.5, 0.42, 0.03, flat(c)); p.position.set(-3.6 + i * 0.62, 3.6 + (i % 2) * 0.15, -2.88); p.rotation.z = (i % 3 - 1) * 0.08; s.add(p);
  });
  // Bureau, chaise, portable
  const desk = new THREE.Group();
  const top = box(1.8, 0.08, 0.9, flat(C.wood)); top.position.y = 0.78; desk.add(top);
  for (const [x, z] of [[-0.8, -0.38], [0.8, -0.38], [-0.8, 0.38], [0.8, 0.38]]) { const l = box(0.07, 0.78, 0.07, flat(0x8a6038)); l.position.set(x, 0.39, z); desk.add(l); }
  const lapBase = box(0.5, 0.025, 0.34, flat(0xc9cdd8, { metalness: 0.5, roughness: 0.4 })); lapBase.position.set(0.1, 0.835, 0.1); desk.add(lapBase);
  const lid = new THREE.Group(); lid.position.set(0.1, 0.85, -0.07); lid.rotation.x = -0.28;
  const back2 = box(0.5, 0.34, 0.02, flat(0xc9cdd8, { metalness: 0.5, roughness: 0.4 })); back2.position.y = 0.17; lid.add(back2);
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(0.46, 0.3), new THREE.MeshBasicMaterial({ map: ui })); screen.position.set(0, 0.17, 0.012); lid.add(screen);
  desk.add(lid);
  const mug = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.11, 8), flat(C.yellow)); mug.position.set(-0.55, 0.88, 0.15); desk.add(mug);
  shadowAll(desk); desk.position.set(0, 0, 0.4); s.add(desk);
  const chair = new THREE.Group();
  const seat = box(0.5, 0.06, 0.5, flat(C.navy)); seat.position.y = 0.48; chair.add(seat);
  const backrest = box(0.5, 0.55, 0.06, flat(C.navy)); backrest.position.set(0, 0.78, 0.25); chair.add(backrest);
  shadowAll(chair); chair.position.set(0.1, 0, 1.25); s.add(chair);
  const claire = person({ top: C.navy, bottom: 0x2d3a55, glasses: true, curly: true });
  claire.g.position.set(0.1, 0.0, 1.15); claire.g.rotation.y = Math.PI; claire.sit(); s.add(claire.g);
  // Rangées de pupitres vides
  for (let r = 0; r < 2; r++) for (let c = 0; c < 3; c++) { const d = box(0.9, 0.06, 0.5, flat(C.wood)); d.position.set(-2.4 + c * 1.6, 0.62, 3 + r * 1.3); d.castShadow = true; s.add(d); }
  const T = V(0.1, 1.05, 0.4);
  SCENES.classe = {
    scene: s,
    update(t: number) {
      claire.type(t);
      const k = easeIO(t / 10);
      // Large de face, puis par-dessus l'épaule jusqu'à l'écran du portable
      const a = V(-3.2, 2.6, 5.2), b = V(0.75, 1.55, 2.0), c = V(0.18, 1.2, 0.95);
      const p = k < 0.6 ? a.clone().lerp(b, easeIO(k / 0.6)) : b.clone().lerp(c, easeIO((k - 0.6) / 0.4));
      const tg = k < 0.6 ? T.clone().lerp(V(0.1, 0.95, 0.15), easeIO(k / 0.6)) : V(0.1, 0.95, 0.15).lerp(V(0.1, 1.01, -0.04), easeIO((k - 0.6) / 0.4));
      if (t > 10) { p.x += Math.sin((t - 10) * 0.3) * 0.04; p.y += Math.sin((t - 10) * 0.4) * 0.02; }
      camera.position.copy(p); camera.lookAt(tg);
    },
  };
}

// 2 · Le quai : Claire et sa classe marchent jusqu'au TER
{
  const s = baseScene(0xbfe0f5, V(8, 12, 6));
  const ground = box(60, 0.1, 40, flat(C.grass)); ground.position.y = -0.05; ground.receiveShadow = true; s.add(ground);
  const platform = box(26, 0.4, 3, flat(0xcfc7b8)); platform.position.set(0, 0.2, 1.6); platform.receiveShadow = true; s.add(platform);
  const edge = box(26, 0.02, 0.18, flat(C.yellow)); edge.position.set(0, 0.41, 0.25); s.add(edge);
  s.add(track(60, -0.6));
  // Gare en pierre, toit de tuiles, horloge
  const st = new THREE.Group();
  const walls = box(5, 2.4, 2, flat(C.stone)); walls.position.y = 1.2; st.add(walls);
  const roofShape = new THREE.Shape([new THREE.Vector2(-2.8, 0), new THREE.Vector2(2.8, 0), new THREE.Vector2(0, 1.1)]);
  const roof = new THREE.Mesh(new THREE.ExtrudeGeometry(roofShape, { depth: 2.4, bevelEnabled: false }), flat(C.terracotta));
  roof.rotation.y = Math.PI / 2; roof.position.set(0, 2.4, 0); roof.rotation.set(0, 0, 0); roof.position.set(0, 2.4, -1.2); st.add(roof);
  for (const x of [-1.6, 0, 1.6]) { const d = box(0.7, 1.3, 0.05, flat(0x3b5b7a)); d.position.set(x, 0.85, 1.02); st.add(d); }
  const clock = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.3, 0.06, 16), flat(C.white)); clock.rotation.x = Math.PI / 2; clock.position.set(0, 2.05, 1.04); st.add(clock);
  const sign = box(1.8, 0.35, 0.05, flat(C.navy)); sign.position.set(0, 2.5, 1.25); st.add(sign);
  shadowAll(st); st.position.set(-2, 0.4, 4.4); s.add(st);
  [[-8, 5, 0], [-4.5, 6, 1], [3.5, 5.5, 0], [7, 6, 1], [11, 5, 0], [-11, 6, 2]].forEach(([x, z, k]) => { const tr = tree(1.6, k); tr.position.set(x, 0, z); s.add(tr); });
  for (let i = 0; i < 10; i++) { const tr = tree(1.2 + Math.random(), i % 3); tr.position.set(-25 + i * 5.5, 0, -9 - Math.random() * 6); s.add(tr); }
  const ter = buildTrain({ cars: 3 });
  ter.train.position.set(8, 0.07, -0.6); s.add(ter.train);
  ter.train.traverse((o) => { if (o instanceof THREE.Mesh) o.receiveShadow = true; });
  const group = [person({ top: C.navy, bottom: 0x2d3a55, glasses: true, curly: true })];
  const tops = [C.red, C.yellow, 0x3fa7d6, 0x8fd16a, 0xff8a5b, 0x9b7bff];
  for (let i = 0; i < 6; i++) group.push(person({ kid: true, top: tops[i], hair: C.hairKid[i % 4], skin: i === 2 ? C.skinDark : C.skin, bag: tops[(i + 3) % 6] }));
  const spots = [[0, 1.2], [-0.8, 0.8], [-0.9, 1.7], [-1.7, 1.2], [-2.4, 0.7], [-2.6, 1.9], [-3.3, 1.3]];
  group.forEach((p) => { p.g.rotation.y = Math.PI / 2; s.add(p.g); });
  SCENES.quai = {
    scene: s,
    update(t: number) {
      const walkT = Math.min(t, 9), x0 = -7 + walkT * 0.85;
      group.forEach((p, i) => {
        p.g.position.set(x0 + spots[i][0], 0.4, spots[i][1] + 0.4);
        p.walk(t, t < 9 ? 1 : Math.max(0, 1 - (t - 9) * 2));
      });
      // Devant le groupe, sur le quai : la caméra recule pendant qu'ils avancent, puis pivote vers le TER
      const k = easeIO(t / 10), lead = group[0].g.position;
      const p = V(lead.x + 4.2 - k * 1.2, 1.35 + k * 0.5, 2.9);
      if (t > 10) p.y += Math.sin((t - 10) * 0.4) * 0.05;
      camera.position.copy(p);
      camera.lookAt(lead.x - 1 + k * 7, 0.95, 0.9 - k * 1.2);
    },
  };
}

// 3 · Le trajet : le TER file entre collines, vignes et étang
{
  const s = baseScene(0xa9d8f2, V(10, 14, 4));
  s.add(hills(120, 60, 5, C.grass, 1));
  const lagoon = new THREE.Mesh(new THREE.PlaneGeometry(200, 30), flat(C.water, { roughness: 0.3, metalness: 0.1 }));
  lagoon.rotation.x = -Math.PI / 2; lagoon.position.set(0, 0.02, 20); s.add(lagoon);
  s.add(track(200, 0));
  // Vignes en rangs, arbres et cyprès épars, quelques nuages
  const vine = new THREE.InstancedMesh(new THREE.BoxGeometry(0.35, 0.35, 0.35), flat(0x5f8f3a), 2400), m = new THREE.Matrix4();
  let n = 0;
  for (let r = 0; r < 12; r++) for (let i = 0; i < 200 && n < 2400; i++) { m.makeTranslation(-60 + i * 0.6, 0.18, -3 - r * 0.9); vine.setMatrixAt(n++, m); }
  vine.castShadow = true; s.add(vine);
  for (let i = 0; i < 40; i++) { const tr = tree(1 + Math.random() * 0.8, i % 3); tr.position.set(-60 + Math.random() * 120, 0, -16 - Math.random() * 18); s.add(tr); }
  for (let i = 0; i < 8; i++) {
    const cl = new THREE.Group();
    for (let j = 0; j < 4; j++) { const b = new THREE.Mesh(new THREE.IcosahedronGeometry(1 + Math.random(), 0), flat(0xffffff)); b.position.set(j * 1.3, Math.random() * 0.6, Math.random()); cl.add(b); }
    cl.position.set(-50 + i * 14, 12 + Math.random() * 4, -25 - Math.random() * 10); s.add(cl);
  }
  const ter = buildTrain({ cars: 3 });
  s.add(ter.train);
  SCENES.trajet = {
    scene: s,
    update(t: number) {
      const x = -30 + t * 6;
      ter.train.position.set(x, 0.07, 0);
      ter.wheels.forEach((w) => (w.rotation.z -= 0.5));
      ter.caisses.forEach((c, i) => (c.rotation.x = 0.012 * Math.sin(t * 10 + i)));
      // Travelling latéral, puis la caméra passe devant la rame, puis grue au-dessus de l'étang
      const k = Math.min(t, 10);
      const shots: [number, (tt: number) => THREE.Vector3, (tt: number) => THREE.Vector3][] = [
        [0, () => V(x - 1, 1.2, 4.2), () => V(x - 1, 0.6, 0)],
        [3.4, () => V(x + 4.5, 0.8, 1.6), () => V(x - 1, 0.6, 0)],
        [6.6, (tt: number) => V(x - 6 + (tt - 6.6) * 1.5, 7 + (tt - 6.6) * 0.6, 12), () => V(x - 2, 0, 2)],
      ];
      let i = 0; while (i + 1 < shots.length && k >= shots[i + 1][0]) i++;
      let p = shots[i][1](k), g = shots[i][2](k);
      if (i > 0 && k - shots[i][0] < 0.7) { const e = easeIO((k - shots[i][0]) / 0.7); p = shots[i - 1][1](k).lerp(p, e); g = shots[i - 1][2](k).lerp(g, e); }
      camera.position.copy(p); camera.lookAt(g);
    },
  };
}

// 4 · Carcassonne : remparts, tours à toits pointus, la classe arrive au pied des murs
{
  const s = baseScene(0xf7c99a, V(-12, 9, 8), 0xffd9a8);
  s.fog = new THREE.Fog(0xf7c99a, 35, 100);
  const ground = box(120, 0.1, 120, flat(0xa9b86a)); ground.position.y = -0.05; ground.receiveShadow = true; s.add(ground);
  const hill = new THREE.Mesh(new THREE.CylinderGeometry(9, 12, 1.6, 10), flat(0x9aa85e)); hill.position.set(0, 0.8, -6); hill.receiveShadow = true; s.add(hill);
  const mStone = flat(C.stone), mDark = flat(C.stoneDark), mRoof = flat(C.slate);
  function towerAt(x: number, z: number, r: number, h: number) {
    const g = new THREE.Group();
    const body = new THREE.Mesh(new THREE.CylinderGeometry(r, r * 1.05, h, 8), mStone); body.position.y = h / 2; g.add(body);
    const roof = new THREE.Mesh(new THREE.ConeGeometry(r * 1.25, h * 0.7, 8), mRoof); roof.position.y = h + h * 0.35; g.add(roof);
    for (let i = 0; i < 3; i++) { const w = box(0.12, 0.3, 0.05, flat(0x3a3328)); const a = i * 2.1; w.position.set(Math.cos(a) * r, h * 0.65, Math.sin(a) * r); w.lookAt(0, h * 0.65, 0); g.add(w); }
    g.position.set(x, 1.6, z); shadowAll(g); return g;
  }
  function wallRing(R: number, h: number, nT: number, z0: number) {
    const g = new THREE.Group();
    for (let i = 0; i < nT; i++) {
      const a = (i / nT) * Math.PI * 2, b = ((i + 1) / nT) * Math.PI * 2;
      const A = V(Math.cos(a) * R, 0, Math.sin(a) * R * 0.75), B = V(Math.cos(b) * R, 0, Math.sin(b) * R * 0.75);
      const len = A.distanceTo(B), wall = box(len, h, 0.5, mDark);
      wall.position.set((A.x + B.x) / 2, 1.6 + h / 2, (A.z + B.z) / 2 + z0); wall.rotation.y = -Math.atan2(B.z - A.z, B.x - A.x); g.add(wall);
      for (let c = 0; c < Math.floor(len / 0.5); c++) {
        const m = box(0.25, 0.25, 0.52, mDark), f = -len / 2 + 0.25 + c * 0.5;
        m.position.set(wall.position.x + Math.cos(-wall.rotation.y) * f, 1.6 + h + 0.12, wall.position.z + Math.sin(-wall.rotation.y) * f);
        m.rotation.y = wall.rotation.y; g.add(m);
      }
      g.add(towerAt(A.x, A.z + z0, 0.7, h + 1.4));
    }
    shadowAll(g); return g;
  }
  s.add(wallRing(7.5, 1.6, 12, -6), wallRing(5, 2.4, 9, -6));
  s.add(towerAt(0, -7, 1.3, 5.5), towerAt(-1.8, -6, 0.8, 4.2), towerAt(1.9, -5.6, 0.9, 4.6));
  const keep = box(3, 3, 2, mStone); keep.position.set(0, 3.1, -5.2); keep.castShadow = true; s.add(keep);
  const gate = box(1.4, 1.6, 0.6, flat(0x3a3328)); gate.position.set(0, 2.3, -0.4); s.add(gate);
  const path = box(1.6, 0.04, 14, flat(0xd8c49c)); path.position.set(0, 0.03, 6); path.receiveShadow = true; s.add(path);
  for (let i = 0; i < 18; i++) { const tr = tree(1.1 + Math.random() * 0.6, 2); tr.position.set((Math.random() < 0.5 ? -1 : 1) * (12 + Math.random() * 20), 0, -20 + Math.random() * 35); s.add(tr); }
  const group = [person({ top: C.navy, bottom: 0x2d3a55, glasses: true, curly: true })];
  const tops = [C.red, C.yellow, 0x3fa7d6, 0x8fd16a, 0xff8a5b, 0x9b7bff];
  for (let i = 0; i < 6; i++) group.push(person({ kid: true, top: tops[i], hair: C.hairKid[i % 4], skin: i === 2 ? C.skinDark : C.skin, bag: tops[(i + 3) % 6] }));
  const spots = [[0, 0], [-0.8, 0.6], [0.8, 0.7], [-0.4, 1.4], [0.5, 1.6], [-1.2, 1.6], [1.3, 1.5]];
  group.forEach((p) => { p.g.rotation.y = Math.PI; s.add(p.g); });
  SCENES.ville = {
    scene: s,
    update(t: number) {
      const walk = Math.min(t, 7), z = 11 - walk * 0.9;
      group.forEach((p, i) => {
        p.g.position.set(spots[i][0], 0.04, z + spots[i][1]);
        p.walk(t, t < 7 ? 1 : 0);
        if (i === 2 && t > 7) p.point(t);
      });
      // De dos, au ras du chemin, puis grande grue qui découvre toute la Cité
      const k = easeIO(Math.min(t, 10) / 10);
      const p = V(Math.sin(k * 1.2) * 6, 1.2 + k * 9, z + 4.5 + k * 9);
      if (t > 10) { const a = (t - 10) * 0.04; p.x = Math.sin(1.2 + a) * 6; }
      camera.position.copy(p);
      camera.lookAt(0, 2.2 + k * 0.6, -4 + (1 - k) * 8);
    },
  };
}

let current: string | null = null, start = 0, raf = 0;
function frame(now: number) {
  raf = requestAnimationFrame(frame);
  if (!current) return;
  const t = Math.max(0, (now - start) / 1000);
  SCENES[current].update(t);
  renderer.render(SCENES[current].scene, camera);
}
export const DeckStory = {
  play(slide: HTMLElement, name: string, delayMs = 0) {
    this.stop();
    slide.querySelector(".stage3d")?.append(renderer.domElement);
    current = name; start = performance.now() + delayMs;
    raf = requestAnimationFrame(frame);
  },
  stop(slide?: HTMLElement) {
    if (slide && !slide.contains(renderer.domElement)) return;
    cancelAnimationFrame(raf); current = null;
  },
};
// Préchauffage hors écran : une scène par tâche, quand le navigateur souffle
const idle = (f: () => void) => ("requestIdleCallback" in window ? requestIdleCallback(f, { timeout: 2000 }) : setTimeout(f, 300));
Object.keys(SCENES).forEach((name) => idle(() => {
  if (current) return;
  SCENES[name].update(0);
  renderer.render(SCENES[name].scene, camera);
}));
