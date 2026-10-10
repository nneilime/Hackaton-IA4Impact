import { fmtDate } from "../api";
import { ErrorBox, Loading, useFetch } from "../components/ui";

export default function Audit() {
  const { data, error } = useFetch<any[]>("/api/audit?limit=500");
  if (error) return <ErrorBox e={error} />;
  if (!data) return <Loading />;
  return <>
    <div className="page-head"><div><h1>Journal d'audit</h1><p>Actions sensibles horodatées : connexions, consultations de dossiers, décisions, corrections, exports. Les données personnelles ne sont pas recopiées dans le journal.</p></div></div>
    <div className="panel"><div className="table-wrap" style={{ maxHeight: "calc(100vh - 200px)" }}><table className="data">
      <thead><tr><th>Date</th><th>Utilisateur</th><th>Action</th><th>Cible</th><th>Détails</th></tr></thead>
      <tbody>{data.map(r => <tr key={r.id}><td className="nowrap">{fmtDate(r.ts)}</td><td>{r.username}</td><td className="mono small">{r.action}</td><td className="mono small">{r.target || "—"}</td>
        <td className="small mono" style={{ maxWidth: 520, wordBreak: "break-word" }}>{r.details ? JSON.stringify(r.details) : ""}</td></tr>)}</tbody></table></div></div>
  </>;
}
