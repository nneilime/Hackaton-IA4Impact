import { useMemo, useState } from "react";
import { CaseRow, CASE_STATUSES, euro, User } from "../api";
import { ErrorBox, Loading, go, useFetch, ZoneStrip } from "../components/ui";
import { STATUS_LABEL } from "../api";

const VERIFIED = ["Écart confirmé", "Faux positif reconnu", "Contrôle terminé", "Clôturé"];

export default function Cases({ user, params, pick }: { user: User; params: URLSearchParams; pick?: boolean }) {
  const { data, error } = useFetch<CaseRow[]>("/api/cases");
  const [q, setQ] = useState(params.get("q") || "");
  const [status, setStatus] = useState(params.get("status") || "");
  const [etat, setEtat] = useState(params.get("etat") || "");
  const [rule, setRule] = useState(params.get("regle") || "");
  const [fam, setFam] = useState("");
  const [zone, setZone] = useState(params.get("zone") || "");
  const [zst, setZst] = useState(params.get("zstatut") || "");
  const [sort, setSort] = useState<{ k: keyof CaseRow; d: number }>({ k: "id", d: 1 });

  const rows = useMemo(() => {
    if (!data) return [];
    const qq = q.trim().toLowerCase();
    return data.filter(c =>
      (!qq || [c.id, c.invoice_no, c.establishment, c.finess].some(x => (x || "").toLowerCase().includes(qq))) &&
      (!status || (status === "verifies" ? VERIFIED.includes(c.status) : c.status === status)) &&
      (!etat || (etat === "anomalie" ? c.n_anomalies > 0 : etat === "nv" ? c.n_nv > 0 : c.state === etat)) &&
      (!rule || c.anomaly_rules.includes(rule)) && (!fam || c.family === fam) &&
      (!zone || !zst || (c as any).zones?.[zone] === zst) && (!zone || zst || ["ANOMALIE", "NON_VERIFIABLE", "ERREUR_TECHNIQUE"].includes((c as any).zones?.[zone]))
    ).sort((a, b) => {
      const x = a[sort.k] as any, y = b[sort.k] as any;
      return (x > y ? 1 : x < y ? -1 : 0) * sort.d;
    });
  }, [data, q, status, etat, rule, fam, sort, zone, zst]);

  if (error) return <ErrorBox e={error} />;
  if (!data) return <Loading />;
  const th = (k: keyof CaseRow, l: string, num = false) =>
    <th className={`sortable ${num ? "num" : ""}`} onClick={() => setSort({ k, d: sort.k === k ? -sort.d : 1 })}
      aria-sort={sort.k === k ? (sort.d > 0 ? "ascending" : "descending") : "none"}>{l}{sort.k === k ? (sort.d > 0 ? " ▲" : " ▼") : ""}</th>;
  const fams = [...new Set(data.map(c => c.family))];
  const rules = [...new Set(data.flatMap(c => c.anomaly_rules))].sort();

  return <>
    <div className="page-head">
      <div><h1>{pick ? "Choisir un dossier à contrôler" : "Tous les dossiers"}</h1>
        <p>{rows.length} dossier(s) sur {data.length}. Les montants sont ceux du fichier TXT (TotalPrestations + TotalHonoraires).
          {user.role === "agent" && " Vous voyez les dossiers non affectés et ceux qui vous sont affectés."}</p></div>
    </div>
    <div className="panel">
      <div className="pane-head">
        <input className="input" placeholder="Filtrer : dossier, facture, établissement, FINESS" value={q} onChange={e => setQ(e.target.value)} style={{ minWidth: 280 }} />
        <select className="input" value={status} onChange={e => setStatus(e.target.value)} aria-label="Statut">
          <option value="">Tous les statuts</option>{CASE_STATUSES.map(s => <option key={s}>{s}</option>)}<option value="verifies">Déjà vérifiés</option>
        </select>
        <select className="input" value={etat} onChange={e => setEtat(e.target.value)} aria-label="Résultat">
          <option value="">Tous les résultats</option><option value="anomalie">Avec écart</option><option value="nv">Avec point à vérifier</option><option value="conforme">Aucun écart</option>
        </select>
        <details className="adv-filters" open={!!(rule || zone || fam) || undefined}><summary className="small">Plus de filtres</summary><div className="row">
        <select className="input" value={rule} onChange={e => setRule(e.target.value)} aria-label="Règle">
          <option value="">Toutes les règles</option>{rules.map(r => <option key={r}>{r}</option>)}
        </select>
        <select className="input" value={zone} onChange={e => setZone(e.target.value)} aria-label="Zone">
          <option value="">Toutes les zones</option>{Array.from({ length: 15 }, (_, i) => `Z${i + 1}`).map(z => <option key={z} value={z}>{z}{zst ? "" : " à revoir"}</option>)}
        </select>
        {zone && <select className="input" value={zst} onChange={e => setZst(e.target.value)} aria-label="Statut de la zone">
          <option value="">anomalie, non vérifiable ou erreur</option>{Object.entries(STATUS_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>}
        <select className="input" value={fam} onChange={e => setFam(e.target.value)} aria-label="Famille">
          <option value="">Toutes les familles</option>{fams.map(f => <option key={f}>{f}</option>)}
        </select>
        </div></details>
      </div>
      <div className="table-wrap" style={{ maxHeight: "calc(100vh - 230px)" }}>
        <table className="data">
          <thead><tr>{th("id", "Dossier")}{th("establishment", "Établissement")}{th("invoice_no", "N° facture")}{th("billed_cents", "Montant", true)}
            {th("n_anomalies", "Résultat")}<th>15 zones</th>{th("assigned_name", "Agent")}{th("status", "Statut")}</tr></thead>
          <tbody>
            {rows.map(c => <tr key={c.id} className="clickable" onClick={() => go(`/controle/${c.id}`)}>
              <td className="mono nowrap">{c.id}</td>
              <td>{c.establishment}<div className="hint">FINESS {c.finess}</div></td>
              <td className="mono">{c.invoice_no}</td>
              <td className="num nowrap">{euro(c.billed_cents)}</td>
              <td><span className={`s-pill ${c.n_anomalies ? "bad" : c.n_nv ? "warn" : "ok"}`}>{c.n_anomalies ? `${c.n_anomalies} écart${c.n_anomalies > 1 ? "s" : ""}` : c.n_nv ? `${c.n_nv} à vérifier` : "Aucun écart"}</span>
                {c.pairing_status !== "confirmé" && <div className="hint">documents peut-être non homologues</div>}</td>
              <td><ZoneStrip zones={(c as any).zones} /></td>
              <td>{c.assigned_name || <span className="muted">—</span>}</td>
              <td><span className="case-status">{c.status}</span></td>
            </tr>)}
            {rows.length === 0 && <tr><td colSpan={8} className="empty">Aucun dossier ne correspond à ces filtres.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  </>;
}
