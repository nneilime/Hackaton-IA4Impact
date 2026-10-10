// Réseau liO sur les cartes SVG : entrée de la carte, petits trains qui circulent, trajet Perpignan → Albi.
// Ce qui bouge à chaque image vit dans le SVG superposé (.net-ov, rendu par <Net>) : la carte, elle, est
// dessinée une fois au lieu d'être repeinte 60 fois par seconde.
import { NETWORK, ROUTE, ST } from "../data";
import type { SlideRun } from "./loop";
import { A, BACK, RED, SVGNS, WHITE, YELLOW, rand, short } from "./util";

/** Voisins de chaque gare sur le graphe */
export const ADJ: number[][] = ST.map(() => []);
NETWORK.edges.forEach(([a, b]) => { ADJ[a].push(b); ADJ[b].push(a); });

const overlayOf = (svg: SVGSVGElement) => {
  const ov = svg.nextElementSibling;
  if (!(ov instanceof SVGSVGElement) || !ov.classList.contains("net-ov")) throw new Error("SVG superposé introuvable");
  return ov;
};

/** La carte entre d'un seul balayage de gauche à droite, appliqué au SVG entier (une couche qu'on découpe) */
export function enterNet(run: SlideRun, svg: SVGSVGElement, t0: number, { draw = 2200, trains = 0 } = {}) {
  svg.animate({ clipPath: ["inset(0 100% 0 0)", "inset(0 0% 0 0)"], opacity: [0.2, 1] }, { duration: draw, delay: t0, easing: "cubic-bezier(.45,0,.2,1)", fill: "both" });
  if (trains) run.later(t0 + draw, () => runTrains(run, overlayOf(svg).querySelector(".trains")!, trains));
}

/** Petits trains qui circulent sans fin sur le graphe, de gare en gare */
function runTrains(run: SlideRun, g: SVGGElement, count: number) {
  const starts = ST.map((_, i) => i).filter((i) => ADJ[i].length);
  const list = Array.from({ length: count }, (_, k) => {
    const el = document.createElementNS(SVGNS, "g");
    el.innerHTML = `<circle r="13" fill="${k % 3 ? YELLOW : RED}" opacity=".22"/><rect x="-13" y="-4.5" width="26" height="9" rx="4.5" class="${k % 3 ? "train" : "train-red"}"/>`;
    g.append(el);
    el.animate({ opacity: [0, 1] }, { duration: 800, fill: "both" });
    const a = starts[Math.floor(Math.random() * starts.length)];
    return { el, a, b: ADJ[a][Math.floor(Math.random() * ADJ[a].length)], t: Math.random(), speed: rand(55, 95) };
  });
  let last = performance.now();
  run.tick((now) => {
    const dt = Math.min(0.05, (now - last) / 1000); last = now;
    for (const tr of list) {
      const [ax, ay] = ST[tr.a], [bx, by] = ST[tr.b];
      tr.t += (tr.speed * dt) / (Math.hypot(bx - ax, by - ay) || 1);
      if (tr.t >= 1) {
        const next = ADJ[tr.b].filter((n) => n !== tr.a), pick = next.length ? next : ADJ[tr.b];
        tr.a = tr.b; tr.b = pick[Math.floor(Math.random() * pick.length)]; tr.t = 0;
        continue;
      }
      const x = ax + (bx - ax) * tr.t, y = ay + (by - ay) * tr.t;
      tr.el.setAttribute("transform", `translate(${x} ${y}) rotate(${(Math.atan2(by - ay, bx - ax) * 180) / Math.PI})`);
    }
  });
}

/** Position du train à chaque image : tronçon, avancement f (0 → 1), phase, segment i et avancement s dedans */
export interface RoutePos { leg: number; f: number; phase: "ride" | "wait"; x: number; y: number; a: number; i: number; s: number }

/** Le trajet se dessine à `at`, puis un train le parcourt en boucle, en s'arrêtant à la correspondance */
export function routeOn(run: SlideRun, svg: SVGSVGElement, at: number, onPos?: (p: RoutePos) => void) {
  const extra = svg.querySelector<SVGGElement>(".extra")!;
  const legs = ROUTE.legs.map((l) => l.stops.map((i) => ST[i]));
  const pts = (ps: typeof legs[number]) => ps.map(([x, y]) => `${x},${y}`).join(" ");
  const ends = [legs[0][0], legs[0][legs[0].length - 1], legs[1][legs[1].length - 1]];
  const names = [short(ROUTE.from), short(ROUTE.legs[0].to), short(ROUTE.to)];
  extra.innerHTML = legs.map((ps, i) => `<polyline class="leg leg-${i}" pathLength="1" points="${pts(ps)}"/>`).join("") +
    legs.flatMap((ps) => ps.slice(1, -1)).map(([x, y]) => `<circle class="mid" cx="${x}" cy="${y}" r="5"/>`).join("") +
    `<circle class="halo" cx="${ends[1][0]}" cy="${ends[1][1]}" r="22"/>` +
    ends.map(([x, y]) => `<circle class="end" cx="${x}" cy="${y}" r="13"/>`).join("") +
    ends.map(([x, y], i) => `<text class="lbl" x="${x + (i === 0 ? -20 : 22)}" y="${y + (i === 1 ? -18 : 8)}" text-anchor="${i === 0 ? "end" : "start"}" style="font-size:28px">${names[i]}</text>`).join("") +
    `<g class="route-train" opacity="0"><circle r="24" fill="${YELLOW}" opacity=".3"/><rect x="-22" y="-8" width="44" height="16" rx="8" fill="${RED}" stroke="${WHITE}" stroke-width="3"/></g>`;
  const durs = [1500, 800];
  extra.querySelectorAll(".leg").forEach((p, i) => A(p, [{ strokeDasharray: "1 1", strokeDashoffset: 1 }, { strokeDasharray: "1 1", strokeDashoffset: 0 }],
    { duration: durs[i], delay: at + (i ? durs[0] + 200 : 0), easing: "ease-in-out" }));
  extra.querySelectorAll<SVGElement>(".mid, .end, .halo").forEach((c) => {
    c.style.transformBox = "fill-box"; c.style.transformOrigin = "center";
    A(c, [{ opacity: 0, transform: "scale(0)" }, { opacity: 1, transform: "none" }], { duration: 500, delay: at + 300 + Math.random() * 2000, easing: BACK });
  });
  extra.querySelectorAll(".lbl").forEach((l, i) => A(l, [{ opacity: 0 }, { opacity: 1 }], { duration: 600, delay: at + 600 + i * 700 }));
  const halo = extra.querySelector(".halo")!;
  run.later(at + 2600, () => halo.animate({ scale: ["1", "1.9"], opacity: [1, 0] }, { duration: 1600, iterations: Infinity, easing: "ease-out" }));

  const cum = legs.map((ps) => { const c = [0]; for (let i = 1; i < ps.length; i++) c.push(c[i - 1] + Math.hypot(ps[i][0] - ps[i - 1][0], ps[i][1] - ps[i - 1][1])); return c; });
  const posAt = (k: number, f: number) => {
    const ps = legs[k], c = cum[k], target = f * c[c.length - 1];
    let i = 1; while (i < c.length - 1 && c[i] < target) i++;
    const s = (target - c[i - 1]) / (c[i] - c[i - 1] || 1);
    const [ax, ay] = ps[i - 1], [bx, by] = ps[i];
    return { x: ax + (bx - ax) * s, y: ay + (by - ay) * s, a: Math.atan2(by - ay, bx - ax), i, s };
  };
  const K = 40; // ms par minute de trajet
  const plan: ["ride" | "wait", number, number][] = [["ride", 0, ROUTE.legs[0].minutes * K], ["wait", 0, ROUTE.legs[1].wait * K + 600], ["ride", 1, ROUTE.legs[1].minutes * K], ["wait", 1, 2000]];
  const cycle = plan.reduce((s, p) => s + p[2], 0);
  const trainEl = extra.querySelector(".route-train")!;
  overlayOf(svg).querySelector(".movers")!.replaceChildren(halo, trainEl); // le halo pulse sans fin : couche superposée aussi
  run.later(at + 2600, () => {
    trainEl.animate({ opacity: [0, 1] }, { duration: 500, fill: "forwards" });
    const start = performance.now();
    run.tick((now) => {
      let t = (now - start) % cycle, info: RoutePos | undefined;
      for (const [phase, leg, dur] of plan) {
        if (t <= dur) {
          const f = phase === "ride" ? (1 - Math.cos((t / dur) * Math.PI)) / 2 : 1;
          info = { leg, f, phase, ...posAt(leg, f) };
          break;
        }
        t -= dur;
      }
      if (!info) return;
      trainEl.setAttribute("transform", `translate(${info.x} ${info.y}) rotate(${(info.a * 180) / Math.PI})`);
      onPos?.(info);
    });
  });
}
