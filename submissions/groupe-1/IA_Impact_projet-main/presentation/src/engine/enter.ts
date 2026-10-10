// Entrée d'une slide : les blocs marqués data-in entrent un par un (décalés par data-d, ou à data-at ms),
// puis seul le mouvement lent (data-idle : flotter, tourner, respirer) continue, sans fin.
// L'entrée anime `transform`, le mouvement lent les propriétés séparées `translate` / `rotate` / `scale` :
// les deux se cumulent sans se gêner.
import { SlideRun } from "./loop";
import { A, BACK, fmtInt, rand, reduceMotion } from "./util";

/** Pas entre deux blocs (data-d), en ms */
export const STEP = 70;

type Preset = (el: HTMLElement, delay: number, run: SlideRun) => number; // renvoie la durée

const flapText = new WeakMap<HTMLElement, string>();

const IN: Record<string, Preset> = {
  up: (el, d) => (A(el, [{ opacity: 0, transform: "translateY(70px)" }, { opacity: 1, transform: "none" }], { duration: 600, delay: d }), 600),
  left: (el, d) => (A(el, [{ opacity: 0, transform: "translateX(-110px)" }, { opacity: 1, transform: "none" }], { duration: 600, delay: d }), 600),
  right: (el, d) => (A(el, [{ opacity: 0, transform: "translateX(110px)" }, { opacity: 1, transform: "none" }], { duration: 600, delay: d }), 600),
  zoom: (el, d) => (A(el, [{ opacity: 0, transform: "scale(.4) rotate(-40deg)" }, { opacity: 1, transform: "none" }], { duration: 900, delay: d }), 900),
  pop: (el, d) => (A(el, [{ opacity: 0, transform: "scale(.3)" }, { opacity: 1, transform: "none" }], { duration: 550, delay: d, easing: BACK }), 550),
  // Écran du site qui arrive de loin, incliné, et se pose face à la caméra
  screen: (el, d) => (A(el, [
    { opacity: 0, transform: "perspective(2400px) translate3d(300px, 260px, -1600px) rotateY(-38deg) rotateX(24deg) rotateZ(-6deg)" },
    { opacity: 1, offset: 0.3 },
    { opacity: 1, transform: "none" }], { duration: 1100, delay: d, easing: "cubic-bezier(.16,.84,.24,1)" }), 1100),
  // Caméra lente sur une image : « échelle,x%,y% ; échelle,x%,y% » en 10 s
  kenburns: (el, d) => {
    const [a, b] = (el.dataset.kb ?? "1,0,0;1,0,0").split(";").map((k) => k.split(",").map(Number));
    const tf = ([s, x, y]: number[]) => `translate(${x}%, ${y}%) scale(${s})`;
    A(el, [{ transform: tf(a), opacity: 0 }, { opacity: 1, offset: 0.08 }, { transform: tf(b), opacity: 1 }],
      { duration: 10000, delay: d, easing: "cubic-bezier(.3,.1,.3,1)" });
    return 10000;
  },
  throw: (el, d) => (A(el, [{ opacity: 0, transform: "translate(420px,-260px) rotate(28deg) scale(.7)" }, { opacity: 1, transform: "none" }], { duration: 700, delay: d, easing: BACK }), 700),
  mask: (el, d) => (A(el, [{ clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0% 0 0)" }], { duration: 600, delay: d }), 600),
  draw: (el, d) => {
    el.setAttribute("pathLength", "1");
    A(el, [{ strokeDasharray: "1 1", strokeDashoffset: 1 }, { strokeDasharray: "1 1", strokeDashoffset: 0 }], { duration: 900, delay: d, easing: "ease-in-out" });
    return 900;
  },
  // Chaque mot (rendu en <span class="w"><span class="wi">) sort de son masque
  words: (el, d) => {
    const ws = el.querySelectorAll(".wi");
    ws.forEach((w, i) => A(w, [{ transform: "translateY(115%) rotate(8deg)" }, { transform: "none" }], { duration: 650, delay: d + i * 50 }));
    el.closest<HTMLElement>(".slide")?.style.setProperty("--ul", `${d + ws.length * 50 + 350}ms`);
    return ws.length * 50 + 650;
  },
  // Capsules de la trame qui arrivent comme des voitures de train, de gauche à droite
  trame: (el, d) => {
    el.querySelectorAll("rect").forEach((r) => A(r, [{ opacity: 0, transform: "translateX(-90px)" }, { opacity: 1, transform: "none" }],
      { duration: 550, delay: d + +(r.getAttribute("x") ?? 0) * 1.4 }));
    return 950;
  },
  // Panneau d'affichage à palettes : chaque lettre tourne puis se fige, de gauche à droite
  flap: (el, d, run) => {
    if (!flapText.has(el)) flapText.set(el, el.textContent ?? "");
    const chars = [...(flapText.get(el) ?? "")];
    el.textContent = "";
    const spans = chars.map(() => {
      const s = document.createElement("span");
      s.className = "flap"; s.textContent = " "; el.append(s);
      return s;
    });
    A(el, [{ opacity: 0 }, { opacity: 1 }], { duration: 250, delay: d });
    const ABC = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", per = 32, spin = 380;
    const t0 = performance.now() + d;
    run.tick((now) => {
      let done = true;
      spans.forEach((s, i) => {
        const start = t0 + i * per;
        if (chars[i] === " ") { s.textContent = " "; return; }
        if (now < start) { done = false; return; }
        if (now < start + spin) { done = false; s.textContent = ABC[Math.floor(Math.random() * ABC.length)]; return; }
        s.textContent = chars[i];
      });
      return !done;
    });
    return chars.length * per + spin;
  },
};

// ── Mouvements lents qui ne s'arrêtent jamais ─────────
const loopOpts = (duration: number, easing = "ease-in-out"): KeyframeAnimationOptions =>
  ({ duration, iterations: Infinity, direction: "alternate", easing });
const IDLE: Record<string, (el: HTMLElement) => Animation> = {
  float: (el) => el.animate({ translate: ["0 0", "0 -16px"] }, loopOpts(rand(3000, 4600))),
  bob: (el) => el.animate({ translate: ["0 0", "0 -7px"] }, loopOpts(rand(1700, 2400))),
  pulse: (el) => el.animate({ scale: ["1", "1.14"] }, loopOpts(rand(1300, 1700))),
  drift: (el) => el.animate({ translate: ["0 0", "26px 0"] }, loopOpts(5200)),
  sway: (el) => el.animate({ rotate: ["0deg", `${rand(1.5, 3) * (Math.random() < 0.5 ? -1 : 1)}deg`], translate: ["0 0", "0 -10px"] }, loopOpts(rand(3200, 4800))),
  spin: (el) => el.animate({ rotate: ["0deg", "360deg"] }, { duration: (+(el.dataset.speed ?? 0) || 40) * 1000, iterations: Infinity }),
  "spin-rev": (el) => el.animate({ rotate: ["360deg", "0deg"] }, { duration: (+(el.dataset.speed ?? 0) || 40) * 1000, iterations: Infinity }),
  wheel: (el) => el.animate({ rotate: ["0deg", "360deg"] }, { duration: 14000, iterations: Infinity, pseudoElement: "::before" }),
};

/** Lance l'entrée des blocs, les mouvements lents et les compteurs. `t0` : délai avant le premier bloc */
export function enterBlocks(slide: HTMLElement, t0: number, run: SlideRun) {
  slide.classList.remove("on"); void slide.offsetWidth; slide.classList.add("on");
  const ends = new Map<Element, number>();
  const tb = reduceMotion ? 0 : t0;
  slide.querySelectorAll<HTMLElement>("[data-in]").forEach((el) => {
    const d = reduceMotion ? 0 : el.dataset.at ? t0 + +el.dataset.at : tb + (+(el.dataset.d ?? 0) || 0) * STEP;
    const preset = IN[el.dataset.in ?? ""];
    if (!preset) throw new Error(`Entrée inconnue : ${el.dataset.in}`);
    ends.set(el, d + (reduceMotion ? 0 : preset(el, d, run)));
  });
  if (!reduceMotion) slide.querySelectorAll<HTMLElement>("[data-idle]").forEach((el) => {
    const host = el.hasAttribute("data-in") ? el : el.closest("[data-in]");
    const idle = IDLE[el.dataset.idle ?? ""];
    if (!idle) throw new Error(`Mouvement inconnu : ${el.dataset.idle}`);
    run.later(((host && ends.get(host)) ?? tb + 600) - 60, () => idle(el));
  });
  slide.querySelectorAll<HTMLElement>("[data-count]").forEach((el) => {
    const to = +(el.dataset.count ?? 0), host = el.closest("[data-in]");
    const start = performance.now() + (reduceMotion ? 0 : ((host && ends.get(host)) ?? tb) - 700), dur = reduceMotion ? 1 : 1800;
    el.textContent = "0";
    run.tick((now) => {
      const p = Math.min(1, Math.max(0, (now - start) / dur));
      el.textContent = fmtInt.format(Math.round(to * (1 - Math.pow(2, -10 * p)) * (p < 1 ? 1 : 1 / (1 - Math.pow(2, -10)))));
      if (p >= 1) { el.textContent = fmtInt.format(to); return false; }
    });
  });
}

/** Tout ce qui tourne sur la slide s'arrête ; elle redevient prête pour sa prochaine entrée */
export function leaveSlide(slide: HTMLElement, run: SlideRun) {
  run.stop();
  slide.getAnimations({ subtree: true }).forEach((a) => a.cancel());
  slide.querySelectorAll(".trains").forEach((g) => (g.innerHTML = ""));
  slide.classList.remove("on", "shown");
}

/** Tape un texte lettre par lettre dans un élément, à partir de `at` ms ; renvoie l'instant de fin */
export function typeInto(run: SlideRun, el: HTMLElement, text: string, at: number, per = 55) {
  el.textContent = "";
  const start = performance.now() + at;
  run.tick((now) => {
    const n = Math.max(0, Math.min(text.length, Math.floor((now - start) / per)));
    el.textContent = text.slice(0, n);
    if (n >= text.length) return false;
  });
  return at + text.length * per;
}

/** Bouton qu'on « clique » */
export const press = (el: Element, at: number) =>
  A(el, [{ transform: "none" }, { transform: "scale(.94)", offset: 0.4 }, { transform: "none" }], { duration: 380, delay: at, fill: "none" });
