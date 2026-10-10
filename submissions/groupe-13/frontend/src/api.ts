export type Role = "agent" | "superviseur" | "admin" | "auditeur";
export interface User { id: number; username: string; display_name: string; role: Role }

export type RuleStatus = "CONFORME" | "ANOMALIE" | "NON_VERIFIABLE" | "NON_APPLICABLE" | "ERREUR_TECHNIQUE";

export interface Ref { label: string; box?: number[]; box_norm?: number[]; zone?: string; line_no?: number; start?: number; end?: number }

export interface RuleResult {
  rule_id: string; category: string; category_label: string; title: string; spec: string; convention: string;
  status: RuleStatus; jpg_value: string | null; txt_value: string | null;
  gap: { type: string; amount_cents: number | null; label: string } | null;
  zones: string[]; txt_fields: string[]; img_refs: Ref[]; txt_refs: Ref[];
  explanation: string; uncertainty: { level: string; reason: string } | null; details: any;
  next_action: string; processed_at: string; engine_version: string; ruleset_version: string; provenance: any;
}

export interface CaseRow {
  id: string; family: string; finess: string; establishment: string; invoice_no: string; billed_cents: number;
  n_anomalies: number; n_nv: number; n_errors: number; n_observations: number; state: string;
  net_gap_cents: number; act_gap_cents: number; priority_score: number; priority_reasons: string[];
  status: string; pairing_status: string; priority_override: string | null; analyzed_at: string;
  assigned_to: number | null; assigned_name: string | null; anomaly_rules: string[];
}

export class ApiError extends Error { status: number; constructor(s: number, m: string) { super(m); this.status = s; } }

async function req<T>(method: string, url: string, body?: any): Promise<T> {
  const r = await fetch(url, {
    method, credentials: "same-origin",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    let msg = r.statusText;
    try { const j = await r.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* */ }
    if (r.status === 401) window.dispatchEvent(new Event("sentinel:unauthorized"));
    throw new ApiError(r.status, msg);
  }
  const ct = r.headers.get("content-type") || "";
  return (ct.includes("json") ? r.json() : r.text()) as Promise<T>;
}

export const api = {
  get: <T,>(u: string) => req<T>("GET", u),
  post: <T,>(u: string, b?: any) => req<T>("POST", u, b ?? {}),
  del: <T,>(u: string) => req<T>("DELETE", u),
};

export const euro = (c: number | null | undefined) =>
  c === null || c === undefined ? "—" :
    (c / 100).toLocaleString("fr-FR", { style: "currency", currency: "EUR" });

export const STATUS_LABEL: Record<RuleStatus, string> = {
  CONFORME: "Conforme", ANOMALIE: "Écart", NON_VERIFIABLE: "À vérifier",
  NON_APPLICABLE: "Sans objet", ERREUR_TECHNIQUE: "Erreur technique",
};

export const CASE_STATUSES = ["À contrôler", "En analyse", "Anomalie à vérifier", "Revue complémentaire nécessaire",
  "Écart confirmé", "Faux positif reconnu", "Contrôle terminé", "Clôturé"];

export const ROLE_LABEL: Record<Role, string> = {
  agent: "Agent de contrôle", superviseur: "Gestionnaire de caisse", admin: "Administrateur technique", auditeur: "Auditeur",
};

export const fmtDate = (s?: string | null) => s ? new Date(s.replace(" ", "T")).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "—";
