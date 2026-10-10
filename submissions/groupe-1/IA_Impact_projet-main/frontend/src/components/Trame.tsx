// La « trame » de la charte liO : des rangées de capsules (traits à bouts ronds)
// et de points, qui évoquent le mouvement d'une ligne à l'autre. Rouge, jaune,
// marine ou blanc selon le fond. Pseudo-aléatoire stable : même dessin à chaque rendu.

type Props = { rows?: number; columns?: number; palette?: string[]; className?: string };

function rng(seed: number) {
  return () => {
    seed = (seed * 1664525 + 1013904223) % 4294967296;
    return seed / 4294967296;
  };
}

export default function Trame({ rows = 6, columns = 22, palette = ["var(--red)", "var(--yellow)"], className }: Props) {
  const unit = 10; // diamètre d'un point = épaisseur d'une capsule
  const gap = 6;
  const rand = rng(rows * 97 + columns);
  const shapes: { x: number; y: number; len: number; color: string }[] = [];

  for (let r = 0; r < rows; r++) {
    let c = Math.floor(rand() * 3); // départ décalé : bord gauche irrégulier
    while (c < columns) {
      const roll = rand();
      const len = roll < 0.45 ? 1 : roll < 0.75 ? 3 : roll < 0.92 ? 5 : 7; // 1 = point
      if (c + len > columns) break;
      shapes.push({ x: c, y: r, len, color: palette[Math.floor(rand() * palette.length)] });
      c += len + 1 + (rand() < 0.25 ? 1 : 0);
    }
  }

  const step = unit + gap;
  const W = columns * (unit + 2);
  const H = rows * step;
  return (
    <svg className={className} viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
      {shapes.map((s, i) => (
        <rect
          key={i}
          x={s.x * (unit + 2)}
          y={s.y * step}
          width={s.len * (unit + 2) - 2}
          height={unit}
          rx={unit / 2}
          fill={s.color}
        />
      ))}
    </svg>
  );
}
