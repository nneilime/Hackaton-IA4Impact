import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { NgIcon } from '@ng-icons/core';
import { HlmButtonImports } from '@spartan-ng/helm/button';
import type { Answer } from '../../../core/api/models';
import { I18n, type MessageKey } from '../../../core/i18n/i18n';

type MessageKind = 'clarification' | 'no_data' | 'out_of_scope';

/**
 * `other`, `no_data` et `needs_clarification` : un message clair, jamais une réponse inventée.
 * - hors périmètre : on le dit et on propose des questions (affichées par le cadre) ;
 * - aucune donnée : on a rien trouvé DANS NOS SOURCES (le périmètre de recherche est affiché par le cadre) ;
 * - question ambiguë : les options deviennent des boutons qui relancent la question.
 */
@Component({
  selector: 'app-message-template',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgIcon, HlmButtonImports],
  template: `
    <div
      class="border-line-strong bg-surface flex flex-col gap-3 rounded-lg border border-dashed p-5"
      [attr.data-message]="kind()"
    >
      <h3 class="type-display-m flex items-center gap-2" data-toc-level="1">
        <ng-icon [name]="kind() === 'clarification' ? 'lucideCircleHelp' : 'lucideInfo'" aria-hidden="true" />
        {{ i18n.t(titleKey()) }}
      </h3>
      <p class="text-ink">{{ i18n.t(bodyKey()) }}</p>

      @if (kind() === 'clarification') {
        <div class="flex flex-wrap gap-2" role="group" [attr.aria-label]="i18n.t('msg.options')">
          @for (option of answer().clarificationOptions ?? []; track option) {
            <button hlmBtn variant="secondary" type="button" (click)="clarify.emit(option)">{{ option }}</button>
          }
        </div>
      }
    </div>
  `,
})
export class MessageTemplate {
  protected readonly i18n = inject(I18n);

  readonly answer = input.required<Answer>();
  /** Option choisie parmi `clarificationOptions` : le cadre relance la question avec elle. */
  readonly clarify = output<string>();

  protected readonly kind = computed<MessageKind>(() => {
    const status = this.answer().answerStatus;
    if (status === 'needs_clarification') return 'clarification';
    if (status === 'no_data') return 'no_data';
    return 'out_of_scope';
  });

  protected readonly titleKey = computed<MessageKey>(() => {
    const kind = this.kind();
    return kind === 'clarification' ? 'msg.clarification.title' : kind === 'no_data' ? 'msg.noData.title' : 'msg.outOfScope.title';
  });

  protected readonly bodyKey = computed<MessageKey>(() => {
    const kind = this.kind();
    return kind === 'clarification' ? 'msg.clarification.body' : kind === 'no_data' ? 'msg.noData.body' : 'msg.outOfScope.body';
  });
}
