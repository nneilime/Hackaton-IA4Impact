import { ChangeDetectionStrategy, Component, DestroyRef, inject, input, signal } from '@angular/core';
import { NgIcon } from '@ng-icons/core';
import { I18n, type MessageKey } from '../../core/i18n/i18n';

/** Étapes affichées pendant que l'agent travaille (textes d'ambiance : ce n'est pas une progression mesurée). */
const STEPS: MessageKey[] = [
  'thinking.read',
  'thinking.entities',
  'thinking.sources',
  'thinking.eppo',
  'thinking.compare',
  'thinking.verify',
  'thinking.write',
];

/** Temps d'affichage de chaque étape, en millisecondes. */
const STEP_MS = 2200;

/**
 * Pendant le chargement : des textes qui se relaient (comme les assistants IA) pour montrer que l'agent réfléchit.
 * On s'arrête sur la dernière étape au lieu de boucler, pour ne pas suggérer une progression qui n'existe pas.
 * Les lecteurs d'écran n'entendent que le message fixe « state.loading » (le texte animé est aria-hidden).
 */
@Component({
  selector: 'app-thinking-status',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgIcon],
  template: `
    <div class="flex items-center gap-3">
      <ng-icon name="lucideSparkles" class="text-brand animate-pulse text-lg" aria-hidden="true" />
      <div class="relative min-h-6 flex-1 overflow-hidden" aria-hidden="true">
        <!-- Un élément neuf à chaque étape : l'animation d'entrée se rejoue -->
        @for (current of [step()]; track current) {
          <p class="text-shimmer animate-in fade-in slide-in-from-bottom-2 text-base font-medium duration-500" data-thinking-step>
            {{ i18n.t(steps[current]) }}
          </p>
        }
      </div>
      <span class="sr-only">{{ i18n.t('state.loading') }}</span>
    </div>
    @if (sources()) {
      <p class="text-ink-muted pl-8 text-sm">
        {{ i18n.t('scope.sources') }} <span class="type-code-sm text-ink-strong">{{ sources() }}</span>
      </p>
    }
  `,
})
export class ThinkingStatus {
  protected readonly i18n = inject(I18n);

  /** Sources interrogées (« FR-EPHY · DE-BVL · CA-PPID »), affichées sous le texte animé. */
  readonly sources = input('');

  protected readonly steps = STEPS;
  protected readonly step = signal(0);

  constructor() {
    const timer = setInterval(() => {
      if (this.step() < STEPS.length - 1) {
        this.step.update((value) => value + 1);
      } else {
        clearInterval(timer);
      }
    }, STEP_MS);
    inject(DestroyRef).onDestroy(() => clearInterval(timer));
  }
}
