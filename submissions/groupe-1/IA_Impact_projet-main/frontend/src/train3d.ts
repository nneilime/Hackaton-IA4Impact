// Petit TER liO en 3D pour la simulation : deux voitures en primitives three.js (aucun fichier à charger),
// rendues dans un canvas transparent posé sur la carte comme marqueur HTML. Animé à chaque image :
// roues qui tournent, caisse qui roule et tangue en marche, phares qui pulsent, petit saut à l'arrivée.
// À l'arrivée, une contrôleuse low poly surgit sur la gare et agite un voyant vert et un voyant rouge,
// entourée de petites fleurs d'oranger kawaii qui tournent autour d'elle.
// Le point du marqueur est le nez du train (pas son centre) : à l'arrivée il s'arrête juste devant elle.
// Rame articulée : chaque voiture est posée par ses deux bogies sur le tracé déjà parcouru (fourni en pixels
// écran par la carte), la seconde est attelée à la première ; les bogies pivotent sous la caisse.
import * as THREE from "three";

const NAVY = 0x0f2149, RED = 0xc90c0f, WHITE = 0xf4f5f8, DARK = 0x1a1f2e, YELLOW = 0xffd500;

export type TrainMode = "moving" | "stopped" | "arrived";

export type Train3D = {
  el: HTMLElement;
  // Tracé derrière le nez, en pixels écran relatifs au point du marqueur, du nez vers l'arrière
  setTrack(points: [number, number][]): void;
  setMode(mode: TrainMode, speed: number): void;
  // Taille affichée (1 = pleine taille) : la carte la réduit quand on dézoome
  setScale(scale: number): void;
  frame(now: number): void;
  // Le point écran (clientX, clientY) touche-t-il la rame ?
  hit(x: number, y: number): boolean;
  // Porte flottante au-dessus de la voiture de tête : un clic dessus appelle onDoor
  showDoor(on: boolean): void;
  onDoor: (() => void) | null;
  dispose(): void;
};

// Canvas assez grand pour la rame entière derrière le nez, dans n'importe quel cap. L'objectif est ouvert
// en proportion pour garder la même échelle à l'écran qu'avec l'ancien canvas de 140 px de haut.
const W = 400, H = 400;
const FOV = (2 * Math.atan(Math.tan((15 * Math.PI) / 180) * (H / 140)) * 180) / Math.PI;

// Contrôleuse liO : tailleur marine cintré à boutons dorés, foulard rouge noué, casquette à galon et insigne,
// cheveux blonds avec frange, mèches et queue de cheval, un voyant dans chaque main (boîtier, lentille, halo).
// Même principe que la rame (primitives, aucun fichier) mais en rondeurs lisses pour qu'elle se lise de près.
// Pieds à y = 0, regard vers +z ; les deux bras pivotent à l'épaule.
function buildConductor(glowTex: THREE.Texture) {
  const std = (color: number, roughness = 0.6, metalness = 0) => new THREE.MeshStandardMaterial({ color, roughness, metalness });
  const m = {
    jacket: std(0x14285c, 0.7), skirt: std(NAVY, 0.75), red: std(RED, 0.55), white: std(WHITE, 0.5),
    gold: std(0xd9b24c, 0.3, 0.8), skin: std(0xf3cdb0, 0.65), tights: std(0x2b2f3d, 0.5), shoe: std(0x111318, 0.25, 0.2),
    hair: std(0xf5d26a, 0.45), hairDark: std(0xdcae45, 0.5), iris: std(0x2e5fa8, 0.3), pupil: std(0x0d0f16, 0.3),
    lips: std(0xd35a6a, 0.45), brow: std(0xb98a35, 0.6), visor: std(0x0b0d14, 0.2, 0.3), chrome: std(0xc9ced8, 0.25, 0.9),
    blush: new THREE.MeshBasicMaterial({ color: 0xf08b8b, transparent: true, opacity: 0.35, depthWrite: false }),
  };
  const part = (geo: THREE.BufferGeometry, mt: THREE.Material, x: number, y: number, z: number, parent: THREE.Object3D) => {
    const o = new THREE.Mesh(geo, mt);
    o.position.set(x, y, z);
    parent.add(o);
    return o;
  };
  const ball = (r: number, mt: THREE.Material, x: number, y: number, z: number, parent: THREE.Object3D, sx = 1, sy = 1, sz = 1) => {
    const o = part(new THREE.SphereGeometry(r, 16, 12), mt, x, y, z, parent);
    o.scale.set(sx, sy, sz);
    return o;
  };
  const body = new THREE.Group();

  // Jambes en collant sombre, escarpins vernis à petit talon
  for (const x of [-0.04, 0.04]) {
    part(new THREE.CylinderGeometry(0.025, 0.019, 0.16, 14), m.tights, x, 0.09, 0, body);
    ball(0.026, m.shoe, x, 0.016, 0.014, body, 0.95, 0.6, 1.6);
    part(new THREE.CylinderGeometry(0.008, 0.006, 0.02, 8), m.shoe, x, 0.01, -0.018, body);
  }
  // Jupe crayon avec liseré rouge à l'ourlet
  part(new THREE.CylinderGeometry(0.066, 0.086, 0.12, 24), m.skirt, 0, 0.205, 0, body).scale.z = 0.82;
  part(new THREE.CylinderGeometry(0.087, 0.087, 0.008, 24), m.red, 0, 0.148, 0, body).scale.z = 0.82;
  // Veste cintrée (profil tourné), un peu aplatie d'avant en arrière
  const jacketProfile = [[0.001, 0.24], [0.074, 0.24], [0.068, 0.27], [0.064, 0.29], [0.072, 0.33], [0.084, 0.37], [0.088, 0.395], [0.072, 0.418], [0.034, 0.43], [0.001, 0.432]]
    .map(([r, y]) => new THREE.Vector2(r, y));
  part(new THREE.LatheGeometry(jacketProfile, 24), m.jacket, 0, 0, 0, body).scale.z = 0.8;
  // Basque de la veste qui s'évase sur les hanches
  part(new THREE.CylinderGeometry(0.07, 0.082, 0.035, 24, 1, true), m.jacket, 0, 0.235, 0, body).scale.z = 0.82;
  // Ceinture et boucle dorée
  part(new THREE.CylinderGeometry(0.066, 0.066, 0.014, 24), m.skirt, 0, 0.285, 0, body).scale.z = 0.82;
  part(new THREE.BoxGeometry(0.022, 0.016, 0.006), m.gold, 0, 0.285, 0.055, body);
  // Chemise blanche dans l'encolure, revers, boutons dorés
  const shirt = new THREE.Shape([new THREE.Vector2(-0.03, 0.43), new THREE.Vector2(0.03, 0.43), new THREE.Vector2(0, 0.355)]);
  part(new THREE.ShapeGeometry(shirt), m.white, 0, 0, 0.0645, body);
  for (const s of [-1, 1]) {
    const lapel = part(new THREE.BoxGeometry(0.014, 0.075, 0.006), m.jacket, s * 0.022, 0.39, 0.067, body);
    lapel.rotation.z = s * 0.38;
    lapel.rotation.x = -0.12;
  }
  for (const y of [0.3, 0.33, 0.355]) ball(0.0055, m.gold, 0, y, 0.0575 + (y - 0.3) * 0.15, body, 1, 1, 0.6);
  // Poche de poitrine et badge
  part(new THREE.BoxGeometry(0.024, 0.004, 0.004), m.gold, -0.04, 0.37, 0.066, body).rotation.y = -0.3;
  // Foulard rouge noué, deux pans
  ball(0.012, m.red, 0, 0.415, 0.062, body, 1.2, 0.9, 0.8);
  for (const s of [-1, 1]) {
    const tail = part(new THREE.ConeGeometry(0.011, 0.04, 10), m.red, s * 0.01, 0.392, 0.064, body);
    tail.rotation.set(Math.PI, 0, s * 0.35);
  }
  // Épaulettes à galon doré
  for (const s of [-1, 1]) {
    part(new THREE.BoxGeometry(0.04, 0.008, 0.03), m.jacket, s * 0.072, 0.418, 0, body).rotation.z = s * -0.25;
    part(new THREE.BoxGeometry(0.006, 0.009, 0.031), m.gold, s * 0.088, 0.414, 0, body).rotation.z = s * -0.25;
  }
  part(new THREE.CylinderGeometry(0.024, 0.028, 0.045, 14), m.skin, 0, 0.445, 0, body); // cou

  // Tête : visage, yeux qui clignent, sourcils, nez, bouche, joues roses, oreilles
  const head = new THREE.Group();
  head.position.y = 0.515;
  body.add(head);
  ball(0.074, m.skin, 0, 0, 0, head, 1, 1.08, 0.96);
  ball(0.04, m.skin, 0, -0.035, 0.022, head, 1.1, 0.8, 1); // menton plus doux
  const eyes: THREE.Object3D[] = [];
  for (const s of [-1, 1]) {
    const eye = new THREE.Group();
    eye.position.set(s * 0.026, 0.006, 0.064);
    head.add(eye);
    ball(0.013, m.white, 0, 0, 0, eye, 1.15, 1.2, 0.5);
    ball(0.0085, m.iris, 0, -0.001, 0.005, eye, 1, 1.1, 0.5);
    ball(0.0045, m.pupil, 0, -0.001, 0.0085, eye, 1, 1.1, 0.5);
    ball(0.0022, m.white, s * -0.003, 0.003, 0.011, eye);
    eyes.push(eye);
    const brow = part(new THREE.CapsuleGeometry(0.003, 0.022, 4, 8), m.brow, s * 0.027, 0.03, 0.066, head);
    brow.rotation.z = Math.PI / 2 + s * 0.15;
    const cheek = part(new THREE.CircleGeometry(0.011, 16), m.blush, s * 0.042, -0.018, 0.0625, head);
    cheek.rotation.y = s * 0.45;
    ball(0.012, m.skin, s * 0.072, 0.0, -0.004, head, 0.5, 1, 0.8); // oreille
    ball(0.004, m.gold, s * 0.073, -0.014, 0.002, head); // boucle d'oreille
  }
  ball(0.008, m.skin, 0, -0.012, 0.072, head, 0.9, 1.1, 1);
  ball(0.011, m.lips, 0, -0.037, 0.066, head, 1.4, 0.45, 0.6);

  // Cheveux : calotte, frange en mèches, longues mèches qui encadrent le visage, queue de cheval en chapelet
  const cap = ball(0.081, m.hair, 0, 0.008, -0.01, head, 1.04, 1.06, 1.02);
  cap.geometry.dispose();
  cap.geometry = new THREE.SphereGeometry(0.081, 24, 16, 0, Math.PI * 2, 0, Math.PI * 0.6);
  cap.rotation.x = -0.6;
  for (let i = -2; i <= 2; i++) {
    const a = i * 0.32;
    const fringe = ball(0.022, i % 2 ? m.hairDark : m.hair, Math.sin(a) * 0.06, 0.045 - Math.abs(i) * 0.005, Math.cos(a) * 0.058, head, 0.9, 1.4, 0.55);
    fringe.rotation.set(-0.5, a, -i * 0.18);
  }
  for (const s of [-1, 1]) {
    const lock = ball(0.02, m.hair, s * 0.068, -0.03, 0.016, head, 0.8, 2.6, 0.9);
    lock.rotation.z = s * 0.12;
    ball(0.016, m.hairDark, s * 0.072, -0.012, -0.02, head, 0.9, 2.2, 1.2);
  }
  ball(0.07, m.hair, 0, -0.012, -0.03, head, 1, 1.05, 0.9); // arrière de la tête
  part(new THREE.TorusGeometry(0.016, 0.0055, 8, 16), m.red, 0, 0.018, -0.096, head);
  const pony: [number, number, number, number][] = [[0.024, 0.01, -0.112], [0.022, -0.02, -0.122], [0.019, -0.05, -0.124], [0.015, -0.078, -0.118], [0.01, -0.1, -0.108]]
    .map(([r, y, z], i) => [r, y, z, i]);
  for (const [r, y, z, i] of pony) ball(r, i % 2 ? m.hairDark : m.hair, 0, y, z, head, 1, 1.35, 1);

  // Casquette SNCF : calot évasé, bandeau rouge, galon et insigne dorés, visière vernie
  const kepi = new THREE.Group();
  kepi.position.set(0, 0.07, 0.004);
  kepi.rotation.x = -0.14;
  head.add(kepi);
  part(new THREE.CylinderGeometry(0.08, 0.071, 0.042, 28), m.jacket, 0, 0.014, 0, kepi);
  part(new THREE.CylinderGeometry(0.0805, 0.0805, 0.004, 28), m.jacket, 0, 0.036, 0, kepi);
  part(new THREE.CylinderGeometry(0.0725, 0.0725, 0.014, 28), m.red, 0, -0.004, 0, kepi);
  part(new THREE.TorusGeometry(0.0728, 0.0018, 6, 32), m.gold, 0, 0.004, 0, kepi).rotation.x = Math.PI / 2;
  const badge = part(new THREE.CylinderGeometry(0.011, 0.011, 0.004, 20), m.gold, 0, 0.016, 0.077, kepi);
  badge.rotation.x = Math.PI / 2 - 0.1;
  const visor = part(new THREE.CylinderGeometry(0.076, 0.076, 0.005, 28, 1, false, -Math.PI / 2, Math.PI), m.visor, 0, -0.011, 0.012, kepi);
  visor.scale.z = 0.95;
  visor.rotation.x = 0.22;

  // Bras articulés (épaule, coude, poignet à galon) + voyant : manche, boîtier, lentille, bague chromée, halo
  const lamps: { lamp: THREE.MeshBasicMaterial; glow: THREE.SpriteMaterial; color: THREE.Color }[] = [];
  const arm = (side: 1 | -1, color: number) => {
    const pivot = new THREE.Group();
    pivot.position.set(side * 0.09, 0.405, 0);
    body.add(pivot);
    ball(0.026, m.jacket, 0, 0, 0, pivot);
    part(new THREE.CylinderGeometry(0.024, 0.021, 0.08, 14), m.jacket, 0, -0.042, 0, pivot);
    ball(0.021, m.jacket, 0, -0.083, 0, pivot);
    part(new THREE.CylinderGeometry(0.021, 0.018, 0.065, 14), m.jacket, 0, -0.115, 0, pivot);
    part(new THREE.CylinderGeometry(0.0195, 0.0195, 0.008, 14), m.red, 0, -0.143, 0, pivot);
    part(new THREE.TorusGeometry(0.0195, 0.0014, 6, 20), m.gold, 0, -0.139, 0, pivot).rotation.x = Math.PI / 2;
    ball(0.019, m.skin, 0, -0.163, 0.002, pivot, 1, 1.15, 0.85);
    ball(0.008, m.skin, -side * 0.014, -0.158, 0.01, pivot, 1, 1.6, 1); // pouce
    part(new THREE.CylinderGeometry(0.0065, 0.0065, 0.08, 10), m.visor, 0, -0.2, 0.004, pivot);
    const lampHead = new THREE.Group();
    lampHead.position.set(0, -0.255, 0.006);
    pivot.add(lampHead);
    const housing = part(new THREE.CylinderGeometry(0.05, 0.046, 0.026, 28), m.visor, 0, 0, -0.004, lampHead);
    housing.rotation.x = Math.PI / 2;
    const lampMat = new THREE.MeshBasicMaterial({ color });
    const lens = part(new THREE.SphereGeometry(0.043, 28, 10, 0, Math.PI * 2, 0, Math.PI * 0.32), lampMat, 0, 0, -0.03, lampHead);
    lens.rotation.x = Math.PI / 2;
    const ring = part(new THREE.TorusGeometry(0.046, 0.005, 10, 32), m.chrome, 0, 0, 0.011, lampHead);
    ring.scale.z = 0.8;
    const glowMat = new THREE.SpriteMaterial({ map: glowTex, color, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
    const glow = new THREE.Sprite(glowMat);
    glow.position.set(0, 0, 0.03);
    glow.scale.setScalar(0.3);
    lampHead.add(glow);
    lamps.push({ lamp: lampMat, glow: glowMat, color: new THREE.Color(color) });
    return pivot;
  };
  const armR = arm(1, 0x2ee86a), armL = arm(-1, 0xff3030);

  // Fleurs d'oranger kawaii : cinq pétales ronds crème, cœur orangé avec deux yeux et des joues roses,
  // deux feuilles. Une couronne de sept tourne et flotte autour d'elle, une huitième est piquée dans ses cheveux.
  // Disques dans le plan xy (face +z), donc tournés vers la caméra grâce à la bascule du corps.
  const fm = {
    petal: std(0xfffaf0, 0.55), petalTip: std(0xffe3e8, 0.55), heart: std(0xffa630, 0.45),
    leaf: std(0x4caf50, 0.55), eye: std(0x2a1a12, 0.3),
    cheek: new THREE.MeshBasicMaterial({ color: 0xff7a9a, transparent: true, opacity: 0.6, depthWrite: false }),
  };
  const blossom = (parent: THREE.Object3D, size: number) => {
    const f = new THREE.Group();
    f.scale.setScalar(size);
    parent.add(f);
    for (let i = 0; i < 5; i++) {
      const a = (i / 5) * Math.PI * 2 + Math.PI / 2;
      ball(0.017, fm.petal, Math.cos(a) * 0.02, Math.sin(a) * 0.02, 0, f, 1, 1, 0.35);
      ball(0.006, fm.petalTip, Math.cos(a) * 0.031, Math.sin(a) * 0.031, 0.002, f, 1, 1, 0.3);
    }
    ball(0.014, fm.heart, 0, 0, 0.006, f, 1, 1, 0.6);
    for (const s of [-1, 1]) {
      ball(0.0026, fm.eye, s * 0.0055, 0.002, 0.0145, f, 1, 1.3, 0.5);
      part(new THREE.CircleGeometry(0.0028, 12), fm.cheek, s * 0.0095, -0.0035, 0.0142, f);
      const leaf = ball(0.012, fm.leaf, s * 0.03, -0.024, -0.004, f, 0.5, 1.2, 0.3);
      leaf.rotation.z = s * 0.9;
    }
    return f;
  };
  const blossoms = Array.from({ length: 7 }, (_, i) => ({ f: blossom(body, 1.15 + (i % 3) * 0.25), a: (i / 7) * Math.PI * 2, h: 0.12 + ((i * 3) % 7) * 0.065 }));
  const hairFlower = blossom(head, 0.95);
  hairFlower.position.set(-0.07, 0.055, 0.05);
  hairFlower.rotation.set(-0.2, -0.5, 0.3);

  // Basculée en arrière, face levée vers la caméra plongeante : sans ça on ne verrait que le dessus de la casquette
  const lean = new THREE.Group();
  lean.rotation.x = -0.75;
  lean.add(body);
  const g = new THREE.Group();
  g.add(lean);

  return {
    g,
    animate(t: number) {
      // Bras levés en alternance, voyants qui clignotent en opposition, clin d'yeux toutes les ~3 s
      const w = Math.sin(t * 5.5);
      armR.rotation.z = 2.25 + 0.5 * w;
      armL.rotation.z = -(2.25 - 0.5 * w);
      armR.rotation.x = armL.rotation.x = -0.25;
      body.position.y = 0.012 * Math.abs(Math.sin(t * 5.5));
      head.rotation.z = 0.1 * w;
      const blink = (t % 3.2) < 0.12 ? 0.15 : 1;
      for (const e of eyes) e.scale.y = blink;
      // Fleurs : orbite lente, petit flottement, rotation sur elles-mêmes ; celles de derrière passent sous le corps
      blossoms.forEach(({ f, a, h }, i) => {
        const o = a + t * 0.7;
        f.position.set(Math.cos(o) * 0.2, h + 0.015 * Math.sin(t * 2.4 + i), Math.sin(o) * 0.11);
        f.rotation.z = t * 0.9 + i;
      });
      lamps.forEach(({ lamp, glow, color }, i) => {
        const k = 0.5 + 0.5 * (i ? -w : w);
        lamp.color.copy(color).multiplyScalar(0.55 + 0.45 * k);
        glow.opacity = 0.35 + 0.65 * k;
      });
    },
  };
}

// `scale` réduit la rame à l'écran (téléphone, dézoom) : la scène reste la même, seul le canvas affiché rétrécit
export function createTrain3D(scale = 1, doorLabel = ""): Train3D {
  const el = document.createElement("div");
  el.className = "train-3d";
  const resize = () => {
    el.style.width = `${W * scale}px`;
    el.style.height = `${H * scale}px`;
  };
  resize();
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio));
  renderer.setSize(W, H, false);
  renderer.domElement.style.width = renderer.domElement.style.height = "100%";
  el.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(FOV, W / H, 0.1, 50);
  camera.position.set(0, 6.2, 4.4);
  camera.lookAt(0, 0.1, 0);
  camera.updateMatrixWorld(); // le tracé est projeté au sol avant le premier rendu
  // Deux scènes : la rame, puis la contrôleuse dessinée par-dessus (sinon la rame la cache quand elle arrive
  // du bas de l'écran)
  const front = new THREE.Scene();
  for (const sc of [scene, front]) {
    sc.add(new THREE.HemisphereLight(0xffffff, 0x8090b0, 1.6));
    const sun = new THREE.DirectionalLight(0xffffff, 1.8);
    sun.position.set(3, 6, 4);
    sc.add(sun);
  }
  renderer.autoClear = false;

  const mat = (color: number, extra: THREE.MeshStandardMaterialParameters = {}) =>
    new THREE.MeshStandardMaterial({ color, roughness: 0.55, metalness: 0.05, ...extra });
  const mats = {
    body: mat(RED), navy: mat(NAVY), white: mat(WHITE), roof: mat(0xa30a0c, { roughness: 0.7 }),
    glass: mat(DARK, { roughness: 0.15, metalness: 0.3 }), wheel: mat(0x2a2f3a, { metalness: 0.5 }),
    outline: new THREE.MeshBasicMaterial({ color: 0xffffff, side: THREE.BackSide }),
    head: new THREE.MeshBasicMaterial({ color: YELLOW }), tail: new THREE.MeshBasicMaterial({ color: RED }),
  };

  // Profil d'une voiture vu de côté (longueur x hauteur), nez profilé vers +x, extrudé sur la largeur
  const LEN = 1.9, HGT = 0.62, WID = 0.62;
  const profile = new THREE.Shape();
  profile.moveTo(0, 0.08);
  profile.lineTo(LEN - 0.35, 0.08);
  profile.quadraticCurveTo(LEN, 0.1, LEN, 0.3);
  profile.lineTo(LEN - 0.32, HGT);
  profile.lineTo(0, HGT);
  profile.closePath();
  const bodyGeo = new THREE.ExtrudeGeometry(profile, { depth: WID, bevelEnabled: true, bevelSize: 0.03, bevelThickness: 0.03, bevelSegments: 2 });
  bodyGeo.translate(0, 0, -WID / 2);

  const wheels: { w: THREE.Mesh; dir: number }[] = [];
  const wheelGeo = new THREE.CylinderGeometry(0.11, 0.11, 0.06, 14);
  wheelGeo.rotateX(Math.PI / 2);
  const box = (w: number, h: number, d: number, m: THREE.Material, x: number, y: number, z: number) => {
    const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
    b.position.set(x, y, z);
    return b;
  };

  // Une voiture motrice, nez vers +x ; la seconde est la même retournée (rame réversible comme un Régiolis)
  function car(lead: boolean) {
    const g = new THREE.Group();
    const caisse = new THREE.Group();
    caisse.add(new THREE.Mesh(bodyGeo, mats.body));
    // Liseré blanc (coque inversée, un peu plus grande) : la rame rouge ressort sur la ligne rouge du trajet
    const outline = new THREE.Mesh(bodyGeo, mats.outline);
    outline.scale.set(1.035, 1.07, 1.1);
    outline.position.set(-0.03, -0.02, 0);
    caisse.add(outline);
    caisse.add(box(LEN - 0.2, 0.1, WID + 0.07, mats.navy, (LEN - 0.2) / 2, 0.14, 0)); // jupe marine
    caisse.add(box(LEN - 0.45, 0.05, WID + 0.075, mats.white, (LEN - 0.45) / 2 + 0.02, 0.26, 0)); // filet blanc
    caisse.add(box(LEN - 0.6, 0.14, WID + 0.07, mats.glass, (LEN - 0.6) / 2 + 0.05, 0.43, 0)); // bandeau de baies
    caisse.add(box(LEN - 0.38, 0.05, WID - 0.1, mats.roof, (LEN - 0.38) / 2, HGT + 0.05, 0)); // toit
    // Nez : pare-brise et masque marine (sur une caisse rouge, comme les rames liO)
    const screen = box(0.05, 0.2, WID - 0.06, mats.glass, LEN - 0.17, 0.48, 0);
    screen.rotation.z = Math.atan2(HGT - 0.3, 0.32);
    caisse.add(screen);
    caisse.add(box(0.06, 0.16, WID - 0.02, mats.navy, LEN - 0.02, 0.2, 0));
    const lights = new THREE.SphereGeometry(0.04, 8, 6);
    for (const z of [-0.2, 0.2]) {
      const l = new THREE.Mesh(lights, lead ? mats.head : mats.tail);
      l.position.set(LEN + 0.01, 0.3, z);
      caisse.add(l);
    }
    g.add(caisse);
    // Bogies et roues, chacun sur son pivot pour suivre la courbe sous la caisse ([avant, arrière] côté nez)
    const bogies = [LEN - 0.5, 0.38].map((x) => {
      const b = new THREE.Group();
      b.position.x = x;
      b.add(box(0.5, 0.08, WID - 0.12, mats.wheel, 0, 0.06, 0));
      for (const dx of [-0.15, 0.15])
        for (const z of [-(WID / 2 - 0.02), WID / 2 - 0.02]) {
          const w = new THREE.Mesh(wheelGeo, mats.wheel);
          w.position.set(dx, 0.06, z);
          b.add(w);
          wheels.push({ w, dir: lead ? 1 : -1 });
        }
      g.add(b);
      return b;
    });
    // Pivot au milieu des bogies, +x vers l'avant de la rame : la motrice de tête a le nez devant,
    // la seconde est retournée (nez vers l'arrière, attelage devant)
    const pivot = new THREE.Group();
    const mid = (LEN - 0.5 + 0.38) / 2;
    if (lead) g.position.x = -mid;
    else {
      g.rotation.y = Math.PI;
      g.position.x = mid;
    }
    pivot.add(g);
    const shade = new THREE.Mesh(new THREE.PlaneGeometry(2.5, 1.5), shadowMat);
    shade.rotation.x = -Math.PI / 2;
    shade.position.y = 0.005 / S;
    shade.raycast = () => {}; // l'ombre au sol ne compte pas comme un clic sur le train
    pivot.add(shade);
    return { pivot, caisse, bogies: lead ? bogies : [bogies[1], bogies[0]] };
  }

  // Ombre portée douce
  const shadowTex = (() => {
    const c = document.createElement("canvas");
    c.width = c.height = 64;
    const x = c.getContext("2d")!;
    const grad = x.createRadialGradient(32, 32, 2, 32, 32, 32);
    grad.addColorStop(0, "rgba(15,33,73,.45)");
    grad.addColorStop(1, "rgba(15,33,73,0)");
    x.fillStyle = grad;
    x.fillRect(0, 0, 64, 64);
    return new THREE.CanvasTexture(c);
  })();
  const shadowMat = new THREE.MeshBasicMaterial({ map: shadowTex, transparent: true, depthWrite: false });

  const S = 0.92; // échelle de la rame
  const train = new THREE.Group();
  const lead = car(true), back = car(false);
  train.add(lead.pivot, back.pivot);
  // Soufflet entre les deux voitures, recentré et réorienté à chaque image sur l'attelage
  const gangway = box(0.12, 0.44, WID - 0.14, mats.wheel, 0, 0.36, 0);
  train.add(gangway);
  train.scale.setScalar(S);

  scene.add(train);

  // Abscisses le long du tracé (unités de scène, depuis le point suivi vers l'arrière). Le nez s'arrête
  // un peu avant le point suivi (la gare, à l'arrivée) ; la seconde voiture suit à 0,08 d'intervalle.
  const GAP = 0.4, MID = (LEN - 0.5 + 0.38) / 2, HALF = (LEN - 0.5 - 0.38) / 2; // centre des bogies, demi-empattement
  const LEAD_MID = GAP + S * (LEN - MID);
  const COUPLE = S * (MID + 0.04); // du centre d'une voiture au milieu de l'attelage
  const MAX_BEND = 0.75; // angle maximal entre les deux caisses : au-delà, la seconde quitte un peu la voie
  const MAX_BOGIE = 0.45;

  // Tracé au sol (x, z) : les pixels écran sont projetés sur le plan y = 0 vu par la caméra
  const ray = new THREE.Raycaster(), ground = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), hit = new THREE.Vector3();
  let path = [{ x: 0, z: 0 }, { x: -1, z: 0 }]; // en ligne droite vers la droite tant que la carte n'a rien dit
  const toGround = (dx: number, dy: number) => {
    ray.setFromCamera(new THREE.Vector2((2 * dx) / W, (-2 * dy) / H), camera);
    return ray.ray.intersectPlane(ground, hit) ? { x: hit.x, z: hit.z } : null;
  };
  // Point et tangente (vers l'avant) à l'abscisse s ; au-delà du tracé connu, on prolonge en ligne droite
  const at = (s: number) => {
    let acc = 0;
    let dir = { x: 1, z: 0 };
    for (let i = 0; i + 1 < path.length; i++) {
      const a = path[i], b = path[i + 1];
      const len = Math.hypot(b.x - a.x, b.z - a.z);
      if (len < 1e-6) continue;
      dir = { x: (a.x - b.x) / len, z: (a.z - b.z) / len };
      if (acc + len >= s) {
        const k = (s - acc) / len;
        return { x: a.x + (b.x - a.x) * k, z: a.z + (b.z - a.z) * k, dir };
      }
      acc += len;
    }
    const end = path[path.length - 1] ?? { x: 0, z: 0 };
    return { x: end.x - dir.x * (s - acc), z: end.z - dir.z * (s - acc), dir };
  };
  const yawOf = (d: { x: number; z: number }) => Math.atan2(-d.z, d.x);
  const wrap = (a: number) => Math.atan2(Math.sin(a), Math.cos(a));
  const clamp = (v: number, m: number) => Math.max(-m, Math.min(m, v));

  // Pose les deux voitures sur le tracé (coordonnées de scène, la rame est mise à l'échelle S)
  let leadYaw = 0, backYaw = 0;
  const place = (pivot: THREE.Object3D, x: number, z: number, yaw: number) => {
    pivot.position.set(x / S, 0, z / S);
    pivot.rotation.y = yaw;
  };
  const steer = (c: typeof lead, yaw: number, s: [number, number]) =>
    c.bogies.forEach((b, i) => (b.rotation.y = clamp(wrap(yawOf(at(s[i]).dir) - yaw), MAX_BOGIE)));
  function layout() {
    // Voiture de tête : ses deux bogies sur la voie, caisse le long de la corde
    const f = at(LEAD_MID - S * HALF), r = at(LEAD_MID + S * HALF);
    const dl = Math.hypot(f.x - r.x, f.z - r.z);
    leadYaw = dl > 1e-6 ? Math.atan2(-(f.z - r.z), f.x - r.x) : leadYaw;
    const lc = { x: (f.x + r.x) / 2, z: (f.z + r.z) / 2 };
    place(lead.pivot, lc.x, lc.z, leadYaw);
    steer(lead, leadYaw, [LEAD_MID - S * HALF, LEAD_MID + S * HALF]);
    // Attelage : point arrière de la tête ; la seconde voiture y est accrochée et vise son bogie arrière
    const ld = { x: Math.cos(leadYaw), z: -Math.sin(leadYaw) };
    const joint = { x: lc.x - ld.x * COUPLE, z: lc.z - ld.z * COUPLE };
    const BACK_MID = LEAD_MID + 2 * COUPLE;
    const br = at(BACK_MID + S * HALF);
    const jx = joint.x - ld.x * S * 0.04, jz = joint.z - ld.z * S * 0.04;
    const want = Math.atan2(-(jz - br.z), jx - br.x);
    backYaw = leadYaw + clamp(wrap(want - leadYaw), MAX_BEND);
    const bd = { x: Math.cos(backYaw), z: -Math.sin(backYaw) };
    place(back.pivot, joint.x - bd.x * COUPLE, joint.z - bd.z * COUPLE, backYaw);
    steer(back, backYaw, [BACK_MID - S * HALF, BACK_MID + S * HALF]);
    // Soufflet sur l'attelage, dans l'axe moyen
    const mid = wrap(backYaw - leadYaw) / 2 + leadYaw;
    gangway.position.set(joint.x / S, 0.36, joint.z / S);
    gangway.rotation.y = mid;
  }

  // Contrôleuse debout pile sur la gare (centre du canvas) ; cachée tant que le train n'est pas arrivé
  const glowTex = (() => {
    const c = document.createElement("canvas");
    c.width = c.height = 64;
    const x = c.getContext("2d")!;
    const grad = x.createRadialGradient(32, 32, 0, 32, 32, 32);
    grad.addColorStop(0, "rgba(255,255,255,1)");
    grad.addColorStop(0.35, "rgba(255,255,255,.45)");
    grad.addColorStop(1, "rgba(255,255,255,0)");
    x.fillStyle = grad;
    x.fillRect(0, 0, 64, 64);
    return new THREE.CanvasTexture(c);
  })();
  const conductor = buildConductor(glowTex);
  const conductorShadow = new THREE.Mesh(new THREE.PlaneGeometry(0.7, 0.45), shadowMat);
  conductorShadow.rotation.x = -Math.PI / 2;
  conductorShadow.position.y = 0.006;
  scene.add(conductorShadow);
  front.add(conductor.g);
  let show = 0;

  let mode: TrainMode = "stopped", speed = 1, last = 0, roll = 0, hop = 0, prevMode: TrainMode = "stopped";

  // Porte HTML (cliquable, le reste du canvas laisse passer la souris vers la carte), suit la voiture de tête
  const door = document.createElement("button");
  door.type = "button";
  door.className = "train-door";
  door.innerHTML = `<span class="train-door-frame"><span class="train-door-leaf"></span><span class="train-door-leaf"></span></span><span class="train-door-label"></span>`;
  door.querySelector(".train-door-label")!.textContent = doorLabel;
  door.setAttribute("aria-label", doorLabel);
  door.addEventListener("click", (e) => {
    e.stopPropagation();
    api.onDoor?.();
  });
  for (const ev of ["pointerdown", "mousedown", "touchstart", "dblclick"]) door.addEventListener(ev, (e) => e.stopPropagation());
  el.appendChild(door);
  let doorOn = false;
  const doorPoint = new THREE.Vector3();
  const placeDoor = () => {
    if (!doorOn) return;
    lead.caisse.localToWorld(doorPoint.set(LEN * 0.45, HGT + 0.5, 0));
    doorPoint.project(camera);
    door.style.left = `${((doorPoint.x + 1) / 2) * 100}%`;
    door.style.top = `${((1 - doorPoint.y) / 2) * 100}%`;
  };
  const pick = new THREE.Raycaster();

  const api: Train3D = {
    el,
    onDoor: null,
    hit(x, y) {
      const r = renderer.domElement.getBoundingClientRect();
      if (!r.width || x < r.left || x > r.right || y < r.top || y > r.bottom) return false;
      pick.setFromCamera(new THREE.Vector2(((x - r.left) / r.width) * 2 - 1, -((y - r.top) / r.height) * 2 + 1), camera);
      return pick.intersectObject(train, true).length > 0;
    },
    showDoor(on) {
      if (on === doorOn) return;
      doorOn = on;
      door.classList.toggle("is-on", on);
      placeDoor();
    },
    setTrack(points) {
      const next: { x: number; z: number }[] = [];
      for (const [dx, dy] of points) {
        const g = toGround(dx / scale, dy / scale); // pixels écran → pixels du canvas, plus grand qu'affiché
        if (!g) break;
        next.push(g);
      }
      if (next.length < 2) return; // tracé dégénéré (train immobile au départ) : on garde la pose précédente
      path = next;
    },
    setScale(k) {
      if (Math.abs(k - scale) < 0.005) return;
      scale = k;
      resize();
    },
    setMode(m, s) {
      if (m === "arrived" && prevMode !== "arrived") hop = 1;
      prevMode = mode = m;
      speed = s;
    },
    frame(now) {
      const dt = last ? Math.min(0.1, (now - last) / 1000) : 0;
      last = now;
      const t = now / 1000;
      layout();

      const moving = mode === "moving";
      roll += ((moving ? 1 : 0) - roll) * Math.min(1, dt * 4); // montée / descente en vitesse
      for (const { w, dir } of wheels) w.rotation.z -= dir * dt * roll * (6 + 4 * Math.min(speed, 4));
      // Caisses : tangage et roulis en marche, respiration légère à quai
      const sway = roll * 0.04 * Math.sin(t * 9), pitch = roll * 0.02 * Math.sin(t * 7 + 1);
      for (const [c, k] of [[lead.caisse, 0], [back.caisse, 1.3]] as const) {
        c.position.y = roll * 0.015 * Math.abs(Math.sin(t * 12 + k)) + (1 - roll) * 0.006 * Math.sin(t * 2 + k);
        c.rotation.x = sway * (k ? -1 : 1);
        c.rotation.z = pitch;
      }
      // Saut d'arrivée
      if (hop > 0) hop = Math.max(0, hop - dt * 1.6);
      train.position.y = Math.sin((1 - hop) * Math.PI * 2) * hop * 0.35;
      // Phares qui pulsent
      mats.head.color.setHex(YELLOW).multiplyScalar(0.75 + 0.25 * Math.sin(t * (moving ? 8 : 2.5)));
      // Contrôleuse : surgit avec un rebond à l'arrivée, rentre dès que le trajet repart
      const want = mode === "arrived" ? 1 : 0;
      show = want ? Math.min(1, show + dt * 2.2) : Math.max(0, show - dt * 5);
      conductor.g.visible = conductorShadow.visible = show > 0;
      if (show > 0) {
        const s = want ? 1 + 2.7 * (show - 1) ** 3 + 1.7 * (show - 1) ** 2 : show; // easeOutBack
        conductor.g.scale.setScalar(4.2 * Math.max(0.001, s));
        conductorShadow.scale.setScalar(2.2 * Math.max(0.001, s));
        conductor.animate(t);
      }
      renderer.clear();
      renderer.render(scene, camera);
      placeDoor();
      if (show > 0) {
        renderer.clearDepth();
        renderer.render(front, camera);
      }
    },
    dispose() {
      renderer.dispose();
      [scene, front].forEach((sc) => sc.traverse((o) => {
        if (o instanceof THREE.Mesh) {
          o.geometry.dispose();
          (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => m.dispose());
        } else if (o instanceof THREE.Sprite) o.material.dispose();
      }));
      shadowTex.dispose();
      glowTex.dispose();
      el.remove();
    },
  };
  return api;
}
