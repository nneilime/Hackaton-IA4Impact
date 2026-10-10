import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NgIcon } from '@ng-icons/core';
import { HlmButtonImports } from '@spartan-ng/helm/button';
import type { Answer, Evidence, Review, SisterCandidate } from '../../../core/api/models';
import { ReviewsService } from '../../../core/api/reviews.service';
import { I18n } from '../../../core/i18n/i18n';
import type { EvidenceView } from '../../../core/state/evidence-view';
import { ConfidenceMeter } from '../../../shared/confidence-meter';
import { EvidenceLink } from '../../../shared/evidence-link';
import { SourceRef } from '../../../shared/source-ref';
import { StatusBadge } from '../../../shared/status-badge';

/**
 * T04 · `sister_product` : une carte par candidat.
 * Une hypothèse se lit comme une hypothèse : trait pointillé et badge « hypothèse à confirmer » tant que
 * `reviewStatus` n'est pas `validated`. Le trait plein n'apparaît que pour une revue validée, et le type
 * de relation reste affiché (une formulation liée n'est pas un produit identique).
 */
@Component({
  selector: 'app-sister-product',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgIcon, HlmButtonImports, StatusBadge, ConfidenceMeter, EvidenceLink, SourceRef],
  template: `
    <ul class="flex flex-col gap-4" [attr.aria-label]="i18n.t('sister.listLabel')">
      @for (c of candidates(); track c.candidateId) {
        <li
          class="border-line bg-surface flex flex-col gap-3 rounded-md border px-4 py-4"
          [attr.data-hypothesis]="isValidated(c) ? null : 'true'"
          [attr.data-candidate]="c.candidateId"
        >
          <div class="grid grid-cols-[1fr_2.5rem_1fr] items-center gap-2">
            <div class="flex flex-col">
              <span class="type-caption text-ink-muted">{{ i18n.t('sister.reference') }}</span>
              <strong class="text-ink-strong">{{ c.productId }}</strong>
            </div>
            <span
              class="h-0 w-full border-t-2"
              [class]="isValidated(c) ? 'border-status-validated border-solid' : 'border-status-review border-dashed'"
              aria-hidden="true"
              data-link
            ></span>
            <div class="flex flex-col">
              <span class="type-caption text-ink-muted">{{ i18n.t('sister.candidate') }}</span>
              <strong class="text-ink-strong">
                {{ c.candidateName }}
                @if (c.marketOrCountry) {
                  <span class="text-ink-muted font-normal">({{ c.marketOrCountry }})</span>
                }
              </strong>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
            @if (!isValidated(c)) {
              <app-status-badge state="hypothesis" size="default" />
            }
            <span class="type-code text-ink-strong" [attr.title]="i18n.t('sister.relationship')">{{ c.relationshipType }}</span>
            <app-confidence-meter [value]="c.confidenceScore" />
            @if (c.confidenceStatus) {
              <span class="type-code-sm text-ink-muted">{{ c.confidenceStatus }}</span>
            }
            <span class="inline-flex items-center gap-1 text-sm">
              <span class="text-ink-muted">{{ i18n.t('sister.review') }}</span>
              <app-status-badge [state]="c.reviewStatus" />
            </span>
          </div>

          @if (c.sharedTraits?.length) {
            <ul class="flex flex-wrap gap-1" [attr.aria-label]="i18n.t('sister.sharedTraits')">
              @for (trait of c.sharedTraits; track trait) {
                <li class="bg-surface-muted text-ink-strong rounded-sm px-2 py-0.5 text-xs">{{ trait }}</li>
              }
            </ul>
          }

          <p class="text-sm">
            <span class="text-ink-muted">{{ i18n.t('sister.why') }}</span>
            « {{ c.evidenceSummary }} »
          </p>

          @if (c.evidence?.length) {
            <ul class="flex flex-col gap-1">
              @for (e of c.evidence; track e.evidenceId ?? e.sourceId) {
                <li class="flex flex-wrap items-center gap-2 text-sm">
                  <app-source-ref [evidence]="e" />
                  <app-evidence-link [view]="view(c, e)">{{ i18n.t('evidence.open') }}</app-evidence-link>
                </li>
              }
            </ul>
          } @else {
            <p class="text-ink-muted text-xs">{{ i18n.t('sister.noOfficialEvidence') }}</p>
          }

          @if (reviewAvailable()) {
            <div class="flex flex-wrap items-center gap-2">
              <button hlmBtn size="sm" type="button" [disabled]="pending() === c.candidateId" (click)="decide(c, 'validated')">
                <ng-icon name="lucideCheck" aria-hidden="true" />{{ i18n.t('sister.confirm') }}
              </button>
              <button hlmBtn variant="secondary" size="sm" type="button" [disabled]="pending() === c.candidateId" (click)="decide(c, 'rejected')">
                <ng-icon name="lucideX" aria-hidden="true" />{{ i18n.t('sister.reject') }}
              </button>
              @if (decisions()[c.candidateId]; as review) {
                <span class="text-ink-muted text-xs" role="status">
                  {{ i18n.t('sister.recorded', { decision: i18n.status(review.decision), date: i18n.dateTime(review.reviewedAt) }) }}
                </span>
              }
            </div>
          } @else {
            <p class="text-ink-muted text-xs">{{ i18n.t('sister.reviewUnavailable') }}</p>
          }
        </li>
      }
    </ul>
  `,
})
export class SisterProduct {
  protected readonly i18n = inject(I18n);
  private readonly reviews = inject(ReviewsService);
  private readonly destroyRef = inject(DestroyRef);

  readonly answer = input.required<Answer>();

  protected readonly candidates = computed(() => this.answer().sisterCandidates ?? []);
  /** Décisions enregistrées par le back. Rien n'est modifié à l'écran avant sa réponse. */
  protected readonly decisions = signal<Record<string, Review>>({});
  protected readonly pending = signal<string | null>(null);
  /** POST /reviews est optionnel côté back : s'il n'existe pas, les boutons disparaissent. */
  protected readonly reviewAvailable = signal(true);

  protected isValidated(candidate: SisterCandidate): boolean {
    return candidate.reviewStatus === 'validated';
  }

  protected decide(candidate: SisterCandidate, decision: 'validated' | 'rejected'): void {
    this.pending.set(candidate.candidateId);
    this.reviews
      .submit({ targetType: 'sister_candidate', targetId: candidate.candidateId, decision })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (review) => {
          this.decisions.update((all) => ({ ...all, [candidate.candidateId]: review }));
          this.pending.set(null);
        },
        error: (error: unknown) => {
          this.pending.set(null);
          if (error instanceof HttpErrorResponse && [404, 405, 501].includes(error.status)) {
            this.reviewAvailable.set(false);
          }
        },
      });
  }

  protected view(candidate: SisterCandidate, evidence: Evidence): EvidenceView {
    return {
      title: this.i18n.t('sister.evidenceTitle', { name: candidate.candidateName }),
      evidence,
      valueNormalized: candidate.relationshipType,
      valueOriginal: candidate.evidenceSummary,
      confidence: candidate.confidenceScore,
    };
  }
}
