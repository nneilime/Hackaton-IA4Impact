import { ChangeDetectionStrategy, Component, inject, input } from '@angular/core';
import { NgIcon } from '@ng-icons/core';
import { AnswerStore } from '../core/state/answer.store';
import type { EvidenceView } from '../core/state/evidence-view';

/**
 * Rend n'importe quelle valeur réglementaire cliquable : un clic ouvre le panneau de preuve (toujours le même).
 * Le contenu projeté est la valeur affichée ; sans contenu, le bouton affiche « Preuve ».
 */
@Component({
  selector: 'app-evidence-link',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgIcon],
  template: `
    <button
      type="button"
      class="text-link focus-visible:outline-focus inline-flex items-center gap-1 text-left underline decoration-dotted underline-offset-2"
      aria-haspopup="dialog"
      (click)="store.openEvidence(view())"
    >
      <ng-content />
      <ng-icon name="lucideFileText" class="text-sm" aria-hidden="true" />
      <span class="sr-only">{{ view().title }}</span>
    </button>
  `,
  host: { class: 'inline-flex' },
})
export class EvidenceLink {
  protected readonly store = inject(AnswerStore);

  readonly view = input.required<EvidenceView>();
}
