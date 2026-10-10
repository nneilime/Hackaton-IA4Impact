// Transitions entre deux slides : chacune lance l'entrée de la nouvelle slide au bon moment (env.enter)
// et appelle done() quand elle a fini.
import { deck3d } from "./three";
import { passTrain } from "./train";
import { H, IO3, NAVY, RED, W, WHITE, YELLOW, rand } from "./util";

export type TransKind = "train" | "zoom" | "cube" | "iris" | "flap" | "push" | "ter3d" | "ter3d-front";

export interface TransEnv {
  stage: HTMLElement;
  /** calque au-dessus des slides (TER, lignes de vitesse, volets) */
  layer: HTMLElement;
  /** lance l'entrée de `slide` dans `delay` ms */
  enter: (slide: HTMLElement, delay: number) => void;
}

type Transition = (env: TransEnv, prev: HTMLElement, next: HTMLElement, dir: 1 | -1, done: () => void, fast: boolean) => void;

export const LOCO_SPEED = 1250;

const fx = (layer: HTMLElement, cls: string) => {
  const e = document.createElement("i");
  e.className = cls;
  layer.append(e);
  return e;
};

export const TRANSITIONS: Record<TransKind, Transition> = {
  // Un TER traverse l'écran et tire la nouvelle slide derrière lui
  train(env, prev, next, dir, done, fast) {
    const duration = fast ? 950 : LOCO_SPEED;
    [...prev.querySelectorAll("[data-in]")].forEach((el, i) => el.animate(
      { opacity: [1, 0], transform: ["none", `translateX(${dir * 140}px)`] },
      { duration: 420, delay: Math.min(i * 18, 260), easing: "ease-in", fill: "forwards" }));
    next.classList.add("revealing");
    next.classList.toggle("rev-right", dir < 0);
    next.style.clipPath = dir > 0 ? `inset(0 ${W}px 0 0)` : `inset(0 0 0 ${W}px)`;
    env.enter(next, duration * 0.72);
    passTrain(env.layer, dir, duration, (rev) => {
      next.style.clipPath = dir > 0 ? `inset(0 ${W - rev}px 0 0)` : `inset(0 0 0 ${W - rev}px)`;
    }, () => { next.style.clipPath = ""; next.classList.remove("revealing", "rev-right"); done(); });
  },

  // Plongée : la caméra fonce dans l'ancienne slide, lignes de vitesse, la nouvelle sort de la profondeur.
  // Pas de filter: blur : flouter une slide 1920 × 1080 à chaque image faisait saccader
  zoom(env, prev, next, _dir, done) {
    prev.animate([{ transform: "scale(1)", opacity: 1 }, { transform: "scale(3.2)", opacity: 0 }],
      { duration: 800, easing: "cubic-bezier(.55,0,.9,.4)", fill: "forwards" });
    next.animate([{ transform: "scale(.4) rotate(-4deg)", opacity: 0 }, { transform: "none", opacity: 1 }],
      { duration: 1000, delay: 380, easing: "cubic-bezier(.1,.8,.2,1)", fill: "backwards" });
    for (let i = 0; i < 36; i++) {
      const l = fx(env.layer, "warp");
      l.style.background = [YELLOW, WHITE, RED][i % 3];
      l.style.rotate = `${(i / 36) * 360 + rand(-4, 4)}deg`;
      l.animate([{ transform: "translateX(60px) scaleX(.1)", opacity: 0 }, { opacity: 1, offset: 0.3 }, { transform: `translateX(${rand(900, 1400)}px) scaleX(1)`, opacity: 0 }],
        { duration: rand(650, 950), delay: rand(0, 300), easing: "cubic-bezier(.5,0,.8,.6)" }).finished.then(() => l.remove());
    }
    env.enter(next, 700);
    setTimeout(done, 1400);
  },

  // Cube : les deux slides sont deux faces qui tournent ensemble, avec un recul au milieu du mouvement
  cube(env, prev, next, dir, done) {
    env.stage.classList.add("persp");
    const o = dir > 0 ? ["100% 50%", "0% 50%"] : ["0% 50%", "100% 50%"];
    prev.style.transformOrigin = o[0]; next.style.transformOrigin = o[1];
    const out = prev.animate([{ transform: "translateX(0) rotateY(0) scale(1)" }, { transform: `translateX(${-dir * 50}%) rotateY(${-dir * 45}deg) scale(.82)`, offset: 0.5 }, { transform: `translateX(${-dir * 100}%) rotateY(${-dir * 90}deg) scale(1)` }],
      { duration: 1200, easing: IO3, fill: "forwards" });
    const inn = next.animate([{ transform: `translateX(${dir * 100}%) rotateY(${dir * 90}deg) scale(1)` }, { transform: `translateX(${dir * 50}%) rotateY(${dir * 45}deg) scale(.82)`, offset: 0.5 }, { transform: "translateX(0) rotateY(0) scale(1)" }],
      { duration: 1200, easing: IO3 });
    env.enter(next, 750);
    inn.finished.then(() => { out.cancel(); prev.style.transformOrigin = next.style.transformOrigin = ""; env.stage.classList.remove("persp"); done(); });
  },

  // Iris : un anneau jaune s'ouvre depuis le centre et découvre la slide
  iris(env, prev, next, _dir, done) {
    const ring = fx(env.layer, "iris-ring");
    next.animate([{ clipPath: "circle(0% at 50% 50%)" }, { clipPath: "circle(75% at 50% 50%)" }], { duration: 1100, easing: "cubic-bezier(.7,0,.2,1)" });
    ring.animate([{ transform: "translate(-50%,-50%) scale(0)", opacity: 1 }, { transform: "translate(-50%,-50%) scale(1)", opacity: 1, offset: 0.85 }, { transform: "translate(-50%,-50%) scale(1.08)", opacity: 0 }],
      { duration: 1100, easing: "cubic-bezier(.7,0,.2,1)" }).finished.then(() => ring.remove());
    prev.animate([{ transform: "scale(1)" }, { transform: "scale(.88)" }], { duration: 1100, easing: IO3, fill: "forwards" });
    env.enter(next, 650);
    setTimeout(done, 1150);
  },

  // Panneau à palettes : une grille de volets couvre l'écran en diagonale, puis se rabat sur la nouvelle slide
  flap(env, prev, next, dir, done) {
    const C = 10, Rw = 6, tw = W / C, th = H / Rw, tiles: HTMLElement[] = [];
    const pal = [NAVY, "#1d3166", RED, YELLOW, NAVY, "#1d3166"];
    next.style.visibility = "hidden";
    for (let r = 0; r < Rw; r++) for (let c = 0; c < C; c++) {
      const t = fx(env.layer, "flap-tile");
      Object.assign(t.style, { left: `${c * tw}px`, top: `${r * th}px`, width: `${tw + 1}px`, height: `${th + 1}px`, background: pal[(r * 7 + c * 3) % pal.length] });
      const order = dir > 0 ? c + r : C - c + r;
      t.animate([{ transform: "perspective(900px) rotateX(-90deg)" }, { transform: "perspective(900px) rotateX(0deg)" }], { duration: 300, delay: order * 45, easing: "cubic-bezier(.3,.7,.4,1)", fill: "backwards" });
      t.animate([{ transform: "perspective(900px) rotateX(0deg)" }, { transform: "perspective(900px) rotateX(90deg)" }], { duration: 300, delay: 980 + order * 45, easing: "cubic-bezier(.6,0,.7,.3)", fill: "forwards" });
      tiles.push(t);
    }
    setTimeout(() => { next.style.visibility = ""; prev.style.visibility = "hidden"; }, 960);
    env.enter(next, 1100);
    setTimeout(() => { tiles.forEach((t) => t.remove()); prev.style.visibility = ""; done(); }, 980 + (C + Rw) * 45 + 320);
  },

  // Poussée : une grande capsule rouge pousse l'ancienne slide hors champ, en perspective
  push(env, prev, next, dir, done) {
    env.stage.classList.add("persp");
    const bar = fx(env.layer, "push-bar");
    const ease = "cubic-bezier(.75,0,.25,1)";
    prev.animate([{ transform: "none" }, { transform: `translateX(${-dir * 100}%) rotateY(${dir * 18}deg) scale(.86)` }], { duration: 1050, easing: ease, fill: "forwards" });
    next.animate([{ transform: `translateX(${dir * 100}%) rotateY(${-dir * 18}deg) scale(.86)` }, { transform: "none" }], { duration: 1050, easing: ease });
    bar.animate({ transform: dir > 0 ? ["translateX(1920px)", "translateX(-140px)"] : ["translateX(-140px)", "translateX(1920px)"] }, { duration: 1050, easing: ease })
      .finished.then(() => { bar.remove(); env.stage.classList.remove("persp"); done(); });
    env.enter(next, 650);
  },

  // Un TER 3D grandeur écran passe de profil, tout près, et découvre la slide derrière sa queue
  ter3d(env, prev, next, dir, done, fast) {
    if (!deck3d) return TRANSITIONS.train(env, prev, next, dir, done, fast);
    [...prev.querySelectorAll("[data-in]")].forEach((el, i) => el.animate(
      { opacity: [1, 0], transform: ["none", `translateX(${dir * 140}px)`] },
      { duration: 420, delay: Math.min(i * 18, 260), easing: "ease-in", fill: "forwards" }));
    next.classList.add("revealing");
    next.classList.toggle("rev-right", dir < 0);
    next.style.clipPath = dir > 0 ? `inset(0 ${W}px 0 0)` : `inset(0 0 0 ${W}px)`;
    env.enter(next, 1000);
    deck3d.transition(env.layer, "ter3d", dir, {
      onReveal(rev) { next.style.clipPath = dir > 0 ? `inset(0 ${W - rev}px 0 0)` : `inset(0 0 0 ${W - rev}px)`; },
      done() { next.style.clipPath = ""; next.classList.remove("revealing", "rev-right"); done(); },
    });
  },

  // Un TER 3D fonce vers la caméra, remplit l'écran : la slide change derrière lui
  "ter3d-front"(env, prev, next, dir, done, fast) {
    if (!deck3d) return TRANSITIONS.zoom(env, prev, next, dir, done, fast);
    next.style.visibility = "hidden";
    prev.animate([{ transform: "scale(1)" }, { transform: "scale(1.08)" }], { duration: 1200, easing: "ease-in", fill: "forwards" });
    env.enter(next, 1250);
    deck3d.transition(env.layer, "front", dir, {
      onCover() { next.style.visibility = ""; prev.style.visibility = "hidden"; },
      done() { prev.style.visibility = ""; done(); },
    });
  },
};
