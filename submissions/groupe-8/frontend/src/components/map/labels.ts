// Screen-space label placement: highest priority first, each label tries a few anchors
// and is dropped (unless forced) when every anchor overlaps something already placed.
import type { RGBA } from '../../lib/theme';

export type Anchor = 'center' | 'below' | 'above' | 'right' | 'left';
export type LabelLine = { text: string; size: number; bold: boolean; color: RGBA };
export type LabelSpec = {
  id: string;
  lon: number;
  lat: number;
  lines: LabelLine[];
  /** Shorter fallback tried when no anchor fits the full lines. */
  fallback?: LabelLine[];
  priority: number;
  anchors: Anchor[];
  gap?: number;
  force?: boolean;
};
export type PlacedLine = LabelLine & { lon: number; lat: number; offset: [number, number] };
export type Rect = { x0: number; y0: number; x1: number; y1: number };

const LINE_H = 1.18;
const textWidth = (l: LabelLine) => l.text.length * l.size * (l.bold ? 0.64 : 0.55);

const overlaps = (a: Rect, b: Rect) => a.x0 < b.x1 && a.x1 > b.x0 && a.y0 < b.y1 && a.y1 > b.y0;

export function placeLabels(
  specs: LabelSpec[],
  project: (lon: number, lat: number) => { x: number; y: number },
  size: { width: number; height: number },
  obstacles: Rect[],
): PlacedLine[] {
  const taken: Rect[] = [...obstacles];
  const out: PlacedLine[] = [];
  for (const spec of [...specs].sort((a, b) => b.priority - a.priority)) {
    const variants = spec.fallback ? [spec, { ...spec, lines: spec.fallback, fallback: undefined }] : [spec];
    for (const s of variants) {
      if (placeOne(s)) break;
    }
  }
  return out;

  function placeOne(s: LabelSpec): boolean {
    const p = project(s.lon, s.lat);
    if (p.x < -50 || p.y < -50 || p.x > size.width + 50 || p.y > size.height + 50) return true;
    const w = Math.max(...s.lines.map(textWidth));
    const h = s.lines.reduce((sum, l) => sum + l.size * LINE_H, 0);
    const g = s.gap ?? 9;
    const boxAt = (a: Anchor): { left: number; top: number } => {
      switch (a) {
        case 'center':
          return { left: -w / 2, top: -h / 2 };
        case 'below':
          return { left: -w / 2, top: g };
        case 'above':
          return { left: -w / 2, top: -g - h };
        case 'right':
          return { left: g, top: -h / 2 };
        case 'left':
          return { left: -g - w, top: -h / 2 };
      }
    };
    let chosen: { left: number; top: number } | null = null;
    for (const a of s.anchors) {
      const b = boxAt(a);
      const r = { x0: p.x + b.left - 2, y0: p.y + b.top - 1, x1: p.x + b.left + w + 2, y1: p.y + b.top + h + 1 };
      const inside = r.x0 >= 0 && r.y0 >= 0 && r.x1 <= size.width && r.y1 <= size.height;
      if (inside && !taken.some((t) => overlaps(t, r))) {
        chosen = b;
        taken.push(r);
        break;
      }
    }
    if (!chosen && s.force) chosen = boxAt(s.anchors[0]);
    if (!chosen) return false;
    let y = chosen.top;
    for (const l of s.lines) {
      out.push({ ...l, lon: s.lon, lat: s.lat, offset: [chosen.left + w / 2, y] });
      y += l.size * LINE_H;
    }
    return true;
  }
}
