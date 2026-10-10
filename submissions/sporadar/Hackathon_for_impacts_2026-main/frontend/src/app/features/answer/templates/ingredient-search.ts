import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { HlmBadgeImports } from '@spartan-ng/helm/badge';
import { HlmTableImports } from '@spartan-ng/helm/table';
import type { Answer, ProductMatch, Registration } from '../../../core/api/models';
import { I18n } from '../../../core/i18n/i18n';
import type { EvidenceView } from '../../../core/state/evidence-view';
import { EvidenceLink } from '../../../shared/evidence-link';
import { StatusBadge, type BadgeState } from '../../../shared/status-badge';

/**
 * `ingredient_search` : matrice produit × pays.
 * Une ligne par produit (nom, substance active avec son ancien nom, LPC ou concurrent, « sœur ? »),
 * une colonne par pays avec l'état et la cible trouvée. Les pays viennent des données reçues, pas du code.
 */
@Component({
  selector: 'app-ingredient-search',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [HlmBadgeImports, HlmTableImports, StatusBadge, EvidenceLink],
  template: `
    <div hlmTableContainer>
      <table hlmTable>
        <caption class="sr-only">
          {{ i18n.t('matrix.caption') }}
        </caption>
        <thead hlmTHead>
          <tr hlmTr>
            <th hlmTh scope="col" class="bg-surface-muted sticky left-0 min-w-64">{{ i18n.t('matrix.product') }}</th>
            @for (code of countries(); track code) {
              <th hlmTh scope="col" class="min-w-40">{{ code }}</th>
            }
          </tr>
        </thead>
        <tbody hlmTBody>
          @for (match of matches(); track match.product.productId) {
            <tr hlmTr [attr.data-product]="match.product.productId">
              <th scope="row" class="bg-surface border-line sticky left-0 border-r border-b px-3 py-2 text-start align-top font-normal">
                <div class="flex flex-wrap items-center gap-2">
                  <strong class="text-ink-strong">{{ match.product.commercialName }}</strong>
                  <span hlmBadge [variant]="match.product.isLpcProduct ? 'secondary' : 'outline'" size="sm">
                    {{ match.product.isLpcProduct ? i18n.t('matrix.lpc') : i18n.t('matrix.competitor') }}
                  </span>
                  @if (isSisterCandidate(match)) {
                    <app-status-badge state="hypothesis" [text]="i18n.t('matrix.sister')" />
                  }
                </div>
                @if (match.product.activeEntityNormalized) {
                  <div class="text-ink text-sm">{{ match.product.activeEntityNormalized }}</div>
                }
                @if (match.product.activeEntityOriginal) {
                  <div class="text-ink-muted text-xs">« {{ match.product.activeEntityOriginal }} »</div>
                }
                @if (match.product.matchedVia; as via) {
                  <div class="text-ink-muted text-xs" data-matched-via>
                    {{ i18n.t('matrix.foundVia', { name: via.matchedName }) }}
                    @if (via.aliasReviewStatus && via.aliasReviewStatus !== 'validated') {
                      <app-status-badge [state]="via.aliasReviewStatus" />
                    }
                  </div>
                }
                @for (former of formerNames(match); track former) {
                  <div class="text-ink-muted text-xs">{{ i18n.t('matrix.formerName', { name: former }) }}</div>
                }
              </th>
              @for (code of countries(); track code) {
                <td hlmTd class="align-top whitespace-normal" [attr.data-country]="code">
                  @let found = registrationsOf(match, code);
                  @if (found.length > 0) {
                    <div class="flex flex-col gap-2">
                      @for (reg of found; track reg.registrationId) {
                        <div class="flex flex-col items-start gap-1">
                          <app-status-badge [state]="reg.evidence.validationStatus" />
                          <app-evidence-link [view]="view(match, reg)">
                            <span class="text-sm">{{ reg.statusOriginal ?? i18n.status(reg.statusNormalized) }}</span>
                          </app-evidence-link>
                          @for (target of targets(reg); track target) {
                            <span class="text-ink-muted text-xs">{{ target }}</span>
                          }
                        </div>
                      }
                    </div>
                  } @else {
                    <app-status-badge [state]="emptyState(code)" />
                  }
                </td>
              }
            </tr>
          }
        </tbody>
      </table>
    </div>
  `,
})
export class IngredientSearch {
  protected readonly i18n = inject(I18n);

  readonly answer = input.required<Answer>();

  protected readonly matches = computed(() => this.answer().products ?? []);

  /** Colonnes : les pays de la couverture renvoyée par le back, complétés par ceux des homologations reçues. */
  protected readonly countries = computed(() => {
    const codes = new Set<string>();
    for (const cov of this.answer().coverage ?? []) codes.add(cov.countryCode);
    for (const match of this.matches()) {
      for (const reg of match.registrations) codes.add(reg.countryCode);
    }
    return [...codes];
  });

  protected registrationsOf(match: ProductMatch, code: string): Registration[] {
    return match.registrations.filter((reg) => reg.countryCode === code);
  }

  /** Rien reçu pour ce produit dans ce pays : « pas trouvé » (jamais « non homologué »), sauf pays non couvert. */
  protected emptyState(code: string): BadgeState {
    const outcome = this.answer().coverage?.find((c) => c.countryCode === code)?.outcome;
    return outcome === 'not_covered' || outcome === 'source_unavailable' ? outcome : 'not_found';
  }

  protected isSisterCandidate(match: ProductMatch): boolean {
    return (match.product.aliases ?? []).some((alias) => alias.relationshipType === 'sister_product_candidate');
  }

  protected formerNames(match: ProductMatch): string[] {
    return (match.product.aliases ?? [])
      .filter((alias) => alias.kind === 'active_entity' && alias.relationshipType === 'former_taxonomic_name')
      .map((alias) => alias.name);
  }

  protected targets(reg: Registration): string[] {
    const names = (reg.uses ?? []).map((use) => use.targetNormalized ?? use.targetOriginal).filter((name): name is string => !!name);
    return [...new Set(names)];
  }

  protected view(match: ProductMatch, reg: Registration): EvidenceView {
    return {
      title: this.i18n.t('lookup.evidenceTitle', { country: `${reg.countryCode} · ${match.product.commercialName}` }),
      evidence: reg.evidence,
      valueNormalized: this.i18n.status(reg.statusNormalized),
      valueOriginal: reg.statusOriginal,
      matchedVia: reg.matchedVia?.matchedName,
    };
  }
}
