import { CdkTrapFocus } from '@angular/cdk/a11y';
import { ChangeDetectionStrategy, Component, HostListener, inject } from '@angular/core';
import { NgIcon } from '@ng-icons/core';
import { HlmButtonImports } from '@spartan-ng/helm/button';
import { I18n } from '../core/i18n/i18n';
import { AnswerStore } from '../core/state/answer.store';
import { ConfidenceMeter } from './confidence-meter';
import { DataBadges } from './data-badges';
import { StatusBadge } from './status-badge';

/**
 * Le panneau de preuve : UN seul composant, le même pour toutes les valeurs de tous les gabarits.
 * Il garde le focus tant qu'il est ouvert, se ferme avec Échap, et rend le focus au bouton qui l'a ouvert.
 */
@Component({
  selector: 'app-evidence-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CdkTrapFocus, NgIcon, HlmButtonImports, StatusBadge, ConfidenceMeter, DataBadges],
  template: `
    @if (store.evidence(); as view) {
      <div class="fixed inset-0 z-40 bg-black/30" aria-hidden="true" (click)="store.closeEvidence()"></div>
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidence-title"
        class="border-line-strong bg-surface fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col gap-4 overflow-y-auto border-l-2 p-5 shadow-md"
        cdkTrapFocus
        [cdkTrapFocusAutoCapture]="true"
      >
        <header class="flex items-start justify-between gap-3">
          <div class="flex flex-col gap-1">
            <p class="type-caption text-ink-muted">{{ i18n.t('evidence.heading') }}</p>
            <h2 id="evidence-title" class="type-title text-ink-strong">{{ view.title }}</h2>
          </div>
          <button hlmBtn variant="ghost" size="sm" type="button" (click)="store.closeEvidence()">
            <ng-icon name="lucideX" aria-hidden="true" />
            {{ i18n.t('evidence.close') }}
          </button>
        </header>

        <app-data-badges [synthetic]="view.evidence.isSynthetic" [frozen]="view.evidence.isFrozenExtract" />

        <dl class="grid grid-cols-[8.5rem_1fr] gap-x-3 gap-y-3 text-sm">
          @if (view.valueNormalized) {
            <dt class="text-ink-muted">{{ i18n.t('evidence.normalized') }}</dt>
            <dd class="text-ink-strong font-semibold">{{ view.valueNormalized }}</dd>
          }
          @if (view.valueOriginal) {
            <dt class="text-ink-muted">
              {{ i18n.t('evidence.original') }}
              @if (view.evidence.languageOriginal) {
                <span class="type-code-sm">({{ view.evidence.languageOriginal }})</span>
              }
            </dt>
            <dd>« {{ view.valueOriginal }} »</dd>
          }
          <dt class="text-ink-muted">{{ i18n.t('evidence.source') }}</dt>
          <dd>
            <span class="type-code text-ink-strong bg-surface-muted rounded-sm px-1.5">{{ view.evidence.sourceId }}</span>
            @if (view.evidence.sourceName) {
              <span class="ml-1">{{ view.evidence.sourceName }}</span>
            }
          </dd>
          <dt class="text-ink-muted">{{ i18n.t('evidence.record') }}</dt>
          <dd>
            @if (view.evidence.sourceRecordUrl || view.evidence.sourceUrl; as href) {
              <a
                [href]="href"
                target="_blank"
                rel="noopener noreferrer"
                class="text-link inline-flex items-center gap-1 break-all underline underline-offset-2"
              >
                {{ i18n.t('source.open') }}
                <ng-icon name="lucideExternalLink" class="text-sm" aria-hidden="true" />
              </a>
            } @else {
              —
            }
          </dd>
          <dt class="text-ink-muted">{{ i18n.t('evidence.collectedAt') }}</dt>
          <dd class="type-code">{{ i18n.dateTime(view.evidence.collectedAt) }}</dd>
          <dt class="text-ink-muted">{{ i18n.t('evidence.validation') }}</dt>
          <dd><app-status-badge [state]="view.evidence.validationStatus" /></dd>
          <dt class="text-ink-muted">{{ i18n.t('confidence.label') }}</dt>
          <dd class="flex flex-col gap-1">
            <app-confidence-meter [value]="view.confidence ?? view.evidence.confidence" [compact]="true" />
            <span class="text-ink-muted text-xs">{{ i18n.t('confidence.notValidation') }}</span>
          </dd>
          @if (view.matchedVia) {
            <dt class="text-ink-muted">{{ i18n.t('evidence.matchedVia') }}</dt>
            <dd>« {{ view.matchedVia }} »</dd>
          }
        </dl>

        @if (view.evidence.excerpt) {
          <figure class="flex flex-col gap-1">
            <figcaption class="type-caption text-ink-muted">{{ i18n.t('evidence.excerpt') }}</figcaption>
            <blockquote class="bg-surface-muted border-line-strong rounded-sm border-l-2 px-3 py-2 text-sm italic">
              {{ view.evidence.excerpt }}
            </blockquote>
          </figure>
        }
      </aside>
    }
  `,
})
export class EvidencePanel {
  protected readonly store = inject(AnswerStore);
  protected readonly i18n = inject(I18n);

  @HostListener('document:keydown.escape')
  protected onEscape(): void {
    if (this.store.evidence()) {
      this.store.closeEvidence();
    }
  }
}
