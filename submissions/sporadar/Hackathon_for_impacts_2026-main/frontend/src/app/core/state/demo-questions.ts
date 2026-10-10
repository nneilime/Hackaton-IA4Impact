import type { Intent } from '../api/models';
import type { Lang } from '../i18n/i18n';

export interface DemoQuestion {
  /** Intention de la question : sert de nom d'exemple au mock, et d'étiquette sur le bouton. */
  intent: Intent;
  /** Étiquette courte (T01…T05) du scénario du jury. */
  test: string;
  question: Record<Lang, string>;
}

/**
 * Les 5 questions test du jury sur le produit pilote LALGUARD M52 OD.
 * Elles s'affichent en exemples cliquables quand la barre de question est vide.
 */
export const DEMO_QUESTIONS: readonly DemoQuestion[] = [
  {
    intent: 'registration_lookup',
    test: 'T01',
    question: {
      fr: 'Dans quels pays LALGUARD M52 OD est-il homologué ?',
      en: 'In which countries is LALGUARD M52 OD registered?',
    },
  },
  {
    intent: 'use_comparison',
    test: 'T02',
    question: {
      fr: 'Compare les usages de LALGUARD M52 OD entre la France et le Canada',
      en: 'Compare the uses of LALGUARD M52 OD between France and Canada',
    },
  },
  {
    intent: 'data_quality',
    test: 'T03',
    question: {
      fr: 'Quels champs sont incertains pour LALGUARD M52 OD ?',
      en: 'Which fields are uncertain for LALGUARD M52 OD?',
    },
  },
  {
    intent: 'sister_product',
    test: 'T04',
    question: {
      fr: 'Quels produits pourraient être des produits sœurs de LALGUARD M52 OD ?',
      en: 'Which products could be sister products of LALGUARD M52 OD?',
    },
  },
  {
    intent: 'source_lookup',
    test: 'T05',
    question: {
      fr: 'Donne la source officielle de chaque donnée sur LALGUARD M52 OD',
      en: 'Give the official source of each data point for LALGUARD M52 OD',
    },
  },
];
