import examples from '../core/mock/examples.json';
import type { Answer, ComparisonResponse, SisterCandidatesResponse } from '../core/api/models';

// Jeux de données des tests : les réponses d'exemple de mocks/examples.yaml (converties par scripts/build-mocks.mjs).
// On ne recrée aucune donnée ailleurs : si le contrat change, ces exemples changent et les tests suivent.
const all = examples as unknown as Record<string, object>;

export type AskExample =
  | 'registration_lookup'
  | 'use_comparison'
  | 'data_quality'
  | 'sister_product'
  | 'source_lookup'
  | 'ingredient_search'
  | 'expiry_watch'
  | 'needs_clarification'
  | 'other';

export function askExample(name: AskExample): Answer {
  return structuredClone(all[`ask_${name}`]) as Answer;
}

export function comparisonExample(): ComparisonResponse {
  return structuredClone(all['compare_m52_fr_ca']) as ComparisonResponse;
}

export function sistersExample(): SisterCandidatesResponse {
  return structuredClone(all['sisters_m52']) as SisterCandidatesResponse;
}

export function issuesExample(): object {
  return structuredClone(all['issues_m52']);
}

export function sourcesExample(): object {
  return structuredClone(all['sources_all']);
}

export function reviewExample(): object {
  return structuredClone(all['review_alias_validated']);
}
