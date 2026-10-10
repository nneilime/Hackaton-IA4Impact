import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { STATUS_LABEL, RuleStatus } from "../api";

export interface VBox { id: string; box: number[]; label?: string; cls?: string; title?: string }
export interface View { s: number; x: number; y: number }
/** Zone CERFA superposée au bordereau : couleur = statut de conformité (jamais remplacée par la sélection). */
export interface ZoneOverlay { id: string; label: string; status: RuleStatus; regions: { box: number[]; label?: string }[]; flags?: string[] }

interface Props {
  src: string;
  size: [number, number];            // taille naturelle de l'image
  boxes?: VBox[];
  focusId?: string | null;
  onBoxClick?: (id: string) => void;
  view?: View; onView?: (v: View) => void;   // contrôle externe (synchronisation)
  showBoxes?: boolean;
  overlaySrc?: string | null; overlayOpacity?: number;
  zones?: ZoneOverlay[]; showZones?: boolean; onToggleZones?: (v: boolean) => void;
  selectedZone?: string | null; onZoneClick?: (id: string) => void;
  focusRect?: { box: number[]; n: number } | null;   // cadrage demandé (n change à chaque demande)
  rotate180?: boolean;
  legend?: boolean;
  /** Mode simple : zones conformes et sans objet affichées discrètement (sans badge), problèmes mis en avant. */
  quiet?: boolean;
}

const ICON: Record<string, string> = { CONFORME: "✓", ANOMALIE: "!", NON_VERIFIABLE: "?", NON_APPLICABLE: "–", ERREUR_TECHNIQUE: "×" };
// badges placés sous la zone lorsque l'espace au-dessus est occupé par une zone voisine
const BADGE_BELOW = new Set(["Z4", "Z8", "Z13"]);
const ORDER: RuleStatus[] = ["CONFORME", "ANOMALIE", "NON_VERIFIABLE", "NON_APPLICABLE", "ERREUR_TECHNIQUE"];

export function bboxOf(regions: { box: number[] }[]): number[] | null {
  if (!regions.length) return null;
  return [Math.min(...regions.map(r => r.box[0])), Math.min(...regions.map(r => r.box[1])),
    Math.max(...regions.map(r => r.box[2])), Math.max(...regions.map(r => r.box[3]))];
}

export default function ImageViewer({ src, size, boxes = [], focusId, onBoxClick, view, onView, showBoxes = true, overlaySrc, overlayOpacity = 0.5,
  zones = [], showZones = true, onToggleZones, selectedZone, onZoneClick, focusRect, rotate180, legend = false, quiet = false }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [local, setLocal] = useState<View>({ s: 0.5, x: 0, y: 0 });
  const v = view ?? local;
  const setV = useCallback((nv: View) => { onView ? onView(nv) : setLocal(nv); }, [onView]);
  const drag = useRef<{ x: number; y: number; v: View } | null>(null);
  const [dragging, setDragging] = useState(false);

  const fit = useCallback(() => {
    const el = ref.current; if (!el) return;
    const s = Math.min(el.clientWidth / size[0], el.clientHeight / size[1]) * 0.98;
    setV({ s, x: (el.clientWidth - size[0] * s) / 2, y: 6 });
  }, [size, setV]);

  const frame = useCallback((box: number[], maxScale = 2) => {
    const el = ref.current; if (!el) return;
    const [x0, y0, x1, y1] = box;
    const bw = Math.max(40, x1 - x0), bh = Math.max(20, y1 - y0);
    // la zone occupe au plus 80 % de la visionneuse, zoom limité pour rester lisible et ne pas pixelliser
    const s = Math.min(maxScale, Math.max(0.2, Math.min(el.clientWidth * 0.8 / bw, el.clientHeight * 0.75 / bh)));
    setV({ s, x: el.clientWidth / 2 - (x0 + bw / 2) * s, y: el.clientHeight / 2 - (y0 + bh / 2) * s });
  }, [setV]);

  useLayoutEffect(() => { if (!view) fit(); }, [src]); // eslint-disable-line

  // zoom sur la boîte sélectionnée
  useEffect(() => {
    if (!focusId) return;
    const b = boxes.find(x => x.id === focusId); const el = ref.current;
    if (!b || !el) return;
    const [x0, y0, x1, y1] = b.box;
    const bw = Math.max(40, x1 - x0), bh = Math.max(20, y1 - y0);
    const s = Math.min(2, Math.max(0.3, Math.min(el.clientWidth * 0.5 / bw, el.clientHeight * 0.5 / bh)));
    setV({ s, x: el.clientWidth / 2 - (x0 + bw / 2) * s, y: el.clientHeight / 2 - (y0 + bh / 2) * s });
  }, [focusId]); // eslint-disable-line

  useEffect(() => { if (focusRect?.box) frame(focusRect.box); }, [focusRect?.n]); // eslint-disable-line

  const onWheel = (e: React.WheelEvent) => {
    const el = ref.current; if (!el) return;
    const r = el.getBoundingClientRect();
    const mx = e.clientX - r.left, my = e.clientY - r.top;
    const f = Math.exp(-e.deltaY * 0.0015);
    const s = Math.min(6, Math.max(0.15, v.s * f));
    setV({ s, x: mx - (mx - v.x) * (s / v.s), y: my - (my - v.y) * (s / v.s) });
  };
  const onDown = (e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest(".box, .zbox, .viewer-legend")) return;
    drag.current = { x: e.clientX, y: e.clientY, v }; setDragging(true);
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
  };
  const onMove = (e: React.PointerEvent) => {
    if (!drag.current) return;
    const d = drag.current;
    setV({ ...d.v, x: d.v.x + e.clientX - d.x, y: d.v.y + e.clientY - d.y });
  };
  const onUp = () => { drag.current = null; setDragging(false); };
  const zoom = (f: number) => {
    const el = ref.current; if (!el) return;
    const mx = el.clientWidth / 2, my = el.clientHeight / 2;
    const s = Math.min(6, Math.max(0.15, v.s * f));
    setV({ s, x: mx - (mx - v.x) * (s / v.s), y: my - (my - v.y) * (s / v.s) });
  };
  const bw = 2.2 / v.s;                       // bordure de ~2,2 px à l'écran quel que soit le zoom
  const sel = zones.find(z => z.id === selectedZone);
  const selBox = sel ? bboxOf(sel.regions) : null;
  const pad = 6 / v.s;

  return <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
    <div className="pane-head" style={{ justifyContent: "flex-end" }}>
      <div className="viewer-tools">
        <button className="btn small" onClick={() => zoom(1 / 1.25)} aria-label="Dézoomer">−</button>
        <span className="zoomval">{Math.round(v.s * 100)} %</span>
        <button className="btn small" onClick={() => zoom(1.25)} aria-label="Zoomer">+</button>
        <button className="btn small" onClick={fit}>Ajuster</button>
      </div>
    </div>
    <div ref={ref} className={`viewer ${dragging ? "dragging" : ""}`} onWheel={onWheel}
      onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerLeave={onUp} data-testid="viewer">
      <div className="stage" style={{ transform: `translate(${v.x}px, ${v.y}px) scale(${v.s})`, width: size[0], height: size[1] }}>
        <img src={src} width={size[0]} height={size[1]} alt="Bordereau de facturation" draggable={false}
          style={rotate180 ? { transform: "rotate(180deg)" } : undefined} />
        {overlaySrc && <img src={overlaySrc} width={size[0]} height={size[1]} alt="" draggable={false}
          style={{ position: "absolute", left: 0, top: 0, opacity: overlayOpacity, mixBlendMode: "multiply" }} />}
        {showZones && zones.flatMap(z => z.regions.map((r, i) => ({ z, r, i })))
          // les grandes régions d'abord : une zone incluse dans une autre (Z9 dans Z10) reste cliquable
          .sort((p, q) => (q.r.box[2] - q.r.box[0]) * (q.r.box[3] - q.r.box[1]) - (p.r.box[2] - p.r.box[0]) * (p.r.box[3] - p.r.box[1]))
          .map(({ z, r, i }) => {
          const [x0, y0, x1, y1] = r.box;
          const isSel = z.id === selectedZone;
          const isQuiet = quiet && !isSel && (z.status === "CONFORME" || z.status === "NON_APPLICABLE");
          return <div key={`${z.id}-${i}`} className={`zbox ${z.status} ${isSel ? "sel" : ""} ${isQuiet ? "quiet" : ""}`} data-zone={z.id} data-status={z.status}
            role="button" tabIndex={i === 0 ? 0 : -1}
            aria-label={`Zone ${z.id.slice(1)} — ${z.label} — ${STATUS_LABEL[z.status]}`}
            title={`${z.id} — ${z.label}${r.label && r.label !== z.label ? ` (${r.label})` : ""} — ${STATUS_LABEL[z.status]}${z.flags?.includes("controles_egalement_incertains") ? " — contrôles également incertains" : ""}`}
            style={{ left: x0, top: y0, width: Math.max(4, x1 - x0), height: Math.max(4, y1 - y0), borderWidth: isQuiet ? bw * 0.5 : bw }}
            onClick={e => { e.stopPropagation(); onZoneClick?.(z.id); }}
            onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onZoneClick?.(z.id); } }}>
            {i === 0 && !isQuiet && <span className={`zbadge ${z.status}`} style={BADGE_BELOW.has(z.id)
              ? { transform: `scale(${1 / v.s})`, transformOrigin: "0 0", top: "100%", borderRadius: "0 3px 3px 3px" }
              : { transform: `scale(${1 / v.s})`, top: -17 / v.s }}>
              <span aria-hidden="true">{ICON[z.status]}</span>{z.id}{z.flags?.includes("controles_egalement_incertains") ? " ?" : ""}</span>}
          </div>;
        })}
        {showZones && selBox && <div className="zfocus" style={{ left: selBox[0] - pad, top: selBox[1] - pad, width: selBox[2] - selBox[0] + 2 * pad, height: selBox[3] - selBox[1] + 2 * pad }} />}
        {showBoxes && boxes.map(b => {
          const [x0, y0, x1, y1] = b.box;
          return <div key={b.id} className={`box ${b.cls || ""} ${focusId === b.id ? "focus" : ""}`}
            title={b.title || b.label}
            style={{ left: x0, top: y0, width: Math.max(4, x1 - x0), height: Math.max(4, y1 - y0), borderWidth: 1.5 / v.s }}
            onClick={() => onBoxClick?.(b.id)}>
            {b.label && (focusId === b.id) && <span className="lbl" style={{ transform: `scale(${1 / v.s})`, transformOrigin: "0 100%", top: -17 / v.s }}>{b.label}</span>}
          </div>;
        })}
      </div>
    </div>
      {legend && <div className="viewer-legend" aria-label="Légende des encadrements">
        {ORDER.map(s => <span key={s}><i className={`sw ${s}`} />{STATUS_LABEL[s]}</span>)}
        {onToggleZones && <button className="btn small" onClick={() => onToggleZones(!showZones)}>{showZones ? "Masquer" : "Afficher"} les encadrements</button>}
      </div>}
  </div>;
}
