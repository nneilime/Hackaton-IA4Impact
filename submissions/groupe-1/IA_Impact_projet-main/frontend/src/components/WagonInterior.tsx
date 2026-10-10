// Intérieur d'une voiture de TER liO en 3D, ouvert en plein écran quand on passe la porte du train sur la carte.
// Tout est en primitives three.js (aucun fichier) : sièges en vis-à-vis 2 + 2, porte-bagages, bandeaux lumineux,
// écran d'information qui annonce le prochain arrêt, barres de maintien aux plateformes. Dehors, la campagne
// d'Occitanie (champs, arbres, collines, poteaux caténaires) défile quand la simulation roule et s'arrête à quai.
// On regarde autour en glissant, on marche dans l'allée aux flèches, à la molette ou avec les deux boutons.
import { useEffect, useRef, type PointerEvent as RPointerEvent } from "react";
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import type { Place } from "../api";
import { useI18n } from "../i18n";
import type { SimState, TrainSim } from "../sim";

type Props = { sim: TrainSim; byId: Map<string, Place>; onClose: () => void };

const NAVY = 0x0f2149, RED = 0xc90c0f, WHITE = 0xf4f5f8, YELLOW = 0xffd500;
const L = 16, WID = 2.8, HGT = 2.3; // voiture : longueur (x), largeur (z), hauteur sous plafond
const WIN_LOW = 0.85, WIN_HIGH = 1.75, PITCH = 1.7; // baies vitrées, pas entre deux baies
const EYE = 1.6, END = L / 2 - 1.3; // hauteur des yeux debout, bout de l'allée
const SCENE_RANGE = 260; // profondeur du paysage qui défile (m de part et d'autre)
const FAR = 1200; // jusqu'où va le sol avant de se fondre dans le panorama
const SKY_TURN = 0; // rotation du panorama (rad) : les montagnes face aux fenêtres

export default function WagonInterior({ sim, byId, onClose }: Props) {
  const { t } = useI18n();
  const host = useRef<HTMLDivElement>(null);
  const walk = useRef(0); // -1, 0, 1 : boutons tenus
  const close = useRef(onClose);
  close.current = onClose;

  useEffect(() => {
    const el = host.current!;
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    el.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.add(new THREE.HemisphereLight(0xffffff, 0xd9d4cc, 1.5));
    const sun = new THREE.DirectionalLight(0xfff2dc, 1.6);
    sun.position.set(30, 60, 20);
    scene.add(sun);
    // Lumière de plafond : deux bandeaux, assez pour que l'intérieur ne soit pas plus sombre que dehors
    for (const x of [-L / 4, L / 4]) {
      const p = new THREE.PointLight(0xffffff, 3, 10, 1.4);
      p.position.set(x, HGT - 0.2, 0);
      scene.add(p);
    }

    const camera = new THREE.PerspectiveCamera(70, 1, 0.05, FAR * 1.5);
    const mat = (color: number, extra: THREE.MeshStandardMaterialParameters = {}) =>
      new THREE.MeshStandardMaterial({ color, roughness: 0.7, metalness: 0.02, ...extra });
    const m = {
      wall: mat(0xe8ebf1), panel: mat(0xd5dae4), floor: mat(0x3d4250, { roughness: 0.9 }), aisle: mat(0x2b2f3a, { roughness: 0.95 }),
      ceiling: mat(0xf3f5f9), light: new THREE.MeshBasicMaterial({ color: 0xffffff }),
      seat: mat(NAVY, { roughness: 0.95 }), seatRed: mat(RED, { roughness: 0.9 }), cover: mat(WHITE, { roughness: 0.85 }),
      plastic: mat(0x9aa2b2, { roughness: 0.5 }), chrome: mat(0xcfd4dc, { roughness: 0.25, metalness: 0.85 }),
      pole: mat(YELLOW, { roughness: 0.35, metalness: 0.2 }), red: mat(RED, { roughness: 0.6 }),
      glass: new THREE.MeshStandardMaterial({ color: 0xcfe6ff, transparent: true, opacity: 0.12, roughness: 0.05, metalness: 0.1, depthWrite: false }),
      rack: new THREE.MeshStandardMaterial({ color: 0xbfd2e6, transparent: true, opacity: 0.45, roughness: 0.2, depthWrite: false }),
      table: mat(0x6b7487, { roughness: 0.5 }),
    };
    const wagon = new THREE.Group();
    scene.add(wagon);
    // Tous les blocs ont les arêtes arrondies (bevel) : rayon proportionnel à la plus petite cote, plafonné à 4 cm ;
    // une géométrie par jeu de cotes, partagée (les poteaux, sièges, traverses reviennent des dizaines de fois)
    const geoCache = new Map<string, THREE.BufferGeometry>();
    const bevelBox = (w: number, h: number, d: number, maxR = 0.04) => {
      const key = `${w}|${h}|${d}|${maxR}`;
      let g = geoCache.get(key);
      if (!g) {
        const r = Math.min(maxR, Math.min(w, h, d) * 0.3);
        g = r < 0.004 ? new THREE.BoxGeometry(w, h, d) : new RoundedBoxGeometry(w, h, d, 2, r);
        geoCache.set(key, g);
      }
      return g;
    };
    const box = (w: number, h: number, d: number, mt: THREE.Material, x: number, y: number, z: number, parent: THREE.Object3D = wagon) => {
      const b = new THREE.Mesh(bevelBox(w, h, d), mt);
      b.position.set(x, y, z);
      parent.add(b);
      return b;
    };

    // Caisse : plancher, allée, plafond, bandeaux lumineux
    box(L, 0.05, WID, m.floor, 0, -0.025, 0);
    box(L, 0.006, 0.7, m.aisle, 0, 0.003, 0);
    box(L, 0.05, WID, m.ceiling, 0, HGT + 0.025, 0);
    for (const z of [-0.45, 0.45]) box(L - 1, 0.02, 0.16, m.light, 0, HGT - 0.01, z);
    // Corniches inclinées entre plafond et parois (la voûte d'un Régiolis)
    for (const s of [-1, 1]) {
      const c = box(L, 0.04, 0.55, m.ceiling, 0, HGT - 0.12, s * (WID / 2 - 0.22));
      c.rotation.x = s * 0.5;
    }

    // Parois : allège, bandeau haut, trumeaux entre les baies, vitrage ; liseré rouge sous les fenêtres
    const nWin = Math.floor((L - 2.6) / PITCH);
    const winW = PITCH - 0.32;
    const x0 = -((nWin - 1) * PITCH) / 2;
    for (const s of [-1, 1]) {
      const z = s * WID / 2;
      box(L, WIN_LOW, 0.06, m.panel, 0, WIN_LOW / 2, z);
      box(L, HGT - WIN_HIGH, 0.06, m.wall, 0, (HGT + WIN_HIGH) / 2, z);
      box(L, 0.04, 0.07, m.red, 0, WIN_LOW - 0.02, z - s * 0.005);
      // Trumeaux : bouts pleins (plateformes) + entre chaque baie
      const pierH = WIN_HIGH - WIN_LOW, pierY = (WIN_LOW + WIN_HIGH) / 2;
      const endW = L / 2 - (-x0 + winW / 2);
      for (const e of [-1, 1]) box(endW, pierH, 0.06, m.wall, e * (L / 2 - endW / 2), pierY, z);
      for (let i = 0; i + 1 < nWin; i++) box(PITCH - winW, pierH, 0.06, m.wall, x0 + (i + 0.5) * PITCH, pierY, z);
      for (let i = 0; i < nWin; i++) {
        const g = new THREE.Mesh(new THREE.PlaneGeometry(winW, pierH), m.glass);
        g.position.set(x0 + i * PITCH, pierY, z);
        g.rotation.y = s > 0 ? Math.PI : 0;
        wagon.add(g);
        // Encadrement arrondi suggéré par un joint gris
        box(winW + 0.04, 0.03, 0.08, m.plastic, x0 + i * PITCH, WIN_HIGH, z - s * 0.01);
        box(winW + 0.04, 0.03, 0.08, m.plastic, x0 + i * PITCH, WIN_LOW + 0.01, z - s * 0.03).scale.z = 2.2; // tablette
      }
      // Porte-bagages vitré sur toute la longueur des baies
      box(nWin * PITCH, 0.03, 0.42, m.rack, 0, 1.98, s * (WID / 2 - 0.24));
      box(nWin * PITCH, 0.03, 0.03, m.chrome, 0, 1.98, s * (WID / 2 - 0.45));
      for (let i = 0; i <= nWin; i++) {
        const b = box(0.03, 0.03, 0.45, m.chrome, x0 + (i - 0.5) * PITCH, 2.02, s * (WID / 2 - 0.22));
        b.rotation.x = s * -0.35;
      }
    }

    // Siège tourné vers +x (dossier en -x), posé au sol
    const seatGeo = {
      cushion: bevelBox(0.46, 0.12, 0.44, 0.05),
      back: bevelBox(0.1, 0.62, 0.44, 0.05),
      band: bevelBox(0.105, 0.08, 0.445),
      cover: bevelBox(0.11, 0.16, 0.34),
      leg: bevelBox(0.06, 0.38, 0.3),
    };
    const seat = (x: number, z: number, facing: 1 | -1) => {
      const g = new THREE.Group();
      g.position.set(x, 0, z);
      g.rotation.y = facing > 0 ? 0 : Math.PI;
      const add = (geo: THREE.BufferGeometry, mt: THREE.Material, px: number, py: number, rz = 0) => {
        const o = new THREE.Mesh(geo, mt);
        o.position.set(px, py, 0);
        o.rotation.z = rz;
        g.add(o);
      };
      add(seatGeo.leg, m.plastic, 0, 0.19);
      add(seatGeo.cushion, m.seat, 0.02, 0.44);
      add(seatGeo.back, m.seat, -0.22, 0.8, -0.12);
      add(seatGeo.band, m.seatRed, -0.205, 0.64, -0.12);
      add(seatGeo.cover, m.cover, -0.265, 1.05, -0.12);
      wagon.add(g);
    };
    // Vis-à-vis : deux rangs face à face par baie, tablette entre eux contre la paroi
    for (let i = 0; i < nWin; i++) {
      const cx = x0 + i * PITCH;
      for (const s of [-1, 1]) {
        for (const z of [0.58, 1.04]) {
          seat(cx - 0.62, s * z, 1);
          seat(cx + 0.62, s * z, -1);
        }
        box(0.5, 0.03, 0.34, m.table, cx, 0.74, s * (WID / 2 - 0.2));
        box(0.05, 0.7, 0.05, m.plastic, cx, 0.38, s * (WID / 2 - 0.12));
      }
    }

    // Plateformes : barres de maintien jaunes, cloison vitrée, porte d'intercirculation, écran d'information
    const poleGeo = new THREE.CylinderGeometry(0.02, 0.02, HGT, 12);
    for (const e of [-1, 1]) {
      for (const z of [-0.5, 0.5]) {
        const p = new THREE.Mesh(poleGeo, m.pole);
        p.position.set(e * (L / 2 - 0.9), HGT / 2, z);
        wagon.add(p);
      }
      const ex = e * (L / 2);
      for (const s of [-1, 1]) box(0.08, HGT, WID / 2 - 0.5, m.wall, ex, HGT / 2, s * (WID / 4 + 0.25));
      box(0.08, HGT - 2.0, 1.0, m.wall, ex, (HGT + 2.0) / 2, 0);
      // Porte vitrée coulissante, cadre rouge
      box(0.04, 1.95, 0.9, m.glass, ex - e * 0.02, 0.975, 0);
      for (const z of [-0.47, 0.47]) box(0.06, 2.0, 0.05, m.red, ex - e * 0.03, 1.0, z);
      box(0.06, 0.05, 0.98, m.red, ex - e * 0.03, 2.0, 0);
      box(1.2, 2.2, 1.3, m.aisle, ex + e * 0.65, 1.1, 0); // soufflet sombre derrière la porte
      // Portes extérieures (louvoiement des plateformes), jaune liO pour le bouton d'ouverture
      for (const s of [-1, 1]) {
        box(1.1, 1.95, 0.04, m.plastic, e * (L / 2 - 0.9), 0.975, s * (WID / 2 - 0.04));
        box(0.06, 0.06, 0.02, m.pole, e * (L / 2 - 1.55), 1.2, s * (WID / 2 - 0.07));
      }
    }

    // Écran d'information au-dessus de chaque porte d'intercirculation (canvas redessiné quand l'arrêt change)
    const info = document.createElement("canvas");
    info.width = 1024;
    info.height = 192;
    const infoTex = new THREE.CanvasTexture(info);
    infoTex.colorSpace = THREE.SRGBColorSpace;
    infoTex.anisotropy = 4;
    const infoMat = new THREE.MeshBasicMaterial({ map: infoTex, toneMapped: false });
    for (const e of [-1, 1]) {
      const scr = new THREE.Mesh(new THREE.PlaneGeometry(1.0, 0.19), infoMat);
      scr.position.set(e * (L / 2 - 0.06), 2.12, 0);
      scr.rotation.y = e > 0 ? -Math.PI / 2 : Math.PI / 2;
      wagon.add(scr);
      box(0.04, 0.23, 1.05, m.plastic, e * (L / 2 - 0.035), 2.12, 0);
    }
    const name = (id: string) => byId.get(id)?.name ?? id;
    const infoText = (s: SimState) =>
      s.kind === "moving" ? t.wagonNext(name(s.toId)) : s.kind === "arrived" ? t.wagonTerminus(name(s.stopId)) : t.wagonAtStop(name(s.stopId));
    let shown = "";
    const drawInfo = (text: string) => {
      if (text === shown) return;
      shown = text;
      const x = info.getContext("2d")!;
      x.fillStyle = "#0b0f1c";
      x.fillRect(0, 0, info.width, info.height);
      x.fillStyle = "#c90c0f";
      x.fillRect(0, 0, 150, info.height);
      x.fillStyle = "#fff";
      x.font = "800 64px system-ui, sans-serif";
      x.textBaseline = "middle";
      x.fillText("liO", 26, info.height / 2);
      x.fillStyle = "#ffd500";
      x.font = "700 58px system-ui, sans-serif";
      let size = 58;
      while (x.measureText(text).width > info.width - 200 && size > 28) x.font = `700 ${(size -= 2)}px system-ui, sans-serif`;
      x.fillText(text, 180, info.height / 2);
      infoTex.needsUpdate = true;
    };
    drawInfo(infoText(sim.getSnapshot().state));

    // Paysage réaliste : ciel et lointain sont une vraie photo panoramique (Poly Haven), qui éclaire aussi la scène ;
    // le sol en textures photo ; arbres et cyprès Sketchfab (public/models/scenery/SOURCE.md). Le sol, le ballast et
    // les rails sont fixes, tout le reste défile le long de x et revient de l'autre côté.
    const outside = new THREE.Group();
    scene.add(outside);
    const movers: THREE.Object3D[] = [];
    const rnd = (() => {
      let k = 7;
      return () => ((k = (k * 16807) % 2147483647) - 1) / 2147483646;
    })();
    const side = () => (rnd() < 0.5 ? -1 : 1);
    const along = () => (rnd() * 2 - 1) * SCENE_RANGE;
    const place = (o: THREE.Object3D, x: number, y: number, z: number) => {
      o.position.set(x, y, z);
      outside.add(o);
      movers.push(o);
      return o;
    };
    const GROUND_Y = -1.15;
    const ASSETS = "/models/scenery/";
    let disposed = false;
    const texLoader = new THREE.TextureLoader();
    const photo = (name: string, repeat: number) => {
      const tex = texLoader.load(ASSETS + name);
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
      tex.repeat.set(repeat, repeat);
      tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
      return tex;
    };

    // Ciel : le panorama sert de fond et d'éclairage d'ambiance ; le brouillard prend la couleur de son horizon pour
    // que le sol se fonde dans la photo sans ligne nette
    scene.background = new THREE.Color(0xc9d6e2);
    scene.fog = new THREE.Fog(0xc9d6e2, 160, FAR * 0.9);
    const pmrem = new THREE.PMREMGenerator(renderer);
    texLoader.load(ASSETS + "sky.jpg", (sky) => {
      if (disposed) return sky.dispose();
      sky.mapping = THREE.EquirectangularReflectionMapping;
      sky.colorSpace = THREE.SRGBColorSpace;
      scene.background = sky;
      scene.backgroundRotation.y = SKY_TURN;
      scene.environment = pmrem.fromEquirectangular(sky).texture;
      scene.environmentRotation.y = SKY_TURN;
      scene.environmentIntensity = 0.8;
      // Couleur de l'horizon : moyenne d'une bande juste sous la ligne d'horizon de la photo
      const img = sky.image as HTMLImageElement;
      const c = document.createElement("canvas");
      c.width = 256;
      c.height = 128;
      const x = c.getContext("2d")!;
      x.drawImage(img, 0, 0, 256, 128);
      const px = x.getImageData(0, 62, 256, 4).data;
      let r = 0, g = 0, b = 0;
      for (let i = 0; i < px.length; i += 4) (r += px[i]), (g += px[i + 1]), (b += px[i + 2]);
      const n = px.length / 4;
      (scene.fog as THREE.Fog).color.setRGB(r / n / 255, g / n / 255, b / n / 255, THREE.SRGBColorSpace);
    });

    // Sol : prairie photo (teintée un peu plus verte), ballast en gravier, traverses béton, rails, fil de contact
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(FAR * 2, FAR * 2), mat(0xcfe3a4, { roughness: 1, map: photo("leafy_grass.jpg", FAR / 4) }));
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = GROUND_Y;
    scene.add(ground);
    const gravel = photo("gravel_stones.jpg", 1);
    gravel.repeat.set(SCENE_RANGE, 2);
    box(SCENE_RANGE * 3, 0.16, 5.2, mat(0xd8d2c8, { roughness: 1, map: gravel }), 0, -1.12, 0, scene);
    const railMat = mat(0xb8bec8, { roughness: 0.3, metalness: 0.8 });
    for (const z of [-0.72, 0.72]) {
      box(SCENE_RANGE * 3, 0.1, 0.07, railMat, 0, -0.9, z, scene);
      box(SCENE_RANGE * 3, 0.03, 0.16, mat(0x5b5550, { metalness: 0.4 }), 0, -0.95, z, scene); // patin
    }
    // Traverses : un seul groupe qui recule de dx et se recale toutes les 0,6 m (le motif se répète à l'identique)
    const SLEEPER = 0.6;
    const sleepers = new THREE.Group();
    scene.add(sleepers);
    const sleeperMat = mat(0xa8a49c, { roughness: 0.95 });
    for (let x = -90; x <= 90; x += SLEEPER) box(0.26, 0.1, 2.5, sleeperMat, x, -0.98, 0, sleepers);
    box(SCENE_RANGE * 3, 0.025, 0.025, mat(0x30343c), 0, 5.4, 0, scene);

    // Champs labourés et prés fauchés : dalles de terre photo, légèrement teintées pour varier
    const mud = photo("dry_mud_field_001.jpg", 1), grass = photo("leafy_grass.jpg", 1);
    const fieldMats = [
      mat(0xe9d39a, { roughness: 1, map: grass }), // pré sec, doré
      mat(0xffffff, { roughness: 1, map: mud }), // labour
      mat(0xbfd28c, { roughness: 1, map: grass }), // pré vert
      mat(0xf3dc8c, { roughness: 1, map: grass }), // chaume
    ];
    for (let i = 0; i < 22; i++) {
      const w = 40 + rnd() * 50, d = 25 + rnd() * 60, s = side();
      const f = new THREE.Mesh(new THREE.PlaneGeometry(w, d), fieldMats[i % fieldMats.length]);
      // Les UV suivent la taille du champ : la texture garde la même échelle partout (une répétition tous les 8 m)
      const uv = f.geometry.attributes.uv as THREE.BufferAttribute;
      for (let k = 0; k < uv.count; k++) uv.setXY(k, (uv.getX(k) * w) / 8, (uv.getY(k) * d) / 8);
      f.rotation.x = -Math.PI / 2;
      place(f, along(), GROUND_Y + 0.02 + i * 0.002, s * (28 + d / 2 + rnd() * 70)); // pas de champ au pied de la voie
    }

    // Arbres et cyprès : des emplacements vides posés tout de suite (ils défilent déjà), remplis au chargement des
    // modèles. Le kit d'arbres contient sept arbres dans une seule scène : on les sépare, chacun recentré sur son pied
    // et ramené à une hauteur réaliste.
    type Kind = "tree" | "bush" | "cypress";
    const slots: { anchor: THREE.Group; kind: Kind }[] = [];
    const slot = (kind: Kind, x: number, z: number) => {
      const anchor = new THREE.Group();
      anchor.rotation.y = rnd() * Math.PI * 2;
      anchor.scale.setScalar(0.8 + rnd() * 0.45);
      place(anchor, x, GROUND_Y, z);
      slots.push({ anchor, kind });
    };
    for (let i = 0; i < 90; i++) {
      const r = rnd();
      slot(r < 0.25 ? "cypress" : r < 0.4 ? "bush" : "tree", along(), side() * (9 + rnd() * 110));
    }
    // Haie de cyprès coupe-vent, typique du Midi, et alignement d'arbres le long d'un chemin de terre
    for (let x = -SCENE_RANGE; x < SCENE_RANGE; x += 7) slot("cypress", x, -(34 + rnd() * 1.5));
    box(SCENE_RANGE * 3, 0.03, 3, mat(0xc9b896, { roughness: 1 }), 0, GROUND_Y + 0.03, 22, scene);
    for (let x = -SCENE_RANGE; x < SCENE_RANGE; x += 16) slot("tree", x + rnd() * 4, 19);
    const normalize = (src: THREE.Object3D, height: number) => {
      src.updateMatrixWorld(true);
      const bb = new THREE.Box3().setFromObject(src);
      const c = src.clone();
      src.matrixWorld.decompose(c.position, c.quaternion, c.scale);
      const k = height / (bb.max.y - bb.min.y);
      const g = new THREE.Group();
      g.add(c);
      c.position.set((c.position.x - (bb.min.x + bb.max.x) / 2) * k, (c.position.y - bb.min.y) * k, (c.position.z - (bb.min.z + bb.max.z) / 2) * k);
      c.scale.multiplyScalar(k);
      return g;
    };
    // Feuillages en découpe alpha (pas en transparence) : pas de tri, pas de feuilles qui passent devant les troncs
    const cutout = (o: THREE.Object3D) =>
      o.traverse((m) => {
        const mesh = m as THREE.Mesh;
        if (!mesh.isMesh) return;
        for (const x of [mesh.material].flat() as THREE.MeshStandardMaterial[]) {
          if (!x.map) continue;
          x.transparent = false;
          x.alphaTest = 0.45;
          x.depthWrite = true;
          x.side = THREE.DoubleSide;
        }
      });
    const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
    Promise.all([loader.loadAsync(ASSETS + "trees.glb"), loader.loadAsync(ASSETS + "cypress.glb")])
      .then(([kit, cyp]) => {
        if (disposed) return;
        cutout(kit.scene);
        cutout(cyp.scene);
        kit.scene.updateMatrixWorld(true);
        const trees: THREE.Object3D[] = [], bushes: THREE.Object3D[] = [];
        kit.scene.traverse((o) => {
          // Les arbres sont les enfants directs de RootNode (GLTFLoader réécrit leurs noms : « Tree_EZTree0Large »)
          if (o.parent?.name !== "RootNode" || !o.name.startsWith("Tree")) return;
          if (o.name.includes("Bush")) bushes.push(normalize(o, 3));
          else trees.push(normalize(o, o.name.includes("Large") ? 14 : 10));
        });
        const cypresses = [normalize(cyp.scene, 11)];
        const kinds = { tree: trees, bush: bushes, cypress: cypresses };
        slots.forEach(({ anchor, kind }, i) => {
          const list = kinds[kind];
          if (list.length) anchor.add(list[i % list.length].clone());
        });
      })
      .catch(() => {}); // sans les modèles, le paysage reste un sol, des champs et le panorama

    // Poteaux caténaires tout près : profil en H, console, isolateurs. Ce sont eux qui donnent la sensation de vitesse
    const poleMat = mat(0x7c838f, { metalness: 0.6, roughness: 0.4 }), insMat = mat(0x8a4a2a, { roughness: 0.4 });
    for (let i = 0; i < 16; i++) {
      const p = new THREE.Group();
      box(0.12, 0.6, 1.0, mat(0xb9b4aa), 0, 0.3, 0, p); // socle béton
      for (const dz of [-0.09, 0.09]) box(0.2, 7.2, 0.04, poleMat, 0, 3.6, dz, p);
      box(0.06, 7.2, 0.16, poleMat, 0, 3.6, 0, p);
      const arm = box(0.07, 0.07, 3.1, poleMat, 0, 6.55, -1.5, p);
      arm.rotation.x = -0.06;
      const brace = box(0.05, 0.05, 2.6, poleMat, 0, 5.9, -1.15, p);
      brace.rotation.x = 0.35;
      for (const z of [-0.6, -2.4]) {
        const ins = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.07, 0.45, 10), insMat);
        ins.position.set(0, 6.25, z);
        p.add(ins);
      }
      place(p, -SCENE_RANGE + i * ((2 * SCENE_RANGE) / 16), GROUND_Y, 2.9);
    }

    // Regard et déplacement
    let yaw = -Math.PI / 2 + 0.0001, pitch = -0.08; // départ : au bout de l'allée, regard vers l'autre bout
    let camX = -END, sway = 0;
    const keys = new Set<string>();
    let drag: { x: number; y: number } | null = null;
    const down = (e: PointerEvent) => {
      drag = { x: e.clientX, y: e.clientY };
      el.setPointerCapture(e.pointerId);
    };
    const move = (e: PointerEvent) => {
      if (!drag) return;
      const k = 0.0035;
      yaw += (e.clientX - drag.x) * k;
      pitch = Math.max(-1.1, Math.min(1.0, pitch + (e.clientY - drag.y) * k));
      drag = { x: e.clientX, y: e.clientY };
    };
    const up = () => (drag = null);
    const wheel = (e: WheelEvent) => {
      e.preventDefault();
      const dir = -Math.sin(yaw) >= 0 ? 1 : -1; // sens du regard le long de l'allée
      camX = Math.max(-END, Math.min(END, camX - Math.sign(e.deltaY) * dir * 0.35));
    };
    const keyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") close.current();
      keys.add(e.key);
    };
    const keyUp = (e: KeyboardEvent) => keys.delete(e.key);
    el.addEventListener("pointerdown", down);
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
    el.addEventListener("pointercancel", up);
    el.addEventListener("wheel", wheel, { passive: false });
    window.addEventListener("keydown", keyDown);
    window.addEventListener("keyup", keyUp);

    const resize = () => {
      const { clientWidth: w, clientHeight: h } = el;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.fov = w < h ? 82 : 70; // téléphone en portrait : on voit les deux rangées
      camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(el);
    resize();

    let last = performance.now(), speed = 0, run = 0;
    const look = new THREE.Vector3();
    renderer.setAnimationLoop((now) => {
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      const snap = sim.getSnapshot();
      drawInfo(infoText(snap.state));
      const moving = snap.state.kind === "moving" && snap.playing && !snap.state.walk;
      speed += ((moving ? 22 + 6 * snap.speed : 0) - speed) * Math.min(1, dt * 0.8); // m/s, freinage doux
      const dx = speed * dt;
      for (const o of movers) {
        o.position.x -= dx;
        if (o.position.x < -SCENE_RANGE) o.position.x += 2 * SCENE_RANGE;
      }
      sleepers.position.x = (sleepers.position.x - dx) % SLEEPER;
      // Marche : boutons, flèches / ZQSD dans le sens du regard le long de l'allée
      const fwd = -Math.sin(yaw) >= 0 ? -1 : 1;
      let w = walk.current;
      if (keys.has("ArrowUp") || keys.has("z") || keys.has("w")) w = 1;
      if (keys.has("ArrowDown") || keys.has("s")) w = -1;
      if (keys.has("ArrowLeft") || keys.has("q") || keys.has("a")) yaw += dt * 1.6;
      if (keys.has("ArrowRight") || keys.has("d")) yaw -= dt * 1.6;
      if (w) camX = Math.max(-END, Math.min(END, camX - w * fwd * dt * 1.6));
      run += (w ? 1 : 0) * dt;
      // Roulis de la voiture en marche, petit balancement de la tête quand on marche
      const k = speed / 30;
      sway = Math.sin(now / 1000 * 2.3) * 0.006 * k + Math.sin(now / 1000 * 7.1) * 0.002 * k;
      wagon.rotation.x = sway;
      camera.position.set(camX, EYE + Math.sin(run * 9) * 0.02 * (w ? 1 : 0) + Math.sin(now / 1000 * 9) * 0.004 * k, Math.sin(run * 4.5) * 0.015 * (w ? 1 : 0));
      look.set(camX - Math.sin(yaw) * Math.cos(pitch), camera.position.y + Math.sin(pitch), -Math.cos(yaw) * Math.cos(pitch));
      camera.lookAt(look);
      camera.rotation.z += sway * 0.5;
      renderer.render(scene, camera);
    });

    return () => {
      disposed = true;
      renderer.setAnimationLoop(null);
      observer.disconnect();
      el.removeEventListener("pointerdown", down);
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      el.removeEventListener("pointercancel", up);
      el.removeEventListener("wheel", wheel);
      window.removeEventListener("keydown", keyDown);
      window.removeEventListener("keyup", keyUp);
      const geos = new Set<THREE.BufferGeometry>(), mats = new Set<THREE.Material>();
      scene.traverse((o) => {
        const mesh = o as THREE.Mesh;
        if (!mesh.isMesh) return;
        geos.add(mesh.geometry);
        [mesh.material].flat().forEach((x) => mats.add(x));
      });
      geos.forEach((g) => g.dispose());
      mats.forEach((x) => {
        (x as THREE.MeshStandardMaterial).map?.dispose();
        x.dispose();
      });
      infoTex.dispose();
      pmrem.dispose();
      scene.environment?.dispose();
      (scene.background as THREE.Texture | null)?.dispose?.();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [sim, byId, t]);

  const hold = (dir: number) => ({
    onPointerDown: (e: RPointerEvent) => {
      e.currentTarget.setPointerCapture(e.pointerId);
      walk.current = dir;
    },
    onPointerUp: () => (walk.current = 0),
    onPointerCancel: () => (walk.current = 0),
    onLostPointerCapture: () => (walk.current = 0),
  });

  return (
    <div className="wagon" role="dialog" aria-modal="true" aria-label={t.wagonTitle}>
      <div className="wagon-view" ref={host} />
      <div className="wagon-bar">
        <button type="button" className="wagon-exit" onClick={onClose}>
          ← {t.wagonExit}
        </button>
        <span className="wagon-title">{t.wagonTitle}</span>
      </div>
      <div className="wagon-walk">
        <button type="button" aria-label={t.wagonForward} {...hold(1)}>▲</button>
        <button type="button" aria-label={t.wagonBack} {...hold(-1)}>▼</button>
      </div>
      <div className="wagon-hint">{t.wagonHint}</div>
      <p className="wagon-credits">{t.wagonCredits}</p>
      {/* Portes coulissantes qui s'ouvrent sur la voiture à l'entrée */}
      <div className="wagon-doors" aria-hidden="true">
        <div className="wd-glow" />
        {(["l", "r"] as const).map((k) => (
          <div key={k} className={`wd-leaf wd-${k}`}>
            <div className="wd-window">
              <span className="wd-glare" />
            </div>
            <div className="wd-band">{k === "l" && <span className="wd-logo">liO</span>}</div>
            {k === "l" ? <span className="wd-warn" /> : <span className="wd-button"><i /></span>}
            <span className="wd-seal" />
          </div>
        ))}
        <div className="wd-header">
          <span className="wd-lamp" />
        </div>
        <div className="wd-sill" />
      </div>
    </div>
  );
}
