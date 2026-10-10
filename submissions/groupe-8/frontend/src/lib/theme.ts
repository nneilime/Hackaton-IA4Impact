// Bridges the CSS variables of tokens.css to the map (deck.gl arrays, MapLibre strings).
export type RGBA = [number, number, number, number];

const NAMES = [
  'blue',
  'bg',
  'surface',
  'tag',
  'selected',
  'line',
  'text',
  'green',
  'teal',
  'yellow',
  'waiting',
  'critical',
  'green-text',
  'waiting-text',
  'blue-muted',
] as const;
export type Token = (typeof NAMES)[number];

function readVar(name: string): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  if (v.startsWith('var(')) return readVar(v.slice(4, -1).trim());
  return v;
}

let cache: Record<Token, string> | null = null;

export function palette(): Record<Token, string> {
  if (!cache) cache = Object.fromEntries(NAMES.map((n) => [n, readVar(`--${n}`) || '#000000'])) as Record<Token, string>;
  return cache;
}

export function rgba(hex: string, a = 255): RGBA {
  const h = hex.replace('#', '');
  const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h;
  const n = parseInt(full, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255, a];
}
