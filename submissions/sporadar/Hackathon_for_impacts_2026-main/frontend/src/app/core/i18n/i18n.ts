import { Injectable, signal } from '@angular/core';
import { EN } from './en';
import { FR, type MessageKey } from './fr';

export type Lang = 'fr' | 'en';
export type { MessageKey } from './fr';

const DICTIONARIES: Record<Lang, Record<MessageKey, string>> = { fr: FR, en: EN };
const LOCALES: Record<Lang, string> = { fr: 'fr-FR', en: 'en-GB' };

/**
 * Textes d'interface FR / EN, bascule à chaud (le signal `lang` est lu dans les gabarits).
 * Seuls les textes de l'interface passent par ici : les valeurs venues des sources
 * (cultures, cibles, statuts d'origine, extraits…) ne sont JAMAIS traduites.
 */
@Injectable({ providedIn: 'root' })
export class I18n {
  readonly lang = signal<Lang>('fr');

  t(key: MessageKey, params?: Record<string, string | number>): string {
    let text = DICTIONARIES[this.lang()][key];
    for (const [name, value] of Object.entries(params ?? {})) {
      text = text.replaceAll(`{${name}}`, String(value));
    }
    return text;
  }

  /** Libellé d'un statut (validation, homologation, couverture, revue). Inconnu : la valeur brute. */
  status(value: string): string {
    const key = `status.${value}`;
    return key in FR ? this.t(key as MessageKey) : value;
  }

  /** Libellé d'un type de problème de qualité (missing, uncertain…). */
  issueType(value: string): string {
    const key = `issue.${value}`;
    return key in FR ? this.t(key as MessageKey) : value;
  }

  /** Date au fuseau UTC (les collectes sont datées en UTC), ex. 10/10/2026. */
  date(iso: string | null | undefined): string {
    const date = this.parse(iso);
    return date ? new Intl.DateTimeFormat(LOCALES[this.lang()], { dateStyle: 'short', timeZone: 'UTC' }).format(date) : '—';
  }

  /** Date et heure UTC, ex. 10/10/2026 03:20 UTC. */
  dateTime(iso: string | null | undefined): string {
    const date = this.parse(iso);
    if (!date) return '—';
    const text = new Intl.DateTimeFormat(LOCALES[this.lang()], {
      dateStyle: 'short',
      timeStyle: 'short',
      timeZone: 'UTC',
    }).format(date);
    return `${text} UTC`;
  }

  /** Nombre tel que reçu (virgule en français) : mise en forme seulement, aucune conversion. */
  number(value: number | null | undefined): string {
    return value === null || value === undefined
      ? '—'
      : new Intl.NumberFormat(LOCALES[this.lang()], { maximumFractionDigits: 4 }).format(value);
  }

  /** Score de confiance sur deux décimales, ex. 0,90. */
  score(value: number | null | undefined): string {
    return value === null || value === undefined
      ? '–'
      : new Intl.NumberFormat(LOCALES[this.lang()], { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
  }

  private parse(iso: string | null | undefined): Date | null {
    if (!iso) return null;
    const date = new Date(iso);
    return Number.isNaN(date.getTime()) ? null : date;
  }
}
