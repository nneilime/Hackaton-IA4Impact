import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import type { CountryCoverage } from '../core/api/models';
import { I18n } from '../core/i18n/i18n';
import { StatusBadge } from './status-badge';

/**
 * Ligne d'un pays où il n'y a PAS de résultat à montrer : cherché sans résultat, ou source indisponible.
 * Elle dit où, quand et sous quels noms on a cherché, et rappelle qu'un résultat vide ne prouve rien.
 */
@Component({
  selector: 'app-coverage-row',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [StatusBadge],
  template: `
    <div
      class="border-line-strong grid grid-cols-[3.5rem_1fr] gap-x-3 gap-y-1 rounded-md border border-dashed px-3 py-3"
      [class]="outcome() === 'not_found' ? hatched : 'bg-surface-muted/40'"
      [attr.data-outcome]="outcome()"
    >
      <span class="type-label text-ink-strong pt-0.5">{{ coverage().countryCode }}</span>
      <div class="flex flex-col gap-1.5">
        <div class="flex flex-wrap items-center gap-2">
          <app-status-badge [state]="outcome()" size="default" />
          @if (coverage().lastCollectedAt) {
            <span class="type-code-sm text-ink-muted">{{ i18n.dateTime(coverage().lastCollectedAt) }}</span>
          }
        </div>
        @if (outcome() === 'not_found') {
          <p class="text-sm">
            {{
              i18n.t('coverage.notFound', {
                sources: sources(),
                count: terms().length,
              })
            }}
          </p>
          <p class="text-ink-strong text-sm font-bold">{{ i18n.t('coverage.notProof') }}</p>
          @if (terms().length > 0) {
            <ul class="flex flex-wrap gap-1" [attr.aria-label]="i18n.t('coverage.searchedTerms')">
              @for (term of terms(); track term) {
                <li class="type-code-sm bg-surface text-ink-strong border-line rounded-sm border px-1.5">{{ term }}</li>
              }
            </ul>
          }
        } @else {
          <p class="text-sm">{{ i18n.t('coverage.sourceUnavailable', { sources: sources() }) }}</p>
          <p class="text-ink-strong text-sm font-bold">{{ i18n.t('coverage.notProof') }}</p>
        }
        @if (coverage().note) {
          <p class="text-ink-muted text-xs">{{ coverage().note }}</p>
        }
      </div>
    </div>
  `,
})
export class CoverageRow {
  protected readonly i18n = inject(I18n);

  readonly coverage = input.required<CountryCoverage>();

  protected readonly hatched =
    'bg-[repeating-linear-gradient(135deg,var(--synthetic-hatch)_0_6px,transparent_6px_10px)]';

  protected readonly outcome = computed(() => (this.coverage().outcome === 'source_unavailable' ? 'source_unavailable' : 'not_found'));
  protected readonly terms = computed(() => this.coverage().searchedTerms ?? []);
  protected readonly sources = computed(() => this.coverage().sourceIds?.join(', ') || '—');
}
