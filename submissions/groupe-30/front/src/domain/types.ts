export interface Equipment {
  id: string;
  family: string;
  label: string;
  residenceId: string;
  buildingId: string;
  housingId: string | null;
  collective: boolean;
  installedAt: string | null;
  installationOrigin: string;
  cycleStartedAt: string | null;
  ageYears: number | null;
  referenceLifeYears: number;
  underContract: boolean;
  annualVisit: boolean;
  providerId: string;
  inScope: boolean;
  buildingHousingCount: number;
  recentRepairCount: number;
  recentAnomalyCount: number;
  latestObservation: { text: string; date: string; id: string } | null;
  needsVerification: boolean;
  housingDpe?: string | null;
}

export interface Housing {
  id: string;
  buildingId: string;
  residenceId: string;
  typology: string;
  area: number;
  floor: number;
  dpeEnergy: string;
  dpeGes: string;
  dpeGlobal: string;
  consoEp: number;
  ges: number;
  tenantTurnover: number;
  occupancyStatus: string;
}

export interface Residence {
  id: string;
  name: string;
  housingCount: number;
  buildingCount?: number;
  constructionYear?: number;
  energyHeating?: string;
  heatingType?: string;
  heatingGenerator?: string;
  ecsProduction?: string;
  ventilation?: string;
  dpeTag?: string;
  consoEp?: number;
  ges?: number;
  lat?: number;
  lng?: number;
  district?: string;
}

export interface Catalog {
  revision?: number;
  snapshotDate: string;
  equipment: Equipment[];
  residences: Residence[];
  housings?: Housing[];
  providers: { id: string; name: string; domain: string }[];
  baselineScores: Record<string, number>;
}
export interface Intervention {
  id: string;
  date: string;
  type: string;
  symptom: string;
  severity: string;
  result: string;
  comment: string;
  providerId: string;
  requestId: string | null;
}
export interface RequestEvidence {
  id: string;
  date: string;
  closedAt: string | null;
  housingId: string;
  buildingId: string;
  parts: string;
  motif: string;
  subject: string;
  text: string;
}
export interface ReportEvidence {
  year?: number;
  id: string;
  quarter: number;
  page: number | null;
  text: string;
  url: string;
}
export interface HistoryData {
  events: Record<string, Intervention[]>;
  requests: RequestEvidence[];
  reports: Record<string, ReportEvidence[]>;
}
export interface ScoreMetadata {
  label: string;
  modelVersion: string;
  referenceDate: string;
  horizonStart: string;
  horizonEndExclusive: string;
  kind: "ranking_score" | "calibrated_probability";
  importedAt: string | null;
}
export interface ScoreResult {
  stale?: boolean;
  runId?: string;
  revision?: number;
  scores: Record<string, number>;
  metadata: ScoreMetadata;
}
export type ActionStatus =
  "preparing" | "planned" | "completed" | "closed" | "review";
export const STATUS_LABELS: Record<ActionStatus, string> = {
  preparing: "À préparer",
  planned: "Planifiée",
  completed: "Réalisée",
  closed: "Clôturée",
  review: "À réexaminer",
};
export interface ActionEvent {
  date: string;
  label: string;
  note: string;
  status?: ActionStatus;
  outcome?: string;
}
export interface Inspection {
  version?: number;
  id: string;
  equipmentId: string;
  status: ActionStatus;
  owner: string;
  providerId: string;
  objective: string;
  desiredDate: string;
  confirmedDate: string;
  reviewDate: string;
  visitedDate: string;
  outcome: string;
  note: string;
  conclusion: string;
  externalReference: string;
  cycleStartedAt: string | null;
  scoreVersion: string;
  createdAt: string;
  updatedAt: string;
  history: ActionEvent[];
}
export interface DataFeedback {
  id: string;
  equipmentId: string;
  subject: string;
  comment: string;
  author: string;
  createdAt: string;
}
export interface ActionBackup {
  version: 1;
  actions: Inspection[];
  feedback?: DataFeedback[];
}
