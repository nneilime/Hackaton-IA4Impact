// Le TER liO en 3D (rame réversible de n voitures), utilisé par les scènes 3D de la carte, les transitions et l'histoire low poly.
import * as THREE from "three";

const NAVY = 0x0f2149, RED = 0xc90c0f, YELLOW = 0xffd500, WHITE = 0xf4f5f8, GREY = 0xc9cdd8;
export const mat = (color: number, extra: THREE.MeshStandardMaterialParameters = {}) =>
  new THREE.MeshStandardMaterial({ color, roughness: 0.45, metalness: 0.1, ...extra });
export const MATS = {
  body: new THREE.MeshPhysicalMaterial({ color: RED, roughness: 0.32, metalness: 0.15, clearcoat: 0.8, clearcoatRoughness: 0.2 }),
  navy: mat(NAVY), white: mat(WHITE), yellow: mat(YELLOW, { roughness: 0.4 }), roof: mat(0x8f0a0c, { roughness: 0.6 }),
  grey: mat(GREY, { roughness: 0.5, metalness: 0.4 }),
  glass: new THREE.MeshPhysicalMaterial({ color: 0x0c1428, roughness: 0.05, metalness: 0.2, clearcoat: 1 }),
  wheel: mat(0x2a2f3a, { metalness: 0.6, roughness: 0.4 }),
  head: new THREE.MeshBasicMaterial({ color: 0xfff3b0 }), tail: new THREE.MeshBasicMaterial({ color: RED }),
};
const LEN = 2.1, HGT = 0.66, WID = 0.64;
const PROFILE = new THREE.Shape();
PROFILE.moveTo(0, 0.1); PROFILE.lineTo(LEN - 0.42, 0.1); PROFILE.quadraticCurveTo(LEN + 0.02, 0.12, LEN, 0.34);
PROFILE.quadraticCurveTo(LEN - 0.12, HGT - 0.02, LEN - 0.42, HGT); PROFILE.lineTo(0, HGT); PROFILE.closePath();
const BODY = new THREE.ExtrudeGeometry(PROFILE, { depth: WID, bevelEnabled: true, bevelSize: 0.035, bevelThickness: 0.035, bevelSegments: 3, curveSegments: 16 });
BODY.translate(0, 0, -WID / 2);
const WHEEL = new THREE.CylinderGeometry(0.11, 0.11, 0.05, 18); WHEEL.rotateX(Math.PI / 2);
const LAMP = new THREE.SphereGeometry(0.045, 10, 8);
export const box = (bw: number, bh: number, bd: number, m: THREE.Material, x: number, y: number, z: number) => {
  const b = new THREE.Mesh(new THREE.BoxGeometry(bw, bh, bd), m);
  b.position.set(x, y, z);
  return b;
};

export interface Train3D { train: THREE.Group; wheels: THREE.Mesh[]; caisses: THREE.Group[]; length: number }

export function buildTrain({ cars = 2 } = {}): Train3D {
  const wheels: THREE.Mesh[] = [], caisses: THREE.Group[] = [];
  function car(lead: boolean) {
    const g = new THREE.Group(), c = new THREE.Group();
    c.add(new THREE.Mesh(BODY, MATS.body));
    c.add(box(LEN - 0.25, 0.12, WID + 0.075, MATS.navy, (LEN - 0.25) / 2, 0.17, 0));       // jupe marine
    c.add(box(LEN - 0.5, 0.03, WID + 0.08, MATS.yellow, (LEN - 0.5) / 2 + 0.03, 0.255, 0)); // filet jaune
    c.add(box(LEN - 0.5, 0.025, WID + 0.08, MATS.white, (LEN - 0.5) / 2 + 0.03, 0.29, 0));  // filet blanc
    // Baies vitrées une à une, et deux portes par face
    for (let k = 0; k < 6; k++) {
      const x = 0.2 + k * 0.24;
      if (k === 1 || k === 4) {
        c.add(box(0.17, 0.36, WID + 0.08, MATS.grey, x, 0.47, 0));
        c.add(box(0.13, 0.15, WID + 0.085, MATS.glass, x, 0.53, 0));
      } else c.add(box(0.17, 0.15, WID + 0.075, MATS.glass, x, 0.5, 0));
    }
    c.add(box(LEN - 0.55, 0.05, WID - 0.12, MATS.roof, (LEN - 0.55) / 2, HGT + 0.055, 0));
    c.add(box(0.36, 0.08, WID - 0.26, MATS.grey, 0.5, HGT + 0.1, 0));                        // climatisation
    // Nez : grand pare-brise sombre, masque marine, phares et feux
    const screen = box(0.05, 0.26, WID - 0.04, MATS.glass, LEN - 0.21, 0.5, 0);
    screen.rotation.z = 0.62;
    c.add(screen, box(0.06, 0.13, WID - 0.02, MATS.navy, LEN - 0.005, 0.2, 0));
    for (const z of [-0.2, 0.2]) { const l = new THREE.Mesh(LAMP, lead ? MATS.head : MATS.tail); l.position.set(LEN + 0.012, 0.3, z); c.add(l); }
    if (lead) {
      const arm = (a: number) => { const s = box(0.38, 0.022, 0.022, MATS.navy, 1.1, HGT + 0.16, 0); s.rotation.z = a; return s; };
      c.add(arm(0.5), arm(-0.5), box(0.04, 0.02, 0.42, MATS.navy, 1.1, HGT + 0.24, 0));
    }
    g.add(c); caisses.push(c);
    for (const x of [0.42, LEN - 0.55]) {
      g.add(box(0.52, 0.09, WID - 0.1, MATS.wheel, x, 0.07, 0));
      for (const dx of [-0.16, 0.16]) for (const z of [-(WID / 2 - 0.03), WID / 2 - 0.03]) {
        const wh = new THREE.Mesh(WHEEL, MATS.wheel); wh.position.set(x + dx, 0.07, z); g.add(wh); wheels.push(wh);
      }
    }
    return g;
  }
  // Rame réversible : la motrice de tête regarde vers +x, les voitures suivantes sont retournées derrière elle
  const train = new THREE.Group();
  for (let i = 0; i < cars; i++) {
    const g = car(i === 0);
    if (i > 0) { g.rotation.y = Math.PI; g.position.x = -(i - 1) * (LEN + 0.12) - 0.06; train.add(box(0.14, 0.46, WID - 0.12, MATS.wheel, -(i - 1) * (LEN + 0.12), 0.38, 0)); }
    else g.position.x = 0.06;
    train.add(g);
  }
  train.traverse((o) => { if (o instanceof THREE.Mesh) o.castShadow = true; });
  return { train, wheels, caisses, length: cars * (LEN + 0.12) };
}
