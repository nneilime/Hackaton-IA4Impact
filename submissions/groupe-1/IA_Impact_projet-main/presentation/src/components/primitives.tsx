// Briques visuelles du diapo : titre découpé en mots, trame de capsules, icônes.
import type { ElementType, HTMLAttributes } from "react";
import { COLORS, typo, type ColorName } from "../engine/util";

type DataAttrs = { [K in `data-${string}`]?: string | number };

/** Titre dont chaque mot sort de son masque (entrée « words »). Le texte peut contenir des <em> */
export function Words({ text, as: Tag = "h2", ...rest }: { text: string; as?: ElementType } & HTMLAttributes<HTMLElement> & DataAttrs) {
  const words = (s: string, key: string) =>
    s.split(/( +)/).filter(Boolean).map((p, i) => (/^ +$/.test(p) ? p : <span className="w" key={key + i}><span className="wi">{p}</span></span>));
  const parts = typo(text).split(/(<em>.*?<\/em>)/).filter(Boolean);
  return (
    <Tag data-in="words" {...rest}>
      {parts.map((p, i) => (p.startsWith("<em>") ? <em key={i}>{words(p.slice(4, -5), `e${i}-`)}</em> : words(p, `t${i}-`)))}
    </Tag>
  );
}

/** Trame de capsules et de points (même dessin que le composant Trame du site), pseudo-aléatoire répétable */
export function Trame({ rows, cols, palette, className = "trame", ...rest }: { rows: number; cols: number; palette: ColorName[]; className?: string } & DataAttrs) {
  let seed = rows * 97 + cols;
  const rng = () => (seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296;
  const unit = 10, gap = 6, step = unit + gap, rects: JSX.Element[] = [];
  for (let r = 0; r < rows; r++) {
    let c = Math.floor(rng() * 3);
    while (c < cols) {
      const roll = rng();
      const len = roll < 0.45 ? 1 : roll < 0.75 ? 3 : roll < 0.92 ? 5 : 7;
      if (c + len > cols) break;
      const color = COLORS[palette[Math.floor(rng() * palette.length)]];
      rects.push(<rect key={rects.length} x={c * (unit + 2)} y={r * step} width={len * (unit + 2) - 2} height={unit} rx={5} fill={color} />);
      c += len + 1 + (rng() < 0.25 ? 1 : 0);
    }
  }
  return (
    <div className={className} {...rest}>
      <svg viewBox={`0 0 ${cols * (unit + 2)} ${rows * step}`} aria-hidden="true">{rects}</svg>
    </div>
  );
}

const ICONS = {
  route: <><circle cx="10" cy="38" r="5" /><circle cx="38" cy="10" r="5" /><path d="M10 33V22a8 8 0 0 1 8-8h12" /><path d="M24 8l6 6-6 6" /></>,
  pin: <><path d="M24 44s14-13 14-24a14 14 0 0 0-28 0c0 11 14 24 14 24z" /><circle cx="24" cy="20" r="5" /></>,
  train: <><rect x="10" y="6" width="28" height="30" rx="7" /><path d="M10 24h28M17 14h14" /><circle cx="17" cy="30" r="1.5" /><circle cx="31" cy="30" r="1.5" /><path d="M15 36l-5 7M33 36l5 7" /></>,
  photo: <><path d="M6 40l12-18 8 10 6-8 10 16z" /><circle cx="34" cy="11" r="5" /></>,
  cube: <><path d="M8 16l16-8 16 8v16l-16 8-16-8z" /><path d="M8 16l16 8 16-8M24 24v16" /></>,
  code: <path d="M16 10l-8 14 8 14M32 10l8 14-8 14M27 8l-6 32" />,
  bolt: <path d="M27 4L10 28h13l-2 16 17-24H25z" />,
  map: <><path d="M6 12l12-5 12 5 12-5v29l-12 5-12-5-12 5z" /><path d="M18 7v29M30 12v29" /></>,
  window: <><rect x="6" y="8" width="36" height="28" rx="9" /><path d="M6 28l10-9 8 7 6-5 12 9" /><circle cx="32" cy="17" r="3" /></>,
  school: <><path d="M4 18l20-10 20 10-20 10z" /><path d="M12 22v10c4 4 20 4 24 0V22M44 18v12" /></>,
  chat: <><path d="M8 10h32a4 4 0 0 1 4 4v16a4 4 0 0 1-4 4H22l-10 8v-8H8a4 4 0 0 1-4-4V14a4 4 0 0 1 4-4z" /><path d="M14 22h.01M24 22h.01M34 22h.01" /></>,
  ter: <><rect x="10" y="6" width="28" height="30" rx="7" /><path d="M10 24h28M17 14h14M15 36l-5 7M33 36l5 7" /></>,
};

export function Icon({ name, className }: { name: keyof typeof ICONS; className?: string }) {
  return <svg className={className} viewBox="0 0 48 48">{ICONS[name]}</svg>;
}
