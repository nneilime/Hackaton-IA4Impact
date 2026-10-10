import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { isMock, isOfflineDemo } from '../../core/api/runtime';
import { I18n } from '../../core/i18n/i18n';
import { AnswerStore } from '../../core/state/answer.store';

/**
 * Bloc 1 : nom de l'application et bascule FR / EN (la fraîcheur des sources est dans le pied de page).
 * Les bandeaux « mock » et « démo hors ligne » rappellent que les données affichées sont fictives.
 */
@Component({
  selector: 'app-header',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="bg-brand h-[3px] w-full" aria-hidden="true"></div>
    @if (mock) {
      <div class="bg-status-review-soft text-status-review border-status-review-line border-b px-6 py-1 text-center text-xs font-semibold" role="status" data-banner="mock">
        {{ i18n.t('banner.mock') }}
      </div>
    }
    @if (offline) {
      <div class="bg-status-review-soft text-status-review border-status-review-line border-b px-6 py-1 text-center text-xs font-semibold" role="status" data-banner="offline">
        {{ i18n.t('banner.offline') }}
      </div>
    }
    <header class="bg-surface border-line border-b">
      <div class="mx-auto flex max-w-6xl items-center justify-between gap-6 px-6 py-3">
        <div class="flex items-baseline gap-3">
          <span class="type-display-m">Sporadar</span>
          <span class="type-caption text-ink-muted hidden sm:inline">{{ i18n.t('header.tagline') }}</span>
        </div>

        <div class="border-line-strong inline-flex overflow-hidden rounded-md border" role="group" [attr.aria-label]="i18n.t('header.language')">
          @for (lang of languages; track lang) {
            <button
              type="button"
              class="aria-pressed:bg-primary aria-pressed:text-primary-foreground text-ink-strong hover:bg-surface-muted px-3 py-1 text-sm font-semibold uppercase"
              [attr.aria-pressed]="i18n.lang() === lang"
              [attr.lang]="lang"
              (click)="store.setLanguage(lang)"
            >
              {{ lang }}
            </button>
          }
        </div>
      </div>
    </header>
  `,
})
export class AppHeader {
  protected readonly i18n = inject(I18n);
  protected readonly store = inject(AnswerStore);

  protected readonly mock = isMock;
  protected readonly offline = isOfflineDemo;
  protected readonly languages = ['fr', 'en'] as const;
}
