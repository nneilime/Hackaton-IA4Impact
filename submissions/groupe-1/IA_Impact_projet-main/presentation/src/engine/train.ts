// Le TER liO dessiné (SVG) qui traverse l'écran pendant une transition. Il est dessiné une fois puis seulement
// glissé : aucune animation à l'intérieur (roues, caisses) — elles faisaient repeindre tout le dessin et son ombre
// floue à chaque image, d'où des saccades.
import { NAVY, RED, SVGNS, W, WHITE, YELLOW } from "./util";

const CAR_TOP = 40, CAR_BOT = 268;

function carSVG(id: string, w: number, nose: boolean, mirrored: boolean) {
  const body = nose
    ? `M18 ${CAR_TOP}H${w - 190}C${w - 70} ${CAR_TOP} ${w - 8} 110 ${w} 205V${CAR_BOT - 16}Q${w} ${CAR_BOT} ${w - 18} ${CAR_BOT}H18Q0 ${CAR_BOT} 0 ${CAR_BOT - 18}V${CAR_TOP + 18}Q0 ${CAR_TOP} 18 ${CAR_TOP}Z`
    : `M14 ${CAR_TOP}H${w - 14}Q${w} ${CAR_TOP} ${w} ${CAR_TOP + 14}V${CAR_BOT - 14}Q${w} ${CAR_BOT} ${w - 14} ${CAR_BOT}H14Q0 ${CAR_BOT} 0 ${CAR_BOT - 14}V${CAR_TOP + 14}Q0 ${CAR_TOP} 14 ${CAR_TOP}Z`;
  const stop = nose ? w - 260 : w - 70;
  let win = "";
  for (let x = 60; x + 84 <= stop; x += 112) {
    win += Math.round(x / 112) % 3 === 1
      ? `<rect x="${x}" y="64" width="84" height="196" rx="10" fill="#e3e6ee" stroke="${NAVY}" stroke-width="3"/><rect x="${x + 14}" y="78" width="56" height="70" rx="8" fill="${NAVY}"/><line x1="${x + 42}" y1="78" x2="${x + 42}" y2="258" stroke="${NAVY}" stroke-width="3"/>`
      : `<rect x="${x}" y="70" width="84" height="66" rx="14" fill="${NAVY}"/><path d="M${x + 10} 120 L${x + 40} 78" stroke="#ffffff" stroke-opacity=".25" stroke-width="8" stroke-linecap="round"/>`;
  }
  const front = nose ? `<path d="M${w - 235} 66H${w - 150}C${w - 85} 66 ${w - 40} 110 ${w - 20} 150H${w - 235}Z" fill="${NAVY}"/>
    <path d="M${w - 200} 120 L${w - 160} 76" stroke="#fff" stroke-opacity=".3" stroke-width="10" stroke-linecap="round"/>
    <ellipse cx="${w - 22}" cy="226" rx="12" ry="8" fill="${YELLOW}"/>` : "";
  const tx = nose ? w * 0.38 : w * 0.5;
  return `<clipPath id="${id}"><path d="${body}"/></clipPath>
    <rect x="${nose ? 30 : 20}" y="${CAR_TOP - 12}" width="${nose ? w - 260 : w - 40}" height="16" rx="8" fill="#c9cdd8"/>
    <path d="${body}" fill="${WHITE}"/>
    <g clip-path="url(#${id})">
      <rect x="0" y="196" width="${w}" height="80" fill="${NAVY}"/>
      <rect x="0" y="180" width="${w}" height="12" fill="${RED}"/>
      <rect x="0" y="166" width="${w}" height="9" fill="${YELLOW}"/>
      ${win}${front}
      <text x="${tx}" y="250"${mirrored ? ` transform="translate(${2 * tx} 0) scale(-1 1)"` : ""} font-family="Barlow, sans-serif" font-weight="800" font-size="46" fill="${WHITE}" text-anchor="middle">li<tspan fill="${YELLOW}">O</tspan></text>
    </g>`;
}

function bogie(x: number) {
  const wheel = (cx: number) => `<g transform="translate(${cx} 290)"><circle r="27" fill="#1a1f2e"/><circle r="12" fill="#5d6680"/><path d="M-22 0H22M0-22V22" stroke="#5d6680" stroke-width="5"/></g>`;
  return `<rect x="${x - 75}" y="262" width="210" height="26" rx="10" fill="#1a1f2e"/>${wheel(x)}${wheel(x + 60)}`;
}

const CARS: { w: number; nose?: "left" | "right" }[] = [{ w: 860, nose: "left" }, { w: 700 }, { w: 860, nose: "right" }];
const GAP = 26;
const TRAIN_LEN = CARS.reduce((s, c) => s + c.w, 0) + GAP * (CARS.length - 1);
let carUid = 0;

function makeTrain() {
  let x = 0, out = "";
  CARS.forEach((c, i) => {
    const inner = carSVG(`car${carUid++}`, c.w, !!c.nose, c.nose === "left");
    const car = c.nose === "left" ? `<g transform="translate(${c.w} 0) scale(-1 1)">${inner}</g>` : inner;
    const panto = !c.nose ? `<path d="M${c.w / 2 - 60} ${CAR_TOP - 10}L${c.w / 2} 4L${c.w / 2 + 50} ${CAR_TOP - 10}M${c.w / 2 - 50} 4H${c.w / 2 + 50}" stroke="#1a1f2e" stroke-width="5" fill="none"/>` : "";
    out += `<g transform="translate(${x} 0)">${bogie(110)}${bogie(c.w - 220)}<g>${panto}${car}</g></g>`;
    if (i < CARS.length - 1) out += `<rect x="${x + c.w - 4}" y="190" width="${GAP + 8}" height="44" fill="#1a1f2e"/>`;
    x += c.w + GAP;
  });
  const svg = document.createElementNS(SVGNS, "svg");
  svg.setAttribute("class", "ter");
  svg.setAttribute("viewBox", `0 0 ${TRAIN_LEN} 330`);
  svg.setAttribute("width", String(TRAIN_LEN));
  svg.setAttribute("height", "330");
  svg.innerHTML = out;
  return svg;
}

/** Passage du train ; `onReveal(px)` reçoit la largeur découverte derrière sa queue, à chaque image */
export function passTrain(layer: HTMLElement, dir: 1 | -1, duration: number, onReveal: (px: number) => void, done: () => void) {
  const train = makeTrain();
  const rails = document.createElement("div");
  rails.className = "pass-rails";
  layer.append(rails, train);
  rails.animate({ opacity: [0, 1, 1, 0] }, { duration, fill: "both" });
  const start = performance.now();
  const travel = W + TRAIN_LEN;
  (function frame(now: number) {
    const p = Math.min(1, (now - start) / duration);
    const e = 0.3 * p + 0.7 * (p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2);
    const head = e * travel, left = head - TRAIN_LEN;
    const x = dir > 0 ? left : W - head;
    train.style.transform = `translateX(${x}px)${dir > 0 ? "" : " scaleX(-1)"} translateY(${Math.sin(now / 60) * 1.5}px)`;
    onReveal(Math.max(0, Math.min(W, left)));
    if (p < 1) requestAnimationFrame(frame);
    else { train.remove(); rails.remove(); done(); }
  })(start);
}
