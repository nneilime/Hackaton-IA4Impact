export interface FinanceContext {
  billed12m: number;
  invoiceCount12m: number;
  outstanding: number;
  orderCount: number;
}
export interface EconomicEquipment {
  equipmentId: string;
  label: string;
  family: string;
  residenceId: string;
  buildingId: string;
  housingId: string | null;
  providerId: string;
  collective: boolean;
  buildingHousingCount: number;
  underContract: boolean;
  rank: number | null;
  priority: boolean;
  cycleKnown: boolean;
  repairCount12m: number | null;
  pricedRepairCount12m: number;
  simulatedRepairCost12m: number | null;
  replacementMin: number | null;
  replacementMax: number | null;
  repairReplacementRatioMin: number | null;
  repairReplacementRatioMax: number | null;
  firstFailureCost: number | null;
  weightedFirstFailureCost: number | null;
  financeContext: FinanceContext | null;
  financeScope: string;
  operationIds: string[];
}
export interface Investment {
  id: string;
  residenceId: string;
  label: string;
  perimeter: string;
  desiredYear: number | null;
  cost: number | null;
  energyGain: number | null;
  housingCount: number | null;
  costPerHousing: number | null;
  reason: string;
  status: string;
  priorityEquipmentCount: number | null;
  families: string[];
  buildingIds: string[] | null;
  chronologicalRank: number | null;
}
export interface VisitGroup {
  residenceId: string;
  providerId: string;
  equipmentIds: string[];
  potentialVisitsCombined: number;
}
export interface BudgetPlan {
  year: number;
  version: number;
  renovationBudget: number;
  maintenanceBudget: number | null;
  operationIds: string[];
  isDefault: boolean;
}
export interface Economics {
  revision: number;
  referenceDate: string;
  periodStart: string;
  result: {
    stale: boolean;
    revision?: number;
    metadata: { modelVersion: string };
  };
  equipment: EconomicEquipment[];
  operations: Investment[];
  residenceFinance: Record<string, FinanceContext>;
  groups: VisitGroup[];
  plan: BudgetPlan;
}
export interface EquipmentEconomy {
  equipment: EconomicEquipment;
  referenceDate: string;
  revision: number;
  periodStart: string;
  stale: boolean;
  operations: Investment[];
  groups: VisitGroup[];
}
export const euros = (value: number | null | undefined) =>
  value == null
    ? "Non renseigné"
    : value.toLocaleString("fr-FR", {
        style: "currency",
        currency: "EUR",
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
      });
export function replacementRange(item: EconomicEquipment) {
  return item.replacementMin == null || item.replacementMax == null
    ? "Devis nécessaire"
    : `${euros(item.replacementMin)} à ${euros(item.replacementMax)}`;
}
export function selectionTotal(operations: Investment[], ids: string[]) {
  const unique = new Set(ids);
  const selected = operations.filter((o) => unique.has(o.id));
  if (
    selected.length !== unique.size ||
    selected.some((o) => o.cost === null || o.cost! < 0)
  )
    return null;
  // Les tarifs sont en centimes ; éviter les erreurs flottantes près de l'enveloppe.
  return (
    selected.reduce((total, o) => total + Math.round(o.cost! * 100), 0) / 100
  );
}
export function preventionScenario(
  cost: number,
  probability: number,
  efficacy: number,
  avoidableCost: number,
) {
  if (
    ![cost, probability, efficacy, avoidableCost].every(Number.isFinite) ||
    cost < 0 ||
    avoidableCost < 0 ||
    probability < 0 ||
    probability > 1 ||
    efficacy < 0 ||
    efficacy > 1
  )
    return null;
  const avoided = probability * efficacy * avoidableCost;
  return {
    net: avoided - cost,
    avoided,
    breakEvenProbability:
      efficacy * avoidableCost > 0 ? cost / (efficacy * avoidableCost) : null,
  };
}
