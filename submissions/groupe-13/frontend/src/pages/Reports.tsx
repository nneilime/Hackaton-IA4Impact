import { useState } from "react";
import { api, CaseRow, fmtDate, User } from "../api";
import { ErrorBox, Loading, useFetch, useToast } from "../components/ui";

export default function Reports({ user }: { user: User }) {
  const { data, error } = useFetch<CaseRow[]>("/api/cases");
  const corpus = useFetch<any>("/api/corpus");
  const jobs = useFetch<any[]>("/api/jobs");
  const backups = useFetch<any[]>(user.role === "admin" ? "/api/admin/backups" : null);
  const cache = useFetch<any>(user.role === "admin" || user.role === "superviseur" ? "/api/admin/cache" : null);
  const [cid, setCid] = useState("");
  const toast = useToast();
  if (error) return <ErrorBox e={error} />;
  if (!data) return <Loading />;
  const id = cid || data[0]?.id;
  const m = corpus.data?.manifest;
  return <>
    <div className="page-head"><div><h1>Rapports et exports</h1><p>Rapport de contrôle par dossier (PDF pour la revue, JSON pour l'intégration) et export tabulaire de tous les résultats. Aucune connexion au système d'information de la MSA n'est simulée.</p></div></div>
    <div className="grid cols-2">
      <section className="panel panel-pad">
        <h2>Rapport d'un dossier</h2>
        <p className="small">Références, sources et empreintes, résultat des 22 règles, anomalies avec preuves (zones du bordereau, lignes et positions du fichier), contrôles non vérifiables, écarts mesurés, observations, corrections et décisions horodatées.</p>
        <div className="row"><select className="input" value={id} onChange={e => setCid(e.target.value)}>{data.map(c => <option key={c.id}>{c.id}</option>)}</select>
          <a className="btn primary" href={`/api/cases/${id}/report.pdf`}>Télécharger le PDF</a>
          <a className="btn" href={`/api/cases/${id}/report.json`}>JSON</a></div>
      </section>
      <section className="panel panel-pad">
        <h2>Tous les résultats</h2>
        <p className="small">Une ligne par dossier et par règle (séparateur « ; », encodage UTF-8 compatible Excel).</p>
        <a className="btn primary" href="/api/export/results.csv">Télécharger le CSV</a>
        {user.role === "admin" && <div style={{ marginTop: 16 }}>
          <h3>Administration</h3>
          <div className="row">
            <button className="btn" onClick={() => api.post("/api/admin/sync").then(() => { toast("Synchronisation lancée (dossiers nouveaux ou modifiés)"); jobs.reload(); })}>Synchroniser le corpus</button>
            <button className="btn" onClick={() => api.post("/api/admin/reanalyze").then(() => { toast("Réanalyse complète lancée"); jobs.reload(); })}>Recalcul forcé de tous les dossiers</button>
            <button className="btn" onClick={() => api.post<any>("/api/admin/backup").then(b => { toast(`Sauvegarde créée et vérifiée : ${b.file}`); backups.reload(); }).catch(e => toast(e.message))}>Créer une sauvegarde</button>
            <button className="btn danger" onClick={() => { if (window.confirm("Effacer toutes les décisions, corrections, affectations et le journal ? Une sauvegarde est créée automatiquement avant l'effacement. Les comptes et les documents originaux sont conservés.")) api.post<any>("/api/admin/purge").then(r => toast(`Métadonnées effacées — sauvegarde ${r.sauvegarde.file}`)).catch(e => toast(e.message)); }}>Effacer les métadonnées de session</button>
          </div>
          {backups.data && backups.data.length > 0 && <table className="data small" style={{ marginTop: 10 }}><thead><tr><th>Sauvegarde</th><th>Motif</th><th>Intégrité</th><th>SHA-256</th></tr></thead>
            <tbody>{backups.data.slice(0, 6).map(b => <tr key={b.file}><td className="mono">{b.file}</td><td>{b.reason}</td><td>{b.verification?.ok ? "vérifiée" : "invalide"}</td><td className="mono">{b.sha256.slice(0, 16)}…</td></tr>)}</tbody></table>}
          <p className="hint">Restauration (application arrêtée) : <span className="mono">python -m sentinel.cli restore &lt;fichier&gt;</span> — la base courante est sauvegardée avant remplacement.</p>
          </div>}
      </section>
      <section className="panel panel-pad" style={{ gridColumn: "1 / -1" }}>
        <h2>Traitements</h2>
        {cache.data && <p className="small">Cache OCR : empreinte du code d'extraction <span className="mono">{cache.data.code_hash}</span> · {Object.entries(cache.data.fichiers).map(([k, v]: any) => `${v} ${k.replace("_", " ")}`).join(" · ") || "vide"} · moteurs de ce poste : RapidOCR {cache.data.engine_profile.rapidocr || "absent"}{cache.data.engine_profile.tesseract ? ` + Tesseract ${cache.data.engine_profile.tesseract}` : ", sans Tesseract"}</p>}
        {!jobs.data ? <Loading /> : jobs.data.length === 0 ? <p className="muted">Aucun traitement.</p> :
          <div className="table-wrap" style={{ maxHeight: 260 }}><table className="data small"><thead><tr><th>#</th><th>Type</th><th>Cible</th><th>Statut</th><th>Progression</th><th>Début</th><th>Durée</th><th>Résultat</th></tr></thead>
            <tbody>{jobs.data.map(j => <tr key={j.id}><td>{j.id}</td><td>{j.kind.replace("_", " ")}</td><td className="mono">{j.target}</td>
              <td>{({ en_attente: "en attente", en_cours: "en cours", termine: "terminé", erreur: "erreur", interrompu: "interrompu" } as any)[j.status] || j.status}</td>
              <td>{j.total ? `${j.progress}/${j.total}` : "—"}</td><td>{fmtDate(j.started_at || j.created_at)}</td><td>{j.duration_s ? `${j.duration_s} s` : "—"}</td>
              <td className="small">{j.error ? <span className="error-text">{j.error.split("\n")[0]}</span> : j.message || "—"}</td></tr>)}</tbody></table></div>}
      </section>
      <section className="panel panel-pad" style={{ gridColumn: "1 / -1" }}>
        <h2>Manifeste du corpus</h2>
        {!m ? <Loading /> : <>
          <p className="small">Racine {m.root} · {m.files.length} fichiers · {m.counts.bordereau_jpg} bordereaux JPG · {m.counts.facture_txt} factures TXT · {m.counts.specification} spécification · originaux en lecture seule · doublons de contenu : {m.duplicates.length}</p>
          <div className="table-wrap" style={{ maxHeight: 360 }}><table className="data small"><thead><tr><th>Fichier</th><th>Type</th><th className="num">Taille</th><th>SHA-256</th><th>Lecture seule</th></tr></thead>
            <tbody>{m.files.map((f: any) => <tr key={f.path}><td>{f.path}</td><td>{f.kind}</td><td className="num">{f.size.toLocaleString("fr-FR")}</td><td className="mono">{f.sha256.slice(0, 24)}…</td><td>{f.read_only ? "oui" : "non"}</td></tr>)}</tbody></table></div>
        </>}
      </section>
    </div>
  </>;
}
