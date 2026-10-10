import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { NgIcon } from '@ng-icons/core';
import type { Answer, Evidence, Fact } from '../../../core/api/models';
import { I18n } from '../../../core/i18n/i18n';
import type { EvidenceView } from '../../../core/state/evidence-view';
import { ConfidenceMeter } from '../../../shared/confidence-meter';
import { DataBadges } from '../../../shared/data-badges';
import { EvidenceLink } from '../../../shared/evidence-link';
import { SourceRef } from '../../../shared/source-ref';
import { StatusBadge } from '../../../shared/status-badge';

interface FactRow {
  fact: Fact;
  /** Preuves retrouvées à partir de `evidenceIds` ; une preuve introuvable est signalée, jamais ignorée. */
  proofs: { id: string; evidence: Evidence | null }[];
}

/**
 * T05 · `source_lookup` : la liste des faits, chacun avec sa ou ses preuves.
 * Une valeur sans preuve accessible est interdite : si une preuve annoncée manque dans la réponse, on le dit.
 */
@Component({
  selector: 'app-source-lookup',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgIcon, StatusBadge, ConfidenceMeter, DataBadges, EvidenceLink, SourceRef],
  template: `
    <h3 class="type-display-m pb-2">{{ i18n.t('facts.heading') }}</h3>
    <ul class="flex flex-col" [attr.aria-label]="i18n.t('facts.heading')">
      @for (row of rows(); track row.fact.factId) {
        <li class="border-line grid gap-x-4 gap-y-2 border-t py-3 first:border-t-0 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]" [attr.data-fact]="row.fact.factId">
          <div class="flex flex-col gap-1">
            <span class="type-caption text-ink-muted">
              {{ row.fact.label }}
              @if (row.fact.countryCode) {
                · {{ row.fact.countryCode }}
              }
            </span>
            <span class="text-ink-strong text-base font-semibold">{{ row.fact.value ?? '—' }}</span>
            @if (row.fact.valueOriginal) {
              <span class="text-ink-muted text-sm">« {{ row.fact.valueOriginal }} »</span>
            }
            <span class="flex flex-wrap items-center gap-2">
              @if (row.fact.validationStatus) {
                <app-status-badge [state]="row.fact.validationStatus" />
              }
              @if (row.fact.confidence !== null && row.fact.confidence !== undefined) {
                <app-confidence-meter [value]="row.fact.confidence" />
              }
            </span>
          </div>

          <ul class="flex flex-col gap-2">
            @for (proof of row.proofs; track proof.id) {
              <li class="flex flex-wrap items-center gap-2 text-sm">
                @if (proof.evidence; as evidence) {
                  <app-source-ref [evidence]="evidence" />
                  <app-status-badge [state]="evidence.validationStatus" />
                  <app-data-badges [synthetic]="evidence.isSynthetic" [frozen]="evidence.isFrozenExtract" />
                  <app-evidence-link [view]="view(row.fact, evidence)">{{ i18n.t('evidence.open') }}</app-evidence-link>
                } @else {
                  <span class="text-status-review inline-flex items-center gap-1">
                    <ng-icon name="lucideTriangleAlert" aria-hidden="true" />
                    {{ i18n.t('facts.missingProof', { id: proof.id }) }}
                  </span>
                }
              </li>
            }
          </ul>
        </li>
      }
    </ul>

    @if (sources().length > 0) {
      <h3 class="type-display-m pt-6 pb-2">{{ i18n.t('facts.sources') }}</h3>
      <ul class="flex flex-col gap-2">
        @for (source of sources(); track source.sourceId) {
          <li class="border-line bg-surface flex flex-col gap-1 rounded-md border px-3 py-2 text-sm" [attr.data-source]="source.sourceId">
            <div class="flex flex-wrap items-center gap-2">
              <span class="type-code text-ink-strong bg-surface-muted rounded-sm px-1.5">{{ source.sourceId }}</span>
              <strong>{{ source.officialName }}</strong>
              @if (source.availability === 'unavailable') {
                <app-status-badge state="source_unavailable" />
              }
              <app-data-badges [frozen]="source.isFrozenExtract" />
            </div>
            <div class="text-ink-muted flex flex-wrap gap-x-4 gap-y-1 text-xs">
              <span>{{ source.countryOrRegion ?? '—' }}</span>
              <span>{{ source.accessMethod }}</span>
              @if (source.dataFormat) {
                <span>{{ source.dataFormat }}</span>
              }
              @if (source.licenseName) {
                <span>{{ source.licenseName }}</span>
              }
              <span>{{ i18n.t('facts.lastCollected', { date: i18n.dateTime(source.lastCollectedAt) }) }}</span>
              @if (source.baseUrl; as href) {
                <a [href]="href" target="_blank" rel="noopener noreferrer" class="text-link inline-flex items-center gap-1 underline underline-offset-2">
                  {{ i18n.t('source.open') }}<ng-icon name="lucideExternalLink" class="text-sm" aria-hidden="true" />
                </a>
              }
            </div>
          </li>
        }
      </ul>
    }
  `,
})
export class SourceLookup {
  protected readonly i18n = inject(I18n);

  readonly answer = input.required<Answer>();

  protected readonly sources = computed(() => this.answer().sources ?? []);

  protected readonly rows = computed<FactRow[]>(() => {
    const byId = new Map<string, Evidence>();
    for (const evidence of this.answer().evidence) {
      if (evidence.evidenceId) byId.set(evidence.evidenceId, evidence);
    }
    return (this.answer().facts ?? []).map((fact) => ({
      fact,
      proofs: fact.evidenceIds.map((id) => ({ id, evidence: byId.get(id) ?? null })),
    }));
  });

  protected view(fact: Fact, evidence: Evidence): EvidenceView {
    return {
      title: fact.label,
      evidence,
      valueNormalized: fact.value === null || fact.value === undefined ? null : String(fact.value),
      valueOriginal: fact.valueOriginal,
      confidence: fact.confidence,
    };
  }
}
