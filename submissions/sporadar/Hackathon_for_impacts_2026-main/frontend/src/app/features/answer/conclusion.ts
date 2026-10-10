import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import type { Answer, CoverageOutcome } from '../../core/api/models';
import { I18n } from '../../core/i18n/i18n';
import { StatusBadge, type BadgeState } from '../../shared/status-badge';

interface Counter {
  state: BadgeState;
  count: number;
}

// Ordre de la légende (cahier §2). Les compteurs sans occurrence ne s'affichent pas.
const ORDER: BadgeState[] = [
  'validated',
  'to_verify',
  'automatically_extracted',
  'rejected',
  'obsolete',
  'not_found',
  'source_unavailable',
  'not_covered',
];

/**
 * Bloc 4 : la conclusion de l'IA avec son incertitude, puis les compteurs par état.
 * Les compteurs sont un simple décompte de ce que le back a envoyé (statuts de validation et `coverage[].outcome`).
 */
@Component({
  selector: 'app-conclusion',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [StatusBadge],
  template: `
    <section class="flex flex-col gap-3" aria-labelledby="conclusion-title">
      <h2 id="conclusion-title" class="sr-only">{{ i18n.t('conclusion.heading') }}</h2>
      <p class="text-ink-strong text-lg leading-7 font-semibold" data-answer>{{ answer().answer }}</p>
      <ul class="flex flex-wrap items-center gap-2" [attr.aria-label]="i18n.t('conclusion.counters')">
        @if (answer().answerStatus; as status) {
          <li class="type-caption text-ink-muted">{{ i18n.t(statusKey(status)) }}</li>
        }
        @for (counter of counters(); track counter.state) {
          <li>
            <app-status-badge
              size="default"
              [state]="counter.state"
              [text]="counter.count + ' ' + i18n.status(counter.state)"
            />
          </li>
        }
      </ul>
      @if (answer().generator; as generator) {
        <p class="text-ink-muted text-xs" data-generator>
          {{ i18n.t('conclusion.generator', { provider: generator.provider ?? '—', model: generator.model ?? '—' }) }}
          @if (generator.mode; as mode) {
            · {{ i18n.t(mode === 'llm' ? 'conclusion.mode.llm' : 'conclusion.mode.keyword') }}
          }
        </p>
      }
    </section>
  `,
})
export class Conclusion {
  protected readonly i18n = inject(I18n);

  readonly answer = input.required<Answer>();

  protected readonly counters = computed<Counter[]>(() => {
    const answer = this.answer();
    const tally = new Map<BadgeState, number>();
    const add = (state: BadgeState) => tally.set(state, (tally.get(state) ?? 0) + 1);

    // Statuts de validation : la première liste disponible (homologations, sinon faits, sinon problèmes).
    const registrations = answer.registrations ?? answer.comparison?.registrations ?? [];
    const statuses =
      registrations.length > 0
        ? registrations.map((r) => r.evidence.validationStatus)
        : (answer.facts?.length ?? 0) > 0
          ? (answer.facts ?? []).flatMap((f) => (f.validationStatus ? [f.validationStatus] : []))
          : (answer.issues ?? []).flatMap((i) => (i.validationStatus ? [i.validationStatus] : []));
    statuses.forEach(add);

    // Couverture : pas trouvé, source indisponible, non couvert.
    for (const coverage of answer.coverage ?? []) {
      if (coverage.outcome !== 'found') add(coverage.outcome as Exclude<CoverageOutcome, 'found'>);
    }
    return ORDER.filter((state) => tally.has(state)).map((state) => ({ state, count: tally.get(state) ?? 0 }));
  });

  protected statusKey(status: NonNullable<Answer['answerStatus']>) {
    return `answerStatus.${status}` as const;
  }
}
