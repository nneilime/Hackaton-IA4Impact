import { ChangeDetectionStrategy, Component, inject, input } from '@angular/core';
import { NgIcon } from '@ng-icons/core';
import { HlmBadgeImports } from '@spartan-ng/helm/badge';
import { I18n } from '../core/i18n/i18n';

/** Badges « donnée fictive » et « extrait figé », visibles sur chaque valeur concernée (règle LPC n°6). */
@Component({
  selector: 'app-data-badges',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgIcon, HlmBadgeImports],
  template: `
    @if (synthetic()) {
      <span
        class="border-line-strong bg-surface text-ink inline-flex items-center gap-1.5 rounded-sm border border-dashed py-px pr-1.5 pl-[3px] text-xs leading-4 font-semibold tracking-[0.04em] uppercase"
        data-badge="synthetic"
      >
        <span
          class="size-2.5 rounded-[2px] bg-[repeating-linear-gradient(135deg,var(--synthetic-hatch)_0_3px,transparent_3px_6px)]"
          aria-hidden="true"
        ></span>
        {{ i18n.t('badge.synthetic') }}
      </span>
    }
    @if (frozen()) {
      <span hlmBadge variant="outline" size="sm" data-badge="frozen">
        <ng-icon name="lucideDatabase" aria-hidden="true" />{{ i18n.t('badge.frozen') }}
      </span>
    }
  `,
  host: { class: 'inline-flex flex-wrap items-center gap-1' },
})
export class DataBadges {
  protected readonly i18n = inject(I18n);

  readonly synthetic = input<boolean | undefined>(false);
  readonly frozen = input<boolean | undefined>(false);
}
