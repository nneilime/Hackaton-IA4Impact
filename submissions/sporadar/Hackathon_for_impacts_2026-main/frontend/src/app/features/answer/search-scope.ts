import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import type { CountryCoverage } from '../../core/api/models';
import { I18n } from '../../core/i18n/i18n';

/**
 * Bloc 5 : le périmètre de recherche. « Toujours montrer ce qu'on a cherché » : noms et alias cherchés,
 * sources interrogées. Ces informations viennent de `coverage[].searchedTerms` et `coverage[].sourceIds`.
 */
@Component({
  selector: 'app-search-scope',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (terms().length > 0 || sources().length > 0) {
      <section class="bg-surface-muted flex flex-col gap-1 rounded-md px-4 py-3 text-sm" [attr.aria-label]="i18n.t('scope.heading')">
        @if (terms().length > 0) {
          <p class="flex flex-wrap items-center gap-1.5">
            <span class="text-ink-muted">{{ i18n.t('scope.searched') }}</span>
            @for (term of terms(); track term) {
              <span class="type-code-sm bg-surface text-ink-strong border-line rounded-sm border px-1.5">{{ term }}</span>
            }
          </p>
        }
        @if (sources().length > 0) {
          <p class="flex flex-wrap items-center gap-1.5">
            <span class="text-ink-muted">{{ i18n.t('scope.sources') }}</span>
            @for (source of sources(); track source) {
              <span class="type-code-sm text-ink-strong">{{ source }}</span>
            }
          </p>
        }
      </section>
    }
  `,
})
export class SearchScope {
  protected readonly i18n = inject(I18n);

  readonly coverage = input<readonly CountryCoverage[] | undefined>([]);

  protected readonly terms = computed(() => unique((this.coverage() ?? []).flatMap((c) => c.searchedTerms ?? [])));
  protected readonly sources = computed(() => unique((this.coverage() ?? []).flatMap((c) => c.sourceIds ?? [])));
}

function unique(values: string[]): string[] {
  return [...new Set(values)];
}
