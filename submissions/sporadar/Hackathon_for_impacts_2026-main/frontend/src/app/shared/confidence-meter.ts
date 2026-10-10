import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { I18n } from '../core/i18n/i18n';

/**
 * Confiance de l'IA : une barre de 5 segments et la valeur. C'est une mesure d'extraction automatique,
 * PAS une validation humaine : elle est toujours affichée à côté du statut de validation, jamais fusionnée.
 */
@Component({
  selector: 'app-confidence-meter',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="text-ink-muted inline-flex items-center gap-2 text-xs leading-4" [attr.title]="i18n.t('confidence.hint')">
      @if (!compact()) {
        <span>{{ i18n.t('confidence.label') }}</span>
      }
      <span class="inline-flex gap-0.5" aria-hidden="true">
        @for (i of segments; track i) {
          <span class="h-1.5 w-2.5 rounded-[1px]" [class]="i < filled() ? 'bg-ink-muted' : 'bg-line'"></span>
        }
      </span>
      <span class="type-code-sm text-ink">{{ i18n.score(value()) }}</span>
      <span class="sr-only">{{ i18n.t('confidence.hint') }}</span>
    </span>
  `,
})
export class ConfidenceMeter {
  protected readonly i18n = inject(I18n);

  readonly value = input<number | null | undefined>(null);
  readonly compact = input(false);

  protected readonly segments = [0, 1, 2, 3, 4];
  protected readonly filled = computed(() => Math.round((this.value() ?? 0) * 5));
}
