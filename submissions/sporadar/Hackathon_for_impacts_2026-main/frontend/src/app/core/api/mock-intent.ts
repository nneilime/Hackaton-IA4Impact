import type { Intent } from './models';

/**
 * Choix de l'exemple Prism pour une question TAPÉE LIBREMENT (mode mock uniquement).
 * Le vrai back détecte l'intention lui-même : ce code ne sert qu'à faire varier le mock.
 * Les questions cliquées (exemples, suggestions) portent leur `intent` et ne passent pas par ici.
 */
export type MockAskExample = Intent | 'needs_clarification';

const RULES: readonly (readonly [RegExp, MockAskExample])[] = [
  [/^\s*lalguard\s*$/i, 'needs_clarification'],
  [/m[ée]t[ée]o|weather|recette|recipe/i, 'other'],
  [/compar|compare|versus|\bvs\b/i, 'use_comparison'],
  [/incertain|uncertain|manqu|missing|qualit|quality|[àa] v[ée]rifier/i, 'data_quality'],
  [/s(?:œ|oe)ur|sister/i, 'sister_product'],
  [/source|d['’]o[ùu] vient|provenance/i, 'source_lookup'],
  [/expir|[ée]ch[ée]ance/i, 'expiry_watch'],
  [
    /souche|strain|culture|crop|tomate|fraisier|fraise|ingr[ée]dient|substance|contre|against|quels? produits?|which products?/i,
    'ingredient_search',
  ],
];

export function guessMockExample(question: string): MockAskExample {
  return RULES.find(([pattern]) => pattern.test(question))?.[1] ?? 'registration_lookup';
}
