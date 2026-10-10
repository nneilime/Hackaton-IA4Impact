import { useState } from "react";
import { Database, FileUp, RefreshCw, Download } from "lucide-react";
import { useAppData } from "../../data/store";
import { api } from "../../data/api";
import {
  dateLabel,
  download,
  numberLabel,
  parseActionBackup,
} from "../../domain/rules";
import { Field, Modal } from "../../ui/components";
interface Preview {
  token: string;
  revision: number;
  files: {
    file: string;
    table?: string;
    rows: number;
    added: number;
    updated: number;
    unchanged: number;
  }[];
  tables: Record<string, { added: number; updated: number; unchanged: number }>;
  errors: { file: string; line: number; message: string }[];
}
export function DataDialog({ onClose }: { onClose: () => void }) {
  const {
    catalog,
    result,
    user,
    jobs,
    horizon,
    setHorizon,
    asOfDate,
    setAsOfDate,
    refresh,
    recalculate,
    importBackup,
    notify,
  } = useAppData();
  const [tab, setTab] = useState("context");
  const [files, setFiles] = useState<File[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [recovery, setRecovery] = useState<{
    raw: string;
    actions: number;
    feedback: number;
    skipped: number;
  } | null>(null);
  const running = jobs.find((j) =>
    ["en_attente", "en_cours"].includes(j.statut),
  );
  const latest = jobs[0];
  async function work(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function checkFiles() {
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    setPreview(
      await api<Preview>("/imports/preview", { method: "POST", body: form }),
    );
  }
  async function confirm() {
    if (!preview) return;
    const response = await api<{ calculationError?: string }>(
      "/imports/" + preview.token + "/confirm?as_of_date=" + asOfDate,
      { method: "POST" },
    );
    await refresh();
    setPreview(null);
    setFiles([]);
    setTab("context");
    notify(
      response.calculationError ||
        "Import enregistré. Le classement s’actualise si les données du modèle ont changé.",
    );
  }
  async function checkRecovery() {
    const raw = localStorage.getItem("batia.actions.v1");
    if (!raw) throw new Error("Aucune donnée locale à récupérer.");
    const value = JSON.parse(raw);
    const backup = parseActionBackup(
      JSON.stringify(
        Array.isArray(value) ? { version: 1, actions: value } : value,
      ),
      catalog.equipment,
    );
    const counts = await api<{
      actions: number;
      feedback: number;
      skipped: number;
    }>("/workspace/recovery/preview", {
      method: "POST",
      body: JSON.stringify(backup),
    });
    setRecovery({ raw: JSON.stringify(backup), ...counts });
  }
  return (
    <Modal
      title="Données et classement"
      description="Les sources partagées et les résultats du modèle."
      onClose={onClose}
      wide
    >
      <div className="modal-tabs">
        <button
          className={tab === "context" ? "active" : ""}
          onClick={() => setTab("context")}
        >
          Résultat disponible
        </button>
        {user.role === "admin" && (
          <button
            className={tab === "import" ? "active" : ""}
            onClick={() => setTab("import")}
          >
            Importer des CSV
          </button>
        )}
        <button
          className={tab === "recovery" ? "active" : ""}
          onClick={() => setTab("recovery")}
        >
          Récupérer les dossiers locaux
        </button>
      </div>
      <div className="modal-body">
        {error && (
          <p role="alert" className="form-error">
            {error}
          </p>
        )}
        {tab === "context" && (
          <>
            <div className="data-result">
              <span className="data-icon">
                <Database size={25} />
              </span>
              <div>
                <span className="eyebrow">SOURCE DU CLASSEMENT</span>
                <h3>{result.metadata.label}</h3>
                <p>
                  Version {result.metadata.modelVersion} · révision{" "}
                  {result.revision ?? catalog.revision}
                </p>
              </div>
            </div>
            <div className="field-grid">
              <Field
                label="Date de prédiction"
                hint="L’historique strictement antérieur à cette date est utilisé."
              >
                <input
                  type="date"
                  value={asOfDate}
                  onChange={(e) => {
                    if (e.target.value) setAsOfDate(e.target.value);
                  }}
                />
              </Field>
              <Field label="Horizon">
                <select
                  aria-label="Horizon"
                  value={horizon}
                  onChange={(e) => setHorizon(Number(e.target.value))}
                >
                  {[90, 180, 365, 730].map((h) => (
                    <option key={h} value={h}>
                      {h} jours
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <div className="data-grid">
              <div>
                <small>Historique affiché jusqu’au</small>
                <strong>{dateLabel(catalog.snapshotDate, true)}</strong>
              </div>
              <div>
                <small>Horizon étudié</small>
                <strong>
                  {dateLabel(result.metadata.horizonStart)} –{" "}
                  {dateLabel(result.metadata.horizonEndExclusive)} (fin exclue)
                </strong>
              </div>
              <div>
                <small>Couverture du résultat</small>
                <strong>
                  {numberLabel(Object.keys(result.scores).length)} /{" "}
                  {numberLabel(
                    catalog.equipment.filter((e) => e.inScope).length,
                  )}
                </strong>
              </div>
              <div>
                <small>Nature du score</small>
                <strong>Score de risque non calibré</strong>
              </div>
            </div>
            <p className="fine-print">
              Les données initiales du kit sont arrêtées au 31/12/2025. Un
              nouvel import ne réentraîne pas les modèles. Les rangs sont
              calculés sur tous les équipements scorés avant vos filtres.
            </p>
            {running && (
              <div role="status">
                <p>Calcul des quatre horizons : {running.progression} %</p>
                <progress value={running.progression} max={100} />
              </div>
            )}
            {!running && latest?.statut === "echec" && (
              <p role="alert" className="form-error">
                {latest.erreur}
              </p>
            )}
            <button
              className="button primary"
              disabled={busy || !!running}
              onClick={() => void work(recalculate)}
            >
              <RefreshCw size={17} />
              Recalculer le classement
            </button>
          </>
        )}
        {tab === "import" && (
          <>
            <div className="upload-zone">
              <FileUp size={30} />
              <strong>Importer les données du patrimoine</strong>
              <p>
                Un ou plusieurs CSV du kit, avec toutes leurs colonnes. Les
                lignes absentes restent en base.
              </p>
              <input
                type="file"
                multiple
                accept=".csv,text/csv"
                aria-label="Fichiers CSV à importer"
                onChange={(e) => {
                  setFiles(Array.from(e.target.files || []));
                  setPreview(null);
                  setError("");
                }}
              />
              {files.map((f) => (
                <span key={f.name}>{f.name}</span>
              ))}
            </div>
            <button
              className="button secondary"
              disabled={busy || !files.length}
              onClick={() => void work(checkFiles)}
            >
              Vérifier les fichiers
            </button>
            <button
              className="button subtle"
              disabled={busy}
              onClick={() =>
                void work(async () => {
                  const formats =
                    await api<{ table: string; columns: string[] }[]>(
                      "/imports/formats",
                    );
                  formats.forEach((f) =>
                    download(f.table + ".csv", f.columns.join(",") + "\n"),
                  );
                })
              }
            >
              <Download size={16} />
              Télécharger les modèles CSV
            </button>
            {preview && (
              <>
                <h3>Aperçu de l’import</h3>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Fichier / table</th>
                        <th>Ajouts</th>
                        <th>Modifications</th>
                        <th>Inchangées</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.files.map((counts, index) => (
                        <tr key={index}>
                          <td>
                            {counts.file}
                            <br />
                            <small>{counts.table}</small>
                          </td>
                          <td>{counts.added}</td>
                          <td>{counts.updated}</td>
                          <td>{counts.unchanged}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {preview.errors.length > 0 && (
                  <div role="alert">
                    <h3>{preview.errors.length} erreur(s) à corriger</h3>
                    <ul>
                      {preview.errors.slice(0, 50).map((e, i) => (
                        <li key={i}>
                          {e.file}, ligne {e.line} : {e.message}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <p className="fine-print">
                  Le lot sera appliqué en entier ou annulé en entier. Les
                  inspections et signalements seront conservés.
                </p>
              </>
            )}
          </>
        )}
        {tab === "recovery" && (
          <>
            <p>
              Vérifiez les dossiers enregistrés sur ce navigateur avant de les
              partager. Les dossiers déjà présents en base seront conservés.
            </p>
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => void work(checkRecovery)}
            >
              Vérifier les données locales
            </button>
            <button
              className="button subtle"
              onClick={() =>
                download(
                  "donnees-locales.json",
                  localStorage.getItem("batia.actions.v1") || "{}",
                  "application/json",
                )
              }
            >
              Exporter la copie locale
            </button>
            {recovery && (
              <>
                <p>
                  {recovery.actions} dossier(s) et {recovery.feedback}{" "}
                  signalement(s) à récupérer ; {recovery.skipped} dossier(s)
                  déjà présent(s).
                </p>
                <button
                  className="button primary"
                  disabled={busy}
                  onClick={() =>
                    void work(async () => {
                      await importBackup(recovery.raw);
                      setRecovery(null);
                    })
                  }
                >
                  Partager les données vérifiées
                </button>
              </>
            )}
          </>
        )}
      </div>
      <div className="modal-footer">
        <button className="button secondary" onClick={onClose}>
          Fermer
        </button>
        {tab === "import" && preview && (
          <button
            className="button primary"
            disabled={busy || preview.errors.length > 0}
            onClick={() => void work(confirm)}
          >
            Confirmer l’import
          </button>
        )}
      </div>
    </Modal>
  );
}
