import { useState } from "react";

const SERIES = "#2a78d6";
export const STATUS_COLORS: Record<string, string> = {
  CONFORME: "#16a34a", ANOMALIE: "#dc2626", NON_VERIFIABLE: "#6b7280", NON_APPLICABLE: "#d4d9de", ERREUR_TECHNIQUE: "#f59e0b",
};

function Tip({ t }: { t: { x: number; y: number; text: string } | null }) {
  if (!t) return null;
  return <div className="tip" style={{ left: t.x + 12, top: t.y + 12 }}>{t.text}</div>;
}

/** Barres horizontales, une seule série (le titre de la carte nomme la série). */
export function HBar({ data, unit = "", onClick, fmt }: { data: { label: string; value: number; sub?: string; key?: string }[]; unit?: string; onClick?: (k: string) => void; fmt?: (v: number) => string }) {
  const [tip, setTip] = useState<any>(null);
  const max = Math.max(1, ...data.map(d => d.value));
  const rowH = 26, labelW = 200, w = 600, barW = w - labelW - 60;
  const f = fmt || ((v: number) => `${v}${unit}`);
  return <div className="chart">
    <svg viewBox={`0 0 ${w} ${data.length * rowH + 6}`} width="100%" role="img" aria-label="Diagramme en barres">
      {data.map((d, i) => {
        const y = i * rowH + 4, bw = Math.max(d.value > 0 ? 3 : 0, (d.value / max) * barW);
        return <g key={d.label} style={{ cursor: onClick ? "pointer" : "default" }}
          onClick={() => onClick?.(d.key || d.label)}
          onMouseMove={e => setTip({ x: e.clientX, y: e.clientY, text: `${d.label}${d.sub ? " — " + d.sub : ""} : ${f(d.value)}` })}
          onMouseLeave={() => setTip(null)}>
          <rect x={0} y={y - 2} width={w} height={rowH} fill="transparent" />
          <text x={labelW - 8} y={y + 13} textAnchor="end" fontSize="12" fill="#4a5864">{d.label}</text>
          <rect x={labelW} y={y + 3} width={bw} height={14} rx={3} fill={SERIES} />
          <text x={labelW + bw + 6} y={y + 14} fontSize="12" fill="#1d2a33">{f(d.value)}</text>
        </g>;
      })}
      <line x1={labelW} x2={labelW} y1={0} y2={data.length * rowH + 4} stroke="#c9d0d6" />
    </svg>
    <Tip t={tip} />
  </div>;
}

/** Barres empilées par statut (chaque segment séparé par un liseré de 2 px). */
export function StatusStack({ rows, onClick }: { rows: { key: string; label: string; counts: Record<string, number> }[]; onClick?: (k: string) => void }) {
  const [tip, setTip] = useState<any>(null);
  const order = ["ANOMALIE", "NON_VERIFIABLE", "ERREUR_TECHNIQUE", "CONFORME", "NON_APPLICABLE"];
  const names: Record<string, string> = { CONFORME: "Conforme", ANOMALIE: "Anomalie", NON_VERIFIABLE: "Non vérifiable", NON_APPLICABLE: "Non applicable", ERREUR_TECHNIQUE: "Erreur technique" };
  const total = Math.max(1, ...rows.map(r => Object.values(r.counts).reduce((a, b) => a + b, 0)));
  const rowH = 22, labelW = 56, w = 560, barW = w - labelW - 90;
  return <div className="chart">
    <div className="legend">{order.map(s => <span key={s}><i style={{ background: STATUS_COLORS[s] }} />{names[s]}</span>)}</div>
    <svg viewBox={`0 0 ${w} ${rows.length * rowH + 4}`} width="100%" role="img" aria-label="Résultats par règle">
      {rows.map((r, i) => {
        let x = labelW; const y = i * rowH + 2;
        const an = r.counts.ANOMALIE || 0, nv = r.counts.NON_VERIFIABLE || 0;
        return <g key={r.key} style={{ cursor: onClick ? "pointer" : "default" }} onClick={() => onClick?.(r.key)}>
          <text x={labelW - 8} y={y + 13} textAnchor="end" fontSize="11.5" fontFamily="IBM Plex Mono, monospace" fill="#232c73">{r.key}</text>
          {order.map(s => {
            const n = r.counts[s] || 0; if (!n) return null;
            const ww = (n / total) * barW; const el = <rect key={s} x={x} y={y + 3} width={Math.max(1, ww - 2)} height={13} rx={2} fill={STATUS_COLORS[s]}
              onMouseMove={e => setTip({ x: e.clientX, y: e.clientY, text: `${r.key} ${r.label} — ${names[s]} : ${n}` })} onMouseLeave={() => setTip(null)} />;
            x += ww; return el;
          })}
          <text x={labelW + barW + 6} y={y + 13} fontSize="11.5" fill="#4a5864">{an ? `${an} anom.` : ""}{an && nv ? " · " : ""}{nv ? `${nv} n.v.` : ""}</text>
        </g>;
      })}
    </svg>
    <Tip t={tip} />
  </div>;
}
