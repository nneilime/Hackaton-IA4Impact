import { guessMockExample } from './mock-intent';

describe('guessMockExample (mock uniquement)', () => {
  it.each([
    ['Compare les usages entre FR et CA', 'use_comparison'],
    ['Quels champs sont incertains ?', 'data_quality'],
    ['Il manque quoi ?', 'data_quality'],
    ['Quels produits sœurs ?', 'sister_product'],
    ["D'où vient chaque donnée ? donne la source", 'source_lookup'],
    ['Qu’est-ce qui expire dans 12 mois ?', 'expiry_watch'],
    ['Quels produits avec la souche J1446 sur tomate ?', 'ingredient_search'],
    ["Quel produit utiliser contre l'oïdium ?", 'ingredient_search'],
    ['Which product against powdery mildew?', 'ingredient_search'],
    ['Dans quels pays est-il homologué ?', 'registration_lookup'],
    ['lalguard', 'needs_clarification'],
  ])('« %s » → %s', (question, expected) => {
    expect(guessMockExample(question)).toBe(expected);
  });
});
