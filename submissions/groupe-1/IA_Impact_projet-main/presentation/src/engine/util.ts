// Constantes et petites fonctions partagées par le moteur d'animation.

/** Scène fixe, mise à l'échelle de l'écran */
export const W = 1920;
export const H = 1080;

export const NAVY = "#0f2149";
export const RED = "#c90c0f";
export const YELLOW = "#ffd500";
export const WHITE = "#ffffff";
export const COLORS = { red: RED, yellow: YELLOW, navy: NAVY, white: WHITE, navy2: "#1d3166" } as const;
export type ColorName = keyof typeof COLORS;

export const EASE = "cubic-bezier(.2,.8,.2,1)";
export const BACK = "cubic-bezier(.34,1.56,.64,1)";
export const IO3 = "cubic-bezier(.65,0,.35,1)";

export const SVGNS = "http://www.w3.org/2000/svg";

export const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Option d'URL : `?lite` retire les scènes WebGL (si une machine rame pendant la présentation) */
export const FLAGS = {
  lite: /[?&]lite\b/.test(location.search),
};

export const fmtInt = new Intl.NumberFormat("fr-FR");
export const fmtMin = (m: number) =>
  m < 60 ? `${Math.round(m)} min` : `${Math.floor(m / 60)} h ${String(Math.round(m % 60)).padStart(2, "0")}`;
/** « Toulouse Matabiau » → « Toulouse » */
export const short = (name: string) => name.replace(/ (Ville|Centre|Matabiau|Saint-Roch)$/, "");
export const rand = (a: number, b: number) => a + Math.random() * (b - a);
export const easeIO = (p: number) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);

/** Typographie française : espaces insécables avant : ? ! ; » et après « */
export const typo = (s: string) => s.replace(/ ([:?!;»])/g, " $1").replace(/« /g, "« ");
/** Pour dangerouslySetInnerHTML : les textes contiennent <em> et <b>, écrits par nous */
export const html = (s: string) => ({ __html: typo(s) });

/** animate() avec les réglages par défaut du diapo (remplissage, courbe douce) */
export const A = (el: Element, kf: Keyframe[] | PropertyIndexedKeyframes, o: KeyframeAnimationOptions) =>
  el.animate(kf, { fill: "both", easing: EASE, ...o });

export const $ = <E extends Element = HTMLElement>(root: ParentNode, sel: string) => {
  const el = root.querySelector<E>(sel);
  if (!el) throw new Error(`Élément introuvable : ${sel}`);
  return el;
};
export const $$ = <E extends Element = HTMLElement>(root: ParentNode, sel: string) => [...root.querySelectorAll<E>(sel)];
