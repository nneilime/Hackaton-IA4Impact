import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { NgIcon } from '@ng-icons/core';
import { HlmAlertImports } from '@spartan-ng/helm/alert';
import type { SourceInfo } from '../../core/api/models';
import { I18n } from '../../core/i18n/i18n';
import { AnswerStore } from '../../core/state/answer.store';

const DAY_MS = 24 * 60 * 60 * 1000;

interface SourceChip {
  source: SourceInfo;
  /** Orange : collecte de plus de 24 h, extrait figé ou source indisponible. */
  stale: boolean;
  note: string | null;
}

/**
 * Pied de page : disclaimer (toujours présent) et fraîcheur de chaque source (GET /sources).
 */
@Component({
  selector: 'app-footer',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgIcon, HlmAlertImports],
  template: `
    <footer class="border-line border-t">
      <div class="mx-auto flex max-w-6xl flex-col gap-3 px-6 py-4">
        <div hlmAlert data-section="disclaimer">
          <ng-icon name="lucideInfo" aria-hidden="true" />
          <p hlmAlertDescription>
            @if (store.answer(); as answer) {
              {{ answer.disclaimer }}
              <span class="block">{{ i18n.t('footer.disclaimer') }}</span>
            } @else {
              {{ i18n.t('footer.disclaimer') }}
            }
          </p>
        </div>

        @if (chips().length > 0) {
          <div class="flex flex-wrap items-center gap-2">
            <span class="type-caption text-ink-muted">{{ i18n.t('header.freshness') }}</span>
            <ul class="flex flex-wrap items-center gap-2" [attr.aria-label]="i18n.t('header.freshness')">
              @for (chip of chips(); track chip.source.sourceId) {
                <li
                  class="type-code-sm inline-flex items-center gap-1 rounded-full border px-2 py-0.5"
                  [class]="chip.stale ? 'border-status-review-line bg-status-review-soft text-status-review' : 'border-line text-ink-muted'"
                  [attr.data-stale]="chip.stale"
                  [attr.data-source]="chip.source.sourceId"
                >
                  @if (chip.stale) {
                    <ng-icon name="lucideClock" class="text-sm" aria-hidden="true" />
                  }
                  {{ chip.source.sourceId }} · {{ i18n.date(chip.source.lastCollectedAt) }}
                  @if (chip.note) {
                    <span class="font-semibold">· {{ chip.note }}</span>
                  }
                </li>
              }
            </ul>
          </div>
        }

        <p class="type-caption text-ink-muted">
          <a class="hover:underline" href="https://mixkit.co/free-stock-video/" target="_blank" rel="noopener">{{
            i18n.t('footer.videoCredit')
          }}</a>
        </p>
      </div>
    </footer>
  `,
})
export class AppFooter {
  protected readonly i18n = inject(I18n);
  protected readonly store = inject(AnswerStore);

  protected readonly chips = computed<SourceChip[]>(() =>
    this.store
      .sources()
      // Les sources encore à valider (jamais collectées, sans disponibilité connue) n'ont rien à dire sur la fraîcheur.
      .filter((source) => source.lastCollectedAt || source.availability === 'unavailable')
      .map((source) => {
        const frozen = source.isFrozenExtract === true;
        const unavailable = source.availability === 'unavailable';
        const old = !source.lastCollectedAt || Date.now() - new Date(source.lastCollectedAt).getTime() > DAY_MS;
        const note = unavailable
          ? this.i18n.t('header.unavailable')
          : frozen
            ? this.i18n.t('header.frozen')
            : old
              ? this.i18n.t('header.older24h')
              : null;
        return { source, stale: frozen || unavailable || old, note };
      }),
  );
}
