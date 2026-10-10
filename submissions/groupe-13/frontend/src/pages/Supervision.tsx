import { euro, fmtDate, STATUS_LABEL, User } from "../api";
import { HBar, StatusStack } from "../components/Charts";
import { ErrorBox, Loading, go, useFetch } from "../components/ui";

const ZST = ["CONFORME", "ANOMALIE", "NON_VERIFIABLE", "NON_APPLICABLE", "ERREUR_TECHNIQUE"];
const dur = (s: number | null | undefined) => s === null || s === undefined ? "indisponible" : s < 1 ? `${Math.round(s * 1000)} ms` : s < 120 ? `${s.toFixed(1).replace(".", ",")} s` : s < 7200 ? `${Math.round(s / 60)} min` : `${(s / 3600).toFixed(1).replace(".", ",")} h`;

export default function Supervision({ user }: { user: User }) {
  const { data: s, error } = useFetch<any>("/api/supervision");
  if (error) return <ErrorBox e={error} />;
  if (!s) return <Loading />;
  const d = s.dossiers, f = s.finances;
  const fieldNames: Record<string, string> = { Z1: "Z1 identifiant", Z2: "Z2 FINESS", Z3: "Z3 lot", Z4: "Z4 facture", Z5: "Z5 assuré", ST1: "Sous-total 1", ST2: "Sous-total 2", ST3: "Sous-total 3", Z8: "Z8 total 1+2+3", Z12: "Z12 sous-total 4", Z13: "Z13 montant total", Z15: "Z15 code CERFA" };
  return <>
    <div className="page-head"><div><h1>Supervision de caisse</h1>
      <p>Indicateurs calculés uniquement sur le corpus fourni ({s.denominateurs.paires} paires, {s.denominateurs.controles_executes} contrôles exécutés) et sur les actions enregistrées dans l'application.</p></div>
      <a className="btn" href="/api/export/results.csv">Exporter les résultats (CSV)</a></div>
    <div className="kpis">
      <a className="kpi" href="#/dossiers"><div className="v">{d.total}</div><div className="l">Factures identifiées</div><div className="d">sur {s.denominateurs.fichiers_analyses.bordereau_jpg} JPG et {s.denominateurs.fichiers_analyses.facture_txt} TXT</div></a>
      <div className="kpi"><div className="v">{d.rapproches}</div><div className="l">Rapprochées avec succès</div><div className="d">≥ 2 identifiants concordants sur 3</div></div>
      <a className="kpi" href="#/dossiers?etat=anomalie"><div className="v">{d.avec_anomalie}</div><div className="l">Dossiers avec ≥ 1 anomalie</div><div className="d">sur {d.total} dossiers</div></a>
      <a className="kpi" href="#/dossiers?etat=nv"><div className="v">{d.avec_non_verifiable}</div><div className="l">Dossiers avec contrôle non vérifiable</div><div className="d">lecture humaine requise</div></a>
      <div className="kpi"><div className="v">{d.en_attente_revue}</div><div className="l">En attente de revue</div><div className="d">à contrôler, en analyse ou en revue</div></div>
      <div className="kpi"><div className="v">{d.valides_agent}</div><div className="l">Validés par un agent</div><div className="d">décision finale enregistrée</div></div>
      <div className="kpi"><div className="v">{d.revue_humaine_requise}</div><div className="l">Revue humaine requise</div><div className="d">anomalie ou non vérifiable, sans décision finale</div></div>
      <div className="kpi"><div className="v">{s.activite.controles_confirmes}</div><div className="l">Contrôles confirmés</div><div className="d">{s.activite.faux_positifs} faux positif(s) · {s.activite.revues_demandees} revue(s)</div></div>
      <div className="kpi"><div className="v">{d.clotures}</div><div className="l">Dossiers clôturés</div><div className="d">par un gestionnaire</div></div>
    </div>
    <p className="hint" style={{ marginTop: -6, marginBottom: 14 }}>{s.denominateurs.note}{s.denominateurs.dossiers_importes ? ` Dossiers importés exclus : ${s.denominateurs.dossiers_importes}.` : ""}</p>

    <section className="panel panel-pad" style={{ marginBottom: 14 }}>
      <h2>Matrice des 15 zones du bordereau</h2>
      <p className="hint">Nombre de dossiers par statut de zone (dénominateur : {s.denominateurs.factures_identifiees} dossiers, soit {s.denominateurs.zones_evaluees} zones évaluées). Une zone mixte reste comptée selon son statut, et ses résultats sous-jacents restent visibles dans chaque dossier. Cliquer une cellule ouvre la liste filtrée.</p>
      <div className="table-wrap"><table className="data zmatrix"><thead><tr><th>Zone</th>{ZST.map(k => <th key={k} className="num">{STATUS_LABEL[k as keyof typeof STATUS_LABEL]}</th>)}<th className="num">Mixtes / incertains</th></tr></thead>
        <tbody>{s.zones.map((z: any) => <tr key={z.zone_id}><td><span className="mono">{z.zone_id}</span> {z.label}</td>
          {ZST.map(k => { const n = z.counts[k] || 0; const p = z.denominateur ? n / z.denominateur : 0;
            return <td key={k} className={`cell heat-${k}`} style={{ ["--a" as any]: n ? 0.08 + 0.42 * p : 0 }}>
              {n ? <a href={`#/dossiers?zone=${z.zone_id}&zstatut=${k}`} title={`${z.zone_id} — ${STATUS_LABEL[k as keyof typeof STATUS_LABEL]} : ${n} / ${z.denominateur}`}>{n}<span className="pct">{Math.round(100 * p)} %</span></a> : <span className="muted">0</span>}</td>; })}
          <td className="cell">{z.mixtes || <span className="muted">0</span>}</td></tr>)}</tbody></table></div>
    </section>

    <div className="grid cols-2">
      <section className="panel panel-pad">
        <h2>Résultats par règle</h2>
        <p className="hint">Nombre de dossiers par statut pour chacune des 22 règles. Cliquer une règle ouvre la liste de ses anomalies.</p>
        <StatusStack rows={s.regles.map((r: any) => ({ key: r.rule_id, label: r.title, counts: r.counts }))} onClick={k => go(`/anomalies?regle=${k}`)} />
      </section>
      <section className="panel panel-pad">
        <h2>Anomalies par règle</h2>
        <p className="hint">Règles les plus souvent en écart (nombre de dossiers).</p>
        <HBar data={s.regles.filter((r: any) => r.counts.ANOMALIE).sort((a: any, b: any) => b.counts.ANOMALIE - a.counts.ANOMALIE)
          .map((r: any) => ({ key: r.rule_id, label: `${r.rule_id} · ${r.title.slice(0, 20)}${r.title.length > 20 ? "…" : ""}`, sub: r.title, value: r.counts.ANOMALIE }))}
          onClick={k => go(`/anomalies?regle=${k}`)} />
        <h2 style={{ marginTop: 14 }}>Répartition des dossiers par statut</h2>
        <HBar data={Object.entries(d.par_statut).map(([k, v]: any) => ({ label: k, value: v }))} />
      </section>

      <section className="panel panel-pad">
        <h2>Volet financier</h2>
        <p className="hint">Niveaux distincts, jamais assimilés, sans double comptage. Un écart documentaire n'est ni un indu établi ni une économie réalisée.</p>
        <table className="data"><tbody>
          <tr><td>Montant total facturé dans les dossiers analysés</td><td className="num nowrap">{euro(f.facture_total_cents)}</td></tr>
          <tr><td><b>Montant en anomalie</b> (écarts constatés, dédoublonnés)</td><td className="num nowrap">{euro(f.montant_en_anomalie_cents)}</td></tr>
          <tr><td style={{ paddingLeft: 22 }}>dont différences sur les totaux (|fichier − bordereau|, R12 et R17)</td><td className="num nowrap">{euro(f.ecart_net_mesurable_cents)}</td></tr>
          <tr><td style={{ paddingLeft: 22 }}>dont lignes présentes d'un seul côté (avant dédoublonnage)</td><td className="num nowrap">{euro(f.montants_lignes_en_ecart_cents)}</td></tr>
          <tr><td>Montant facturé des dossiers comportant une alerte (contexte)</td><td className="num nowrap">{euro(f.facture_dossiers_alerte_cents)}</td></tr>
          <tr><td><b>Écarts confirmés par un agent</b> ({f.regles_confirmees} règle(s) confirmée(s) · {f.faux_positifs} faux positif(s))</td><td className="num nowrap">{euro(f.ecart_confirme_cents)}</td></tr>
          <tr><td>Indu établi</td><td className="num nowrap muted">non calculable</td></tr>
          <tr><td>Montants réellement récupérés</td><td className="num nowrap muted">non calculable</td></tr>
        </tbody></table>
        {f.decisions_a_revoir > 0 && <div className="notice warn small" style={{ marginTop: 8 }}>{f.decisions_a_revoir} confirmation(s) portent sur une règle qui n'est plus en anomalie après réanalyse : elles ne sont pas comptées et doivent être revues.</div>}
        <details style={{ marginTop: 8 }}><summary className="small">Définitions</summary>
          <dl className="kv small" style={{ marginTop: 6 }}>{Object.entries(f.notes).map(([k, v]: any) => <><dt key={k}>{k.replace("_", " ")}</dt><dd>{v}</dd></>)}</dl></details>
        <div className="notice warn" style={{ marginTop: 10 }}>Le chiffre de 100 000 € cité dans la présentation iMSA (contrôle interne 2025, ~20 000 factures) est une donnée de contexte : il n'est pas comparable aux montants ci-dessus et n'est pas extrapolé.</div>
      </section>

      <section className="panel panel-pad">
        <h2>Par établissement</h2>
        <table className="data"><thead><tr><th>Établissement</th><th className="num">Dossiers</th><th className="num">Avec anomalie</th><th className="num">Anomalies</th><th className="num">Non vérif.</th></tr></thead>
          <tbody>{s.etablissements.map((e: any) => <tr key={e.nom}><td>{e.nom}</td><td className="num">{e.dossiers}</td><td className="num">{e.avec_anomalie}</td><td className="num">{e.anomalies}</td><td className="num">{e.nv}</td></tr>)}</tbody></table>
        <p className="hint" style={{ marginTop: 6 }}>Effectifs faibles (moins de 30 dossiers par établissement) : ces chiffres décrivent l'échantillon fourni et ne caractérisent pas l'activité globale d'un établissement.</p>
        <h2 style={{ marginTop: 14 }}>Lectures OCR difficiles</h2>
        <p className="hint">Champs du bordereau illisibles ou aux lectures divergentes (nombre de dossiers).</p>
        {Object.keys(s.lectures_difficiles).length === 0 ? <p className="muted">Aucun champ difficile.</p> :
          <HBar data={Object.entries(s.lectures_difficiles).sort((a: any, b: any) => b[1] - a[1]).map(([k, v]: any) => ({ label: fieldNames[k] || k, value: v }))} />}
      </section>

      <section className="panel panel-pad">
        <h2>Dossiers à examiner en priorité</h2>
        <p className="hint">{s.parametres_priorite}</p>
        <table className="data"><thead><tr><th>Dossier</th><th className="num">Score</th><th>Motifs</th><th>Statut</th></tr></thead>
          <tbody>{s.priorites.map((p: any) => <tr key={p.id} className="clickable" onClick={() => go(`/controle/${p.id}`)}>
            <td className="mono">{p.id}{p.override === "haute" ? " ↑" : ""}</td><td className="num">{p.score}</td><td className="small">{p.reasons.join(" ; ") || "—"}</td><td><span className="case-status">{p.status}</span></td></tr>)}</tbody></table>
      </section>

      <section className="panel panel-pad">
        <h2>Activité et productivité mesurées</h2>
        <p className="hint">{s.productivite.note}</p>
        <table className="data"><tbody>
          <tr><td>Lecture OCR d'un bordereau (médiane)</td><td className="num">{dur(s.productivite.ocr_s_median)}</td><td className="hint">{s.productivite.ocr_mesures} mesure(s)</td></tr>
          <tr><td>Analyse automatique d'un dossier (médiane)</td><td className="num">{dur(s.productivite.analyse_s_median)}</td><td className="hint">{s.productivite.analyse_mesures} mesure(s)</td></tr>
          <tr><td>Temps de revue actif par dossier (médiane)</td><td className="num">{dur(s.productivite.temps_actif_s_median)}</td><td className="hint">{s.productivite.temps_actif_dossiers} dossier(s)</td></tr>
          <tr><td>Ouverture → première décision (médiane, temps écoulé)</td><td className="num">{dur(s.productivite.delai_premiere_decision_s_median)}</td><td className="hint">{s.productivite.delai_premiere_decision_mesures} mesure(s)</td></tr>
          <tr><td>Ouverture → clôture (médiane, temps écoulé)</td><td className="num">{dur(s.productivite.delai_cloture_s_median)}</td><td className="hint">{s.productivite.delai_cloture_mesures} mesure(s)</td></tr>
        </tbody></table>
        <h2 style={{ marginTop: 14 }}>Décisions par jour</h2>
        {Object.keys(s.activite.decisions_par_jour).length === 0 ? <p className="muted">Aucune décision enregistrée. {s.activite.note}</p> :
          <HBar data={Object.entries(s.activite.decisions_par_jour).map(([k, v]: any) => ({ label: k, value: v }))} />}
        <p className="hint" style={{ marginTop: 6 }}><a href="#/qualite">Qualité mesurée de l'OCR et des alertes →</a></p>
      </section>

      <section className="panel panel-pad">
        <h2>Charge par agent</h2>
        {s.charge_agents.length === 0 ? <p className="muted">Aucun dossier affecté pour l'instant (affectation depuis l'écran du dossier).</p> :
          <HBar data={s.charge_agents.map((c: any) => ({ label: c.nom, sub: `${c.en_cours} en cours`, value: c.dossiers }))} />}
        <h2 style={{ marginTop: 14 }}>Décisions des agents</h2>
        {s.decisions.length === 0 ? <p className="muted">Aucune décision enregistrée.</p> :
          <ul className="timeline">{s.decisions.slice(0, 25).map((x: any) => <li key={x.id}><a className="mono" href={`#/controle/${x.case_id}`}>{x.case_id}</a> — {x.display_name} : {x.kind.replace("_", " ")}{x.rule_id ? ` (${x.rule_id})` : ""}{x.value ? ` → ${x.value}` : ""}
            {x.comment && <div className="muted">« {x.comment} »</div>}<div className="hint">{fmtDate(x.created_at)}</div></li>)}</ul>}
      </section>

      <section className="panel panel-pad" style={{ gridColumn: "1 / -1" }}>
        <h2>Points du cahier des charges à clarifier</h2>
        <table className="data"><thead><tr><th>Réf.</th><th>Sujet</th><th>Constat</th><th>Convention appliquée</th><th>À clarifier</th></tr></thead>
          <tbody>{s.ambiguites.map((a: any) => <tr key={a.id}><td className="mono">{a.id}</td><td>{a.sujet}</td><td className="small">{a.constat}</td><td className="small">{a.convention}</td><td>{a.a_clarifier ? "oui" : "non"}</td></tr>)}</tbody></table>
        {d.rapprochement_ambigu.length > 0 && <div className="notice warn" style={{ marginTop: 10 }}>Rapprochement ambigu (bordereau et fichier possiblement non homologues) : {d.rapprochement_ambigu.map((x: string) => <a key={x} className="mono" style={{ marginRight: 8 }} href={`#/controle/${x}`}>{x}</a>)}</div>}
      </section>
    </div>
  </>;
}
