import { useEffect, useState } from "react";
import { api, fmtDate, User } from "../api";
import { CaseState, ErrorBox, Loading, useFetch, useToast } from "../components/ui";

export default function Imports({ user, params }: { user: User; params?: URLSearchParams }) {
  const { data, error, reload } = useFetch<any[]>("/api/imports");
  const follow = params?.get("suivre");
  const [img, setImg] = useState<File | null>(null);
  const [txt, setTxt] = useState<File | null>(null);
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const toast = useToast();
  const pending = (data || []).some(x => x.status === "analyse");
  const followed = follow ? (data || []).find(x => x.id === follow) : null;

  useEffect(() => { if (pending) { const t = setTimeout(reload, 2500); return () => clearTimeout(t); } }, [data]); // eslint-disable-line

  const send = async (e: React.FormEvent) => {
    e.preventDefault(); setErr(null);
    if (!img || !txt) { setErr("Choisissez un bordereau (image) et un fichier de facturation (TXT)."); return; }
    setBusy(true);
    const fd = new FormData();
    fd.append("bordereau", img); fd.append("facture", txt); if (label.trim()) fd.append("label", label.trim());
    try {
      const r = await fetch("/api/imports", { method: "POST", body: fd, credentials: "same-origin" });
      if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail; } catch { /* */ } throw new Error(m); }
      toast("Dossier déposé — analyse en cours (suivi ci-dessous)");
      setImg(null); setTxt(null); setLabel(""); (e.target as HTMLFormElement).reset(); reload();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const del = (id: string) => {
    if (!window.confirm(`Supprimer le dossier importé ${id} et ses résultats ?`)) return;
    api.del(`/api/imports/${id}`).then(() => { toast("Dossier importé supprimé"); reload(); }).catch(e => toast(e.message));
  };
  const canWrite = user.role !== "auditeur";

  return <>
    <div className="page-head"><div><h1>Importer un dossier · simulations</h1>
      <p>Déposez un bordereau (image JPG ou PNG) et sa facture B2 (fichier TXT), ou créez une simulation depuis un dossier (bouton « Simuler une modification »).
        Les 22 contrôles et les 15 zones sont calculés par le moteur réel. Ces dossiers sont privés (visibles par vous et les gestionnaires), marqués
        « Import » ou « Simulation » et exclus des statistiques de supervision.</p></div></div>
    {followed && <div className={`notice ${followed.status === "erreur" ? "bad" : followed.status === "analyse" ? "warn" : ""}`} style={{ marginBottom: 14 }}>
      <b>{followed.kind === "simulation" ? "Simulation" : "Import"} {followed.id}</b> — {followed.status === "analyse" ? <>analyse en cours{followed.job?.message ? ` : ${followed.job.message}` : ""}…</> :
        followed.status === "erreur" ? <>erreur d'analyse : {followed.error}</> : <>analyse terminée. <a className="btn small primary" href={`#/controle/${followed.id}`}>Ouvrir le dossier</a></>}
      {followed.edits?.length > 0 && <div className="small" style={{ marginTop: 4 }}>Modification : {followed.edits.map((e: any) => `ligne ${e.line_no}, pos. ${e.start}-${e.end} : « ${e.avant} » → « ${e.apres} »`).join(" ; ")}</div>}
    </div>}
    <div className="grid cols-2">
      {canWrite && <section className="panel panel-pad">
        <h2>Nouveau dossier</h2>
        <form onSubmit={send} style={{ display: "grid", gap: 12 }}>
          <label className="field">Bordereau de facturation (JPG ou PNG)
            <input className="input" type="file" accept=".jpg,.jpeg,.png,image/jpeg,image/png" onChange={e => setImg(e.target.files?.[0] || null)} /></label>
          <label className="field">Facture structurée (TXT, format B2)
            <input className="input" type="file" accept=".txt,text/plain" onChange={e => setTxt(e.target.files?.[0] || null)} /></label>
          <label className="field">Libellé (facultatif)
            <input className="input" value={label} onChange={e => setLabel(e.target.value)} placeholder="ex. test : montant modifié" maxLength={120} /></label>
          {err && <div className="error-text">{err}</div>}
          <div><button className="btn primary" disabled={busy}>{busy ? "Envoi…" : "Déposer et analyser"}</button></div>
        </form>
        <p className="hint" style={{ marginTop: 12 }}>L'analyse prend de 15 à 40 secondes (lecture OCR du bordereau), quelques secondes si l'image est déjà connue.
          Le bordereau doit suivre l'une des trois mises en page du corpus ; sinon il est signalé « mise en page non reconnue » et les contrôles qui dépendent de l'image passent en non vérifiable.</p>
      </section>}
      <section className="panel panel-pad">
        <h2>Pour tester rapidement</h2>
        <ol className="small" style={{ paddingLeft: 18 }}>
          <li>Prenez une paire du corpus, par exemple <span className="mono">Facture1_02.jpg</span> et <span className="mono">Facture1_02.txt</span> (dossier <span className="mono">data\corpus\General-main</span>).</li>
          <li>Copiez le TXT et modifiez-le avec le Bloc-notes : par exemple, sur la ligne qui commence par 5, changez un chiffre du total (positions 42 à 49), ou remplacez le code <span className="mono">PH8</span> par <span className="mono">PH9</span> sur une ligne de type 3.</li>
          <li>Déposez l'image d'origine et votre TXT modifié : l'écart doit apparaître (R12 pour un total, R08/R11/R13 pour un code).</li>
        </ol>
        <p className="hint">Gardez la longueur des lignes : remplacez un caractère par un autre, sans en ajouter ni en supprimer, sinon les positions sont décalées (ce que l'application signale aussi).</p>
      </section>
    </div>
    <section className="panel" style={{ marginTop: 14 }}>
      <div className="pane-head"><h3>Dossiers importés</h3></div>
      {error ? <ErrorBox e={error} /> : !data ? <Loading /> : data.length === 0 ? <p className="empty">Aucun dossier importé pour l'instant.</p> :
        <table className="data"><thead><tr><th>Dossier</th><th>Libellé</th><th>Fichiers</th><th>Déposé</th><th>Analyse</th><th>Résultat</th><th /></tr></thead>
          <tbody>{data.map(x => <tr key={x.id}>
            <td className="mono">{x.id}<div><span className="tag">{x.kind === "simulation" ? `Simulation de ${x.origin}` : "Import"}</span></div></td><td>{x.label || <span className="muted">—</span>}</td>
            <td className="small mono">{x.jpg}<br />{x.txt}</td>
            <td className="small">{fmtDate(x.created_at)}<div className="hint">{x.by}</div></td>
            <td>{x.status === "analyse" ? <span className="jobline">{x.job?.status === "en_attente" ? "en attente" : "en cours"}{x.job?.message ? ` — ${x.job.message}` : ""}…</span>
              : x.status === "erreur" ? <span className="error-text">{x.error}</span> : x.status === "prêt" ? "terminée" : x.status}</td>
            <td>{x.case ? <><CaseState state={x.case.state} /><div className="hint">{x.case.n_anomalies} anomalie(s), {x.case.n_nv} non vérif.</div></> : "—"}</td>
            <td className="nowrap">{x.case && <a className="btn small primary" href={`#/controle/${x.id}`}>Ouvrir</a>}
              {(user.role === "superviseur" || user.role === "admin" || (user.role === "agent" && x.by === user.username)) && x.status !== "analyse" && <button className="btn small danger" style={{ marginLeft: 6 }} onClick={() => del(x.id)}>Supprimer</button>}</td>
          </tr>)}</tbody></table>}
    </section>
  </>;
}
