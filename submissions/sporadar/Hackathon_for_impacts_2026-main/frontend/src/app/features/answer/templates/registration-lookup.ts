import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import type { Answer, Registration } from '../../../core/api/models';
import { I18n } from '../../../core/i18n/i18n';
import type { EvidenceView } from '../../../core/state/evidence-view';
import { ConfidenceMeter } from '../../../shared/confidence-meter';
import { CoverageRow } from '../../../shared/coverage-row';
import { DataBadges } from '../../../shared/data-badges';
import { EvidenceLink } from '../../../shared/evidence-link';
import { SourceRef } from '../../../shared/source-ref';
import { StatusBadge } from '../../../shared/status-badge';

/**
 * T01 · `registration_lookup` : une ligne par pays.
 * Ordre : validé, à vérifier, pas trouvé, source indisponible ; les pays non couverts sont regroupés à part.
 * Le tri ne fait que ranger ce que le back a envoyé : aucune donnée n'est déduite ici.
 */
@Component({
  selector: 'app-registration-lookup',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [StatusBadge, EvidenceLink, SourceRef, DataBadges, ConfidenceMeter, CoverageRow],
  template: `
    <ul class="flex flex-col gap-3" [attr.aria-label]="i18n.t('lookup.listLabel')">
      @for (reg of registrations(); track reg.registrationId) {
        <li
          class="border-line bg-surface grid grid-cols-[3.5rem_1fr] gap-x-3 gap-y-2 rounded-md border px-3 py-3 md:grid-cols-[3.5rem_1fr_auto]"
          data-row="found"
          [attr.data-country]="reg.countryCode"
        >
          <span class="type-label text-ink-strong pt-0.5">{{ reg.countryCode }}</span>

          <div class="flex flex-col gap-1.5">
            <div class="flex flex-wrap items-center gap-2">
              <app-status-badge [state]="reg.evidence.validationStatus" size="default" />
              <app-evidence-link [view]="view(reg)">
                <strong class="text-ink-strong">{{ reg.statusOriginal ?? '—' }}</strong>
              </app-evidence-link>
              @if (reg.statusNormalized === 'withdrawn' || reg.statusNormalized === 'expired') {
                <!-- Rouge : le statut retiré ou expiré vient de la source elle-même. -->
                <app-status-badge [state]="reg.statusNormalized" />
              } @else {
                <span class="text-ink-muted text-sm">→ {{ i18n.status(reg.statusNormalized) }}</span>
              }
            </div>

            <p class="text-sm">
              <span class="font-semibold">{{ reg.productNameOriginal ?? '—' }}</span>
              · {{ reg.authorityName ?? '—' }} · {{ i18n.t('lookup.number') }} {{ reg.registrationNumber ?? '—' }}
            </p>

            @if (reg.matchedVia; as via) {
              <p
                class="text-sm"
                [class]="via.matchedOn === 'commercial_name' ? 'text-ink-muted' : 'border-status-review-line text-ink border-l-2 border-dashed pl-2'"
                data-matched-via
              >
                @if (via.matchedOn === 'commercial_name') {
                  {{ i18n.t('lookup.viaName', { name: via.matchedName }) }}
                } @else {
                  ↳ {{ i18n.t('lookup.viaAlias', { name: via.matchedName }) }}
                  @if (via.aliasRelationshipType) {
                    <span class="type-code-sm text-ink-muted">({{ via.aliasRelationshipType }})</span>
                  }
                  @if (via.aliasReviewStatus) {
                    <app-status-badge [state]="via.aliasReviewStatus" />
                  }
                  @if (via.aliasConfidenceScore !== null && via.aliasConfidenceScore !== undefined) {
                    <span class="text-ink-muted">
                      {{ i18n.t('lookup.aliasConfidence', { score: i18n.score(via.aliasConfidenceScore) }) }}
                    </span>
                  }
                }
              </p>
            }

            @if (reg.approvalDate || reg.expirationDate) {
              <p class="text-ink-muted text-xs">
                {{ i18n.t('lookup.approved') }} {{ i18n.date(reg.approvalDate) }} · {{ i18n.t('lookup.expires') }}
                {{ i18n.date(reg.expirationDate) }}
              </p>
            }
            @if (reg.missingFields?.length) {
              <p class="text-ink-muted text-xs">
                {{ i18n.t('lookup.missing') }} <span class="type-code-sm">{{ reg.missingFields?.join(', ') }}</span>
              </p>
            }
          </div>

          <div class="col-span-full flex flex-col gap-1.5 md:col-span-1 md:col-start-3 md:items-end md:text-right">
            <app-source-ref [evidence]="reg.evidence" />
            <app-data-badges [synthetic]="reg.isSynthetic || reg.evidence.isSynthetic" [frozen]="reg.evidence.isFrozenExtract" />
            @if (reg.evidence.confidence !== null && reg.evidence.confidence !== undefined) {
              <app-confidence-meter [value]="reg.evidence.confidence" />
            }
          </div>
        </li>
      }

      @for (gap of gaps(); track gap.countryCode) {
        <li><app-coverage-row [coverage]="gap" /></li>
      }
    </ul>

    @if (notCovered().length > 0) {
      <div class="mt-4 flex flex-wrap items-center gap-2" data-group="not-covered">
        <span class="text-ink-muted text-sm">{{ i18n.t('lookup.notCovered') }}</span>
        @for (cov of notCovered(); track cov.countryCode) {
          <app-status-badge state="not_covered" [text]="cov.countryCode" />
        }
      </div>
    }
  `,
})
export class RegistrationLookup {
  protected readonly i18n = inject(I18n);

  readonly answer = input.required<Answer>();

  /** Homologations trouvées : validées d'abord, puis les autres (à vérifier, extraites automatiquement…). */
  protected readonly registrations = computed(() =>
    [...(this.answer().registrations ?? [])].sort((a, b) => rank(a) - rank(b)),
  );

  /** Pays cherchés sans résultat, puis pays dont la source était indisponible. */
  protected readonly gaps = computed(() =>
    (this.answer().coverage ?? [])
      .filter((c) => c.outcome === 'not_found' || c.outcome === 'source_unavailable')
      .sort((a, b) => (a.outcome === b.outcome ? 0 : a.outcome === 'not_found' ? -1 : 1)),
  );

  protected readonly notCovered = computed(() => (this.answer().coverage ?? []).filter((c) => c.outcome === 'not_covered'));

  protected view(reg: Registration): EvidenceView {
    return {
      title: this.i18n.t('lookup.evidenceTitle', { country: reg.countryCode }),
      evidence: reg.evidence,
      valueNormalized: this.i18n.status(reg.statusNormalized),
      valueOriginal: reg.statusOriginal,
      matchedVia: reg.matchedVia?.matchedName,
    };
  }
}

function rank(reg: Registration): number {
  return reg.evidence.validationStatus === 'validated' ? 0 : 1;
}
