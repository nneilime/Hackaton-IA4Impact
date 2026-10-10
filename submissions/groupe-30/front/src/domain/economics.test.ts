import { describe, expect, it } from "vitest";
import {
  preventionScenario,
  selectionTotal,
  type Investment,
} from "./economics";

describe("scénarios de prévention", () => {
  it("soustrait le contrôle de la seule dépense évitable, avec des hypothèses explicites", () => {
    expect(preventionScenario(100, 0.2, 0.5, 2000)).toEqual({
      net: 100,
      avoided: 200,
      breakEvenProbability: 0.1,
    });
    expect(preventionScenario(100, 0, 0.5, 2000)?.net).toBe(-100);
    expect(
      preventionScenario(100, 0.2, 0, 2000)?.breakEvenProbability,
    ).toBeNull();
  });
  it("refuse les hypothèses impossibles et les valeurs non finies", () => {
    expect(preventionScenario(-1, 0.2, 0.5, 2000)).toBeNull();
    expect(preventionScenario(100, 1.1, 0.5, 2000)).toBeNull();
    expect(preventionScenario(100, 0.2, NaN, 2000)).toBeNull();
  });
});
describe("enveloppe de rénovation", () => {
  const operations = [
    { id: "A", cost: 0.1 },
    { id: "B", cost: 0.2 },
  ] as Investment[];
  it("compte chaque opération une fois, y compris quand elle est masquée par un filtre", () => {
    expect(selectionTotal(operations, ["A", "B", "A"])).toBe(0.3);
    expect(selectionTotal(operations, [])).toBe(0);
  });
  it("rend une sélection incomplète indisponible plutôt que nulle", () => {
    expect(selectionTotal(operations, ["ABSENT"])).toBeNull();
    expect(
      selectionTotal([{ id: "A", cost: null } as Investment], ["A"]),
    ).toBeNull();
  });
});
