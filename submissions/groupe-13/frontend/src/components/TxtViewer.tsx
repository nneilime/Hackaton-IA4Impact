import { useEffect, useMemo, useRef } from "react";

interface Rec { line_no: number; raw: string; kind: string; label: string; length: number; fields: Record<string, any>; issues: string[] }
export interface Hl { line_no: number; start?: number; end?: number; label?: string }

function ruler(n: number) {
  const a = Array(n).fill("·");
  for (let i = 5; i <= n; i += 5) a[i - 1] = "+";
  for (let i = 10; i <= n; i += 10) { const s = String(i); for (let k = 0; k < s.length; k++) a[i - s.length + k] = s[k]; }
  return a.join("");
}

export default function TxtViewer({ records, highlights, focusLine, badLines = [] }: { records: Rec[]; highlights: Hl[]; focusLine?: number | null; badLines?: number[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const maxLen = Math.max(...records.map(r => r.length), 128);
  useEffect(() => {
    if (!focusLine || !ref.current) return;
    const el = ref.current.querySelector(`[data-line="${focusLine}"]`) as HTMLElement | null;
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [focusLine, highlights]);

  const lines = useMemo(() => records.map(r => {
    // marques : champs du cahier des charges (discret) + éléments du contrôle sélectionné (ocre)
    const marks: { s: number; e: number; cls: string; title: string }[] = [];
    Object.values(r.fields || {}).forEach((f: any) => marks.push({ s: f.start, e: f.end, cls: "fld", title: `${f.name} (pos. ${f.start}-${f.end})` }));
    highlights.filter(h => h.line_no === r.line_no && h.start && h.end).forEach(h =>
      marks.push({ s: h.start!, e: h.end!, cls: "", title: `${h.label || ""} (pos. ${h.start}-${h.end})` }));
    const hit = highlights.some(h => h.line_no === r.line_no);
    // segmentation
    const cuts = new Set<number>([0, r.raw.length]);
    marks.forEach(m => { cuts.add(Math.min(r.raw.length, m.s - 1)); cuts.add(Math.min(r.raw.length, m.e)); });
    const pts = [...cuts].sort((a, b) => a - b);
    const segs: JSX.Element[] = [];
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i], b = pts[i + 1]; if (b <= a) continue;
      const txt = r.raw.slice(a, b);
      const m = marks.filter(m => m.s - 1 <= a && m.e >= b);
      const focus = m.find(x => x.cls === "");
      const fld = m.find(x => x.cls === "fld");
      if (focus) segs.push(<mark key={i} title={focus.title}>{txt}</mark>);
      else if (fld) segs.push(<mark key={i} className="fld" title={fld.title}>{txt}</mark>);
      else segs.push(<span key={i}>{txt}</span>);
    }
    return { r, hit, segs };
  }), [records, highlights]);

  return <div ref={ref} className="txt txt-scroll" style={{ flex: 1 }}>
    <div className="ruler"><span className="no">pos.</span><span className="ty" />{ruler(maxLen)}</div>
    {lines.map(({ r, hit, segs }) =>
      <div key={r.line_no} data-line={r.line_no}
        className={`ln ${hit ? "hit" : ""} ${badLines.includes(r.line_no) ? "badline" : ""}`}
        title={`Ligne ${r.line_no} — ${r.label} — ${r.length} caractères${r.issues.length ? " — " + r.issues.join(" ; ") : ""}`}>
        <span className="no">{r.line_no}</span><span className="ty">{r.kind}</span>{segs}
      </div>)}
  </div>;
}
