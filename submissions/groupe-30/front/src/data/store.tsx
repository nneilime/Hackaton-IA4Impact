import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  useCallback,
  useRef,
  type ReactNode,
} from "react";
import {
  type Catalog,
  type DataFeedback,
  type HistoryData,
  type Inspection,
  type ScoreResult,
} from "../domain/types";
import {
  parseActionBackup,
  ranksFor,
  validateInspection,
} from "../domain/rules";
import { api, authClient } from "./api";
export interface Calculation {
  id: string;
  statut: string;
  progression: number;
  erreur: string | null;
  date_reference: string;
}
interface Workspace {
  catalog: Catalog;
  result: ScoreResult;
  actions: Inspection[];
  feedback: DataFeedback[];
  user: { id: string; email: string; role: string; name: string };
  jobs: Calculation[];
}
const histories = new Map<string, Promise<HistoryData>>();
export function loadHistory(id: string, asOfDate = "2026-01-01") {
  const key = id + ":" + asOfDate;
  if (!histories.has(key))
    histories.set(
      key,
      api<HistoryData>(
        "/equipements/" +
          encodeURIComponent(id) +
          "/historique?as_of_date=" +
          asOfDate,
      ).catch((e) => {
        histories.delete(key);
        throw e;
      }),
    );
  return histories.get(key)!;
}
interface AppData extends Workspace {
  ranks: Map<string, number>;
  horizon: number;
  setHorizon: (value: number) => void;
  asOfDate: string;
  setAsOfDate: (value: string) => void;
  refresh: () => Promise<void>;
  recalculate: () => Promise<void>;
  logout: () => Promise<void>;
  saveAction: (action: Inspection) => Promise<void>;
  deleteAction: (id: string) => Promise<void>;
  saveFeedback: (item: DataFeedback) => Promise<void>;
  importBackup: (raw: string) => Promise<void>;
  notify: (message: string) => void;
  lastListQuery: string;
  setLastListQuery: (value: string) => void;
}
const Context = createContext<AppData | null>(null);
export function useAppData() {
  const value = useContext(Context);
  if (!value) throw new Error("Données non disponibles.");
  return value;
}
export function DataProvider({ children }: { children: ReactNode }) {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [horizon, setHorizon] = useState(90);
  const [asOfDate, setAsOfDate] = useState("2026-01-01");
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [lastListQuery, setLastListQuery] = useState("");
  const query = useRef(0);
  const refresh = useCallback(async () => {
    const request = ++query.current;
    try {
      const next = await api<Workspace>(
        "/workspace?horizon=" + horizon + "&as_of_date=" + asOfDate,
      );
      if (request !== query.current) return;
      histories.clear();
      setWorkspace(next);
      setError("");
    } catch (e) {
      if (request === query.current) setError((e as Error).message);
      throw e;
    }
  }, [horizon, asOfDate]);
  useEffect(() => {
    void refresh().catch(() => {});
    return () => {
      query.current++;
    };
  }, [refresh]);
  const running = workspace?.jobs.some((j) =>
    ["en_attente", "en_cours"].includes(j.statut),
  );
  useEffect(() => {
    const timer = window.setInterval(
      () => {
        void refresh().catch(() => {});
      },
      running ? 2000 : 30000,
    );
    return () => clearInterval(timer);
  }, [refresh, running]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 6000);
    return () => clearTimeout(timer);
  }, [toast]);
  const ranks = useMemo(
    () => ranksFor(workspace?.result.scores || {}),
    [workspace?.result],
  );
  async function updateWorkspace(path: string, method: string, body?: unknown) {
    const result = await api<{
      actions: Inspection[];
      feedback: DataFeedback[];
    }>(path, { method, ...(body ? { body: JSON.stringify(body) } : {}) });
    setWorkspace((previous) =>
      previous ? { ...previous, ...result } : previous,
    );
  }
  if (!workspace)
    return (
      <div className="boot-state">
        <h1>
          {error
            ? "Le patrimoine n’est pas disponible"
            : "Préparation de votre espace"}
        </h1>
        <p>{error || "Chargement des données partagées…"}</p>
        {error ? (
          <>
            <button
              className="button primary"
              onClick={() => void refresh().catch(() => {})}
            >
              Réessayer
            </button>
            <button
              className="button secondary"
              onClick={() => void authClient().then((c) => c.auth.signOut())}
            >
              Se déconnecter
            </button>
          </>
        ) : (
          <span className="loader" />
        )}
      </div>
    );
  const value: AppData = {
    ...workspace,
    ranks,
    horizon,
    setHorizon,
    asOfDate,
    setAsOfDate,
    refresh,
    lastListQuery,
    setLastListQuery,
    notify: setToast,
    async logout() {
      await (await authClient()).auth.signOut();
    },
    async recalculate() {
      await api("/calculs?as_of_date=" + asOfDate, { method: "POST" });
      await refresh();
      setToast("Le calcul des quatre horizons a démarré.");
    },
    async saveAction(action) {
      validateInspection(action, workspace.actions);
      await updateWorkspace(
        "/inspections/" + encodeURIComponent(action.id),
        "PUT",
        action,
      );
      setToast("Le dossier partagé a été enregistré.");
    },
    async deleteAction(id) {
      const action = workspace.actions.find((a) => a.id === id);
      await updateWorkspace(
        "/inspections/" +
          encodeURIComponent(id) +
          "?version=" +
          (action?.version || 1),
        "DELETE",
      );
      setToast("Le dossier a été supprimé.");
    },
    async saveFeedback(item) {
      await updateWorkspace("/signalements", "POST", item);
      setToast("Le signalement est partagé avec l’équipe.");
    },
    async importBackup(raw) {
      const backup = parseActionBackup(raw, workspace.catalog.equipment);
      await updateWorkspace("/workspace/recovery", "POST", backup);
      setToast(
        "Les données ont été récupérées. La copie locale est conservée.",
      );
    },
  };
  return (
    <Context.Provider value={value}>
      {error && (
        <div className="storage-notice" role="alert">
          {error} Les dernières données chargées restent affichées.
          <button onClick={() => void refresh().catch(() => {})}>
            Réessayer
          </button>
        </div>
      )}
      {workspace.result.stale && (
        <div className="storage-notice" role="status">
          Le classement affiché provient d’une ancienne révision. Un nouveau
          calcul est nécessaire.
        </div>
      )}
      {children}
      {toast && (
        <div className="toast" role="status">
          <span className="toast-dot" />
          {toast}
        </div>
      )}
    </Context.Provider>
  );
}
