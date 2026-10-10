import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { NgIcon } from '@ng-icons/core';
import type { Evidence } from '../core/api/models';
import { I18n } from '../core/i18n/i18n';

/** Référence compacte d'une source : identifiant, lien direct vers la fiche officielle, date de collecte. */
@Component({
  selector: 'app-source-ref',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgIcon],
  template: `
    <span class="type-code text-ink-strong bg-surface-muted rounded-sm px-1.5">{{ evidence().sourceId }}</span>
    @if (url(); as href) {
      <a
        [href]="href"
        target="_blank"
        rel="noopener noreferrer"
        class="text-link inline-flex items-center gap-1 underline underline-offset-2"
      >
        {{ i18n.t('source.open') }}
        <ng-icon name="lucideExternalLink" class="text-sm" aria-hidden="true" />
      </a>
    }
    <span class="type-code-sm text-ink-muted">{{ i18n.t('source.collected', { date: i18n.date(evidence().collectedAt) }) }}</span>
  `,
  host: { class: 'type-body-sm inline-flex flex-wrap items-center gap-x-2 gap-y-1' },
})
export class SourceRef {
  protected readonly i18n = inject(I18n);

  readonly evidence = input.required<Evidence>();

  /** Lien direct vers la fiche officielle quand il existe, sinon la page d'accueil de la source. */
  protected readonly url = computed(() => this.evidence().sourceRecordUrl || this.evidence().sourceUrl || null);
}
