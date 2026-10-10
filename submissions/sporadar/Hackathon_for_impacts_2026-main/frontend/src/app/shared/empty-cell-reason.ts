import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { NgIcon } from '@ng-icons/core';
import type { CellState } from '../core/api/models';
import { I18n, type MessageKey } from '../core/i18n/i18n';

interface ReasonStyle {
  icon: string;
  title: MessageKey;
  detail: MessageKey;
  classes: string;
}

const HATCHED = 'bg-[repeating-linear-gradient(135deg,var(--synthetic-hatch)_0_5px,transparent_5px_9px)]';

// Les trois cas de case vide se distinguent par l'icône, le titre ET le style (cahier §6, T02).
const STYLES: Record<Exclude<CellState, 'present'>, ReasonStyle> = {
  registration_not_found: {
    icon: 'lucideCircleHelp',
    title: 'cell.registration_not_found',
    detail: 'cell.registration_not_found.detail',
    classes: `border-dashed ${HATCHED}`,
  },
  not_covered: {
    icon: 'lucideMinus',
    title: 'cell.not_covered',
    detail: 'cell.not_covered.detail',
    classes: 'border-dashed bg-surface-muted/40',
  },
  absent_in_extracted_uses: {
    icon: 'lucideFileText',
    title: 'cell.absent_in_extracted_uses',
    detail: 'cell.absent_in_extracted_uses.detail',
    classes: 'border-dotted',
  },
  source_unavailable: {
    icon: 'lucideCloudOff',
    title: 'cell.source_unavailable',
    detail: 'cell.source_unavailable.detail',
    classes: 'border-solid bg-surface-muted',
  },
};

/** Explique POURQUOI une case du comparatif est vide. Une case vide n'est jamais une preuve d'absence. */
@Component({
  selector: 'app-empty-cell-reason',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgIcon],
  template: `
    <div
      class="border-line-strong text-ink-muted flex flex-col gap-0.5 rounded-sm border px-2 py-1 text-[13px] leading-[18px]"
      [class]="style().classes"
      [attr.data-cell-state]="state()"
    >
      <strong class="text-ink inline-flex items-center gap-1 font-semibold">
        <ng-icon [name]="style().icon" aria-hidden="true" />{{ i18n.t(style().title) }}
      </strong>
      <span>{{ i18n.t(style().detail) }}</span>
    </div>
  `,
})
export class EmptyCellReason {
  protected readonly i18n = inject(I18n);

  readonly state = input.required<Exclude<CellState, 'present'>>();

  protected readonly style = computed(() => STYLES[this.state()]);
}
