import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { NgIcon } from '@ng-icons/core';
import { HlmBadgeImports } from '@spartan-ng/helm/badge';
import { HlmTableImports } from '@spartan-ng/helm/table';
import type { Answer, ExpirationItem } from '../../../core/api/models';
import { I18n } from '../../../core/i18n/i18n';
import type { EvidenceView } from '../../../core/state/evidence-view';
import { EvidenceLink } from '../../../shared/evidence-link';
import { SourceRef } from '../../../shared/source-ref';
import { StatusBadge } from '../../../shared/status-badge';

// Seuils d'urgence du cahier : moins de 3 mois, moins de 9 mois, au-delà.
const URGENT_DAYS = 90;
const SOON_DAYS = 270;

/** `expiry_watch` : liste datée avec compte à rebours. `daysUntilExpiration` est calculé par le back. */
@Component({
  selector: 'app-expiry-watch',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgIcon, HlmBadgeImports, HlmTableImports, EvidenceLink, SourceRef, StatusBadge],
  template: `
    <div hlmTableContainer>
      <table hlmTable>
        <caption class="sr-only">
          {{ i18n.t('expiry.caption') }}
        </caption>
        <thead hlmTHead>
          <tr hlmTr>
            <th hlmTh scope="col">{{ i18n.t('expiry.date') }}</th>
            <th hlmTh scope="col">{{ i18n.t('expiry.in') }}</th>
            <th hlmTh scope="col">{{ i18n.t('expiry.product') }}</th>
            <th hlmTh scope="col">{{ i18n.t('expiry.country') }}</th>
            <th hlmTh scope="col">{{ i18n.t('expiry.status') }}</th>
            <th hlmTh scope="col">{{ i18n.t('expiry.source') }}</th>
          </tr>
        </thead>
        <tbody hlmTBody>
          @for (item of items(); track item.registrationId) {
            <tr hlmTr [attr.data-registration]="item.registrationId">
              <td hlmTd class="type-code">
                <app-evidence-link [view]="view(item)">{{ i18n.date(item.expirationDate) }}</app-evidence-link>
              </td>
              <td hlmTd>
                @if (item.daysUntilExpiration !== undefined) {
                  <span hlmBadge [variant]="urgency(item.daysUntilExpiration)" size="sm" [attr.data-urgency]="urgency(item.daysUntilExpiration)">
                    <ng-icon name="lucideClock" aria-hidden="true" />{{ i18n.t('expiry.days', { n: item.daysUntilExpiration }) }}
                  </span>
                } @else {
                  —
                }
              </td>
              <td hlmTd class="whitespace-normal">
                <strong>{{ item.commercialName ?? item.productId }}</strong>
                @if (item.registrationNumber) {
                  <span class="text-ink-muted block text-xs">{{ i18n.t('lookup.number') }} {{ item.registrationNumber }}</span>
                }
              </td>
              <td hlmTd class="type-label">{{ item.countryCode }}</td>
              <td hlmTd>
                @if (item.statusNormalized) {
                  <app-status-badge [state]="item.statusNormalized" />
                }
              </td>
              <td hlmTd class="whitespace-normal"><app-source-ref [evidence]="item.evidence" /></td>
            </tr>
          }
        </tbody>
      </table>
    </div>
  `,
})
export class ExpiryWatch {
  protected readonly i18n = inject(I18n);

  readonly answer = input.required<Answer>();

  /** Rangées par date d'échéance, la plus proche d'abord. */
  protected readonly items = computed(() =>
    [...(this.answer().expirations ?? [])].sort((a, b) => a.expirationDate.localeCompare(b.expirationDate)),
  );

  protected urgency(days: number): 'rejected' | 'review' | 'secondary' {
    if (days <= URGENT_DAYS) return 'rejected';
    if (days <= SOON_DAYS) return 'review';
    return 'secondary';
  }

  protected view(item: ExpirationItem): EvidenceView {
    return {
      title: this.i18n.t('expiry.evidenceTitle', { country: item.countryCode }),
      evidence: item.evidence,
      valueNormalized: this.i18n.date(item.expirationDate),
    };
  }
}
